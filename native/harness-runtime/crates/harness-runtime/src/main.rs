// Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
// SPDX-License-Identifier: BUSL-1.1
// Licensed under the Business Source License 1.1 (BSL-1.1).
// Commercial use, sale, or use in commercial application development is strictly
// prohibited without prior written permission from the copyright holder.
// Removing or altering this header is prohibited and voids all license rights.

//! Entry point of the `harness-runtime` process (ADR 0021, section 8).
//!
//! `harness-runtime migrate [--repo <path>] --approved-by <human> --approved-at <RFC 3339 time>
//! --reason <text>` cuts the state of a repository over from the file ledger to the runtime store
//! with a human approval (ADR 0020, section 5). It prints one JSON line and exits with 0 (done, or
//! already done), 2 (the approval or a precondition refused it, nothing changed), 3 (it failed
//! after it began; the file ledger is still the authority) or 4 (an invariant broke; an operator
//! must look).
//!
//! `harness-runtime rollback --to-legacy [--repo <path>] --approved-by <human> --approved-at <RFC
//! 3339 time> --reason <text>` exports the runtime store into a new generation of the file ledger
//! and returns the authority to it (ADR 0020, section 5). It holds the instance lock of `serve`
//! for its whole run, so a running `serve` refuses it, prints one JSON line and uses the exit codes
//! of `migrate`.
//!
//! `harness-runtime serve [--repo <path>]` serves the local IPC of one repository until it gets
//! SIGINT or SIGTERM (on Windows, Ctrl+C or Ctrl+Break). Before it reports ready it reconciles the
//! executions of the store, and a stop never signals an execution: they outlive the runtime. On
//! Windows the `socket` key of the readiness line holds the name of the named pipe. ADR 0021,
//! section 8 defines exit code 0 (a normal stop) and 2 (a refusal to start). The ADR leaves a
//! failure of a server that is already ready undefined, so this implementation picks 1 for it. A
//! supervisor learns that the start worked from the readiness line, so a failure to write that
//! line is a refusal to start (2), not a failure of a running server.
//!
//! `harness-runtime ctrl-break --job <name> --group <pgid> --pid <pid> --created <time>` is the
//! ctrl-break helper of a Windows deadline stop (ADR 0022, section 3): the runtime starts it
//! without a console, and it sends `CTRL_BREAK` to the process group on the console of a live
//! member of the job object (`supervisor::ctrl_break`). It exits with 0 (delivered), 3 (the job
//! has no live member) or 1 (not delivered; the reason on stderr). Other platforms refuse it with
//! 2.

#[cfg(unix)]
mod autostart;

use std::env;
use std::ffi::OsString;
use std::io::Write;
use std::path::PathBuf;
use std::process::ExitCode;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use contracts::ErrorCode;
use ipc::{Environment, Server, StartError, resolve_paths};
use serde_json::json;

const EXIT_FAILED: u8 = 1;
const EXIT_REFUSED: u8 = 2;
const USAGE: &str = "usage: harness-runtime serve [--repo <path>] [--owner-session <key> \
    [--owner-pid <pid>] [--owner-ttl-seconds <n>]] | harness-runtime migrate \
    [--repo <path>] --approved-by <human> --approved-at <time> --reason <text> | harness-runtime \
    rollback --to-legacy [--repo <path>] --approved-by <human> --approved-at <time> --reason <text> | \
    harness-runtime repair-import-approval [--check] [--repo <path>] \
    --approved-by <human> --approved-at <time> --reason <text>";

/// What the command line asked for.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Command {
    Serve,
    Migrate,
    Rollback,
    RepairImportApproval,
}

/// The command and the repository it works on.
#[derive(Debug, PartialEq, Eq)]
struct Args {
    command: Command,
    repo: PathBuf,
    /// The approval of `migrate` and `rollback`; a missing flag leaves its field blank, and the
    /// command itself refuses a blank field.
    approval: state::approval::Approval,
    check: bool,
    /// The owner of a runtime the autostart hook starts (`serve --owner-session`, Unix only).
    owner: Owner,
}

