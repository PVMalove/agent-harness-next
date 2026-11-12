//! The IPC server over a real Unix domain socket or Windows named pipe: permissions, `hello`,
//! errors and shutdown. The protocol tests run unchanged on both transports.

use std::fs;
use std::io::{Read, Write};
#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;
#[cfg(unix)]
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Barrier};
use std::thread::{self, JoinHandle};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use contracts::{
    ErrorCode, MAX_FRAME_LEN, Response, Status, decode, encode, read_frame, write_frame,
};
use ipc::{Environment, PeerId, Server, StartError, resolve_paths};
use serde_json::{Value, json};

#[path = "../../state/tests/common/qa_store.rs"]
mod qa_store;

/// The client end of the transport under test.
#[cfg(unix)]
type Client = UnixStream;
#[cfg(windows)]
type Client = platform_ffi::PipeConnection;

/// The identity of the user that runs these tests.
#[cfg(unix)]
fn own_peer() -> PeerId {
    nix::unistd::getuid().as_raw()
}

#[cfg(windows)]
fn own_peer() -> PeerId {
    platform_ffi::current_user_sid().unwrap()
}

/// An identity that no test client has.
#[cfg(unix)]
fn foreign_peer() -> PeerId {
    own_peer().wrapping_add(1)
}

#[cfg(windows)]
fn foreign_peer() -> PeerId {
    // The SID of the "Nobody" authority: it is never the SID of a logon user.
    "S-1-0-0".to_owned()
}

struct Fixture {
    root: PathBuf,
    xdg: PathBuf,
}

