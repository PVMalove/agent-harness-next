//! Compatibility with stores imported before human approval became mandatory (#970).

use crate::approval::{self, Approval};
use crate::authority::{self, Epoch, STORE_NAME};
use crate::canonical::{canonical_json, sha256_hex};
use crate::error::{Error, Result};
use crate::validate;
use crate::{audit, hooks, platform, schema};
use contracts::ErrorCode;
use rusqlite::{Connection, OpenFlags, OptionalExtension};
use serde_json::Value;
use std::fs;
use std::path::Path;

pub const INTENT: &str = "IMPORT_APPROVAL_REPAIR.json";
const BACKUPS: &str = "import-approval-backups";
pub const REMEDY: &str = "keep every writer stopped; repeat harness-runtime repair-import-approval with the same --repo, --approved-by, --approved-at and --reason; retain the repair intent and its backup";

/// A prepared repair must finish before a runtime opens or upgrades the database.
pub fn ensure_no_pending(state: &Path) -> Result<()> {
    if state.join(INTENT).try_exists()? {
        return Err(Error::refused(
            ErrorCode::ApprovalMismatch,
            "an import approval repair is unfinished",
            REMEDY,
        ));
    }
    Ok(())
}

fn broken(error: crate::audit::Broken) -> Error {
    let error = error.to_error();
    Error::refused(error.code, error.message, error.remedy)
}

fn open(state: &Path) -> Result<Connection> {
    let connection = Connection::open_with_flags(
        state.join(STORE_NAME),
        OpenFlags::SQLITE_OPEN_READ_WRITE | OpenFlags::SQLITE_OPEN_NO_MUTEX,
    )?;
    connection.busy_timeout(std::time::Duration::from_secs(5))?;
    Ok(connection)
}

/// Diagnose the import without rebuilding the checkpoint or changing any records.
pub fn check(repo: &Path) -> Result<Value> {
    let state = repo.join(crate::migrate::STATE_REL);
    ensure_no_pending(&state)?;
    let Epoch::Store(authority) = authority::epoch(&state) else {
        return Err(Error::refused(
            ErrorCode::NotFound,
            "no consistent runtime store",
            "inspect ledger.json and AUTHORITY.json; this command repairs only a pre-#826 store",
        ));
    };
    let connection = open(&state)?;
    connection.execute_batch("PRAGMA query_only=ON; BEGIN;")?;
    validate::full_check(&connection, &authority, &state).map_err(broken)?;
    Ok(serde_json::json!({"valid": true, "repair_required": false, "store_id": authority.store_id}))
}