/// The first owner of `serve --owner-session <key> [--owner-pid <pid>] [--owner-ttl-seconds
/// <n>]` (ADR 0031, section 2). Without a key the runtime is manual and never stops by itself.
#[derive(Debug, Default, PartialEq, Eq)]
struct Owner {
    session: Option<String>,
    pid: Option<i64>,
    ttl_seconds: Option<u64>,
}

fn parse_args(args: impl IntoIterator<Item = OsString>) -> Result<Args, String> {
    let mut args = args.into_iter();
    let command = match args.next().as_deref().and_then(|word| word.to_str()) {
        Some("serve") => Command::Serve,
        Some("migrate") => Command::Migrate,
        Some("rollback") => Command::Rollback,
        Some("repair-import-approval") => Command::RepairImportApproval,
        _ => return Err(USAGE.to_owned()),
    };
    let mut repo = None;
    let mut to_legacy = false;
    let mut check = false;
    let mut approval = state::approval::Approval::default();
    let mut owner = Owner::default();
    while let Some(flag) = args.next() {
        let rollback = command == Command::Rollback;
        let approved = command != Command::Serve;
        let owned = cfg!(unix) && command == Command::Serve;
        let field = match flag.to_str() {
            Some("--repo") => None,
            Some(name @ ("--owner-session" | "--owner-pid" | "--owner-ttl-seconds")) if owned => {
                let value = args
                    .next()
                    .and_then(|value| value.into_string().ok())
                    .ok_or_else(|| format!("{name} needs a value; {USAGE}"))?;
                parse_owner_flag(&mut owner, name, &value)?;
                continue;
            }
            Some("--check") if command == Command::RepairImportApproval => {
                check = true;
                continue;
            }
            Some("--to-legacy") if rollback => {
                to_legacy = true;
                continue;
            }
            Some("--approved-by") if approved => Some(&mut approval.approved_by),
            Some("--approved-at") if approved => Some(&mut approval.approved_at),
            Some("--reason") if approved => Some(&mut approval.reason),
            _ => return Err(format!("unknown argument {flag:?}; {USAGE}")),
        };
        let what = if field.is_none() { "a path" } else { "a value" };
        let value = args
            .next()
            .ok_or_else(|| format!("{} needs {what}; {USAGE}", flag.to_string_lossy()))?;
        match field {
            None => repo = Some(PathBuf::from(value)),
            Some(field) => {
                *field = value
                    .into_string()
                    .map_err(|value| format!("{value:?} is not UTF-8; {USAGE}"))?;
            }
        }
    }
    if owner.session.is_none() && (owner.pid.is_some() || owner.ttl_seconds.is_some()) {
        return Err(format!(
            "--owner-pid and --owner-ttl-seconds need --owner-session; {USAGE}"
        ));
    }
    if command == Command::Rollback && !to_legacy {
        return Err(format!("rollback needs --to-legacy; {USAGE}"));
    }
    let repo = match repo {
        Some(repo) => repo,
        None => {
            env::current_dir().map_err(|err| format!("cannot read the working directory: {err}"))?
        }
    };
    Ok(Args {
        command,
        repo,
        approval,
        check,
        owner,
    })
}

/// Read one owner flag of `serve` into `owner`.
fn parse_owner_flag(owner: &mut Owner, name: &str, value: &str) -> Result<(), String> {
    match name {
        "--owner-session" if ipc::valid_key(value) => owner.session = Some(value.to_owned()),
        "--owner-session" => {
            return Err(format!(
                "--owner-session needs 1 to {} characters of [A-Za-z0-9._:/-]; {USAGE}",
                ipc::MAX_KEY_LEN
            ));
        }
        "--owner-pid" => {
            owner.pid = Some(
                value
                    .parse::<i64>()
                    .ok()
                    .filter(|pid| *pid > 0)
                    .ok_or_else(|| format!("--owner-pid needs a positive number; {USAGE}"))?,
            );
        }
        _ => {
            owner.ttl_seconds = Some(
                value
                    .parse::<u64>()
                    .ok()
                    .filter(|seconds| *seconds > 0)
                    .ok_or_else(|| {
                        format!("--owner-ttl-seconds needs a positive number; {USAGE}")
                    })?,
            );
        }
    }
    Ok(())
}

