//! `init` on a repository without orchestration state (ADR 0036): the store of a new project.

mod common;

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

use serde_json::Value;
use state::authority::{Epoch, epoch};
use state::error::Error;
use state::init::run;
use state::validate::validate;

use common::Repo;

/// A repository root with an empty state directory, or none at all.
struct Empty {
    root: PathBuf,
}

impl Empty {
    fn new(name: &str) -> Self {
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let n = NEXT.fetch_add(1, Ordering::Relaxed);
        let root = std::env::temp_dir().join(format!("hr-init-{name}-{}-{n}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&root).unwrap();
        Self { root }
    }

    fn state(&self) -> PathBuf {
        self.root.join(".harness/orchestration/state")
    }
}

impl Drop for Empty {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}

fn read_json(path: &Path) -> Value {
    serde_json::from_slice(&fs::read(path).unwrap()).unwrap()
}

fn code(result: &Result<state::init::Outcome, Error>) -> u8 {
    result.as_ref().map_or_else(Error::exit_code, |_| 0)
}

fn names(dir: &Path) -> Vec<String> {
    let mut found: Vec<String> = fs::read_dir(dir)
        .map(|entries| {
            entries
                .map(|entry| entry.unwrap().file_name().to_string_lossy().into_owned())
                .collect()
        })
        .unwrap_or_default();
    found.sort();
    found
}

#[test]
fn init_creates_a_store_on_a_repository_without_state() {
    let repo = Empty::new("fresh");

    let outcome = run(&repo.root, &common::approval()).unwrap();

    assert!(!outcome.already_initialized);
    let state = repo.state();
    let pointer = read_json(&state.join("ledger.json"));
    assert_eq!(pointer["version"], 4);
    assert!(
        pointer["generation"]
            .as_str()
            .unwrap()
            .starts_with("generation-")
    );
    assert_eq!(pointer.as_object().unwrap().len(), 3);
    let authority = read_json(&state.join("AUTHORITY.json"));
    assert_eq!(authority["authority"], "runtime-store");
    assert_eq!(authority["store_id"], outcome.authority.store_id.as_str());
    assert_eq!(authority["approved_by"], "human:operator");
    assert!(matches!(epoch(&state), Epoch::Store(_)));
    // Reading the store in WAL mode adds its -wal and -shm files; nothing else is left behind.
    let left: Vec<String> = names(&state)
        .into_iter()
        .filter(|name| !name.ends_with("-wal") && !name.ends_with("-shm"))
        .collect();
    assert_eq!(left, ["AUTHORITY.json", "ledger.json", "runtime.db"]);
}

#[test]
fn an_initialized_store_passes_the_full_validation() {
    let repo = Empty::new("validate");
    run(&repo.root, &common::approval()).unwrap();

    let result = validate(&repo.state(), true).unwrap();

    assert_eq!(result["valid"], true, "{result}");
    assert_eq!(result["mode"], "full");
}

#[test]
fn init_on_an_empty_state_directory_creates_the_store() {
    let repo = Empty::new("empty-dir");
    fs::create_dir_all(repo.state()).unwrap();

    run(&repo.root, &common::approval()).unwrap();

    assert!(matches!(epoch(&repo.state()), Epoch::Store(_)));
}

#[test]
fn init_of_a_policy_approver_is_denied_and_changes_nothing() {
    let repo = Empty::new("policy");
    let mut approval = common::approval();
    approval.approved_by = "policy:auto".to_owned();

    let result = run(&repo.root, &approval);

    assert_eq!(code(&result), 2);
    assert_eq!(
        result.unwrap_err().code(),
        contracts::ErrorCode::PolicyDenied
    );
    assert!(!repo.state().exists());
}

#[test]
fn init_without_an_approval_changes_nothing() {
    let repo = Empty::new("no-approval");
    let mut approval = common::approval();
    approval.reason = String::new();

    let result = run(&repo.root, &approval);

    assert_eq!(code(&result), 2);
    assert!(!repo.state().exists());
}

#[test]
fn init_on_a_file_ledger_is_refused_with_the_migrate_remedy() {
    let repo = Repo::new("file-ledger");
    let before = repo.tree();

    let result = run(&repo.root, &common::approval());

    assert_eq!(code(&result), 2, "{result:?}");
    let error = result.unwrap_err();
    assert!(
        error.remedy().contains("harness-runtime migrate"),
        "{error:?}"
    );
    assert_eq!(repo.tree(), before);
}

#[test]
fn init_on_records_without_a_ledger_is_refused() {
    let repo = Empty::new("records");
    fs::create_dir_all(repo.state().join("batches")).unwrap();

    let result = run(&repo.root, &common::approval());

    assert_eq!(code(&result), 2, "{result:?}");
    assert!(!repo.state().join("ledger.json").exists());
    assert!(!repo.state().join("runtime.db").exists());
}

#[test]
fn a_repeat_after_init_reports_already_initialized_and_changes_nothing() {
    let repo = Empty::new("repeat");
    let first = run(&repo.root, &common::approval()).unwrap();
    let pointer = fs::read(repo.state().join("ledger.json")).unwrap();
    let authority = fs::read(repo.state().join("AUTHORITY.json")).unwrap();

    let second = run(&repo.root, &common::approval()).unwrap();

    assert!(second.already_initialized);
    assert_eq!(second.authority.store_id, first.authority.store_id);
    assert_eq!(fs::read(repo.state().join("ledger.json")).unwrap(), pointer);
    assert_eq!(
        fs::read(repo.state().join("AUTHORITY.json")).unwrap(),
        authority
    );
}

#[test]
fn what_an_interrupted_init_left_is_removed() {
    let repo = Empty::new("leftovers");
    let state = repo.state();
    fs::create_dir_all(&state).unwrap();
    fs::write(state.join("runtime.db.importing"), b"half").unwrap();
    fs::write(state.join("runtime.db"), b"renamed but never committed").unwrap();
    fs::write(state.join("AUTHORITY.json"), b"{}").unwrap();

    run(&repo.root, &common::approval()).unwrap();

    assert!(!state.join("runtime.db.importing").exists());
    assert!(matches!(epoch(&state), Epoch::Store(_)));
}

#[test]
fn a_store_kept_after_a_rollback_is_not_deleted() {
    let repo = Empty::new("rolled-back");
    let state = repo.state();
    fs::create_dir_all(&state).unwrap();
    fs::write(state.join("runtime.db"), b"kept for analysis").unwrap();
    fs::write(
        state.join("AUTHORITY.json"),
        "{\"authority\": \"file-ledger\"}\n",
    )
    .unwrap();

    let result = run(&repo.root, &common::approval());

    assert_eq!(code(&result), 2, "{result:?}");
    assert_eq!(
        fs::read(state.join("runtime.db")).unwrap(),
        b"kept for analysis"
    );
}

#[test]
fn a_rollback_after_init_exports_an_empty_generation() {
    let repo = Empty::new("rollback");
    run(&repo.root, &common::approval()).unwrap();
    let approval = state::rollback::Approval {
        approved_by: "human:operator".to_owned(),
        approved_at: "2026-10-27T09:00:00+00:00".to_owned(),
        reason: "back to the file ledger".to_owned(),
    };

    let outcome = state::rollback::run(&repo.root, &approval);

    assert!(outcome.is_ok(), "{outcome:?}");
    let pointer = read_json(&repo.state().join("ledger.json"));
    assert_eq!(pointer["version"], 3);
    assert!(matches!(epoch(&repo.state()), Epoch::FileLedger));
}