/// Restore missing import approval. The caller holds the runtime instance lock.
pub fn run(repo: &Path, approval: &Approval) -> Result<Value> {
    approval::check(approval, "import approval repair")?;
    let state = repo.join(crate::migrate::STATE_REL);
    if state.join(INTENT).try_exists()? {
        return finish(&state, approval);
    }
    let Epoch::Store(authority) = authority::epoch(&state) else {
        return Err(Error::refused(
            ErrorCode::NotFound,
            "no consistent runtime store",
            "inspect ledger.json and AUTHORITY.json before choosing a recovery operation",
        ));
    };
    let connection = open(&state)?;
    let version: i64 = connection.pragma_query_value(None, "user_version", |row| row.get(0))?;
    if version != schema::SCHEMA_VERSION {
        return Err(Error::refused(
            ErrorCode::ProtocolUnsupported,
            format!(
                "repair needs schema {}, found {version}",
                schema::SCHEMA_VERSION
            ),
            "use the matching runtime; upgrade an older schema with serve before this offline repair",
        ));
    }
    connection.execute_batch("PRAGMA query_only=ON; BEGIN;")?;
    let verified = validate::check_content(&connection, &authority).map_err(broken)?;
    let anchor = validate::anchor_details(&connection).map_err(broken)?;
    let marker_path = state.join(authority::AUTHORITY_NAME);
    let marker_bytes = fs::read(&marker_path)?;
    let marker: Value =
        serde_json::from_slice(&marker_bytes).map_err(|err| Error::invariant(err.to_string()))?;
    if !absent(&anchor) || !absent(&marker) {
        validate::full_check(&connection, &authority, &state).map_err(broken)?;
        return Ok(serde_json::json!({
            "repaired": false, "already_repaired": true, "store_id": authority.store_id
        }));
    }
    idle(&connection)?;
    connection.execute_batch("COMMIT; PRAGMA query_only=OFF; PRAGMA synchronous=FULL;")?;
    // With serve excluded, drain WAL and leave a self-contained original. DELETE mode also
    // refuses a reader that could keep the old WAL alive across replacement.
    let mode: String =
        connection.pragma_update_and_check(None, "journal_mode", "DELETE", |row| row.get(0))?;
    if !mode.eq_ignore_ascii_case("delete") {
        return Err(Error::refused(
            ErrorCode::StoreBusy,
            "cannot drain the store WAL",
            REMEDY,
        ));
    }
    connection.close().map_err(|(_, err)| Error::from(err))?;
    let parent = state.join(BACKUPS);
    fs::create_dir_all(&parent)?;
    let backup = format!("{BACKUPS}/{}", platform::random_hex()?);
    let directory = state.join(&backup);
    fs::create_dir(&directory)?;
    for name in [STORE_NAME, authority::AUTHORITY_NAME, "ledger.json"] {
        fs::copy(state.join(name), directory.join(name))?;
        fs::File::open(directory.join(name))?.sync_all()?;
    }
    platform::sync_dir(&directory)?;
    platform::sync_dir(&parent)?;
    platform::sync_dir(&state)?;
    let before_sha = file_sha(&directory.join(STORE_NAME))?;
    let pointer_sha = file_sha(&directory.join("ledger.json"))?;
    let marker_sha = file_sha(&directory.join(authority::AUTHORITY_NAME))?;
    hooks::reach("approval-backup")?;

    let mut repaired_marker = marker.clone();
    for (key, value) in fields(approval) {
        repaired_marker[key] = Value::String(value.to_owned());
    }
    let repaired_marker = canonical_json(&repaired_marker);
    let staged = directory.join("prepared.db");
    fs::copy(directory.join(STORE_NAME), &staged)?;
    let prepared = Connection::open(&staged)?;
    prepared.execute_batch("PRAGMA synchronous=FULL; PRAGMA foreign_keys=ON;")?;
    validate::check_content(&prepared, &authority).map_err(broken)?;
    let mut details = anchor;
    for (key, value) in fields(approval) {
        details[key] = Value::String(value.to_owned());
    }
    // Calculate the replacement outside the short transaction, using the verified chain.
    let mut statement =
        prepared.prepare("SELECT seq, at, action, details_json FROM audit ORDER BY seq")?;
    let originals = statement
        .query_map([], |row| {
            Ok((
                row.get::<_, i64>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, String>(3)?,
            ))
        })?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    drop(statement);
    let mut previous = audit::GENESIS_CHAIN.to_owned();
    let mut replacements = Vec::new();
    for (seq, at, action, raw) in originals {
        let content = if seq == 1 {
            details.clone()
        } else {
            serde_json::from_str(&raw).map_err(|err| Error::invariant(err.to_string()))?
        };
        let record = audit::record_sha256(&at, &action, &content);
        let chain = audit::chain_sha256(&previous, &record);
        replacements.push((seq, record, previous, chain.clone()));
        previous = chain;
    }
    prepared.execute_batch("BEGIN IMMEDIATE;")?;
    prepared.execute(
        "UPDATE audit SET details_json=?1 WHERE seq=1",
        [canonical_json(&details)],
    )?;
    for (seq, record, prev, chain) in &replacements {
        prepared.execute(
            "UPDATE audit SET record_sha256=?1, prev_chain_sha256=?2, chain_sha256=?3 WHERE seq=?4",
            rusqlite::params![record, prev, chain, seq],
        )?;
    }
    let original = Connection::open(directory.join(STORE_NAME))?;
    let before_anchor: String =
        original.query_row("SELECT chain_sha256 FROM audit WHERE seq=1", [], |row| {
            row.get(0)
        })?;
    drop(original);
    let seq = audit::append(
        &prepared,
        &crate::time::iso_now(),
        "import-approval-repair",
        &serde_json::json!({
            "approved_by": approval.approved_by, "approved_at": approval.approved_at,
            "reason": approval.reason, "store_id": authority.store_id,
            "backup": backup, "backup_sha256": before_sha,
            "before_anchor_sha256": before_anchor,
            "before_tail": verified.last, "after_import_tail_sha256": previous,
            "after_anchor_sha256": replacements[0].3,
            "before_authority_sha256": marker_sha,
            "after_authority_sha256": sha256_hex(repaired_marker.as_bytes()),
            "purpose": "retrospective human acceptance of a pre-826 import; not historical cutover approval"
        }),
    )?;
    let (_, tail) =
        audit::tail(&prepared)?.ok_or_else(|| Error::invariant("missing repair tail"))?;
    audit::move_checkpoint(&prepared, seq, &tail)?;
    prepared.execute_batch("COMMIT;")?;
    let mut repaired_authority = authority.clone();
    repaired_authority.approval = approval.clone();
    validate::check_content(&prepared, &repaired_authority).map_err(broken)?;
    // Also prove that both approval copies match before installing the candidate.
    let anchored = validate::anchor_details(&prepared).map_err(broken)?;
    for (key, value) in fields(approval) {
        if anchored[key].as_str() != Some(value) {
            return Err(Error::invariant(
                "prepared approval differs from the human approval",
            ));
        }
    }
    schema::seal(prepared)?;
    fs::File::open(&staged)?.sync_all()?;
    platform::sync_dir(&directory)?;
    let after_sha = file_sha(&staged)?;
    // Refuse any unexpected change between the verified snapshot and publication.
    if file_sha(&state.join(STORE_NAME))? != before_sha
        || fs::read(&marker_path)? != marker_bytes
        || file_sha(&state.join("ledger.json"))? != pointer_sha
    {
        return Err(Error::invariant(
            "the state changed while repair was prepared",
        ));
    }
    let intent = serde_json::json!({
        "version": 1, "store_id": authority.store_id, "backup": backup,
        "before_sha256": before_sha, "after_sha256": after_sha,
        "pointer_sha256": pointer_sha, "marker_sha256": marker_sha,
        "after_marker": repaired_marker
    });
    platform::replace_durable(&state.join(INTENT), canonical_json(&intent).as_bytes())?;
    hooks::reach("approval-intent")?;
    finish(&state, approval)
}