/// The lifetime `serve` starts with: owned by its first owner, or manual.
#[cfg(unix)]
fn lifetime_of(owner: &Owner) -> ipc::Lifetime {
    let Some(session) = owner.session.as_deref() else {
        return ipc::Lifetime::manual();
    };
    let ttl = owner
        .ttl_seconds
        .map_or(ipc::DEFAULT_OWNER_TTL, std::time::Duration::from_secs);
    let lifetime = ipc::Lifetime::owned(ttl);
    let identity = owner
        .pid
        .and_then(|pid| state::identity::observe(pid, &state::identity::observer()));
    lifetime.attach(session, identity, std::time::Instant::now());
    lifetime
}

/// What the ctrl-break helper is asked to do.
#[derive(Debug, PartialEq, Eq)]
struct CtrlBreakArgs {
    job: String,
    group: u32,
    pid: u32,
    created: String,
}

const CTRL_BREAK_USAGE: &str =
    "usage: harness-runtime ctrl-break --job <name> --group <pgid> --pid <pid> --created <time>";

fn parse_ctrl_break(args: impl IntoIterator<Item = OsString>) -> Result<CtrlBreakArgs, String> {
    let (mut job, mut group, mut pid, mut created) = (None, None, None, None);
    let mut args = args.into_iter();
    while let Some(flag) = args.next() {
        let field = match flag.to_str() {
            Some("--job") => &mut job,
            Some("--group") => &mut group,
            Some("--pid") => &mut pid,
            Some("--created") => &mut created,
            _ => return Err(format!("unknown argument {flag:?}; {CTRL_BREAK_USAGE}")),
        };
        let value = args
            .next()
            .and_then(|value| value.into_string().ok())
            .ok_or_else(|| {
                format!(
                    "{} needs a value; {CTRL_BREAK_USAGE}",
                    flag.to_string_lossy()
                )
            })?;
        *field = Some(value);
    }
    let number = |value: Option<String>, name: &str| {
        value
            .and_then(|value| value.parse::<u32>().ok())
            .filter(|number| *number > 0)
            .ok_or_else(|| format!("{name} needs a positive number; {CTRL_BREAK_USAGE}"))
    };
    Ok(CtrlBreakArgs {
        job: job.ok_or_else(|| format!("--job is missing; {CTRL_BREAK_USAGE}"))?,
        group: number(group, "--group")?,
        pid: number(pid, "--pid")?,
        created: created.ok_or_else(|| format!("--created is missing; {CTRL_BREAK_USAGE}"))?,
    })
}

/// Run the ctrl-break helper and turn its outcome into the exit code.
fn ctrl_break(args: impl IntoIterator<Item = OsString>) -> ExitCode {
    let request = match parse_ctrl_break(args) {
        Ok(request) => request,
        Err(message) => {
            return Report::new(
                ErrorCode::MalformedRequest,
                message,
                "the runtime starts the ctrl-break helper itself; pass every flag of the usage",
            )
            .print(EXIT_REFUSED);
        }
    };
    #[cfg(windows)]
    {
        match supervisor::ctrl_break(&request.job, request.group, request.pid, &request.created) {
            supervisor::CtrlBreak::Delivered => ExitCode::SUCCESS,
            supervisor::CtrlBreak::NoMember => ExitCode::from(supervisor::CTRL_BREAK_NO_MEMBER),
            supervisor::CtrlBreak::Failed(reason) => {
                eprintln!("ERROR: {reason}");
                ExitCode::from(EXIT_FAILED)
            }
        }
    }
    #[cfg(not(windows))]
    {
        Report::new(
            ErrorCode::UnknownOperation,
            format!(
                "the ctrl-break helper serves only Windows, not the job {}",
                request.job
            ),
            "a stop on this platform signals the process group itself",
        )
        .print(EXIT_REFUSED)
    }
}

