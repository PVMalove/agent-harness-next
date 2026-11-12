//! `harness-runtime ensure` and `harness-runtime release` (ADR 0031, section 4): the commands the
//! autostart hook runs. `ensure` attaches an owner to the runtime of a repository and starts an
//! owned runtime when none answers; `release` removes the owner. Neither ever signals a process.

use std::ffi::OsString;
use std::fs;
use std::io::Write;
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

use ipc::{Client, ClientError, Environment, RuntimePaths, resolve_paths};
use serde_json::{Value, json};

/// How long `ensure` waits for a runtime it started to answer.
const READY_TIMEOUT: Duration = Duration::from_secs(40);
/// How often `ensure` looks at the runtime while it waits.
const POLL: Duration = Duration::from_millis(100);

pub const EXIT_OK: u8 = 0;
pub const EXIT_FAILED: u8 = 1;
pub const EXIT_REFUSED: u8 = 2;
pub const EXIT_NOT_RUNNING: u8 = 3;

pub const USAGE: &str = "usage: harness-runtime ensure --repo <path> --session <id> [--agent <id>] \
    [--owner-pid <pid>] [--owner-ttl-seconds <n>] [--attach-only] | harness-runtime release \
    --repo <path> --session <id> [--agent <id>]";

/// What `ensure` or `release` is asked to do.
#[derive(Debug, Default, PartialEq, Eq)]
pub struct Args {
    pub repo: PathBuf,
    pub session: String,
    pub agent: Option<String>,
    pub owner_pid: Option<i64>,
    pub ttl_seconds: Option<u64>,
    pub attach_only: bool,
}

impl Args {
    /// The owner key: `<session>` or `<session>/<agent>`.
    pub fn key(&self) -> String {
        match &self.agent {
            Some(agent) => format!("{}/{agent}", self.session),
            None => self.session.clone(),
        }
    }
}

fn positive<T: std::str::FromStr + PartialOrd + Default>(
    value: &str,
    flag: &str,
) -> Result<T, String> {
    value
        .parse::<T>()
        .ok()
        .filter(|number| *number > T::default())
        .ok_or_else(|| format!("{flag} needs a positive number; {USAGE}"))
}

/// Parse the flags of `ensure` (`ensure` true) or `release`.
pub fn parse(args: impl IntoIterator<Item = OsString>, ensure: bool) -> Result<Args, String> {
    let mut parsed = Args::default();
    let mut repo = None;
    let mut session = None;
    let mut args = args.into_iter();
    while let Some(flag) = args.next() {
        let flag = flag.to_string_lossy().into_owned();
        if ensure && flag == "--attach-only" {
            parsed.attach_only = true;
            continue;
        }
        let known = matches!(flag.as_str(), "--repo" | "--session" | "--agent")
            || (ensure && matches!(flag.as_str(), "--owner-pid" | "--owner-ttl-seconds"));
        if !known {
            return Err(format!("unknown argument {flag:?}; {USAGE}"));
        }
        let value = args
            .next()
            .ok_or_else(|| format!("{flag} needs a value; {USAGE}"))?;
        if flag == "--repo" {
            repo = Some(PathBuf::from(value));
            continue;
        }
        let value = value
            .into_string()
            .map_err(|value| format!("{value:?} is not UTF-8; {USAGE}"))?;
        match flag.as_str() {
            "--session" => session = Some(value),
            "--agent" => parsed.agent = Some(value),
            "--owner-pid" => parsed.owner_pid = Some(positive(&value, &flag)?),
            _ => parsed.ttl_seconds = Some(positive(&value, &flag)?),
        }
    }
    parsed.repo = repo.ok_or_else(|| format!("--repo is missing; {USAGE}"))?;
    parsed.session = session.ok_or_else(|| format!("--session is missing; {USAGE}"))?;
    if parsed
        .agent
        .as_deref()
        .is_some_and(|agent| agent.contains('/'))
        || !ipc::valid_key(&parsed.key())
    {
        return Err(format!(
            "--session and --agent need 1 to {} characters of [A-Za-z0-9._:-] together; {USAGE}",
            ipc::MAX_KEY_LEN
        ));
    }
    Ok(parsed)
}

/// What a command prints and how it exits.
pub struct Outcome {
    pub answer: Value,
    pub exit: u8,
}

fn failed(error: impl ToString, remedy: &str) -> Outcome {
    Outcome {
        answer: json!({"status": "failed", "error": error.to_string(), "remedy": remedy}),
        exit: EXIT_FAILED,
    }
}

/// The repository and the paths of its runtime.
fn locate(repo: &Path) -> Result<(PathBuf, RuntimePaths), Outcome> {
    let paths = resolve_paths(repo, &Environment::of_process())
        .map_err(|err| failed(&err, err.remedy()))?;
    let root = fs::canonicalize(repo).map_err(|err| failed(err, "pass an existing --repo"))?;
    Ok((root, paths))
}

