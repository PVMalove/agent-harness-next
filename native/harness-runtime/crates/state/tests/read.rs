//! The read operation of the cut-over store: the records come back as the legacy files had them.

mod common;

use std::fs;

use serde_json::{Value, json};
use state::migrate::run;
use state::read::{ReadError, read, store_id};

use common::Repo;

fn migrated(name: &str) -> (Repo, state::migrate::Outcome) {
    let repo = Repo::new(name);
    let outcome = run(&repo.root, &common::approval()).unwrap();
    (repo, outcome)
}

fn legacy_record(repo: &Repo, outcome: &state::migrate::Outcome, path: &str) -> Value {
    let copy = repo.root.join(&outcome.authority.snapshot).join("state");
    let generation = state::legacy::read_pointer(&copy)
        .unwrap()
        .unwrap()
        .generation;
    let bytes = fs::read(copy.join("generations").join(generation).join(path)).unwrap();
    serde_json::from_slice(&bytes).unwrap()
}

#[test]
fn a_collection_answers_every_record_of_its_directory_as_the_legacy_file_had_it() {
    let (repo, outcome) = migrated("collection");

    let answer = read(
        &repo.state(),
        Some(&json!({"collections": ["batches", "dispatches", "dispatch-status", "checkpoints", "qa-lane", "reports"]})),
        None,
    )
    .unwrap();

    let mut paths: Vec<&String> = answer.records.keys().collect();
    paths.sort();
    assert_eq!(
        paths,
        [
            "batches/batch-aaaaaaaa-0000-4000-8000-000000000001.json",
            "checkpoints/checkpoint-0001.json",
            "dispatch-status/dispatch-11111111-0000-4000-8000-000000000001.json",
            "dispatch-status/dispatch-22222222-0000-4000-8000-000000000002.json",
            "dispatches/dispatch-11111111-0000-4000-8000-000000000001.json",
            "dispatches/dispatch-22222222-0000-4000-8000-000000000002.json",
            "qa-lane/recoveries/r1.json",
            "qa-lane/sequence.json",
            "reports/dispatch-11111111-0000-4000-8000-000000000001.json",
            "reports/integration/int-1.json",
        ]
    );
    for (path, record) in &answer.records {
        assert_eq!(record, &legacy_record(&repo, &outcome, path), "{path}");
    }
}

#[test]
fn the_audit_collection_answers_the_legacy_audit_records_of_the_selected_generation() {
    let (repo, outcome) = migrated("audit");

    let answer = read(
        &repo.state(),
        Some(&json!({"collections": ["audit"]})),
        None,
    )
    .unwrap();

    // The 17 legacy records, then the audit chain of the store: the record of the import.
    assert_eq!(answer.records.len(), 18);
    let chain = "audit/audit-chain-000000000001.json";
    for (path, record) in &answer.records {
        assert!(path.starts_with("audit/audit-"), "{path}");
        if path != chain {
            assert_eq!(record, &legacy_record(&repo, &outcome, path), "{path}");
        }
    }
    assert_eq!(answer.records[chain]["action"], "legacy-import");
}

#[test]
fn a_named_path_answers_its_record_and_a_missing_path_is_left_out() {
    let (repo, outcome) = migrated("paths");
    let present = "plans/batch-aaaaaaaa-0000-4000-8000-000000000001.json";

    let answer = read(
        &repo.state(),
        Some(&json!({"paths": [present, "plans/nobody.json", "qa-lane/lease.json", "reports/integration/int-1.json"]})),
        None,
    )
    .unwrap();

    let mut paths: Vec<&String> = answer.records.keys().collect();
    paths.sort();
    assert_eq!(paths, [present, "reports/integration/int-1.json"]);
    assert_eq!(
        answer.records[present],
        legacy_record(&repo, &outcome, present)
    );
}

#[test]
fn the_numbers_of_a_record_keep_the_text_they_had() {
    let (repo, _) = migrated("numbers");

    let answer = read(
        &repo.state(),
        Some(&json!({"paths": ["dispatches/dispatch-11111111-0000-4000-8000-000000000001.json"]})),
        None,
    )
    .unwrap();

    let text = serde_json::to_string(&answer.records).unwrap();
    assert!(text.contains("1e-05"), "{text}");
    assert!(text.contains("1180591620717411303424"), "{text}");
}