/// `ensure` or `release` (ADR 0031, section 4): one JSON line on stdout, and on a failure the
/// `ERROR:` and `REMEDY:` lines on stderr.
#[cfg(unix)]
fn owner_command(ensure: bool, args: impl IntoIterator<Item = OsString>) -> ExitCode {
    let args = match autostart::parse(args, ensure) {
        Ok(args) => args,
        Err(message) => {
            return Report::new(
                ErrorCode::MalformedRequest,
                message,
                "pass --repo and --session as the usage says",
            )
            .print(EXIT_REFUSED);
        }
    };
    let outcome = if ensure {
        autostart::ensure(&args)
    } else {
        autostart::release(&args)
    };
    println!("{}", outcome.answer);
    if outcome.exit != autostart::EXIT_OK && outcome.exit != autostart::EXIT_NOT_RUNNING {
        let text = |key: &str| outcome.answer[key].as_str().unwrap_or("").to_owned();
        eprintln!("ERROR: {}", text("error"));
        eprintln!("REMEDY: {}", text("remedy"));
    }
    ExitCode::from(outcome.exit)
}

/// `ensure` and `release` serve the autostart hook of Claude Code on Unix only (ADR 0031,
/// section 6).
#[cfg(not(unix))]
fn owner_command(ensure: bool, _args: impl IntoIterator<Item = OsString>) -> ExitCode {
    let command = if ensure { "ensure" } else { "release" };
    Report::new(
        ErrorCode::MalformedRequest,
        format!("harness-runtime {command} serves only Unix; {USAGE}"),
        "start `harness-runtime serve --repo <repo>` by hand outside the agent sandbox",
    )
    .print(EXIT_REFUSED)
}

/// What an error line and its `REMEDY:` line say. The remedy line starts with the protocol error
/// code in brackets (ADR 0021, section 8).
#[derive(Debug)]
struct Report {
    code: ErrorCode,
    message: String,
    remedy: String,
}

impl Report {
    fn new(code: ErrorCode, message: impl ToString, remedy: impl ToString) -> Self {
        Self {
            code,
            message: message.to_string(),
            remedy: remedy.to_string(),
        }
    }

    /// Print the `ERROR:` line and its `REMEDY:` line, and give back the exit code.
    fn print(&self, exit: u8) -> ExitCode {
        eprintln!("ERROR: {}", self.message);
        eprintln!("REMEDY: [{}] {}", self.code.as_str(), self.remedy);
        ExitCode::from(exit)
    }
}

/// Why `serve` ended with an error: it never reported ready, or it failed after it was ready.
#[derive(Debug)]
enum Failure {
    Refused(Report),
    Failed(Report),
}

