//! `harness-runtime init --repo <repo> --approved-by <human> --approved-at <time> --reason <text>`
//! (ADR 0036): the runtime store of a repository that has no orchestration state yet, in one
//! operation with a human approval.
//!
//! 1. The approval (`approval::check`), then the precondition: no `ledger.json` and no record of
//!    the file ledger. A file ledger goes through `migrate` instead.
//! 2. The legacy lock, which the Python coordinator of a file ledger takes too.
//! 3. An empty store in `state/runtime.db.importing`: the store metadata and the anchor of the
//!    audit chain, a `legacy-import` record of an empty manifest with the approval. The anchor has
//!    the form `migrate` writes, so the verification of the chain and the rollback do not change.
//! 4. The commit point of `migrate`: `runtime.db`, `AUTHORITY.json`, then `ledger.json` with
//!    `version: 4`.
//!
//! Until the pointer is written, a repeat starts again; after it, a repeat answers
//! `already_initialized`.

use std::fs;
use std::path::{Path, PathBuf};

use contracts::ErrorCode;
use rusqlite::params;
use serde_json::json;

use crate::approval::{self, Approval};
use crate::audit;
use crate::authority::{Authority, Epoch, IMPORTING_NAME, epoch};
use crate::error::{Error, Result};
use crate::hooks;
use crate::import::manifest_of;
use crate::legacy::{RECORD_DIRECTORIES, read_pointer};
use crate::lock::{self, LegacyLock};
use crate::migrate::{STATE_REL, commit, refuse_a_rolled_back_store, remove_store_leftovers};
use crate::platform;
use crate::schema;
use crate::time::iso_now;

const MIGRATE_REMEDY: &str = "run 'harness-runtime migrate --repo <repo> --approved-by <human> \
    --approved-at <RFC 3339> --reason <text>' to move the file ledger to the runtime store";

/// What a successful `init` reports.
#[derive(Debug, PartialEq, Eq)]
pub struct Outcome {
    /// The runtime store was already the authority: nothing was changed.
    pub already_initialized: bool,
    pub authority: Authority,
}

impl Outcome {
    /// The single JSON line `harness-runtime init` prints.
    pub fn to_json(&self) -> serde_json::Value {
        json!({
            "initialized": !self.already_initialized,
            "already_initialized": self.already_initialized,
            "store_id": self.authority.store_id,
            "manifest_sha256": self.authority.manifest_sha256,
            "cutover_at": self.authority.cutover_at,
        })
    }
}

/// Step 1: the state directory holds nothing of the file ledger.
fn preconditions(state: &Path) -> Result<()> {
    if let Some(pointer) = read_pointer(state)? {
        return Err(Error::refused(
            ErrorCode::ProtocolUnsupported,
            format!(
                "the state directory holds a file ledger of version {}",
                pointer.version
            ),
            MIGRATE_REMEDY,
        ));
    }
    if RECORD_DIRECTORIES
        .iter()
        .any(|directory| state.join(directory).exists())
    {
        return Err(Error::refused(
            ErrorCode::ProtocolUnsupported,
            "the state directory holds records of the file ledger",
            MIGRATE_REMEDY,
        ));
    }
    Ok(())
}

/// Step 3: the empty store, sealed and closed.
fn create(path: &Path, generation: &str, at: &str, approval: &Approval) -> Result<Authority> {
    let store_id = platform::random_hex()?;
    let (_, manifest_sha256) = manifest_of(&[]);
    let mut connection = schema::create(path)?;
    {
        let transaction = connection.transaction()?;
        for (key, value) in [
            ("store_id", store_id.as_str()),
            ("selected_generation", generation),
            ("manifest_sha256", manifest_sha256.as_str()),
        ] {
            transaction.execute(
                "INSERT INTO store_meta (key, value) VALUES (?1, ?2)",
                params![key, value],
            )?;
        }
        audit::append(
            &transaction,
            at,
            "legacy-import",
            &json!({
                "generation": generation,
                "manifest_sha256": manifest_sha256,
                "files": 0,
                "approved_by": approval.approved_by,
                "approved_at": approval.approved_at,
                "reason": approval.reason,
            }),
        )?;
        hooks::reach("init")?;
        transaction.commit()?;
    }
    schema::seal(connection)?;
    Ok(Authority {
        store_id,
        manifest_sha256,
        snapshot: String::new(),
        cutover_at: iso_now(),
        approval: approval.clone(),
    })
}

/// Steps 1 to 4, under the lock. What an attempt leaves of the store goes with it, unless the
/// pointer was replaced.
fn locked(state: &Path, approval: &Approval) -> Result<Authority> {
    preconditions(state)?;
    refuse_a_rolled_back_store(state)?;
    remove_store_leftovers(state)?;
    let generation = format!("generation-{}", &platform::random_hex()?[..8]);
    let outcome = create(
        &state.join(IMPORTING_NAME),
        &generation,
        &iso_now(),
        approval,
    )
    .and_then(|authority| commit(state, &generation, &authority).map(|()| authority));
    if outcome.is_err() && matches!(epoch(state), Epoch::FileLedger) {
        let _ = remove_store_leftovers(state);
    }
    outcome
}

/// Create the runtime store of the repository at `repo` with the human `approval`.
///
/// # Errors
/// `Error::Refused` (exit code 2): the approval or the precondition refused it, nothing was
/// changed. `Error::Interrupted` (3): the operation failed after it began; the partial store was
/// removed. `Error::Invariant` (4): the state directory is cut over but inconsistent.
pub fn run(repo: &Path, approval: &Approval) -> Result<Outcome> {
    approval::check(approval, "initialization")?;
    let state: PathBuf = repo.join(STATE_REL);
    match epoch(&state) {
        Epoch::Store(authority) => {
            return Ok(Outcome {
                already_initialized: true,
                authority,
            });
        }
        Epoch::Inconsistent(reason) => {
            return Err(Error::invariant(format!(
                "the state directory is cut over but inconsistent: {reason}"
            )));
        }
        Epoch::FileLedger => {}
    }
    preconditions(&state)?;
    hooks::reach("preconditions")?;
    fs::create_dir_all(&state)?;
    let held: LegacyLock = lock::acquire(&state, lock::INIT_OPERATION)?;
    let outcome = hooks::reach("locked").and_then(|()| locked(&state, approval));
    // A lock that cannot be removed after the commit point is no failure: the next command
    // removes it when its owner is dead.
    let _ = held.release();
    Ok(Outcome {
        already_initialized: false,
        authority: outcome?,
    })
}