#[test]
fn the_revision_is_the_last_audit_sequence_and_a_stale_expectation_conflicts() {
    let (repo, _) = migrated("revision");

    let answer = read(&repo.state(), None, None).unwrap();
    let stale = read(&repo.state(), None, Some(answer.revision + 1));

    assert_eq!(answer.revision, 1);
    assert!(answer.records.is_empty());
    assert_eq!(
        stale.unwrap_err(),
        ReadError::RevisionConflict {
            expected: 2,
            actual: 1
        }
    );
    assert!(read(&repo.state(), None, Some(1)).is_ok());
}

#[test]
fn a_request_the_protocol_does_not_define_is_refused() {
    let (repo, _) = migrated("malformed");

    for payload in [
        json!({"surprise": 1}),
        json!({"paths": "batches/x.json"}),
        json!({"paths": [1]}),
        json!({"paths": ["../ledger.json"]}),
        json!({"paths": ["/etc/passwd"]}),
        json!({"paths": ["a//b.json"]}),
        json!(["batches"]),
    ] {
        let result = read(&repo.state(), Some(&payload), None);
        assert!(
            matches!(result, Err(ReadError::Malformed(_))),
            "{payload}: {result:?}"
        );
    }
}

#[test]
fn before_the_cutover_there_is_no_store_to_read() {
    let repo = Repo::new("before");

    let result = read(
        &repo.state(),
        Some(&json!({"collections": ["batches"]})),
        None,
    );

    assert!(
        matches!(result, Err(ReadError::NotAttached(_))),
        "{result:?}"
    );
    assert_eq!(store_id(&repo.state()), None);
}

#[test]
fn the_store_id_of_a_cut_over_state_is_the_one_migrate_reported() {
    let (repo, outcome) = migrated("store-id");

    assert_eq!(store_id(&repo.state()), Some(outcome.authority.store_id));
}

mod filter {
    //! The store-side filter of a read: a command that names a batch or a dispatch reads only the
    //! records the filter selects, and never the records of another batch (ADR 0020, section 3).

    use rusqlite::Connection;
    use serde_json::json;
    use state::read::{Answer, ReadError, read};

    use super::migrated;

    const BATCH: &str = "batch-aaaaaaaa-0000-4000-8000-000000000001";
    const FIRST: &str = "dispatch-11111111-0000-4000-8000-000000000001";
    const SECOND: &str = "dispatch-22222222-0000-4000-8000-000000000002";

    fn paths(answer: &Answer) -> Vec<String> {
        let mut paths: Vec<String> = answer.records.keys().cloned().collect();
        paths.sort();
        paths
    }

    /// A second batch with one dispatch and its status, written as another command's commit would.
    fn add_second_batch(state: &std::path::Path) {
        let connection = Connection::open(state.join("runtime.db")).unwrap();
        connection
            .execute_batch(
                "INSERT INTO batch (id, state, body_json)
                 VALUES ('batch-b', 'active', '{\"batch_id\":\"batch-b\",\"state\":\"active\"}');
                 INSERT INTO dispatch (id, batch_id, state, body_json)
                 VALUES ('dispatch-b', 'batch-b', 'working',
                         '{\"dispatch_id\":\"dispatch-b\",\"batch_id\":\"batch-b\",\"state\":\"working\"}');
                 INSERT INTO dispatch_status (id, state, body_json)
                 VALUES ('dispatch-b', 'working', '{\"dispatch_id\":\"dispatch-b\",\"state\":\"working\"}');",
            )
            .unwrap();
    }

    #[test]
    fn a_filter_by_batch_answers_only_the_records_of_that_batch() {
        let (repo, _) = migrated("filter-batch");
        let state = repo.state();
        add_second_batch(&state);

        let answer = read(
            &state,
            Some(&json!({
                "collections": ["batches", "dispatches", "dispatch-status"],
                "filter": {"batch_id": BATCH},
            })),
            None,
        )
        .unwrap();

        assert_eq!(
            paths(&answer),
            [
                format!("batches/{BATCH}.json"),
                format!("dispatch-status/{FIRST}.json"),
                format!("dispatch-status/{SECOND}.json"),
                format!("dispatches/{FIRST}.json"),
                format!("dispatches/{SECOND}.json"),
            ]
        );
    }

    #[test]
    fn a_filter_by_dispatch_answers_its_batch_its_dispatch_and_its_status_only() {
        let (repo, _) = migrated("filter-dispatch");
        let state = repo.state();
        add_second_batch(&state);

        let answer = read(
            &state,
            Some(&json!({
                "collections": ["batches", "dispatches", "dispatch-status"],
                "filter": {"dispatch_id": FIRST},
            })),
            None,
        )
        .unwrap();

        assert_eq!(
            paths(&answer),
            [
                format!("batches/{BATCH}.json"),
                format!("dispatch-status/{FIRST}.json"),
                format!("dispatches/{FIRST}.json"),
            ]
        );
    }

