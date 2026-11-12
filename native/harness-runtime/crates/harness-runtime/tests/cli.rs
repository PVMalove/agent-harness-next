//! The `harness-runtime` binary: every error it prints is followed by a `REMEDY:` line whose
//! first token is the protocol error code in brackets (ADR 0021, section 8; DoD 1 of the
//! failure-domain ticket).

use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use std::sync::atomic::{AtomicUsize, Ordering};

use contracts::ErrorCode;
#[cfg(unix)]
use ipc::MAX_SOCKET_PATH_BYTES;

#[path = "../../ipc/tests/support/runtime_dir.rs"]
mod runtime_dir;
use runtime_dir::RuntimeDir;

const FIXTURE: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../state/tests/fixtures/legacy_v3"
);

/// A scratch directory that is removed when the test ends.
struct Scratch(PathBuf);

impl Scratch {
    fn new(name: &str) -> Self {
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let n = NEXT.fetch_add(1, Ordering::Relaxed);
        let root = std::env::temp_dir().join(format!("hr-cli-{name}-{}-{n}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&root).unwrap();
        // Private whatever the umask: a runtime directory refuses a parent others may write.
        #[cfg(unix)]
        fs::set_permissions(
            &root,
            <fs::Permissions as std::os::unix::fs::PermissionsExt>::from_mode(0o700),
        )
        .unwrap();
        Self(root)
    }

    /// A git working tree root without any orchestration state.
    fn repo(name: &str) -> Self {
        let scratch = Self::new(name);
        fs::create_dir(scratch.0.join(".git")).unwrap();
        scratch
    }

    fn state(&self) -> PathBuf {
        self.0.join(".harness/orchestration/state")
    }

    /// A repository whose state is the legacy fixture: it holds a QA lease and a queued run.
    fn repo_with_ledger(name: &str) -> Self {
        let scratch = Self::repo(name);
        copy_tree(Path::new(FIXTURE), &scratch.state());
        scratch
    }

    fn generation(&self) -> PathBuf {
        let pointer: serde_json::Value =
            serde_json::from_slice(&fs::read(self.state().join("ledger.json")).unwrap()).unwrap();
        self.state()
            .join("generations")
            .join(pointer["generation"].as_str().unwrap())
    }

    fn without_qa_lane_entries(self) -> Self {
        let generation = self.generation();
        fs::remove_file(generation.join("qa-lane/lease.json")).unwrap();
        fs::remove_file(generation.join("qa-lane/queue/00000000000000000001-dispatch.json"))
            .unwrap();
        self
    }
}

impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn copy_tree(from: &Path, to: &Path) {
    fs::create_dir_all(to).unwrap();
    for entry in fs::read_dir(from).unwrap() {
        let entry = entry.unwrap();
        let target = to.join(entry.file_name());
        if entry.file_type().unwrap().is_dir() {
            copy_tree(&entry.path(), &target);
        } else {
            fs::copy(entry.path(), target).unwrap();
        }
    }
}

/// The binary with a scratch runtime directory: a test never touches the real
/// `/tmp/harness-<uid>` of the user.
fn run(args: &[&str]) -> Output {
    let runtime_dir = RuntimeDir::new("run-xdg");
    Command::new(env!("CARGO_BIN_EXE_harness-runtime"))
        .args(args)
        .env("XDG_RUNTIME_DIR", runtime_dir.path())
        .output()
        .unwrap()
}

fn stderr_lines(output: &Output) -> Vec<String> {
    String::from_utf8_lossy(&output.stderr)
        .lines()
        .map(str::to_owned)
        .collect()
}

/// The exit code, and the first `REMEDY:` line of a failed run, after the `ERROR:` line.
fn refusal(output: &Output) -> (i32, String) {
    let lines = stderr_lines(output);
    assert!(lines[0].starts_with("ERROR: "), "{lines:?}");
    (output.status.code().unwrap(), lines[1].clone())
}

#[test]
fn an_unknown_command_prints_the_malformed_request_code_first() {
    let (code, remedy) = refusal(&run(&["rewind"]));

    assert_eq!(code, 2);
    assert!(
        remedy.starts_with("REMEDY: [malformed_request] "),
        "{remedy}"
    );
}

fn migrate_args(repo: &Scratch, approved_by: &str) -> Vec<String> {
    [
        "migrate",
        "--repo",
        repo.0.to_str().unwrap(),
        "--approved-by",
        approved_by,
        "--approved-at",
        "2026-10-27T09:00:00+00:00",
        "--reason",
        "cut the fixture over to the runtime store",
    ]
    .map(str::to_owned)
    .to_vec()
}

/// Every file below `root` and its bytes.
fn files(root: &Path) -> Vec<(PathBuf, Vec<u8>)> {
    let mut found = Vec::new();
    let mut pending = vec![root.to_path_buf()];
    while let Some(dir) = pending.pop() {
        for entry in fs::read_dir(&dir).unwrap() {
            let path = entry.unwrap().path();
            if path.is_dir() {
                pending.push(path);
            } else {
                found.push((path.clone(), fs::read(&path).unwrap()));
            }
        }
    }
    found.sort();
    found
}

/// A refused migrate of the fixture without its QA lease: its exit code and remedy line; the
/// state directory is byte for byte what it was, and neither a snapshot nor a store exists.
fn refused_migrate(name: &str, args: impl FnOnce(&Scratch) -> Vec<String>) -> (i32, String) {
    let repo = Scratch::repo_with_ledger(name).without_qa_lane_entries();
    let before = files(&repo.state());

    let refused = refusal(&run_owned(&args(&repo)));

    assert_eq!(files(&repo.state()), before);
    assert!(!repo.state().join("runtime.db").exists());
    assert!(
        !repo
            .0
            .join(".harness/orchestration/state-snapshots")
            .exists()
    );
    refused
}

#[test]
fn migrate_without_an_approval_prints_the_malformed_request_code_and_changes_nothing() {
    let (code, remedy) = refused_migrate("no-approval", |repo| {
        ["migrate", "--repo", repo.0.to_str().unwrap()]
            .map(str::to_owned)
            .to_vec()
    });

    assert_eq!(code, 2);
    assert!(
        remedy.starts_with("REMEDY: [malformed_request] "),
        "{remedy}"
    );
}

#[test]
fn migrate_of_a_policy_approver_prints_the_policy_denied_code_and_changes_nothing() {
    let (code, remedy) = refused_migrate("policy", |repo| migrate_args(repo, "policy:auto"));

    assert_eq!(code, 2);
    assert!(remedy.starts_with("REMEDY: [policy_denied] "), "{remedy}");
}

#[test]
fn migrate_without_a_ledger_prints_the_not_found_code_first() {
    let repo = Scratch::repo("no-ledger");
    fs::create_dir_all(repo.state()).unwrap();

    let (code, remedy) = refusal(&run_owned(&migrate_args(&repo, "human:operator")));

    assert_eq!(code, 2);
    assert!(remedy.starts_with("REMEDY: [not_found] "), "{remedy}");
}

#[test]
fn migrate_while_the_ledger_lock_is_held_prints_the_store_busy_code_first() {
    let repo = Scratch::repo_with_ledger("busy").without_qa_lane_entries();
    // A lock directory without an owner record: its owner cannot be judged, so the lock stays
    // until it is stale.
    fs::create_dir(repo.state().join(".coordinator.lock")).unwrap();

    let output = run_owned(&migrate_args(&repo, "human:operator"));
    let (code, remedy) = refusal(&output);

    assert_eq!(code, 2);
    assert!(remedy.starts_with("REMEDY: [store_busy] "), "{remedy}");
    assert!(
        stderr_lines(&output)[0].contains("(owner-unknown-recent)"),
        "{:?}",
        stderr_lines(&output)
    );
}

#[test]
fn migrate_while_the_qa_lane_holds_a_lease_prints_the_lease_held_code_first() {
    let repo = Scratch::repo_with_ledger("lease");

    let (code, remedy) = refusal(&run_owned(&migrate_args(&repo, "human:operator")));

    assert_eq!(code, 2);
    assert!(remedy.starts_with("REMEDY: [lease_held] "), "{remedy}");
}

#[test]
fn migrate_of_a_newer_ledger_prints_the_protocol_unsupported_code_first() {
    let repo = Scratch::repo_with_ledger("newer");
    let pointer = repo.state().join("ledger.json");
    let text = fs::read_to_string(&pointer).unwrap();
    fs::write(&pointer, text.replace("\"version\": 3", "\"version\": 9")).unwrap();

    let (code, remedy) = refusal(&run_owned(&migrate_args(&repo, "human:operator")));

    assert_eq!(code, 2);
    assert!(
        remedy.starts_with("REMEDY: [protocol_unsupported] "),
        "{remedy}"
    );
}

#[test]
fn serve_in_a_directory_that_is_no_repository_prints_the_not_found_code_first() {
    let dir = Scratch::new("no-repo");

    let (code, remedy) = refusal(&run(&["serve", "--repo", dir.0.to_str().unwrap()]));

    assert_eq!(code, 2);
    assert!(remedy.starts_with("REMEDY: [not_found] "), "{remedy}");
}

/// A cut-over repository (the fixture without its QA lease), and the path of its store.
fn cut_over(name: &str) -> (Scratch, PathBuf) {
    let repo = Scratch::repo_with_ledger(name).without_qa_lane_entries();
    let output = run_owned(&migrate_args(&repo, "human:operator"));
    assert!(output.status.success(), "{:?}", stderr_lines(&output));
    let store = repo.state().join("runtime.db");
    (repo, store)
}

fn user_version(store: &Path) -> i64 {
    rusqlite::Connection::open(store)
        .unwrap()
        .pragma_query_value(None, "user_version", |row| row.get(0))
        .unwrap()
}

/// Write the store back to the schema of version 1, as the first release left it.
fn downgrade_to_version_one(store: &Path) {
    let connection = rusqlite::Connection::open(store).unwrap();
    connection
        .execute_batch(
            "ALTER TABLE dispatch_status DROP COLUMN execution_state;
             ALTER TABLE dispatch_status DROP COLUMN revision;
             ALTER TABLE qa_queue DROP COLUMN revision;
             ALTER TABLE record DROP COLUMN revision;
             DROP INDEX dispatch_batch_id;
             DROP TABLE operations;
             DROP TABLE audit_checkpoint;
             CREATE TABLE audit_checkpoint (seq INTEGER NOT NULL, chain_sha256 TEXT NOT NULL) STRICT;
             DROP TABLE generation;
             DROP TABLE executions;
             DROP TABLE qa_lane;
             CREATE TABLE qa_lane (
                 id            INTEGER PRIMARY KEY CHECK (id = 1),
                 revision      INTEGER NOT NULL DEFAULT 1,
                 fencing_token INTEGER NOT NULL DEFAULT 0,
                 body_json     TEXT NOT NULL
             ) STRICT;
             PRAGMA user_version = 1;",
        )
        .unwrap();
}

/// `harness-runtime serve` until it prints its readiness line or exits; then it is stopped.
fn serve_once(repo: &Scratch) -> Output {
    use std::io::{BufRead, BufReader};
    use std::process::Stdio;

    let runtime_dir = RuntimeDir::new("xdg");
    let mut child = Command::new(env!("CARGO_BIN_EXE_harness-runtime"))
        .args(["serve", "--repo", repo.0.to_str().unwrap()])
        .env("XDG_RUNTIME_DIR", runtime_dir.path())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let mut line = String::new();
    BufReader::new(child.stdout.take().unwrap())
        .read_line(&mut line)
        .unwrap();
    let ready = line.contains("\"ready\"");
    if ready {
        child.kill().unwrap();
    }
    child.wait_with_output().unwrap()
}

#[test]
fn serve_upgrades_a_store_of_version_one_and_audits_the_step() {
    let (repo, store) = cut_over("serve-upgrade");
    downgrade_to_version_one(&store);
    assert_eq!(user_version(&store), 1);

    serve_once(&repo);

    assert_eq!(user_version(&store), state::schema::SCHEMA_VERSION);
    let connection = rusqlite::Connection::open(&store).unwrap();
    let (action, details): (String, String) = connection
        .query_row(
            "SELECT action, details_json FROM audit ORDER BY seq DESC LIMIT 1",
            [],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .unwrap();
    assert_eq!(action, "schema-migrate");
    assert_eq!(
        serde_json::from_str::<serde_json::Value>(&details).unwrap(),
        serde_json::json!({"from": 1, "to": state::schema::SCHEMA_VERSION})
    );
}

#[test]
fn serve_leaves_a_current_store_unchanged() {
    let (repo, store) = cut_over("serve-current");
    let records = |store: &Path| -> i64 {
        rusqlite::Connection::open(store)
            .unwrap()
            .query_row("SELECT COUNT(*) FROM audit", [], |row| row.get(0))
            .unwrap()
    };
    let before = records(&store);

    serve_once(&repo);

    assert_eq!(records(&store), before);
    assert_eq!(user_version(&store), state::schema::SCHEMA_VERSION);
}

#[test]
fn serve_of_a_store_of_a_newer_schema_prints_the_protocol_unsupported_code_and_writes_nothing() {
    let (repo, store) = cut_over("serve-newer");
    rusqlite::Connection::open(&store)
        .unwrap()
        .pragma_update(None, "user_version", state::schema::SCHEMA_VERSION + 1)
        .unwrap();

    let output = serve_once(&repo);

    let (code, remedy) = refusal(&output);
    assert_eq!(code, 2);
    assert!(
        remedy.starts_with("REMEDY: [protocol_unsupported] "),
        "{remedy}"
    );
    assert_eq!(user_version(&store), state::schema::SCHEMA_VERSION + 1);
}

#[test]
fn every_error_line_is_followed_by_a_remedy_with_a_known_code() {
    let plain = Scratch::new("plain");
    let ledger = Scratch::repo_with_ledger("every");
    let runs = [
        run(&[]),
        run(&["serve", "--socket", "x"]),
        run(&["serve", "--repo"]),
        run(&["serve", "--repo", plain.0.to_str().unwrap()]),
        run_owned(&migrate_args(&plain, "human:operator")),
        run_owned(&migrate_args(&ledger, "human:operator")),
        run(&["rollback", "--repo", ledger.0.to_str().unwrap()]),
        run(&[
            "rollback",
            "--to-legacy",
            "--repo",
            ledger.0.to_str().unwrap(),
        ]),
        run_owned(&rollback_args(&plain, "human:operator")),
        run_owned(&rollback_args(&ledger, "policy:auto")),
        run_owned(&rollback_args(&ledger, "human:operator")),
    ];

    for output in &runs {
        let lines = stderr_lines(output);
        assert!(!output.status.success(), "{lines:?}");
        for (at, line) in lines.iter().enumerate() {
            if !line.starts_with("ERROR: ") {
                continue;
            }
            let remedy = lines.get(at + 1).unwrap_or_else(|| panic!("{lines:?}"));
            let code = remedy
                .strip_prefix("REMEDY: [")
                .and_then(|rest| rest.split_once("] "))
                .map(|(code, _)| code)
                .unwrap_or_else(|| panic!("no code in {remedy:?}"));
            assert!(
                ErrorCode::ALL.iter().any(|known| known.as_str() == code),
                "{code} is not a protocol error code"
            );
        }
    }
}

fn rollback_args(repo: &Scratch, approved_by: &str) -> Vec<String> {
    [
        "rollback",
        "--to-legacy",
        "--repo",
        repo.0.to_str().unwrap(),
        "--approved-by",
        approved_by,
        "--approved-at",
        "2026-10-27T10:00:00+00:00",
        "--reason",
        "return to 1.x",
    ]
    .map(str::to_owned)
    .to_vec()
}

fn run_rollback(repo: &Scratch, approved_by: &str, env: &[(&str, &std::ffi::OsStr)]) -> Output {
    let runtime_dir = RuntimeDir::new("rollback-xdg");
    let mut command = Command::new(env!("CARGO_BIN_EXE_harness-runtime"));
    command
        .args(rollback_args(repo, approved_by))
        .env("XDG_RUNTIME_DIR", runtime_dir.path());
    for (key, value) in env {
        command.env(key, value);
    }
    command.output().unwrap()
}

fn pointer(repo: &Scratch) -> serde_json::Value {
    serde_json::from_slice(&fs::read(repo.state().join("ledger.json")).unwrap()).unwrap()
}

#[test]
fn rollback_prints_one_json_line_and_returns_the_state_to_the_file_ledger() {
    let (repo, store) = cut_over("rollback");

    let output = run_rollback(&repo, "human:operator", &[]);

    assert!(output.status.success(), "{:?}", stderr_lines(&output));
    let line: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(line["rolled_back"], true);
    assert_eq!(pointer(&repo)["version"], 3);
    assert_eq!(pointer(&repo)["generation"], line["generation"]);
    assert!(store.exists());
}

#[test]
fn rollback_of_a_policy_approver_prints_the_policy_denied_code_and_changes_nothing() {
    let (repo, _) = cut_over("rb-policy");
    let before = fs::read(repo.state().join("ledger.json")).unwrap();

    let (code, remedy) = refusal(&run_rollback(&repo, "policy:auto", &[]));

    assert_eq!(code, 2);
    assert!(remedy.starts_with("REMEDY: [policy_denied] "), "{remedy}");
    assert_eq!(fs::read(repo.state().join("ledger.json")).unwrap(), before);
}

#[test]
fn rollback_while_serve_runs_prints_the_lease_held_code_and_changes_nothing() {
    use std::io::{BufRead, BufReader};
    use std::process::Stdio;

    let (repo, _) = cut_over("rb-serving");
    let runtime_dir = RuntimeDir::new("xdg-rollback");
    let mut serve = Command::new(env!("CARGO_BIN_EXE_harness-runtime"))
        .args(["serve", "--repo", repo.0.to_str().unwrap()])
        .env("XDG_RUNTIME_DIR", runtime_dir.path())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .unwrap();
    let mut line = String::new();
    BufReader::new(serve.stdout.take().unwrap())
        .read_line(&mut line)
        .unwrap();
    assert!(line.contains("\"ready\""), "{line}");

    let output = run_rollback(
        &repo,
        "human:operator",
        &[("XDG_RUNTIME_DIR", runtime_dir.path().as_os_str())],
    );
    serve.kill().unwrap();
    serve.wait().unwrap();

    let (code, remedy) = refusal(&output);
    assert_eq!(code, 2);
    assert!(remedy.starts_with("REMEDY: [lease_held] "), "{remedy}");
    assert!(remedy.contains("stop `harness-runtime serve`"), "{remedy}");
    assert_eq!(pointer(&repo)["version"], 4);
}

#[test]
fn rollback_that_stops_before_the_pointer_finishes_on_a_repeat() {
    let (repo, _) = cut_over("rb-crash");

    let failed = run_rollback(
        &repo,
        "human:operator",
        &[(
            "HARNESS_RUNTIME_TEST_FAIL_AT",
            std::ffi::OsStr::new("rollback-pointer-replace"),
        )],
    );

    let (code, remedy) = refusal(&failed);
    assert_eq!(code, 3, "{:?}", stderr_lines(&failed));
    assert!(remedy.starts_with("REMEDY: [internal] "), "{remedy}");
    assert_eq!(pointer(&repo)["version"], 4);
    let authority: serde_json::Value =
        serde_json::from_slice(&fs::read(repo.state().join("AUTHORITY.json")).unwrap()).unwrap();
    assert_eq!(authority["authority"], "file-ledger");

    let repeated = run_rollback(&repo, "human:operator", &[]);

    assert!(repeated.status.success(), "{:?}", stderr_lines(&repeated));
    assert_eq!(pointer(&repo)["version"], 3);
    assert_eq!(pointer(&repo)["generation"], authority["generation"]);
}

#[test]
fn rollback_that_fails_before_the_commit_point_replaces_its_archive_on_a_repeat() {
    let (repo, store) = cut_over("rb-stale");
    let authority: serde_json::Value =
        serde_json::from_slice(&fs::read(repo.state().join("AUTHORITY.json")).unwrap()).unwrap();
    let archive = repo.state().join(format!(
        "runtime-export/{}.tar",
        authority["store_id"].as_str().unwrap()
    ));

    let failed = run_rollback(
        &repo,
        "human:operator",
        &[(
            "HARNESS_RUNTIME_TEST_FAIL_AT",
            std::ffi::OsStr::new("rollback-generation"),
        )],
    );

    let (code, _) = refusal(&failed);
    assert_eq!(code, 3, "{:?}", stderr_lines(&failed));
    assert_eq!(pointer(&repo)["version"], 4);
    let stale = fs::read(&archive).unwrap();
    // The store is still the authority and changes before the repeat.
    rusqlite::Connection::open(&store)
        .unwrap()
        .execute(
            "UPDATE record SET revision = revision + 1 WHERE path = (SELECT MIN(path) FROM record)",
            [],
        )
        .unwrap();

    let repeated = run_rollback(&repo, "human:operator", &[]);

    assert!(repeated.status.success(), "{:?}", stderr_lines(&repeated));
    let line: serde_json::Value = serde_json::from_slice(&repeated.stdout).unwrap();
    let replaced = fs::read(&archive).unwrap();
    assert_ne!(replaced, stale);
    assert_eq!(
        line["export_sha256"],
        state::canonical::sha256_hex(&replaced).as_str()
    );
    assert_eq!(pointer(&repo)["version"], 3);
}

fn run_owned(args: &[String]) -> Output {
    run(&args.iter().map(String::as_str).collect::<Vec<_>>())
}

/// `harness-runtime ensure` and `release` with a real `serve` (ADR 0031, section 4).
#[cfg(unix)]
mod autostart {
    use std::process::{Child, Stdio};
    use std::thread;
    use std::time::{Duration, Instant};

    use serde_json::Value;

    use super::*;

    /// A repository, its private runtime directory and the runtimes a test started.
    struct Setup {
        repo: Scratch,
        xdg: RuntimeDir,
        pids: Vec<u32>,
    }

    impl Setup {
        fn new(name: &str, repo: Scratch) -> Self {
            Self {
                repo,
                xdg: RuntimeDir::new(&format!("{name}-xdg")),
                pids: Vec::new(),
            }
        }

        fn command(&self, words: &[&str]) -> Command {
            let mut command = Command::new(env!("CARGO_BIN_EXE_harness-runtime"));
            command
                .args(&words[..1])
                .arg("--repo")
                .arg(&self.repo.0)
                .args(&words[1..])
                .env("XDG_RUNTIME_DIR", self.xdg.path());
            command
        }

        /// Run `ensure` or `release`: its JSON line and its exit code.
        fn run(&mut self, words: &[&str]) -> (Value, i32) {
            let output = self.command(words).output().unwrap();
            let line = String::from_utf8_lossy(&output.stdout);
            let answer: Value = serde_json::from_str(line.trim())
                .unwrap_or_else(|err| panic!("{err}: {line:?} {:?}", stderr_lines(&output)));
            if let Some(pid) = answer["pid"].as_u64() {
                self.pids.push(u32::try_from(pid).unwrap());
            }
            (answer, output.status.code().unwrap())
        }

        fn socket(&self) -> PathBuf {
            let paths =
                ipc::resolve_paths(&self.repo.0, &ipc::Environment::with_xdg(self.xdg.path()))
                    .unwrap();
            paths.socket
        }

        /// `serve` started by hand, ready.
        fn manual(&mut self) -> Child {
            use std::io::{BufRead, BufReader};

            let mut child = Command::new(env!("CARGO_BIN_EXE_harness-runtime"))
                .args(["serve", "--repo", self.repo.0.to_str().unwrap()])
                .env("XDG_RUNTIME_DIR", self.xdg.path())
                .stdout(Stdio::piped())
                .stderr(Stdio::null())
                .spawn()
                .unwrap();
            let mut line = String::new();
            BufReader::new(child.stdout.take().unwrap())
                .read_line(&mut line)
                .unwrap();
            assert!(line.contains("\"ready\""), "{line}");
            child
        }

        /// Whether the runtime removed its socket within `seconds`.
        fn stops_within(&self, seconds: u64) -> bool {
            let deadline = Instant::now() + Duration::from_secs(seconds);
            while Instant::now() < deadline {
                if !self.socket().exists() {
                    return true;
                }
                thread::sleep(Duration::from_millis(100));
            }
            false
        }

        /// Whether the runtime still serves after it had the time to decide.
        fn keeps_serving(&self) -> bool {
            thread::sleep(Duration::from_millis(2500));
            self.socket().exists()
        }
    }

    impl Drop for Setup {
        fn drop(&mut self) {
            for pid in &self.pids {
                let _ = Command::new("kill")
                    .arg(pid.to_string())
                    .stderr(Stdio::null())
                    .status();
            }
        }
    }

    #[test]
    fn ensure_starts_an_owned_runtime_that_another_session_reuses_and_the_last_release_stops() {
        let mut setup = Setup::new("ensure-start", Scratch::repo("ensure-start"));

        let (started, code) = setup.run(&["ensure", "--session", "s1"]);
        let (reused, reused_code) = setup.run(&["ensure", "--session", "s2", "--agent", "a"]);

        assert_eq!(code, 0, "{started}");
        assert_eq!(started["status"], "started");
        assert_eq!(started["owned"], true);
        assert!(started["pid"].as_u64().is_some());
        let log = PathBuf::from(started["log"].as_str().unwrap());
        assert!(log.ends_with(format!(
            "{}.serve.log",
            setup.socket().file_stem().unwrap().to_str().unwrap()
        )));
        assert!(fs::read_to_string(&log).unwrap().contains("\"ready\""));
        assert_eq!(reused_code, 0);
        assert_eq!(reused["status"], "reused");
        assert_eq!(reused["owned"], true);
        assert_eq!(reused["owners"], serde_json::json!(["s1", "s2/a"]));

        let (released, released_code) = setup.run(&["release", "--session", "s1"]);
        assert_eq!(
            (released["status"].as_str(), released_code),
            (Some("released"), 0)
        );
        assert!(setup.keeps_serving(), "another owner keeps the runtime");
        let (released, _) = setup.run(&["release", "--session", "s2", "--agent", "a"]);
        assert_eq!(released["status"], "released");
        assert!(setup.stops_within(10), "the own runtime did not stop");
        let (after, after_code) = setup.run(&["release", "--session", "s1"]);
        assert_eq!(
            (after["status"].as_str(), after_code),
            (Some("not_running"), 0)
        );
    }

    #[test]
    fn a_manual_runtime_is_reused_and_never_stopped() {
        let mut setup = Setup::new("ensure-manual", Scratch::repo("ensure-manual"));
        let mut manual = setup.manual();

        let (reused, code) = setup.run(&["ensure", "--session", "s"]);
        let (released, _) = setup.run(&["release", "--session", "s"]);
        let (again, _) = setup.run(&["release", "--session", "s"]);

        assert_eq!(code, 0);
        assert_eq!(reused["status"], "reused");
        assert_eq!(reused["owned"], false);
        assert_eq!(released["status"], "released");
        assert_eq!(again["status"], "not_attached");
        assert!(setup.keeps_serving(), "a manual runtime stopped");
        assert!(manual.try_wait().unwrap().is_none());
        manual.kill().unwrap();
        manual.wait().unwrap();
    }

    #[test]
    fn a_busy_store_keeps_the_own_runtime_until_it_is_idle() {
        let (repo, store) = cut_over("ensure-busy");
        let mut setup = Setup::new("ensure-busy", repo);
        let (started, code) = setup.run(&["ensure", "--session", "s"]);
        assert_eq!(
            (started["status"].as_str(), code),
            (Some("started"), 0),
            "{started}"
        );
        let connection = rusqlite::Connection::open(&store).unwrap();
        connection
            .execute(
                "INSERT INTO qa_queue (id, body_json) VALUES ('q1', '{}')",
                [],
            )
            .unwrap();
        let dispatch: String = connection
            .query_row("SELECT id FROM dispatch_status LIMIT 1", [], |row| {
                row.get(0)
            })
            .unwrap();
        let state: String = connection
            .query_row(
                "SELECT state FROM dispatch_status WHERE id = ?1",
                [&dispatch],
                |row| row.get(0),
            )
            .unwrap();

        let (released, _) = setup.run(&["release", "--session", "s"]);
        assert_eq!(released["status"], "released");
        assert_eq!(
            released["busy"],
            serde_json::json!(["the QA queue holds q1"])
        );
        assert!(
            setup.keeps_serving(),
            "a queued QA run must keep the runtime"
        );

        connection
            .execute_batch(&format!(
                "DELETE FROM qa_queue;
                 UPDATE dispatch_status SET state = 'working' WHERE id = '{dispatch}';"
            ))
            .unwrap();
        assert!(
            setup.keeps_serving(),
            "a working dispatch must keep the runtime"
        );

        connection
            .execute(
                "UPDATE dispatch_status SET state = ?1 WHERE id = ?2",
                [&state, &dispatch],
            )
            .unwrap();
        assert!(setup.stops_within(10), "an idle store did not let it stop");
    }

    #[test]
    fn an_owner_whose_process_died_is_released() {
        let mut setup = Setup::new("ensure-dead", Scratch::repo("ensure-dead"));
        let mut owner = Command::new("sleep").arg("60").spawn().unwrap();
        let pid = owner.id().to_string();

        let (started, code) = setup.run(&["ensure", "--session", "s", "--owner-pid", &pid]);
        assert_eq!(
            (started["status"].as_str(), code),
            (Some("started"), 0),
            "{started}"
        );
        assert!(setup.keeps_serving(), "a live owner keeps the runtime");
        owner.kill().unwrap();
        owner.wait().unwrap();

        // Linux observes the start time of a pid; another Unix relies on the time to live.
        if cfg!(target_os = "linux") {
            assert!(setup.stops_within(10), "the dead owner kept the runtime");
        }
    }

    #[test]
    fn an_owner_that_does_not_attach_again_within_the_time_to_live_is_released() {
        let mut setup = Setup::new("ensure-ttl", Scratch::repo("ensure-ttl"));

        let (started, code) = setup.run(&["ensure", "--session", "s", "--owner-ttl-seconds", "1"]);

        assert_eq!(
            (started["status"].as_str(), code),
            (Some("started"), 0),
            "{started}"
        );
        assert!(setup.stops_within(10), "the expired owner kept the runtime");
    }

    #[test]
    fn a_refused_start_is_reported_with_its_error_remedy_and_journal() {
        let (repo, store) = cut_over("ensure-refused");
        rusqlite::Connection::open(&store)
            .unwrap()
            .pragma_update(None, "user_version", state::schema::SCHEMA_VERSION + 1)
            .unwrap();
        let mut setup = Setup::new("ensure-refused", repo);

        let (refused, code) = setup.run(&["ensure", "--session", "s"]);

        assert_eq!(code, 2, "{refused}");
        assert_eq!(refused["status"], "refused");
        assert_eq!(refused["exit_code"], 2);
        assert!(
            refused["remedy"]
                .as_str()
                .unwrap()
                .starts_with("[protocol_unsupported] "),
            "{refused}"
        );
        assert!(!refused["error"].as_str().unwrap().is_empty());
        let log = fs::read_to_string(refused["log"].as_str().unwrap()).unwrap();
        assert!(log.contains("ERROR: "), "{log}");
        assert!(!setup.socket().exists());
    }

    #[test]
    fn a_refused_start_ignores_the_report_an_earlier_start_left_in_the_journal() {
        use std::io::Write;

        let (repo, store) = cut_over("ensure-stale");
        rusqlite::Connection::open(&store)
            .unwrap()
            .pragma_update(None, "user_version", state::schema::SCHEMA_VERSION + 1)
            .unwrap();
        let mut setup = Setup::new("ensure-stale", repo);
        let paths =
            ipc::resolve_paths(&setup.repo.0, &ipc::Environment::with_xdg(setup.xdg.path()))
                .unwrap();
        let (journal, mut file) = ipc::open_serve_log(&paths).unwrap();
        writeln!(file, "ERROR: stale start").unwrap();
        writeln!(file, "REMEDY: [lease_held] stale remedy").unwrap();
        drop(file);

        let (refused, code) = setup.run(&["ensure", "--session", "s"]);

        // A stale `[lease_held]` would send ensure to attach again until its timeout.
        assert_eq!(
            (refused["status"].as_str(), code),
            (Some("refused"), 2),
            "{refused}"
        );
        let remedy = refused["remedy"].as_str().unwrap();
        assert!(remedy.starts_with("[protocol_unsupported] "), "{refused}");
        assert!(
            !refused["error"].as_str().unwrap().contains("stale"),
            "{refused}"
        );
        let log = fs::read_to_string(&journal).unwrap();
        assert!(log.starts_with("ERROR: stale start\n"), "{log}");
    }

    #[test]
    fn attach_only_never_starts_a_runtime() {
        let mut setup = Setup::new("ensure-attach", Scratch::repo("ensure-attach"));

        let (answer, code) = setup.run(&["ensure", "--session", "s", "--attach-only"]);

        assert_eq!((answer["status"].as_str(), code), (Some("not_running"), 3));
        assert!(!setup.socket().exists());
    }

    #[test]
    fn two_concurrent_ensures_leave_one_runtime_with_both_owners() {
        let mut setup = Setup::new("ensure-race", Scratch::repo("ensure-race"));
        let commands: Vec<_> = ["s1", "s2"]
            .into_iter()
            .map(|session| {
                setup
                    .command(&["ensure", "--session", session])
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped())
                    .spawn()
                    .unwrap()
            })
            .collect();
        let mut statuses: Vec<String> = commands
            .into_iter()
            .map(|child| {
                let output = child.wait_with_output().unwrap();
                assert!(output.status.success(), "{:?}", stderr_lines(&output));
                let answer: Value = serde_json::from_slice(&output.stdout).unwrap();
                if let Some(pid) = answer["pid"].as_u64() {
                    setup.pids.push(u32::try_from(pid).unwrap());
                }
                answer["status"].as_str().unwrap().to_owned()
            })
            .collect();
        statuses.sort();

        assert_eq!(statuses, ["reused", "started"]);
        let (answer, _) = setup.run(&["ensure", "--session", "s3"]);
        assert_eq!(answer["owners"], serde_json::json!(["s1", "s2", "s3"]));
    }

    #[test]
    fn ensure_and_release_refuse_a_malformed_owner() {
        for words in [
            &["ensure", "--session", "a b"][..],
            &["release", "--session", "s", "--attach-only"],
        ] {
            let setup = Setup::new("ensure-usage", Scratch::repo("ensure-usage"));
            let output = setup.command(words).output().unwrap();
            let (code, remedy) = refusal(&output);
            assert_eq!(code, 2);
            assert!(
                remedy.starts_with("REMEDY: [malformed_request] "),
                "{remedy}"
            );
        }
    }
}