fn serve(args: &Args) -> Result<(), Failure> {
    // The environment is read once: the runtime directory never moves while the runtime serves.
    let paths = resolve_paths(&args.repo, &Environment::of_process())
        .map_err(|err| Failure::Refused(Report::new(err.code(), &err, err.remedy())))?;
    // The handler comes before the bind: a signal then never kills a bound server without
    // `Drop` removing its socket and token.
    let stop = Arc::new(AtomicBool::new(false));
    let signalled = Arc::clone(&stop);
    ctrlc::set_handler(move || signalled.store(true, Ordering::Relaxed)).map_err(|err| {
        Failure::Refused(Report::new(
            ErrorCode::Internal,
            format!("cannot install the signal handler: {err}"),
            "run the runtime in a process that may handle SIGINT and SIGTERM",
        ))
    })?;
    let state_dir = args.repo.join(state::migrate::STATE_REL);
    // A store that an older release wrote is brought to this schema before the first request; a
    // store of a newer schema is refused, and nothing is written.
    #[cfg(unix)]
    let bound =
        Server::bind_with_lifetime(paths, Some(state_dir.clone()), lifetime_of(&args.owner));
    #[cfg(not(unix))]
    let bound = Server::bind_serving(paths, Some(state_dir.clone()));
    let server =
        bound.map_err(|err| Failure::Refused(Report::new(err.code(), &err, err.remedy())))?;
    state::import_approval::ensure_no_pending(&state_dir)
        .and_then(|()| state::schema::upgrade_store(&state_dir))
        .map_err(|err| Failure::Refused(Report::new(err.code(), &err, err.remedy())))?;
    // With the instance lock held, the executions a dead runtime left are adopted or recorded
    // lost before the first request (ADR 0022, section 2); then the periodic reconcile starts.
    server.supervisor().reconcile_all();
    server.supervisor().start(Arc::clone(&stop));
    let ready = json!({
        "status": "ready",
        "socket": server.paths().socket,
        "token_file": server.paths().token,
        "repo_id": server.paths().repo_id,
    });
    let mut stdout = std::io::stdout().lock();
    writeln!(stdout, "{ready}")
        .and_then(|()| stdout.flush())
        .map_err(|err| {
            Failure::Refused(Report::new(
                ErrorCode::Internal,
                format!("cannot report readiness: {err}"),
                "keep the standard output of the runtime open, then repeat the command",
            ))
        })?;
    drop(stdout);
    server.serve_until(&stop).map_err(|err| {
        Failure::Failed(Report::new(
            ErrorCode::Internal,
            format!("the accept loop failed: {err}"),
            "start `harness-runtime serve --repo <repo>` again",
        ))
    })?;
    #[cfg(unix)]
    if server.lifetime().is_exiting() {
        eprintln!(
            "harness-runtime: no owner is left and the store is idle; the runtime started by \
             the autostart hook stops"
        );
    }
    // The periodic reconcile ends with the accept loop.
    stop.store(true, Ordering::Relaxed);
    Ok(())
}

/// Run the migration and print its outcome as one JSON line.
fn migrate(args: &Args) -> ExitCode {
    match state::migrate::run(&args.repo, &args.approval) {
        Ok(outcome) => {
            let mut stdout = std::io::stdout().lock();
            match writeln!(stdout, "{}", outcome.to_json()).and_then(|()| stdout.flush()) {
                Ok(()) => ExitCode::SUCCESS,
                Err(err) => Report::new(
                    ErrorCode::Internal,
                    format!("the migration is done but its result cannot be written: {err}"),
                    "repeat `harness-runtime migrate --repo <repo>`: a repeat after the commit \
                     point answers already_cut_over",
                )
                .print(EXIT_FAILED),
            }
        }
        Err(error) => Report::new(error.code(), &error, error.remedy()).print(error.exit_code()),
    }
}

/// A compatibility repair is offline and requires the same exclusion as rollback.
fn repair_import_approval(args: &Args) -> ExitCode {
    let result =
        (|| {
            if args.check {
                return state::import_approval::check(&args.repo);
            }
            state::approval::check(&args.approval, "import approval repair")?;
            let paths = resolve_paths(&args.repo, &Environment::of_process())
                .map_err(|err| state::Error::refused(err.code(), err.to_string(), err.remedy()))?;
            let _instance = ipc::hold_instance_lock(&paths).map_err(|err| {
            state::Error::refused(err.code(), err.to_string(),
                "stop harness-runtime serve of this repository, then repeat repair-import-approval")
        })?;
            state::import_approval::run(&args.repo, &args.approval)
        })();
    match result {
        Ok(value) => {
            println!("{value}");
            ExitCode::SUCCESS
        }
        Err(error) => {
            let remedy = match &error {
                state::Error::Refused { remedy, .. } => remedy.as_str(),
                _ => state::import_approval::REMEDY,
            };
            Report::new(error.code(), &error, remedy).print(error.exit_code())
        }
    }
}