    #[test]
    fn a_filter_by_dispatch_of_another_batch_reads_that_batch() {
        let (repo, _) = migrated("filter-other-batch");
        let state = repo.state();
        add_second_batch(&state);

        let answer = read(
            &state,
            Some(&json!({
                "collections": ["batches", "dispatches", "dispatch-status"],
                "filter": {"dispatch_id": "dispatch-b"},
            })),
            None,
        )
        .unwrap();

        assert_eq!(
            paths(&answer),
            [
                "batches/batch-b.json".to_owned(),
                "dispatch-status/dispatch-b.json".to_owned(),
                "dispatches/dispatch-b.json".to_owned(),
            ]
        );
    }

    #[test]
    fn a_batch_and_a_dispatch_of_the_filter_are_anded() {
        let (repo, _) = migrated("filter-and");
        let state = repo.state();
        add_second_batch(&state);

        let answer = read(
            &state,
            Some(&json!({
                "collections": ["batches", "dispatches", "dispatch-status"],
                "filter": {"batch_id": BATCH, "dispatch_id": SECOND},
            })),
            None,
        )
        .unwrap();

        assert_eq!(
            paths(&answer),
            [
                format!("batches/{BATCH}.json"),
                format!("dispatch-status/{SECOND}.json"),
                format!("dispatches/{SECOND}.json"),
            ]
        );
        let excluded = read(
            &state,
            Some(&json!({
                "collections": ["dispatch-status"],
                "filter": {"batch_id": "batch-b", "dispatch_id": SECOND},
            })),
            None,
        )
        .unwrap();
        assert!(excluded.records.is_empty());
    }

    #[test]
    fn a_filter_that_names_no_record_answers_an_empty_collection() {
        let (repo, _) = migrated("filter-missing");

        let answer = read(
            &repo.state(),
            Some(&json!({
                "collections": ["batches", "dispatches", "dispatch-status"],
                "filter": {"batch_id": "batch-nobody"},
            })),
            None,
        )
        .unwrap();

        assert!(answer.records.is_empty());
    }

    #[test]
    fn a_filter_the_protocol_does_not_define_is_refused() {
        let (repo, _) = migrated("filter-malformed");
        for payload in [
            json!({"collections": ["batches"], "paths": ["batches/x.json"],
                   "filter": {"batch_id": BATCH}}),
            json!({"collections": ["reports"], "filter": {"batch_id": BATCH}}),
            json!({"collections": [], "filter": {"batch_id": BATCH}}),
            json!({"collections": ["batches"], "filter": {}}),
            json!({"collections": ["batches"], "filter": {"batch_id": ""}}),
            json!({"collections": ["batches"], "filter": {"batch_id": 1}}),
            json!({"collections": ["batches"], "filter": {"surprise": BATCH}}),
            json!({"collections": ["batches"], "filter": "batch"}),
        ] {
            let result = read(&repo.state(), Some(&payload), None);
            assert!(
                matches!(result, Err(ReadError::Malformed(_))),
                "{payload}: {result:?}"
            );
        }
    }
}

mod snapshots {
    //! Read snapshots that span the requests of one command (ADR 0020, section 3).

    use std::time::{Duration, Instant};

    use rusqlite::Connection;
    use serde_json::{Value, json};
    use state::read::ReadError;
    use state::read_session::Registry;

    use super::migrated;

    const BATCH: &str = "batches/batch-aaaaaaaa-0000-4000-8000-000000000001.json";

    fn ticket(answer: &state::read::Answer) -> Value {
        answer.records[BATCH]["ticket"].clone()
    }

    fn open(registry: &Registry, state: &std::path::Path) -> state::read::Answer {
        registry
            .read(
                state,
                Some(&json!({"snapshot": "open", "paths": [BATCH]})),
                None,
            )
            .unwrap()
    }

    fn named(
        registry: &Registry,
        state: &std::path::Path,
        id: &str,
    ) -> Result<state::read::Answer, ReadError> {
        registry.read(
            state,
            Some(&json!({"snapshot": id, "paths": [BATCH]})),
            None,
        )
    }