/// Attach `args` to the runtime that answers: its answer and the `pid` of the runtime, with
/// `attached: false` for a runtime that does not know `runtime.attach`.
fn attach(paths: &RuntimePaths, root: &Path, args: &Args) -> Result<Value, ClientError> {
    let mut client = Client::connect(paths, root)?;
    let mut answer = if client.serves("runtime.attach") {
        let mut payload = json!({"key": args.key()});
        if let Some(pid) = args.owner_pid {
            payload["owner_pid"] = json!(pid);
        }
        client.call("runtime.attach", Some(payload))?
    } else {
        json!({"owned": false, "attached": false})
    };
    answer["pid"] = client.call("status", None)?["pid"].clone();
    Ok(answer)
}

/// The journal of a runtime this `ensure` started: its path and where the lines of this start
/// begin. The journal is appended to, never emptied (another runtime may write it).
struct Journal {
    path: PathBuf,
    start: u64,
}

/// Start an owned runtime for `args`, its output appended to the journal of the runtime
/// directory after a start marker.
fn spawn(root: &Path, paths: &RuntimePaths, args: &Args) -> Result<(Child, Journal), Outcome> {
    let (log, mut file) =
        ipc::open_serve_log(paths).map_err(|err| refused_to_start(&err, err.remedy(), None))?;
    let start = writeln!(
        file,
        "--- harness-runtime ensure {}: starting serve",
        std::process::id()
    )
    .and_then(|()| file.metadata())
    .map_err(|err| failed(err, "check the runtime directory, then repeat ensure"))?
    .len();
    let stderr = file
        .try_clone()
        .map_err(|err| failed(err, "check the runtime directory, then repeat ensure"))?;
    let program = std::env::current_exe()
        .map_err(|err| failed(err, "run ensure from an installed harness-runtime"))?;
    let mut command = Command::new(program);
    command
        .arg("serve")
        .arg("--repo")
        .arg(root)
        .arg("--owner-session")
        .arg(args.key());
    if let Some(pid) = args.owner_pid {
        command.arg("--owner-pid").arg(pid.to_string());
    }
    if let Some(ttl) = args.ttl_seconds {
        command.arg("--owner-ttl-seconds").arg(ttl.to_string());
    }
    // Its own process group: a signal to the group of the hook never reaches the runtime.
    command
        .stdin(Stdio::null())
        .stdout(file)
        .stderr(stderr)
        .process_group(0);
    let child = command.spawn().map_err(|err| {
        failed(
            err,
            "check that harness-runtime may run, then repeat ensure",
        )
    })?;
    Ok((child, Journal { path: log, start }))
}

fn refused_to_start(error: &dyn std::fmt::Display, remedy: &str, log: Option<&Path>) -> Outcome {
    Outcome {
        answer: json!({
            "status": "refused",
            "exit_code": EXIT_REFUSED,
            "error": error.to_string(),
            "remedy": remedy,
            "log": log,
        }),
        exit: EXIT_REFUSED,
    }
}

/// The last `ERROR:` and `REMEDY:` lines the journal got since this start.
fn last_report(journal: &Journal) -> (String, String) {
    let bytes = fs::read(&journal.path).unwrap_or_default();
    let from = usize::try_from(journal.start).map_or(bytes.len(), |start| start.min(bytes.len()));
    let text = String::from_utf8_lossy(&bytes[from..]);
    let last = |prefix: &str| {
        text.lines()
            .rev()
            .find_map(|line| line.strip_prefix(prefix))
            .unwrap_or("")
            .trim()
            .to_owned()
    };
    (last("ERROR:"), last("REMEDY:"))
}

/// `ensure`: attach to the runtime that answers, or start an owned one and attach to it.
pub fn ensure(args: &Args) -> Outcome {
    let (root, paths) = match locate(&args.repo) {
        Ok(found) => found,
        Err(outcome) => return outcome,
    };
    let deadline = Instant::now() + READY_TIMEOUT;
    let mut started: Option<(Child, Journal)> = None;
    loop {
        match attach(&paths, &root, args) {
            Ok(answer) if answer["exiting"] == true => {
                // The runtime decided to stop: wait until its socket is gone, then start one.
                while paths.socket.exists() && Instant::now() < deadline {
                    thread::sleep(POLL);
                }
            }
            Ok(mut answer) => {
                // The runtime this `ensure` started, or one that another `ensure` started first.
                let own = started
                    .as_ref()
                    .filter(|(child, _)| answer["pid"] == json!(child.id()));
                answer["status"] = json!(if own.is_some() { "started" } else { "reused" });
                if let Some((_, journal)) = own {
                    answer["log"] = json!(journal.path);
                }
                answer["socket"] = json!(paths.socket);
                return Outcome {
                    answer,
                    exit: EXIT_OK,
                };
            }
            Err(ClientError::NotRunning(_)) if args.attach_only => {
                return Outcome {
                    answer: json!({"status": "not_running"}),
                    exit: EXIT_NOT_RUNNING,
                };
            }
            Err(ClientError::NotRunning(_)) => match started.as_mut() {
                None => match spawn(&root, &paths, args) {
                    Ok(child) => started = Some(child),
                    Err(outcome) => return outcome,
                },
                Some((child, journal)) => match child.try_wait() {
                    Ok(None) => {}
                    Ok(Some(status)) => {
                        let (error, remedy) = last_report(journal);
                        // Another `ensure` started the runtime first: attach to that one.
                        if status.code() == Some(i32::from(EXIT_REFUSED))
                            && remedy.starts_with("[lease_held]")
                        {
                            started = None;
                        } else {
                            let mut outcome =
                                refused_to_start(&error, &remedy, Some(&journal.path));
                            outcome.answer["exit_code"] = json!(status.code());
                            return outcome;
                        }
                    }
                    Err(err) => return failed(err, "repeat ensure"),
                },
            },
            Err(ClientError::Refused(error)) => {
                return failed(
                    format!("{}: {}", error.code.as_str(), error.message),
                    &error.remedy,
                );
            }
            Err(ClientError::Failed(reason)) => {
                return failed(reason, "check the runtime directory, then repeat ensure");
            }
        }
        if Instant::now() >= deadline {
            return Outcome {
                answer: json!({
                    "status": "timeout",
                    "log": started.as_ref().map(|(_, journal)| &journal.path),
                    "seconds": READY_TIMEOUT.as_secs(),
                }),
                exit: EXIT_REFUSED,
            };
        }
        thread::sleep(POLL);
    }
}

