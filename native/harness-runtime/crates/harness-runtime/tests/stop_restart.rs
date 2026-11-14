//! `harness-runtime stop` and `harness-runtime restart`: the runtime of a repository stops through
//! its own IPC (`shutdown`, the same stop as SIGTERM) on a Unix socket and on a Windows named pipe.

use std::fs;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, ChildStdout, Command, ExitStatus, Output, Stdio};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use contracts::{Response, Status, decode, encode, read_frame, write_frame};
use serde_json::{Value, json};

const BIN: &str = env!("CARGO_BIN_EXE_harness-runtime");

/// A repository and a private runtime directory, removed when the test ends.
struct Fixture {
    base: PathBuf,
    repo: PathBuf,
    runtime_dir: PathBuf,
}

impl Fixture {
    fn new(name: &str) -> Self {
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let n = NEXT.fetch_add(1, Ordering::Relaxed);
        let base = std::env::temp_dir().join(format!("hr-stop-{name}-{}-{n}", std::process::id()));
        let _ = fs::remove_dir_all(&base);
        fs::create_dir_all(base.join("repo/.git")).unwrap();
        fs::create_dir_all(base.join("run")).unwrap();
        // Private whatever the umask: a runtime directory refuses a parent others may write.
        #[cfg(unix)]
        for dir in [&base, &base.join("run")] {
            fs::set_permissions(
                dir,
                <fs::Permissions as std::os::unix::fs::PermissionsExt>::from_mode(0o700),
            )
            .unwrap();
        }
        let base = fs::canonicalize(base).unwrap();
        Self {
            repo: base.join("repo"),
            runtime_dir: base.join("run"),
            base,
        }
    }

    fn command(&self, words: &[&str]) -> Command {
        let mut command = Command::new(BIN);
        command
            .args(words)
            .arg("--repo")
            .arg(&self.repo)
            .env("XDG_RUNTIME_DIR", &self.runtime_dir);
        command
    }

    fn run(&self, words: &[&str]) -> Output {
        self.command(words).output().unwrap()
    }

    /// `serve` or `restart` until it prints its readiness line.
    fn start(&self, word: &str) -> Serving {
        let mut child = self
            .command(&[word])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        let mut stdout = BufReader::new(child.stdout.take().unwrap());
        let mut line = String::new();
        stdout.read_line(&mut line).unwrap();
        let ready: Value = serde_json::from_str(&line)
            .unwrap_or_else(|_| panic!("no readiness line: {line:?} {:?}", child.kill()));
        assert_eq!(ready["status"], "ready", "{line}");
        Serving {
            child,
            _stdout: stdout,
            socket: PathBuf::from(ready["socket"].as_str().unwrap()),
            token_file: PathBuf::from(ready["token_file"].as_str().unwrap()),
        }
    }
}

impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.base);
    }
}

/// A runtime started by a test; dropping it kills a runtime the test left running.
struct Serving {
    child: Child,
    /// Kept open: a runtime whose standard output closed would fail its next write.
    _stdout: BufReader<ChildStdout>,
    socket: PathBuf,
    token_file: PathBuf,
}

impl Serving {
    fn token(&self) -> String {
        fs::read_to_string(&self.token_file).unwrap()
    }

    /// The exit status once the runtime ends, or `None` after ten seconds.
    fn exit_within_ten_seconds(&mut self) -> Option<ExitStatus> {
        let deadline = Instant::now() + Duration::from_secs(10);
        while Instant::now() < deadline {
            if let Some(status) = self.child.try_wait().unwrap() {
                return Some(status);
            }
            thread::sleep(Duration::from_millis(20));
        }
        None
    }
}

