//! The protocol errors that every command of the store shares (ADR 0021, section 3): which
//! SQLite failure is a lock another process holds, the internal failure and the broken
//! invariant, and the remedies that send an operator to the snapshot named in AUTHORITY.json.

use std::fmt::Display;

use contracts::{ErrorBody, ErrorCode, FailureDomain};

/// The remedy text that restores the state directory; a macro, so the longer remedies below
/// `concat!` the same words.
macro_rules! restore_remedy {
    () => {
        "restore the state directory from the snapshot named in AUTHORITY.json"
    };
}

/// The remedy of a store that no repeat can fix.
pub const RESTORE_REMEDY: &str = restore_remedy!();

/// The remedy of a store that could not be read or written: a repeat first, then the snapshot.
pub const REPEAT_OR_RESTORE_REMEDY: &str = concat!(
    "repeat the command; if the store stays unreadable, ",
    restore_remedy!()
);

/// The remedy of an audit chain that failed its verification.
pub(crate) const VALIDATE_AND_RESTORE_REMEDY: &str = concat!(
    "stop every writer, run `coordinator.py ledger validate --full`, and ",
    restore_remedy!()
);

/// Whether a SQLite failure is a lock another process holds: `store_busy` then, not `internal`.
pub fn is_busy(err: &rusqlite::Error) -> bool {
    matches!(
        err.sqlite_error_code(),
        Some(rusqlite::ErrorCode::DatabaseBusy | rusqlite::ErrorCode::DatabaseLocked)
    )
}

/// `internal`: the store failed for a reason other than a lock.
pub fn store_failed(detail: impl Display) -> ErrorBody {
    ErrorBody::new(
        ErrorCode::Internal,
        FailureDomain::Infrastructure,
        false,
        format!("the store failed: {detail}"),
        REPEAT_OR_RESTORE_REMEDY,
    )
}

/// `invariant_violation`: a change would break an invariant of the store, and nothing was
/// written.
pub fn invariant(message: impl Into<String>) -> ErrorBody {
    ErrorBody::new(
        ErrorCode::InvariantViolation,
        FailureDomain::Tooling,
        false,
        message,
        "nothing was written; run `coordinator.py ledger validate --full` and report the defect",
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_remedies_keep_their_wording() {
        assert_eq!(
            RESTORE_REMEDY,
            "restore the state directory from the snapshot named in AUTHORITY.json"
        );
        assert_eq!(
            REPEAT_OR_RESTORE_REMEDY,
            "repeat the command; if the store stays unreadable, restore the state directory from the snapshot named in AUTHORITY.json"
        );
        assert_eq!(
            VALIDATE_AND_RESTORE_REMEDY,
            "stop every writer, run `coordinator.py ledger validate --full`, and restore the state directory from the snapshot named in AUTHORITY.json"
        );
    }

    #[test]
    fn only_a_lock_is_busy() {
        let busy = rusqlite::Error::SqliteFailure(
            rusqlite::ffi::Error::new(rusqlite::ffi::SQLITE_BUSY),
            None,
        );
        let locked = rusqlite::Error::SqliteFailure(
            rusqlite::ffi::Error::new(rusqlite::ffi::SQLITE_LOCKED),
            None,
        );
        let full = rusqlite::Error::SqliteFailure(
            rusqlite::ffi::Error::new(rusqlite::ffi::SQLITE_FULL),
            None,
        );
        assert!(is_busy(&busy));
        assert!(is_busy(&locked));
        assert!(!is_busy(&full));
        assert!(!is_busy(&rusqlite::Error::QueryReturnedNoRows));
    }

    #[test]
    fn the_shared_errors_keep_their_codes() {
        let failed = store_failed("disk I/O error");
        assert_eq!(failed.code, ErrorCode::Internal);
        assert_eq!(failed.message, "the store failed: disk I/O error");
        assert_eq!(failed.remedy, REPEAT_OR_RESTORE_REMEDY);
        assert!(!failed.retryable);
        let broken = invariant("x");
        assert_eq!(broken.code, ErrorCode::InvariantViolation);
        assert_eq!(broken.domain, FailureDomain::Tooling);
        assert_eq!(broken.message, "x");
    }
}