impl Fixture {
    fn new(name: &str) -> Self {
        let base = std::env::temp_dir().join(format!("hr-ipc-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&base);
        let root = base.join("repo");
        let xdg = base.join("run");
        fs::create_dir_all(root.join(".git")).unwrap();
        fs::create_dir_all(&xdg).unwrap();
        // Private whatever the umask: a runtime directory refuses a parent others may write.
        #[cfg(unix)]
        fs::set_permissions(&xdg, fs::Permissions::from_mode(0o700)).unwrap();
        Self {
            root: fs::canonicalize(root).unwrap(),
            xdg: fs::canonicalize(xdg).unwrap(),
        }
    }

    fn bind(&self) -> Result<Server, StartError> {
        let paths = resolve_paths(&self.root, &Environment::with_xdg(&self.xdg)).unwrap();
        Server::bind(paths)
    }
}

struct Running {
    stop: Arc<AtomicBool>,
    thread: Option<JoinHandle<()>>,
    socket: PathBuf,
    token: String,
}

impl Running {
    fn start(server: Server) -> Self {
        Self::spawn(server, None)
    }

    /// Serve clients that run as `uid`; another uid makes every real client a foreign peer.
    fn start_as(server: Server, peer: PeerId) -> Self {
        Self::spawn(server, Some(peer))
    }

    fn spawn(server: Server, peer: Option<PeerId>) -> Self {
        let stop = Arc::new(AtomicBool::new(false));
        let socket = server.paths().socket.clone();
        let token = fs::read_to_string(&server.paths().token).unwrap();
        let flag = Arc::clone(&stop);
        let thread = thread::spawn(move || {
            match peer {
                Some(peer) => server.serve_until_as(&flag, peer),
                None => server.serve_until(&flag),
            }
            .unwrap();
        });
        Self {
            stop,
            thread: Some(thread),
            socket,
            token,
        }
    }

    #[cfg(unix)]
    fn connect(&self) -> Client {
        let stream = UnixStream::connect(&self.socket).unwrap();
        stream
            .set_read_timeout(Some(Duration::from_secs(5)))
            .unwrap();
        stream
    }

    #[cfg(windows)]
    fn connect(&self) -> Client {
        let timeout = Duration::from_secs(5);
        let mut pipe =
            platform_ffi::connect_client(self.socket.to_str().unwrap(), timeout).unwrap();
        pipe.set_timeout(Some(timeout));
        pipe
    }
}

impl Drop for Running {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
        if let Some(thread) = self.thread.take() {
            let served = thread.join();
            // A second panic during unwinding aborts the process and hides the failed assertion.
            if !thread::panicking() {
                served.unwrap();
            }
        }
    }
}

fn now_ms() -> u64 {
    u64::try_from(
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_millis(),
    )
    .unwrap()
}

fn request(operation: &str, payload: Option<Value>) -> Value {
    let mut body = json!({
        "protocol_version": {"major": 1, "minor": 0},
        "operation_id": format!("{operation}-1"),
        "operation": operation,
        "request_deadline": now_ms() + 10_000,
    });
    if let Some(payload) = payload {
        body["payload"] = payload;
    }
    body
}

fn hello(root: &Path, token: &str, min: u32, max: u32) -> Value {
    request(
        "hello",
        Some(json!({
            "protocol": {"min": {"major": min, "minor": 0}, "max": {"major": max, "minor": 0}},
            "client_version": "test",
            "repo_root": root,
            "token": token,
        })),
    )
}

/// A request that names the protocol minor `minor` it speaks (the envelope of a newer client).
fn request_minor(operation: &str, payload: Option<Value>, minor: u32) -> Value {
    let mut body = request(operation, payload);
    body["protocol_version"] = json!({"major": 1, "minor": minor});
    body
}

/// A `hello` that negotiates exactly `minor`.
fn hello_minor(root: &Path, token: &str, minor: u32) -> Value {
    request_minor(
        "hello",
        Some(json!({
            "protocol": {"min": {"major": 1, "minor": minor},
                         "max": {"major": 1, "minor": minor}},
            "client_version": "test",
            "repo_root": root,
            "token": token,
        })),
        minor,
    )
}

fn exchange(stream: &mut (impl Read + Write), body: &Value) -> Response {
    write_frame(stream, &encode(body).unwrap()).unwrap();
    decode(&read_frame(stream).unwrap()).unwrap()
}

fn error_code(response: &Response) -> ErrorCode {
    assert_eq!(response.status, Status::Error);
    response.error.as_ref().unwrap().code
}

#[cfg(unix)]
fn mode(path: &Path) -> u32 {
    fs::metadata(path).unwrap().permissions().mode() & 0o777
}

#[cfg(unix)]
#[test]
fn the_directory_the_socket_and_the_token_are_private_to_the_owner() {
    let fixture = Fixture::new("modes");
    let server = fixture.bind().unwrap();
    let paths = server.paths().clone();

    assert_eq!(mode(&paths.dir), 0o700);
    assert_eq!(mode(&paths.socket), 0o600);
    assert_eq!(mode(&paths.token), 0o600);
    assert_eq!(fs::read_to_string(&paths.token).unwrap().len(), 64);
}

#[cfg(windows)]
#[test]
fn the_token_file_is_private_to_the_user() {
    let fixture = Fixture::new("modes");
    let server = fixture.bind().unwrap();
    let paths = server.paths().clone();

    let dacl = platform_ffi::dacl_of_path(&paths.token).unwrap();

    assert!(dacl.protected, "{dacl:?}");
    assert_eq!(dacl.aces.len(), 1, "{dacl:?}");
    assert_eq!(dacl.aces[0].kind, "A");
    assert_eq!(dacl.aces[0].trustee, own_peer(), "{dacl:?}");
    assert_eq!(fs::read_to_string(&paths.token).unwrap().len(), 64);
}

#[cfg(windows)]
#[test]
fn the_pipe_is_named_after_the_repository() {
    let fixture = Fixture::new("name");
    let server = fixture.bind().unwrap();

    assert_eq!(
        server.paths().socket,
        PathBuf::from(ipc::pipe_name(&server.paths().repo_id))
    );
}

#[test]
fn hello_with_the_token_then_status() {
    let fixture = Fixture::new("hello");
    let runtime = Running::start(fixture.bind().unwrap());
    let mut stream = runtime.connect();

    let greeting = exchange(&mut stream, &hello(&fixture.root, &runtime.token, 1, 1));
    let status = exchange(&mut stream, &request("status", None));

    assert_eq!(greeting.status, Status::Ok);
    assert_eq!(
        greeting.result.unwrap()["protocol"],
        json!({"major": 1, "minor": 0})
    );
    assert_eq!(status.status, Status::Ok);
    assert_eq!(status.result.unwrap()["state"], "serving");
}

#[test]
fn a_wrong_token_is_unauthorized_and_the_connection_closes() {
    let fixture = Fixture::new("token");
    let runtime = Running::start(fixture.bind().unwrap());
    let mut stream = runtime.connect();

    let answer = exchange(&mut stream, &hello(&fixture.root, "not-the-token", 1, 1));

    assert_eq!(error_code(&answer), ErrorCode::UnauthorizedPeer);
    assert!(read_frame(&mut stream).is_err());
}

#[test]
fn an_incompatible_major_is_protocol_unsupported() {
    let fixture = Fixture::new("major");
    let runtime = Running::start(fixture.bind().unwrap());
    let mut stream = runtime.connect();

    let answer = exchange(&mut stream, &hello(&fixture.root, &runtime.token, 2, 2));

    assert_eq!(error_code(&answer), ErrorCode::ProtocolUnsupported);
}

#[test]
fn an_unknown_field_is_malformed_and_the_connection_stays_usable() {
    let fixture = Fixture::new("field");
    let runtime = Running::start(fixture.bind().unwrap());
    let mut stream = runtime.connect();
    let mut body = request("status", None);
    body["surprise"] = json!(1);

    let refused = exchange(&mut stream, &body);
    let greeting = exchange(&mut stream, &hello(&fixture.root, &runtime.token, 1, 1));

    assert_eq!(error_code(&refused), ErrorCode::MalformedRequest);
    assert_eq!(greeting.status, Status::Ok);
}

#[test]
fn an_oversized_frame_is_refused_without_reading_it() {
    let fixture = Fixture::new("big");
    let runtime = Running::start(fixture.bind().unwrap());
    let mut stream = runtime.connect();

    stream
        .write_all(&(MAX_FRAME_LEN + 1).to_be_bytes())
        .unwrap();
    let answer: Response = decode(&read_frame(&mut stream).unwrap()).unwrap();

    assert_eq!(error_code(&answer), ErrorCode::MalformedRequest);
}

#[test]
fn a_request_before_hello_is_unauthorized() {
    let fixture = Fixture::new("early");
    let runtime = Running::start(fixture.bind().unwrap());
    let mut stream = runtime.connect();

    let answer = exchange(&mut stream, &request("status", None));

    assert_eq!(error_code(&answer), ErrorCode::UnauthorizedPeer);
}

#[test]
fn a_second_runtime_for_the_same_repository_is_refused() {
    let fixture = Fixture::new("rival");
    let _first = Running::start(fixture.bind().unwrap());

    assert!(matches!(fixture.bind(), Err(StartError::AlreadyRunning(_))));
}

#[cfg(unix)]
#[test]
fn a_stale_socket_file_is_replaced() {
    let fixture = Fixture::new("stale");
    let paths = resolve_paths(&fixture.root, &Environment::with_xdg(&fixture.xdg)).unwrap();
    fs::create_dir_all(&paths.dir).unwrap();
    fs::set_permissions(&paths.dir, fs::Permissions::from_mode(0o700)).unwrap();
    // A runtime that was killed leaves its socket file behind; nothing listens on it.
    drop(UnixListener::bind(&paths.socket).unwrap());
    let socket = paths.socket;
    assert!(socket.exists());

    let runtime = Running::start(fixture.bind().unwrap());
    let mut stream = runtime.connect();

    assert!(socket.exists());
    assert_eq!(
        exchange(&mut stream, &hello(&fixture.root, &runtime.token, 1, 1)).status,
        Status::Ok
    );
}

#[test]
fn stopping_the_server_removes_the_socket_and_the_token() {
    let fixture = Fixture::new("stop");
    let server = fixture.bind().unwrap();
    let paths = server.paths().clone();

    drop(server);

    // A pipe name is no file: asking the file system about it would connect to the pipe.
    #[cfg(unix)]
    assert!(!paths.socket.exists());
    assert!(!paths.token.exists());
}

#[test]
fn a_peer_of_another_user_is_refused_with_unauthorized_peer() {
    let fixture = Fixture::new("peer");
    let runtime = Running::start_as(fixture.bind().unwrap(), foreign_peer());
    let mut stream = runtime.connect();

    // The refusal comes before the client has sent anything, even with the right token.
    let answer: Response = decode(&read_frame(&mut stream).unwrap()).unwrap();

    assert_eq!(error_code(&answer), ErrorCode::UnauthorizedPeer);
    assert!(read_frame(&mut stream).is_err());
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

/// The human approval of the cutover of a test repository.
fn approval() -> state::approval::Approval {
    state::approval::Approval {
        approved_by: "human:operator".to_owned(),
        approved_at: "2026-10-27T09:00:00+00:00".to_owned(),
        reason: "cut the test repository over to the runtime store".to_owned(),
    }
}

/// The fixture state of the Python 1.x ledger, without its QA lease and queue, cut over to the
/// store of `fixture`; the state directory.
fn cut_over(fixture: &Fixture) -> PathBuf {
    let state_dir = legacy_state(fixture);
    state::migrate::run(&fixture.root, &approval()).unwrap();
    state_dir
}

/// The fixture state of the Python 1.x ledger, without its QA lease and queue, still in the
/// file-ledger epoch; the state directory.
fn legacy_state(fixture: &Fixture) -> PathBuf {
    let state_dir = fixture.root.join(".harness/orchestration/state");
    copy_tree(
        &Path::new(env!("CARGO_MANIFEST_DIR")).join("../state/tests/fixtures/legacy_v3"),
        &state_dir,
    );
    for generation in fs::read_dir(state_dir.join("generations")).unwrap() {
        let lane = generation.unwrap().path().join("qa-lane");
        let _ = fs::remove_file(lane.join("lease.json"));
        if let Ok(queue) = fs::read_dir(lane.join("queue")) {
            for entry in queue {
                fs::remove_file(entry.unwrap().path()).unwrap();
            }
        }
    }
    state_dir
}

/// The owner of a QA lease is the client process the kernel reports for the connection, never
/// a pid the request names; `qa.lane.inspect` reads it back with the verdict on it.
#[cfg(any(target_os = "linux", windows))]
#[test]
fn a_lease_records_the_client_process_the_kernel_reports() {
    let fixture = Fixture::new("lease-peer");
    let state_dir = cut_over(&fixture);
    let paths = resolve_paths(&fixture.root, &Environment::with_xdg(&fixture.xdg)).unwrap();
    let runtime = Running::start(Server::bind_serving(paths, Some(state_dir)).unwrap());
    let mut stream = runtime.connect();
    assert_eq!(
        exchange(&mut stream, &hello(&fixture.root, &runtime.token, 1, 1)).status,
        Status::Ok
    );

    let acquired = exchange(
        &mut stream,
        &request(
            "state.write",
            Some(json!({"mutations": [{
                "op": "lease_acquire", "path": "qa-lane/lease.json",
                "lease": {"owner_kind": "dispatch", "owner_id": "d1", "ttl_seconds": 60},
            }]})),
        ),
    );
    let inspected = exchange(&mut stream, &request("qa.lane.inspect", None));

    assert_eq!(acquired.status, Status::Ok, "{acquired:?}");
    let lease = &acquired.result.unwrap()["lease"];
    assert_eq!(lease["identity"]["pid"], std::process::id());
    let inspected = inspected.result.unwrap();
    assert_eq!(inspected["lease"], *lease);
    assert_eq!(inspected["verdict"], "owner-alive");
    assert_eq!(inspected["stale_heartbeat"], false);
}

/// A snapshot of one connection answers its later reads from the moment it was opened, while
/// another connection commits.
#[test]
fn a_read_snapshot_spans_requests_while_another_connection_commits() {
    let fixture = Fixture::new("snapshot");
    let state_dir = cut_over(&fixture);
    let paths = resolve_paths(&fixture.root, &Environment::with_xdg(&fixture.xdg)).unwrap();
    let runtime = Running::start(Server::bind_serving(paths, Some(state_dir)).unwrap());
    let mut reader = runtime.connect();
    let mut writer = runtime.connect();
    for stream in [&mut reader, &mut writer] {
        assert_eq!(
            exchange(stream, &hello(&fixture.root, &runtime.token, 1, 1)).status,
            Status::Ok
        );
    }
    let path = "reports/snapshot.json";

    let opened = exchange(
        &mut reader,
        &request(
            "state.read",
            Some(json!({"snapshot": "open", "paths": [path]})),
        ),
    );
    let snapshot = opened.result.as_ref().unwrap()["snapshot"].clone();
    let written = exchange(
        &mut writer,
        &request(
            "state.write",
            Some(json!({"mutations": [{"op": "create", "path": path,
                "content": state::canonical::canonical_json(&json!({"dispatch_id": "d"}))}]})),
        ),
    );
    let again = exchange(
        &mut reader,
        &request(
            "state.read",
            Some(json!({"snapshot": snapshot, "paths": [path], "close": true})),
        ),
    );
    let closed = exchange(
        &mut reader,
        &request("state.read", Some(json!({"snapshot": snapshot}))),
    );

    assert!(snapshot.as_str().unwrap().starts_with("snapshot-"));
    assert_eq!(written.status, Status::Ok, "{written:?}");
    assert_eq!(again.revision, opened.revision);
    assert_eq!(again.result.unwrap()["records"], json!({}));
    assert_eq!(error_code(&closed), ErrorCode::StoreBusy);
    assert_eq!(closed.error.unwrap().facts["reason"], "snapshot_expired");
}

/// The store-side filter selects one batch in the same read transaction as every other read, and
/// a commit of another connection does not change the snapshot's answer. The test runs unchanged
/// on the Unix socket and the Windows named pipe (ADR 0020, section 3).
#[test]
fn a_filtered_read_snapshot_spans_requests_while_another_connection_commits() {
    const BATCH: &str = "batch-aaaaaaaa-0000-4000-8000-000000000001";
    const BATCH_PATH: &str = "batches/batch-aaaaaaaa-0000-4000-8000-000000000001.json";
    let fixture = Fixture::new("filtered-snapshot");
    let state_dir = cut_over(&fixture);
    let paths = resolve_paths(&fixture.root, &Environment::with_xdg(&fixture.xdg)).unwrap();
    let runtime = Running::start(Server::bind_serving(paths, Some(state_dir)).unwrap());
    let mut reader = runtime.connect();
    let mut writer = runtime.connect();
    for stream in [&mut reader, &mut writer] {
        assert_eq!(
            exchange(stream, &hello_minor(&fixture.root, &runtime.token, 7)).status,
            Status::Ok
        );
    }
    let filter = json!({"batch_id": BATCH});
    let collections = json!(["batches", "dispatches", "dispatch-status"]);

    let opened = exchange(
        &mut reader,
        &request_minor(
            "state.read",
            Some(json!({"snapshot": "open", "collections": collections, "filter": filter})),
            7,
        ),
    );
    let answer = opened.result.as_ref().unwrap();
    let snapshot = answer["snapshot"].clone();
    let records = answer["records"].clone();
    assert_eq!(records.as_object().unwrap().len(), 5, "{records}");
    let mut changed = records[BATCH_PATH].clone();
    changed["ticket"] = json!("#changed");
    let written = exchange(
        &mut writer,
        &request_minor(
            "state.write",
            Some(json!({"mutations": [{
                "op": "replace",
                "path": BATCH_PATH,
                "content": state::canonical::canonical_json(&changed),
                "expected_revision": answer["revisions"][BATCH_PATH].clone(),
            }]})),
            7,
        ),
    );
    let again = exchange(
        &mut reader,
        &request_minor(
            "state.read",
            Some(
                json!({"snapshot": snapshot, "collections": collections, "filter": filter,
                        "close": true}),
            ),
            7,
        ),
    );

    assert_eq!(opened.status, Status::Ok, "{opened:?}");
    assert!(snapshot.as_str().unwrap().starts_with("snapshot-"));
    assert_eq!(written.status, Status::Ok, "{written:?}");
    assert_eq!(again.result.as_ref().unwrap()["records"], records);
}

/// A filtered read needs protocol minor 7: a peer that negotiated an older minor gets a typed
/// `protocol_unsupported`, not `malformed_request` for a field it never learned.
#[test]
fn a_filtered_read_from_an_older_protocol_minor_is_protocol_unsupported() {
    let fixture = Fixture::new("filter-minor");
    let state_dir = cut_over(&fixture);
    let paths = resolve_paths(&fixture.root, &Environment::with_xdg(&fixture.xdg)).unwrap();
    let runtime = Running::start(Server::bind_serving(paths, Some(state_dir)).unwrap());
    let mut stream = runtime.connect();
    assert_eq!(
        exchange(&mut stream, &hello_minor(&fixture.root, &runtime.token, 6)).status,
        Status::Ok
    );

    let refused = exchange(
        &mut stream,
        &request_minor(
            "state.read",
            Some(json!({
                "collections": ["batches"],
                "filter": {"batch_id": "batch-aaaaaaaa-0000-4000-8000-000000000001"},
            })),
            6,
        ),
    );

    assert_eq!(error_code(&refused), ErrorCode::ProtocolUnsupported);
    let facts = refused.error.unwrap().facts;
    assert_eq!(facts["negotiated_minor"], 6);
    assert_eq!(facts["required_minor"], 7);
}

#[test]
fn simultaneous_starts_leave_one_runtime_with_its_own_token() {
    let fixture = Arc::new(Fixture::new("race"));
    let starters = 8;
    let barrier = Arc::new(Barrier::new(starters));
    let handles: Vec<_> = (0..starters)
        .map(|_| {
            let fixture = Arc::clone(&fixture);
            let barrier = Arc::clone(&barrier);
            thread::spawn(move || {
                barrier.wait();
                fixture.bind()
            })
        })
        .collect();
    let outcomes: Vec<_> = handles.into_iter().map(|h| h.join().unwrap()).collect();

    let mut winners = Vec::new();
    for outcome in outcomes {
        match outcome {
            Ok(server) => winners.push(server),
            Err(err) => assert!(matches!(err, StartError::AlreadyRunning(_)), "{err}"),
        }
    }
    assert_eq!(winners.len(), 1);
    let runtime = Running::start(winners.pop().unwrap());
    let mut stream = runtime.connect();
    assert_eq!(
        exchange(&mut stream, &hello(&fixture.root, &runtime.token, 1, 1)).status,
        Status::Ok
    );
}

#[test]
#[should_panic(expected = "the test failed first")]
fn a_failing_test_keeps_its_message_when_the_server_thread_failed_too() {
    // A panic of the fixture destructor during unwinding aborts the whole test process, so the
    // message of the failing test would never be printed.
    let thread = thread::spawn(|| panic!("the server thread failed"));
    let _runtime = Running {
        stop: Arc::new(AtomicBool::new(false)),
        thread: Some(thread),
        socket: PathBuf::new(),
        token: String::new(),
    };

    panic!("the test failed first");
}

/// Serve the state of `fixture`, connect and say `hello`; the features `hello` named.
fn serving(fixture: &Fixture, state_dir: PathBuf) -> (Running, Client, Vec<Value>) {
    let paths = resolve_paths(&fixture.root, &Environment::with_xdg(&fixture.xdg)).unwrap();
    let runtime = Running::start(Server::bind_serving(paths, Some(state_dir)).unwrap());
    let mut stream = runtime.connect();
    let greeting = exchange(&mut stream, &hello(&fixture.root, &runtime.token, 1, 1));
    assert_eq!(greeting.status, Status::Ok);
    let features = greeting.result.unwrap()["features"]
        .as_array()
        .unwrap()
        .clone();
    (runtime, stream, features)
}

fn verify(stream: &mut Client, candidate: &str, target: &str) -> Response {
    exchange(
        stream,
        &request(
            "qa.evidence.verify",
            Some(json!({"candidate_sha": candidate, "target_sha": target})),
        ),
    )
}

/// `qa.evidence.verify` over the transport judges only the stored evidence of the pair: an
/// accepted full QA run of exactly the pair is `ok`, an unknown pair is refused, and neither
/// moves the revision of the store.
#[test]
fn qa_evidence_verify_judges_the_stored_pair_and_writes_nothing() {
    let fixture = Fixture::new("qa-evidence");
    let state_dir = legacy_state(&fixture);
    let pointer = state::legacy::read_pointer(&state_dir).unwrap().unwrap();
    let run = qa_store::accepted_qa(qa_store::passed_stages());
    qa_store::write_legacy(
        &state_dir.join("generations").join(pointer.generation),
        &run,
    );
    state::migrate::run(&fixture.root, &approval()).unwrap();
    let (_runtime, mut stream, features) = serving(&fixture, state_dir);
    let before = exchange(
        &mut stream,
        &request("state.read", Some(json!({"paths": []}))),
    );

    let confirmed = verify(&mut stream, qa_store::CANDIDATE, qa_store::TARGET);
    let unknown = verify(&mut stream, &"d".repeat(40), qa_store::TARGET);
    let extra = exchange(
        &mut stream,
        &request(
            "qa.evidence.verify",
            Some(
                json!({"candidate_sha": qa_store::CANDIDATE, "target_sha": qa_store::TARGET,
                        "fallback": true}),
            ),
        ),
    );
    let bad_sha = verify(&mut stream, "HEAD", qa_store::TARGET);
    let after = exchange(
        &mut stream,
        &request("state.read", Some(json!({"paths": []}))),
    );

    assert!(features.contains(&json!("qa.evidence.verify")));
    assert_eq!(confirmed.status, Status::Ok, "{confirmed:?}");
    let confirmed = confirmed.result.unwrap();
    assert_eq!(confirmed["verdict"], "ok", "{confirmed}");
    assert_eq!(confirmed["confirmed_by"]["source"], "original-qa");
    assert_eq!(confirmed["pair"]["candidate_tree_sha"], qa_store::TREE);
    assert_eq!(unknown.status, Status::Ok, "{unknown:?}");
    let unknown = unknown.result.unwrap();
    assert_eq!(unknown["verdict"], "refused");
    let codes: Vec<&str> = unknown["violations"]
        .as_array()
        .unwrap()
        .iter()
        .map(|violation| violation["code"].as_str().unwrap())
        .collect();
    assert_eq!(codes, ["pair_not_recorded", "no_full_qa"]);
    assert_eq!(error_code(&extra), ErrorCode::MalformedRequest);
    assert_eq!(error_code(&bad_sha), ErrorCode::MalformedRequest);
    assert_eq!(before.revision, after.revision);
}

/// The selection a pair requires is the one its stored record says: the stages of the ticket's diff
/// confirm the pair into an integration branch and are refused for the pair into the default
/// branch, over the same transport and with the same request.
#[test]
fn qa_evidence_verify_accepts_diff_stages_only_for_a_pair_that_requires_them() {
    let mut stages = qa_store::passed_stages();
    stages[1].selection = contracts::StageSelection::TicketDiff;
    stages[1].nodeids = Some(vec!["tests/test_x.py".to_owned()]);
    let pairs = [
        ("qa-evidence-into-integration", qa_store::diff_pair_record()),
        ("qa-evidence-into-default", qa_store::pair_record()),
        ("qa-evidence-old-contract", qa_store::legacy_pair_record()),
    ];
    let mut verdicts = Vec::new();

    for (name, pair) in pairs {
        let fixture = Fixture::new(name);
        let state_dir = legacy_state(&fixture);
        let pointer = state::legacy::read_pointer(&state_dir).unwrap().unwrap();
        let run = qa_store::accepted_qa_with(stages.clone(), pair);
        qa_store::write_legacy(
            &state_dir.join("generations").join(pointer.generation),
            &run,
        );
        state::migrate::run(&fixture.root, &approval()).unwrap();
        let (_runtime, mut stream, _features) = serving(&fixture, state_dir);

        let answer = verify(&mut stream, qa_store::CANDIDATE, qa_store::TARGET);

        assert_eq!(answer.status, Status::Ok, "{name}: {answer:?}");
        let result = answer.result.unwrap();
        let codes: Vec<String> = result["violations"]
            .as_array()
            .unwrap()
            .iter()
            .map(|violation| violation["code"].as_str().unwrap().to_owned())
            .collect();
        verdicts.push((result["verdict"].as_str().unwrap().to_owned(), codes));
    }

    let refused = ("refused".to_owned(), vec!["selection_not_full".to_owned()]);
    assert_eq!(
        verdicts,
        [("ok".to_owned(), Vec::new()), refused.clone(), refused]
    );
}

/// The request names the pair and nothing else: a client cannot ask for a weaker check, so a
/// `requirement` (or a `selection`) is a malformed request, even for a pair that would accept it.
#[test]
fn qa_evidence_verify_answers_a_requirement_field_with_malformed_request() {
    let fixture = Fixture::new("qa-evidence-requirement");
    let state_dir = legacy_state(&fixture);
    let pointer = state::legacy::read_pointer(&state_dir).unwrap().unwrap();
    let run = qa_store::accepted_qa_with(qa_store::passed_stages(), qa_store::diff_pair_record());
    qa_store::write_legacy(
        &state_dir.join("generations").join(pointer.generation),
        &run,
    );
    state::migrate::run(&fixture.root, &approval()).unwrap();
    let (_runtime, mut stream, _features) = serving(&fixture, state_dir);
    let before = exchange(
        &mut stream,
        &request("state.read", Some(json!({"paths": []}))),
    );

    for (field, value) in [
        ("requirement", "full"),
        ("requirement", "ticket-diff"),
        ("selection", "ticket-diff"),
    ] {
        let answer = exchange(
            &mut stream,
            &request(
                "qa.evidence.verify",
                Some(json!({"candidate_sha": qa_store::CANDIDATE,
                            "target_sha": qa_store::TARGET, field: value})),
            ),
        );

        assert_eq!(error_code(&answer), ErrorCode::MalformedRequest, "{field}");
    }
    let plain = verify(&mut stream, qa_store::CANDIDATE, qa_store::TARGET);
    let after = exchange(
        &mut stream,
        &request("state.read", Some(json!({"paths": []}))),
    );

    assert_eq!(plain.result.unwrap()["verdict"], "ok");
    assert_eq!(before.revision, after.revision);
}

/// In the file-ledger epoch the store is not the authority: the runtime has no verdict to give.
#[test]
fn qa_evidence_verify_of_the_file_ledger_is_not_found() {
    let fixture = Fixture::new("qa-evidence-file-ledger");
    let state_dir = legacy_state(&fixture);
    let (_runtime, mut stream, features) = serving(&fixture, state_dir);

    let answer = verify(&mut stream, qa_store::CANDIDATE, qa_store::TARGET);

    assert!(!features.contains(&json!("qa.evidence.verify")));
    assert_eq!(error_code(&answer), ErrorCode::NotFound);
}

/// Say `hello` on a new connection of `runtime`.
fn greeted(runtime: &Running, fixture: &Fixture) -> Client {
    let mut stream = runtime.connect();
    let greeting = exchange(&mut stream, &hello(&fixture.root, &runtime.token, 1, 1));
    assert_eq!(greeting.status, Status::Ok);
    stream
}

/// Every runtime names `runtime.attach` and `runtime.release` in `hello`, records its owners and
/// answers whether it is owned; a manual runtime never stops by itself (ADR 0031).
#[test]
fn a_manual_runtime_records_attached_owners_and_releases_them() {
    let fixture = Fixture::new("attach");
    let runtime = Running::start(fixture.bind().unwrap());
    let mut stream = runtime.connect();
    let greeting = exchange(&mut stream, &hello(&fixture.root, &runtime.token, 1, 1));
    let features = greeting.result.unwrap()["features"].clone();

    let attached = exchange(
        &mut stream,
        &request(
            "runtime.attach",
            Some(json!({"key": "s/agent-1", "owner_pid": std::process::id()})),
        ),
    );
    let released = exchange(
        &mut stream,
        &request("runtime.release", Some(json!({"key": "s/agent-1"}))),
    );
    let again = exchange(
        &mut stream,
        &request("runtime.release", Some(json!({"key": "s/agent-1"}))),
    );

    assert_eq!(
        features,
        json!(["status", "runtime.attach", "runtime.release"])
    );
    let attached = attached.result.unwrap();
    assert_eq!(attached["owned"], false);
    assert_eq!(attached["attached"], true);
    assert_eq!(attached["owners"], json!(["s/agent-1"]));
    assert_eq!(attached["busy"], json!([]));
    assert_eq!(attached["exiting"], false);
    let released = released.result.unwrap();
    assert_eq!(released["released"], true);
    assert_eq!(released["owners"], json!([]));
    assert_eq!(again.result.unwrap()["released"], false);
}

/// An owner key outside `[A-Za-z0-9._:/-]{1,256}`, an unknown field and a pid that is no
/// positive number are malformed, and the connection stays usable.
#[test]
fn a_malformed_owner_is_refused() {
    let fixture = Fixture::new("attach-malformed");
    let runtime = Running::start(fixture.bind().unwrap());
    let mut stream = greeted(&runtime, &fixture);

    for payload in [
        None,
        Some(json!({"key": ""})),
        Some(json!({"key": "a b"})),
        Some(json!({"key": "k".repeat(257)})),
        Some(json!({"key": "s", "owner_pid": 0})),
        Some(json!({"key": "s", "owner_pid": "1"})),
        Some(json!({"key": "s", "extra": 1})),
    ] {
        let answer = exchange(&mut stream, &request("runtime.attach", payload.clone()));
        assert_eq!(
            error_code(&answer),
            ErrorCode::MalformedRequest,
            "{payload:?}"
        );
    }
    let answer = exchange(
        &mut stream,
        &request("runtime.release", Some(json!({"key": "s", "owner_pid": 1}))),
    );
    assert_eq!(error_code(&answer), ErrorCode::MalformedRequest);
    assert_eq!(
        exchange(&mut stream, &request("status", None)).status,
        Status::Ok
    );
}

/// An owned runtime stops its accept loop and removes its socket once its last owner released
/// and no connection is open; while a connection is open it keeps serving.
#[cfg(unix)]
#[test]
fn an_owned_runtime_stops_after_its_last_owner_released_and_the_last_connection_closed() {
    let fixture = Fixture::new("owned-stop");
    let paths = resolve_paths(&fixture.root, &Environment::with_xdg(&fixture.xdg)).unwrap();
    let lifetime = ipc::Lifetime::owned(ipc::DEFAULT_OWNER_TTL);
    lifetime.attach("s", None, std::time::Instant::now());
    let mut runtime =
        Running::start(Server::bind_with_lifetime(paths.clone(), None, lifetime).unwrap());
    let mut stream = greeted(&runtime, &fixture);

    let released = exchange(
        &mut stream,
        &request("runtime.release", Some(json!({"key": "s"}))),
    );
    assert_eq!(released.result.unwrap()["owned"], true);
    thread::sleep(Duration::from_millis(1500));
    assert!(
        paths.socket.exists(),
        "an open connection keeps the runtime"
    );
    drop(stream);

    let thread = runtime.thread.take().unwrap();
    let deadline = std::time::Instant::now() + Duration::from_secs(10);
    while !thread.is_finished() && std::time::Instant::now() < deadline {
        thread::sleep(Duration::from_millis(50));
    }
    assert!(thread.is_finished(), "the owned runtime did not stop");
    thread.join().unwrap();
    assert!(!paths.socket.exists());
}

/// An owned runtime keeps serving while the store holds a QA lease.
#[cfg(unix)]
#[test]
fn an_owned_runtime_keeps_serving_while_the_store_is_busy() {
    let fixture = Fixture::new("owned-busy");
    let state_dir = cut_over(&fixture);
    let paths = resolve_paths(&fixture.root, &Environment::with_xdg(&fixture.xdg)).unwrap();
    let busy_before = state::idle::busy(&state_dir);
    let runtime = Running::start(
        Server::bind_with_lifetime(
            paths.clone(),
            Some(state_dir.clone()),
            ipc::Lifetime::owned(ipc::DEFAULT_OWNER_TTL),
        )
        .unwrap(),
    );
    let mut stream = greeted(&runtime, &fixture);
    let acquired = exchange(
        &mut stream,
        &request(
            "state.write",
            Some(json!({"mutations": [{
                "op": "lease_acquire", "path": "qa-lane/lease.json",
                "lease": {"owner_kind": "dispatch", "owner_id": "d1", "ttl_seconds": 60},
            }]})),
        ),
    );
    assert_eq!(acquired.status, Status::Ok, "{acquired:?}");
    let attached = exchange(
        &mut stream,
        &request("runtime.attach", Some(json!({"key": "s"}))),
    );
    let released = exchange(
        &mut stream,
        &request("runtime.release", Some(json!({"key": "s"}))),
    );
    drop(stream);
    thread::sleep(Duration::from_millis(2500));

    assert!(
        attached.result.unwrap()["busy"]
            .as_array()
            .unwrap()
            .contains(&json!("the QA lease is held by dispatch d1")),
        "{busy_before:?}"
    );
    assert_eq!(released.result.unwrap()["released"], true);
    assert!(paths.socket.exists(), "a held lease keeps the runtime");
    assert!(!runtime.thread.as_ref().unwrap().is_finished());
}