/// `release`: remove the owner from the runtime that answers. It never signals the runtime.
pub fn release(args: &Args) -> Outcome {
    let (root, paths) = match locate(&args.repo) {
        Ok(found) => found,
        Err(outcome) => return outcome,
    };
    let released = Client::connect(&paths, &root).and_then(|mut client| {
        if !client.serves("runtime.release") {
            return Ok(json!({"released": false}));
        }
        client.call("runtime.release", Some(json!({"key": args.key()})))
    });
    match released {
        Ok(mut answer) => {
            let status = if answer["released"] == true {
                "released"
            } else {
                "not_attached"
            };
            answer["status"] = json!(status);
            Outcome {
                answer,
                exit: EXIT_OK,
            }
        }
        Err(ClientError::NotRunning(_)) => Outcome {
            answer: json!({"status": "not_running"}),
            exit: EXIT_OK,
        },
        Err(ClientError::Refused(error)) => failed(
            format!("{}: {}", error.code.as_str(), error.message),
            &error.remedy,
        ),
        Err(ClientError::Failed(reason)) => {
            failed(reason, "check the runtime directory, then repeat release")
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn words(items: &[&str]) -> Vec<OsString> {
        items.iter().map(OsString::from).collect()
    }

    #[test]
    fn ensure_takes_the_owner_from_its_flags() {
        let args = parse(
            words(&[
                "--repo",
                "/r",
                "--session",
                "s1",
                "--agent",
                "a1",
                "--owner-pid",
                "42",
                "--owner-ttl-seconds",
                "9",
                "--attach-only",
            ]),
            true,
        )
        .unwrap();

        assert_eq!(args.repo, PathBuf::from("/r"));
        assert_eq!(args.key(), "s1/a1");
        assert_eq!(args.owner_pid, Some(42));
        assert_eq!(args.ttl_seconds, Some(9));
        assert!(args.attach_only);
    }

    #[test]
    fn release_takes_only_the_repository_and_the_owner() {
        let args = parse(words(&["--repo", "/r", "--session", "s1"]), false).unwrap();

        assert_eq!(args.key(), "s1");
        for refused in [
            &["--repo", "/r", "--session", "s1", "--attach-only"][..],
            &["--repo", "/r", "--session", "s1", "--owner-pid", "1"],
        ] {
            assert!(parse(words(refused), false).is_err(), "{refused:?}");
        }
    }

    #[test]
    fn a_missing_or_malformed_owner_is_refused() {
        for refused in [
            &["--repo", "/r"][..],
            &["--session", "s"],
            &["--repo", "/r", "--session", "a b"],
            &["--repo", "/r", "--session", "s", "--agent", "a/b"],
            &["--repo", "/r", "--session", "s", "--owner-pid", "0"],
            &[
                "--repo",
                "/r",
                "--session",
                "s",
                "--owner-ttl-seconds",
                "-1",
            ],
            &["--repo", "/r", "--session"],
            &["--repo", "/r", "--session", "s", "--signal"],
        ] {
            assert!(parse(words(refused), true).is_err(), "{refused:?}");
        }
    }

    #[test]
    fn the_report_of_a_start_ignores_the_lines_of_an_earlier_start() {
        let path = std::env::temp_dir().join(format!(
            "hr-autostart-journal-{}.serve.log",
            std::process::id()
        ));
        let stale = "ERROR: stale\nREMEDY: [lease_held] stale\n--- harness-runtime ensure 1: starting serve\n";
        fs::write(&path, stale).unwrap();
        let journal = Journal {
            path: path.clone(),
            start: u64::try_from(stale.len()).unwrap(),
        };
        let mut file = fs::OpenOptions::new().append(true).open(&path).unwrap();
        writeln!(file, "ERROR: fresh").unwrap();

        let report = last_report(&journal);
        let _ = fs::remove_file(&path);

        assert_eq!(report, ("fresh".to_owned(), String::new()));
    }
}