/// Print what a rollback did as one JSON line, or the failure with the remedy of the rollback.
fn rollback(args: &Args) -> ExitCode {
    let refuse = |code: ErrorCode, message: String, remedy: &str| {
        Report::new(code, message, remedy).print(EXIT_REFUSED)
    };
    if let Err(error) = state::rollback::check_approval(&args.approval) {
        return refuse(
            error.code(),
            error.to_string(),
            state::rollback::remedy(&error),
        );
    }
    let paths = match resolve_paths(&args.repo, &Environment::of_process()) {
        Ok(paths) => paths,
        Err(err) => return refuse(err.code(), err.to_string(), err.remedy()),
    };
    // The instance lock of `serve`: no runtime serves the store while the rollback exports it.
    let _instance = match ipc::hold_instance_lock(&paths) {
        Ok(lock) => lock,
        Err(err @ StartError::AlreadyRunning(_)) => {
            return refuse(
                err.code(),
                err.to_string(),
                "stop `harness-runtime serve` of this repository first, then repeat the rollback",
            );
        }
        Err(err) => return refuse(err.code(), err.to_string(), err.remedy()),
    };
    match state::rollback::run(&args.repo, &args.approval) {
        Ok(outcome) => {
            let mut stdout = std::io::stdout().lock();
            match writeln!(stdout, "{}", outcome.to_json()).and_then(|()| stdout.flush()) {
                Ok(()) => ExitCode::SUCCESS,
                Err(err) => Report::new(
                    ErrorCode::Internal,
                    format!("the rollback is done but its result cannot be written: {err}"),
                    "repeat the rollback: a repeat after the commit point answers \
                     already_rolled_back",
                )
                .print(EXIT_FAILED),
            }
        }
        Err(error) => Report::new(error.code(), &error, state::rollback::remedy(&error))
            .print(error.exit_code()),
    }
}

