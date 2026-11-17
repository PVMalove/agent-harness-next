//! Whether the runtime store still needs its runtime (ADR 0031, section 3).
//!
//! A runtime that the autostart hook started stops itself only when nothing of the store needs it:
//! no dispatch is `dispatched` or `working`, the QA lane holds no lease, the QA queue is empty and
//! every execution is terminal. A store that cannot be read is busy: without proof of idleness the
//! runtime keeps serving. A state directory whose authority is not the runtime store holds nothing
//! that the runtime serves, so it is idle.

use std::path::Path;
use std::time::Duration;

use rusqlite::{Connection, OpenFlags};

use crate::authority::STORE_NAME;

/// Why the store of `state` still needs its runtime; empty when it is idle.
pub fn busy(state: &Path) -> Vec<String> {
    if crate::read::store_id(state).is_none() {
        return Vec::new();
    }
    let reasons = Connection::open_with_flags(
        state.join(STORE_NAME),
        OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
    )
    .and_then(|connection| {
        connection.busy_timeout(Duration::from_secs(5))?;
        busy_in(&connection)
    });
    reasons.unwrap_or_else(|err| vec![format!("the runtime store cannot be read: {err}")])
}

/// Why the store behind `connection` still needs its runtime; empty when it is idle.
///
/// # Errors
/// A store that cannot be read.
pub fn busy_in(connection: &Connection) -> rusqlite::Result<Vec<String>> {
    let mut reasons = Vec::new();
    let mut each = |sql: &str, describe: &dyn Fn(String, String) -> String| {
        let mut statement = connection.prepare(sql)?;
        let rows = statement.query_map([], |row| Ok((row.get(0)?, row.get(1)?)))?;
        for row in rows {
            let (first, second) = row?;
            reasons.push(describe(first, second));
        }
        Ok::<(), rusqlite::Error>(())
    };
    each(
        "SELECT id, state FROM dispatch_status WHERE state IN ('dispatched', 'working') ORDER BY id",
        &|id, state| format!("the dispatch {id} is {state}"),
    )?;
    each(
        "SELECT owner_kind, owner_id FROM qa_lane WHERE id = 1 AND owner_kind IS NOT NULL",
        &|kind, id| format!("the QA lease is held by {kind} {id}"),
    )?;
    each("SELECT id, '' FROM qa_queue ORDER BY id", &|id, _| {
        format!("the QA queue holds {id}")
    })?;
    each(
        "SELECT id, state FROM executions WHERE state NOT IN ('exited', 'lost') ORDER BY id",
        &|id, state| format!("the execution {id} is {state}"),
    )?;
    Ok(reasons)
}