fn fields(approval: &Approval) -> [(&'static str, &str); 3] {
    [
        ("approved_by", &approval.approved_by),
        ("approved_at", &approval.approved_at),
        ("reason", &approval.reason),
    ]
}

fn file_sha(path: &Path) -> Result<String> {
    Ok(sha256_hex(&fs::read(path)?))
}

fn idle(connection: &Connection) -> Result<()> {
    let active: i64 = connection.query_row(
        "SELECT (SELECT count(*) FROM executions WHERE state IN ('launching','running','stopping','unknown'))
             + (SELECT count(*) FROM dispatch_status WHERE execution_state IN ('launching','running','stopping','unknown'))
             + (SELECT count(*) FROM qa_lane WHERE owner_id IS NOT NULL)
             + (SELECT count(*) FROM qa_queue)", [], |row| row.get(0))?;
    if active != 0 {
        return Err(Error::refused(
            ErrorCode::LeaseHeld,
            "executions or QA leases may still be active",
            "finish executions and QA runs, then stop serve and repeat repair-import-approval",
        ));
    }
    Ok(())
}

fn field<'a>(intent: &'a Value, key: &str) -> Result<&'a str> {
    intent[key]
        .as_str()
        .ok_or_else(|| Error::invariant(format!("repair intent has no {key}")))
}