impl Drop for Serving {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

#[cfg(unix)]
type Client = std::os::unix::net::UnixStream;
#[cfg(windows)]
type Client = platform_ffi::PipeConnection;

#[cfg(unix)]
fn connect(serving: &Serving) -> Client {
    let stream = std::os::unix::net::UnixStream::connect(&serving.socket).unwrap();
    stream
        .set_read_timeout(Some(Duration::from_secs(10)))
        .unwrap();
    stream
}

#[cfg(windows)]
fn connect(serving: &Serving) -> Client {
    let timeout = Duration::from_secs(10);
    let mut pipe = platform_ffi::connect_client(serving.socket.to_str().unwrap(), timeout).unwrap();
    pipe.set_timeout(Some(timeout));
    pipe
}

fn hello(fixture: &Fixture, token: &str) -> Value {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_millis();
    json!({
        "protocol_version": {"major": 1, "minor": 0},
        "operation_id": "hello-1",
        "operation": "hello",
        "request_deadline": u64::try_from(now).unwrap() + 10_000,
        "payload": {
            "protocol": {"min": {"major": 1, "minor": 0}, "max": {"major": 1, "minor": 0}},
            "client_version": "test",
            "repo_root": fixture.repo,
            "token": token,
        },
    })
}

fn exchange(stream: &mut Client, body: &Value) -> Response {
    write_frame(stream, &encode(body).unwrap()).unwrap();
    decode(&read_frame(stream).unwrap()).unwrap()
}

/// The one JSON line a successful command prints.
fn json_line(output: &Output) -> Value {
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    serde_json::from_slice(&output.stdout).unwrap()
}

#[test]
fn stop_without_a_runtime_answers_not_running_and_a_repeat_answers_the_same() {
    let fixture = Fixture::new("idle");

    let first = fixture.run(&["stop"]);
    let second = fixture.run(&["stop"]);

    assert_eq!(json_line(&first), json!({"status": "not_running"}));
    assert_eq!(json_line(&second), json!({"status": "not_running"}));
}

#[test]
fn stop_of_a_live_runtime_stops_it_and_frees_the_repository() {
    let fixture = Fixture::new("live");
    let mut serving = fixture.start("serve");
    let pid = serving.child.id();

    let output = fixture.run(&["stop"]);

    assert_eq!(json_line(&output), json!({"status": "stopped", "pid": pid}));
    let status = serving.exit_within_ten_seconds().expect("serve still runs");
    assert_eq!(status.code(), Some(0));
    assert!(!serving.token_file.exists());
    #[cfg(unix)]
    assert!(!serving.socket.exists());
    let again = fixture.start("serve");
    assert_ne!(again.child.id(), pid);
    assert_eq!(json_line(&fixture.run(&["stop"]))["status"], "stopped");
}

#[test]
fn restart_replaces_a_runtime_that_has_a_live_client() {
    let fixture = Fixture::new("restart");
    let mut old = fixture.start("serve");
    let old_token = old.token();
    let mut client = connect(&old);
    assert_eq!(
        exchange(&mut client, &hello(&fixture, &old_token)).status,
        Status::Ok
    );

    let mut new = fixture.start("restart");

    let status = old
        .exit_within_ten_seconds()
        .expect("the old runtime still runs");
    assert_eq!(status.code(), Some(0));
    assert!(
        read_frame(&mut client).is_err(),
        "the old connection is still open"
    );
    let new_token = new.token();
    assert_ne!(new_token, old_token);
    let mut fresh = connect(&new);
    assert_eq!(
        exchange(&mut fresh, &hello(&fixture, &new_token)).status,
        Status::Ok
    );
    drop(fresh);
    assert_eq!(
        json_line(&fixture.run(&["stop"])),
        json!({"status": "stopped", "pid": new.child.id()})
    );
    assert_eq!(
        new.exit_within_ten_seconds().and_then(|s| s.code()),
        Some(0)
    );
}

#[test]
fn stop_takes_a_repository_relative_to_its_working_directory() {
    let fixture = Fixture::new("relative");
    let mut serving = fixture.start("serve");

    let output = Command::new(BIN)
        .args(["stop", "--repo", "repo"])
        .current_dir(&fixture.base)
        .env("XDG_RUNTIME_DIR", &fixture.runtime_dir)
        .output()
        .unwrap();

    assert_eq!(json_line(&output)["status"], "stopped");
    assert_eq!(
        serving.exit_within_ten_seconds().and_then(|s| s.code()),
        Some(0)
    );
}

#[test]
fn stop_outside_a_repository_is_refused_with_the_not_found_code() {
    let fixture = Fixture::new("norepo");
    fs::remove_dir(fixture.repo.join(".git")).unwrap();

    let output = fixture.run(&["stop"]);

    let stderr = String::from_utf8_lossy(&output.stderr);
    let lines: Vec<&str> = stderr.lines().collect();
    assert_eq!(output.status.code(), Some(2), "{stderr}");
    assert!(lines[0].starts_with("ERROR: "), "{stderr}");
    assert!(lines[1].starts_with("REMEDY: [not_found] "), "{stderr}");
}
