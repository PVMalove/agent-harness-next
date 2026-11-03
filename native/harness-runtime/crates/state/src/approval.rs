//! The human approval of an operation that changes the authority over the state (ADR 0020,
//! section 5): `harness-runtime migrate` and `harness-runtime rollback --to-legacy`.

use contracts::ErrorCode;

use crate::error::{Error, Result};
use crate::time::{now_micros, parse_rfc3339};

/// The human approval of an operation (as for `release-lock --force`).
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Approval {
    pub approved_by: String,
    pub approved_at: String,
    pub reason: String,
}

fn refused(code: ErrorCode, message: impl Into<String>, remedy: impl Into<String>) -> Error {
    Error::refused(code, message, remedy)
}

/// Whether `approval` is the approval of a human for `operation` (`migration`, `rollback`):
/// `approved_by`, `approved_at` and `reason` are not blank, the approver is no `policy:` actor,
/// and `approved_at` is an RFC 3339 time that is not in the future.
///
/// # Errors
/// `malformed_request` for a blank field, or an `approved_at` that is no RFC 3339 time or lies in
/// the future; `policy_denied` for a `policy:` approver.
pub fn check(approval: &Approval, operation: &str) -> Result<()> {
    let remedy = format!(
        "pass --approved-by <human>, --approved-at <RFC 3339 time> and --reason <text> of the \
         human who approved the {operation}"
    );
    for (flag, value) in [
        ("--approved-by", &approval.approved_by),
        ("--approved-at", &approval.approved_at),
        ("--reason", &approval.reason),
    ] {
        if value.trim().is_empty() {
            return Err(refused(
                ErrorCode::MalformedRequest,
                format!("{flag} is blank"),
                remedy,
            ));
        }
    }
    if approval.approved_by.trim_start().starts_with("policy:") {
        return Err(refused(
            ErrorCode::PolicyDenied,
            format!(
                "{:?} is a policy approver; a {operation} needs a human approval",
                approval.approved_by
            ),
            format!("ask a human to approve the {operation} and pass their name as --approved-by"),
        ));
    }
    let Some(at) = parse_rfc3339(approval.approved_at.trim()) else {
        return Err(refused(
            ErrorCode::MalformedRequest,
            format!(
                "--approved-at {:?} is no RFC 3339 time",
                approval.approved_at
            ),
            remedy,
        ));
    };
    if at > now_micros() {
        return Err(refused(
            ErrorCode::MalformedRequest,
            format!("--approved-at {} lies in the future", approval.approved_at),
            format!("pass the time at which the human approved the {operation}"),
        ));
    }
    Ok(())
}