fn finish(state: &Path, approval: &Approval) -> Result<Value> {
    let intent: Value = serde_json::from_slice(&fs::read(state.join(INTENT))?)
        .map_err(|err| Error::invariant(err.to_string()))?;
    if intent["version"] != 1 {
        return Err(Error::invariant(
            "unknown import approval repair intent version",
        ));
    }
    let backup = field(&intent, "backup")?;
    let suffix = backup
        .strip_prefix(&format!("{BACKUPS}/"))
        .filter(|suffix| suffix.len() == 32 && suffix.bytes().all(|byte| byte.is_ascii_hexdigit()))
        .ok_or_else(|| Error::invariant("repair backup is outside its reserved directory"))?;
    let directory = state.join(BACKUPS).join(suffix);
    for (name, key) in [
        (STORE_NAME, "before_sha256"),
        (authority::AUTHORITY_NAME, "marker_sha256"),
        ("ledger.json", "pointer_sha256"),
    ] {
        if file_sha(&directory.join(name))? != field(&intent, key)? {
            return Err(Error::invariant(format!(
                "the repair backup {name} changed"
            )));
        }
    }
    if file_sha(&state.join("ledger.json"))? != field(&intent, "pointer_sha256")? {
        return Err(Error::invariant("the epoch pointer changed during repair"));
    }
    let marker = field(&intent, "after_marker")?;
    let desired: Value =
        serde_json::from_str(marker).map_err(|err| Error::invariant(err.to_string()))?;
    for (key, value) in fields(approval) {
        if desired[key].as_str() != Some(value) {
            return Err(Error::refused(
                ErrorCode::ApprovalMismatch,
                "repeat the unfinished repair with its original human approval",
                REMEDY,
            ));
        }
    }
    if desired["store_id"].as_str() != Some(field(&intent, "store_id")?) {
        return Err(Error::invariant("the repair marker names another store"));
    }
    let marker_path = state.join(authority::AUTHORITY_NAME);
    let current_marker = fs::read(&marker_path)?;
    let old_marker = fs::read(directory.join(authority::AUTHORITY_NAME))?;
    let mut expected: Value =
        serde_json::from_slice(&old_marker).map_err(|err| Error::invariant(err.to_string()))?;
    for (key, value) in fields(approval) {
        expected[key] = Value::String(value.to_owned());
    }
    if canonical_json(&expected) != marker {
        return Err(Error::invariant(
            "repair intent changes authority outside the approved fields",
        ));
    }
    let current_sha = file_sha(&state.join(STORE_NAME))?;
    if current_sha == field(&intent, "before_sha256")? {
        if current_marker != old_marker
            || file_sha(&directory.join("prepared.db"))? != field(&intent, "after_sha256")?
        {
            return Err(Error::invariant(
                "the prepared repair or its authority changed",
            ));
        }
        verify_candidate(
            &directory.join("prepared.db"),
            &directory,
            &intent,
            approval,
        )?;
        hooks::reach("approval-install")?;
        fs::rename(directory.join("prepared.db"), state.join(STORE_NAME))?;
        platform::sync_dir(state)?;
    } else if current_sha != field(&intent, "after_sha256")? {
        return Err(Error::invariant(
            "the store is neither the original nor the prepared repair",
        ));
    } else {
        verify_candidate(&state.join(STORE_NAME), &directory, &intent, approval)?;
    }
    if current_marker != old_marker && current_marker != marker.as_bytes() {
        return Err(Error::invariant(
            "AUTHORITY.json is neither the original nor the repaired marker",
        ));
    }
    hooks::reach("approval-installed")?;
    platform::replace_durable(&marker_path, marker.as_bytes())?;
    hooks::reach("approval-authority")?;
    fs::remove_file(state.join(INTENT))?;
    platform::sync_dir(state)?;
    Ok(serde_json::json!({
        "repaired": true, "already_repaired": false,
        "store_id": field(&intent, "store_id")?, "backup": backup
    }))
}

/// Bind the resume intent to the checked candidate's immutable audit evidence.
fn verify_candidate(path: &Path, backup: &Path, intent: &Value, approval: &Approval) -> Result<()> {
    let candidate = Connection::open_with_flags(
        path,
        OpenFlags::SQLITE_OPEN_READ_WRITE | OpenFlags::SQLITE_OPEN_NO_MUTEX,
    )?;
    candidate.execute_batch("PRAGMA query_only=ON; BEGIN;")?;
    let (_, mut expected) =
        authority::read(backup)?.ok_or_else(|| Error::invariant("backup has no authority"))?;
    expected.approval = approval.clone();
    validate::check_content(&candidate, &expected).map_err(broken)?;
    let anchor = validate::anchor_details(&candidate).map_err(broken)?;
    for (key, value) in fields(approval) {
        if anchor[key].as_str() != Some(value) {
            return Err(Error::invariant(
                "the prepared anchor approval differs from the intent",
            ));
        }
    }
    let raw: Option<String> = candidate
        .query_row(
            "SELECT details_json FROM audit WHERE seq=(SELECT MAX(seq) FROM audit)
            AND action='import-approval-repair'",
            [],
            |row| row.get(0),
        )
        .optional()?;
    let proof: Value = raw
        .and_then(|raw| serde_json::from_str(&raw).ok())
        .ok_or_else(|| Error::invariant("the candidate has no final repair audit record"))?;
    for (key, wanted) in [
        ("store_id", field(intent, "store_id")?.to_owned()),
        ("backup", field(intent, "backup")?.to_owned()),
        ("backup_sha256", field(intent, "before_sha256")?.to_owned()),
        (
            "before_authority_sha256",
            field(intent, "marker_sha256")?.to_owned(),
        ),
        (
            "after_authority_sha256",
            sha256_hex(field(intent, "after_marker")?.as_bytes()),
        ),
    ] {
        if proof[key].as_str() != Some(wanted.as_str()) {
            return Err(Error::invariant(format!(
                "repair audit and intent differ at {key}"
            )));
        }
    }
    for (key, value) in fields(approval) {
        if proof[key].as_str() != Some(value) {
            return Err(Error::invariant(
                "the repair audit names another human approval",
            ));
        }
    }
    Ok(())
}

/// Missing fields, rather than explicitly empty or malformed approval, identify the old format.
pub(crate) fn absent(record: &Value) -> bool {
    record.as_object().is_some_and(|record| {
        ["approved_by", "approved_at", "reason"]
            .iter()
            .all(|key| !record.contains_key(*key))
    })
}
