//! Whether the store still needs its runtime: a live dispatch, a held QA lease, a queued QA run
//! and an unfinished execution keep it busy; a store that cannot be read is busy; a state
//! directory whose authority is not the runtime store is idle (ADR 0031, section 3).

mod common;

use rusqlite::Connection;
use serde_json::json;
use state::idle::{busy, busy_in};
use state::schema::create;

use common::Repo;

fn tempdir(name: &str) -> std::path::PathBuf {
    use std::sync::atomic::{AtomicUsize, Ordering};
    static NEXT: AtomicUsize = AtomicUsize::new(0);
    let n = NEXT.fetch_add(1, Ordering::Relaxed);
    let path = std::env::temp_dir().join(format!("hr-idle-{name}-{}-{n}", std::process::id()));
    let _ = std::fs::remove_dir_all(&path);
    std::fs::create_dir_all(&path).unwrap();
    path
}

/// A store of the current schema with one batch and one dispatch in `state`.
fn store(name: &str, state: &str) -> Connection {
    let connection = create(&tempdir(name).join("runtime.db")).unwrap();
    connection
        .execute_batch(&format!(
            "INSERT INTO batch (id, state, body_json) VALUES ('b', 'active', '{{}}');
             INSERT INTO dispatch (id, batch_id, state, body_json) VALUES ('d', 'b', '{state}', '{{}}');
             INSERT INTO dispatch_status (id, state, body_json) VALUES ('d', '{state}', '{{}}');"
        ))
        .unwrap();
    connection
}

#[test]
fn a_store_without_live_work_is_idle() {
    let connection = store("idle", "completed");

    assert_eq!(busy_in(&connection).unwrap(), Vec::<String>::new());
}

#[test]
fn a_dispatched_or_working_dispatch_keeps_the_store_busy() {
    for state in ["dispatched", "working"] {
        let connection = store(state, state);

        assert_eq!(
            busy_in(&connection).unwrap(),
            vec![format!("the dispatch d is {state}")]
        );
    }
}

#[test]
fn a_held_qa_lease_keeps_the_store_busy() {
    let connection = store("lease", "completed");
    connection
        .execute(
            "INSERT INTO qa_lane (id, body_json, owner_kind, owner_id, acquired_at, expires_at,
                                  heartbeat_at)
             VALUES (1, '{}', 'dispatch', 'd', 't', 't', 't')",
            [],
        )
        .unwrap();

    assert_eq!(
        busy_in(&connection).unwrap(),
        vec!["the QA lease is held by dispatch d".to_owned()]
    );
}

#[test]
fn a_released_qa_lane_is_idle() {
    let connection = store("released", "completed");
    connection
        .execute("INSERT INTO qa_lane (id, body_json) VALUES (1, '{}')", [])
        .unwrap();

    assert!(busy_in(&connection).unwrap().is_empty());
}

#[test]
fn a_queued_qa_run_keeps_the_store_busy() {
    let connection = store("queue", "completed");
    connection
        .execute(
            "INSERT INTO qa_queue (id, body_json) VALUES ('q1', '{}')",
            [],
        )
        .unwrap();

    assert_eq!(
        busy_in(&connection).unwrap(),
        vec!["the QA queue holds q1".to_owned()]
    );
}

/// Insert the launch intent `id` of the dispatch `d`: an execution in the state `launching`.
fn launching(connection: &Connection, id: &str, attempt: i64) {
    state::executions::insert(
        connection,
        &state::executions::NewExecution {
            id,
            dispatch_id: "d",
            attempt,
            kind: state::executions::KIND_PROCESS,
            engine: None,
            launch: &json!({"argv": ["sh"], "cwd": "/"}),
            execution_deadline: "2026-10-01T04:00:00+00:00",
            stop_grace_seconds: 30,
            poll_interval_seconds: 1,
            lease_owner: &json!({"pid": 7}),
        },
        "2026-10-01T00:00:00+00:00",
    )
    .unwrap();
}

#[test]
fn an_unfinished_execution_keeps_the_store_busy_and_a_terminal_one_does_not() {
    let connection = store("execution", "completed");
    state::audit::append(
        &connection,
        "2026-10-01T00:00:00+00:00",
        "legacy-import",
        &json!({}),
    )
    .unwrap();
    launching(&connection, "run", 1);
    launching(&connection, "gone", 2);
    connection
        .execute("UPDATE executions SET state = 'lost' WHERE id = 'gone'", [])
        .unwrap();

    assert_eq!(
        busy_in(&connection).unwrap(),
        vec!["the execution run is launching".to_owned()]
    );
}

#[test]
fn a_state_directory_of_the_file_ledger_is_idle() {
    let repo = Repo::new("file-ledger");

    assert!(busy(&repo.state()).is_empty());
}

#[test]
fn a_cut_over_store_is_judged_by_its_records() {
    let repo = Repo::new("cut-over");
    state::migrate::run(&repo.root, &common::approval()).unwrap();
    let connection = Connection::open(repo.state().join("runtime.db")).unwrap();

    assert_eq!(busy(&repo.state()), busy_in(&connection).unwrap());
}

#[test]
fn a_store_that_cannot_be_read_is_busy() {
    let repo = Repo::new("unreadable");
    state::migrate::run(&repo.root, &common::approval()).unwrap();
    Connection::open(repo.state().join("runtime.db"))
        .unwrap()
        .execute_batch("DROP TABLE qa_queue")
        .unwrap();

    let reasons = busy(&repo.state());

    assert_eq!(reasons.len(), 1, "{reasons:?}");
    assert!(reasons[0].starts_with("the runtime store cannot be read"));
}