    /// Change the ticket of the batch outside any snapshot, as another command's commit does.
    fn commit_elsewhere(state: &std::path::Path) {
        let connection = Connection::open(state.join("runtime.db")).unwrap();
        connection
            .execute(
                "UPDATE batch SET body_json = json_set(body_json, '$.ticket', '#changed')",
                [],
            )
            .unwrap();
    }

    #[test]
    fn a_snapshot_keeps_its_answer_across_a_commit_of_another_command() {
        let (repo, _) = migrated("snapshot-commit");
        let state = repo.state();
        let registry = Registry::default();
        let first = open(&registry, &state);
        let id = first.snapshot.clone().unwrap();

        commit_elsewhere(&state);

        let again = named(&registry, &state, &id).unwrap();
        assert_eq!(ticket(&again), ticket(&first));
        assert_eq!(again.revision, first.revision);
        assert_eq!(again.generation_revision, first.generation_revision);
        let fresh = state::read::read(&state, Some(&json!({"paths": [BATCH]})), None).unwrap();
        assert_eq!(ticket(&fresh), "#changed");
    }

    #[test]
    fn a_writer_inside_its_transaction_does_not_delay_a_snapshot_read() {
        let (repo, _) = migrated("snapshot-writer");
        let state = repo.state();
        let registry = Registry::default();
        let before = state::read::read(&state, Some(&json!({"paths": [BATCH]})), None).unwrap();
        let writer = Connection::open(state.join("runtime.db")).unwrap();
        writer.execute_batch("BEGIN IMMEDIATE").unwrap();
        writer
            .execute(
                "UPDATE batch SET body_json = json_set(body_json, '$.ticket', '#half')",
                [],
            )
            .unwrap();

        let started = Instant::now();
        let opened = open(&registry, &state);
        let again = named(&registry, &state, opened.snapshot.as_deref().unwrap()).unwrap();

        assert!(started.elapsed() < Duration::from_secs(2));
        assert_eq!(ticket(&opened), ticket(&before));
        assert_eq!(ticket(&again), ticket(&before));
        writer.execute_batch("ROLLBACK").unwrap();
    }

    fn reason(error: &ReadError) -> &'static str {
        match error {
            ReadError::Snapshot { reason, .. } => reason,
            other => panic!("not a snapshot refusal: {other:?}"),
        }
    }

    #[test]
    fn an_idle_or_old_or_closed_snapshot_is_expired() {
        let (repo, _) = migrated("snapshot-expiry");
        let state = repo.state();
        // A zero idle time or lifetime is outlived by the next request: no test waits for it.
        for registry in [
            Registry::with_limits(Duration::ZERO, Duration::from_secs(60), 8),
            Registry::with_limits(Duration::from_secs(60), Duration::ZERO, 8),
        ] {
            let id = open(&registry, &state).snapshot.unwrap();

            let error = named(&registry, &state, &id).unwrap_err();

            assert_eq!(reason(&error), "snapshot_expired");
            assert!(registry.is_empty());
        }
        let registry = Registry::default();
        let id = open(&registry, &state).snapshot.unwrap();
        registry
            .read(&state, Some(&json!({"snapshot": id, "close": true})), None)
            .unwrap();
        assert_eq!(
            reason(&named(&registry, &state, &id).unwrap_err()),
            "snapshot_expired"
        );
    }

    #[test]
    fn no_more_snapshots_than_the_limit_are_open() {
        let (repo, _) = migrated("snapshot-limit");
        let state = repo.state();
        let registry = Registry::with_limits(Duration::from_secs(60), Duration::from_secs(60), 2);
        let first = open(&registry, &state).snapshot.unwrap();
        open(&registry, &state);

        let error = registry
            .read(&state, Some(&json!({"snapshot": "open"})), None)
            .unwrap_err();

        assert_eq!(reason(&error), "snapshot_limit");
        registry
            .read(
                &state,
                Some(&json!({"snapshot": first, "close": true})),
                None,
            )
            .unwrap();
        open(&registry, &state);
        assert_eq!(registry.len(), 2);
    }

    #[test]
    fn a_read_without_a_snapshot_keeps_the_global_revision_check() {
        let (repo, _) = migrated("snapshot-compat");
        let state = repo.state();
        let registry = Registry::default();
        let answer = registry
            .read(&state, Some(&json!({"paths": [BATCH]})), None)
            .unwrap();
        assert!(answer.snapshot.is_none());

        let error = registry
            .read(
                &state,
                Some(&json!({"paths": [BATCH]})),
                Some(answer.revision + 1),
            )
            .unwrap_err();

        assert!(matches!(error, ReadError::RevisionConflict { .. }));
    }
}