fn main() -> ExitCode {
    let mut words = env::args_os().skip(1).peekable();
    if words.peek().and_then(|word| word.to_str()) == Some("ctrl-break") {
        return ctrl_break(words.skip(1));
    }
    if let Some(command @ ("ensure" | "release")) = words.peek().and_then(|word| word.to_str()) {
        let ensure = command == "ensure";
        return owner_command(ensure, words.skip(1));
    }
    let args = match parse_args(words) {
        Ok(args) => args,
        Err(message) => {
            return Report::new(
                ErrorCode::MalformedRequest,
                message,
                "pass `serve` with an optional `--repo <path>`, `migrate` with `--approved-by`, \
                 `--approved-at` and `--reason`, or `rollback --to-legacy` with the same three",
            )
            .print(EXIT_REFUSED);
        }
    };
    match args.command {
        Command::Migrate => return migrate(&args),
        Command::Rollback => return rollback(&args),
        Command::RepairImportApproval => return repair_import_approval(&args),
        Command::Serve => {}
    }
    match serve(&args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(Failure::Refused(report)) => report.print(EXIT_REFUSED),
        Err(Failure::Failed(report)) => report.print(EXIT_FAILED),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(words: &[&str]) -> Result<Args, String> {
        parse_args(words.iter().map(OsString::from))
    }

    #[test]
    fn serve_takes_the_repository_from_the_flag() {
        assert_eq!(
            parse(&["serve", "--repo", "/r"]).unwrap().repo,
            PathBuf::from("/r")
        );
    }

    #[test]
    fn migrate_takes_the_repository_from_the_flag() {
        let args = parse(&["migrate", "--repo", "/r"]).unwrap();

        assert_eq!(args.command, Command::Migrate);
        assert_eq!(args.repo, PathBuf::from("/r"));
    }

    #[test]
    fn migrate_takes_the_approval_from_its_flags() {
        let args = parse(&[
            "migrate",
            "--approved-by",
            "human:a",
            "--approved-at",
            "2026-10-27T10:00:00+00:00",
            "--reason",
            "cut over",
            "--repo",
            "/r",
        ])
        .unwrap();

        assert_eq!(args.command, Command::Migrate);
        assert_eq!(args.repo, PathBuf::from("/r"));
        assert_eq!(args.approval.approved_by, "human:a");
        assert_eq!(args.approval.approved_at, "2026-10-27T10:00:00+00:00");
        assert_eq!(args.approval.reason, "cut over");
    }

    #[test]
    fn rollback_takes_the_approval_from_its_flags() {
        let args = parse(&[
            "rollback",
            "--to-legacy",
            "--repo",
            "/r",
            "--approved-by",
            "human:a",
            "--approved-at",
            "2026-10-27T10:00:00+00:00",
            "--reason",
            "back to 1.x",
        ])
        .unwrap();

        assert_eq!(args.command, Command::Rollback);
        assert_eq!(args.repo, PathBuf::from("/r"));
        assert_eq!(args.approval.approved_by, "human:a");
        assert_eq!(args.approval.approved_at, "2026-10-27T10:00:00+00:00");
        assert_eq!(args.approval.reason, "back to 1.x");
    }

    #[test]
    fn serve_defaults_to_the_working_directory() {
        assert_eq!(parse(&["serve"]).unwrap().repo, env::current_dir().unwrap());
    }

    #[test]
    fn ctrl_break_takes_the_job_the_group_the_leader_and_its_creation_time() {
        let words = [
            "--job",
            r"Global\harness-runtime-execution-ab",
            "--group",
            "4242",
            "--pid",
            "4242",
            "--created",
            "133000000000000000",
        ];

        let args = parse_ctrl_break(words.iter().map(OsString::from)).unwrap();

        assert_eq!(
            args,
            CtrlBreakArgs {
                job: r"Global\harness-runtime-execution-ab".to_owned(),
                group: 4242,
                pid: 4242,
                created: "133000000000000000".to_owned(),
            }
        );
    }

    #[test]
    fn ctrl_break_refuses_a_missing_flag_and_a_group_of_zero() {
        let parse = |words: &[&str]| parse_ctrl_break(words.iter().map(OsString::from));

        assert!(
            parse(&["--job", "j", "--group", "1", "--pid", "1"])
                .unwrap_err()
                .contains("--created")
        );
        assert!(
            parse(&["--job", "j", "--group", "0", "--pid", "1", "--created", "1"])
                .unwrap_err()
                .contains("--group")
        );
        assert!(
            parse(&["--signal", "x"])
                .unwrap_err()
                .contains("unknown argument")
        );
        assert!(parse(&["--job"]).unwrap_err().contains("needs a value"));
    }

    #[cfg(unix)]
    #[test]
    fn serve_takes_its_first_owner_from_the_owner_flags() {
        let args = parse(&[
            "serve",
            "--owner-session",
            "s/agent-1",
            "--owner-pid",
            "42",
            "--owner-ttl-seconds",
            "5",
        ])
        .unwrap();

        assert_eq!(
            args.owner,
            Owner {
                session: Some("s/agent-1".to_owned()),
                pid: Some(42),
                ttl_seconds: Some(5),
            }
        );
        assert_eq!(parse(&["serve"]).unwrap().owner, Owner::default());
    }

    #[cfg(unix)]
    #[test]
    fn owner_flags_are_refused_when_malformed_or_without_a_session() {
        for words in [
            &["serve", "--owner-session", "a b"][..],
            &["serve", "--owner-session", ""],
            &["serve", "--owner-session", "s", "--owner-pid", "0"],
            &["serve", "--owner-session", "s", "--owner-ttl-seconds", "x"],
            &["serve", "--owner-pid", "42"],
            &["serve", "--owner-session"],
            &["migrate", "--owner-session", "s"],
        ] {
            assert!(parse(words).is_err(), "{words:?}");
        }
    }

    #[test]
    fn anything_else_is_refused_with_the_usage() {
        assert!(parse(&[]).unwrap_err().contains("usage"));
        assert!(parse(&["rewind"]).unwrap_err().contains("usage"));
        assert!(parse(&["rollback"]).unwrap_err().contains("--to-legacy"));
        assert!(
            parse(&["serve", "--reason", "x"])
                .unwrap_err()
                .contains("unknown argument")
        );
        assert!(
            parse(&["migrate", "--to-legacy"])
                .unwrap_err()
                .contains("unknown argument")
        );
        assert!(
            parse(&["serve", "--socket", "x"])
                .unwrap_err()
                .contains("unknown argument")
        );
        assert!(
            parse(&["serve", "--repo"])
                .unwrap_err()
                .contains("needs a path")
        );
    }
}
