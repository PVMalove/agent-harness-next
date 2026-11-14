//! The Rust vocabularies against the `systemFields.v1` registry, in both directions: any
//! difference fails, and so does a registry field in a Rust-owned namespace without a Rust enum.

use std::collections::BTreeSet;
use std::path::Path;

use contracts::{
    ErrorCode, ExecutionState, FailureDomain, OperationState, QaEvidenceVerdict,
    QaEvidenceViolation,
};
use serde_json::Value;

/// Registry fields whose vocabulary the Rust `contracts` crate owns (ADR 0021 section 3).
const RUST_OWNED_FIELDS: [&str; 6] = [
    "runtime.error_code",
    "runtime.failure_domain",
    "runtime.operation_state",
    "runtime.execution_state",
    "qa_evidence.verdict",
    "qa_evidence.violation",
];
/// Namespaces in which every registry field must be one of `RUST_OWNED_FIELDS`.
const RUST_OWNED_PREFIXES: [&str; 2] = ["runtime.", "qa_evidence."];
/// Vocabularies of the superseded Python runtime store (ADR 0026 section 1); never registered.
const SUPERSEDED_FIELDS: [&str; 5] = [
    "runtime.state",
    "runtime.operation_kind",
    "runtime.operation_phase",
    "runtime.effect_state",
    "runtime.failure_code",
];

fn registry() -> Value {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../../harness/orchestration/system_fields.v1.json");
    let text = std::fs::read_to_string(&path).expect("the registry file is readable");
    serde_json::from_str(&text).expect("the registry is JSON")
}

fn registry_fields() -> BTreeSet<String> {
    registry()["fields"]
        .as_object()
        .expect("the registry has fields")
        .keys()
        .cloned()
        .collect()
}

fn registry_values(field: &str) -> BTreeSet<String> {
    registry()["fields"][field]["values"]
        .as_object()
        .unwrap_or_else(|| panic!("registry field {field} has no values"))
        .keys()
        .cloned()
        .collect()
}

fn rust_values<I: IntoIterator<Item = &'static str>>(values: I) -> BTreeSet<String> {
    values.into_iter().map(str::to_owned).collect()
}

#[test]
fn every_registry_field_in_a_rust_namespace_has_a_rust_enum() {
    let registered: BTreeSet<String> = registry_fields()
        .into_iter()
        .filter(|field| {
            RUST_OWNED_PREFIXES
                .iter()
                .any(|prefix| field.starts_with(prefix))
        })
        .collect();

    assert_eq!(registered, rust_values(RUST_OWNED_FIELDS));
}

#[test]
fn the_registry_holds_no_superseded_store_vocabulary() {
    let fields = registry_fields();
    let revived: Vec<&str> = SUPERSEDED_FIELDS
        .into_iter()
        .filter(|field| fields.contains(*field))
        .collect();

    assert!(
        revived.is_empty(),
        "superseded fields registered: {revived:?}"
    );
}

#[test]
fn error_codes_match_the_registry() {
    let rust = rust_values(ErrorCode::ALL.into_iter().map(ErrorCode::as_str));

    assert_eq!(rust, registry_values("runtime.error_code"));
}

#[test]
fn failure_domains_match_the_registry() {
    let rust = rust_values(FailureDomain::ALL.into_iter().map(FailureDomain::as_str));

    assert_eq!(rust, registry_values("runtime.failure_domain"));
}

#[test]
fn operation_states_match_the_registry() {
    let rust = rust_values(OperationState::ALL.into_iter().map(OperationState::as_str));

    assert_eq!(rust, registry_values("runtime.operation_state"));
}

#[test]
fn execution_states_match_the_registry() {
    let rust = rust_values(ExecutionState::ALL.into_iter().map(ExecutionState::as_str));

    assert_eq!(rust, registry_values("runtime.execution_state"));
}

#[test]
fn qa_evidence_verdicts_match_the_registry() {
    let rust = rust_values(
        QaEvidenceVerdict::ALL
            .into_iter()
            .map(QaEvidenceVerdict::as_str),
    );

    assert_eq!(rust, registry_values("qa_evidence.verdict"));
}

#[test]
fn qa_evidence_violations_match_the_registry() {
    let rust = rust_values(
        QaEvidenceViolation::ALL
            .into_iter()
            .map(QaEvidenceViolation::as_str),
    );

    assert_eq!(rust, registry_values("qa_evidence.violation"));
}

#[test]
fn json_spelling_equals_the_machine_value() {
    for state in OperationState::ALL {
        let json = serde_json::to_string(&state).expect("a state serializes");
        assert_eq!(json, format!("\"{}\"", state.as_str()));
    }
    for state in ExecutionState::ALL {
        let json = serde_json::to_string(&state).expect("a state serializes");
        assert_eq!(json, format!("\"{}\"", state.as_str()));
    }
    for code in ErrorCode::ALL {
        let json = serde_json::to_string(&code).expect("a code serializes");
        assert_eq!(json, format!("\"{}\"", code.as_str()));
    }
    for domain in FailureDomain::ALL {
        let json = serde_json::to_string(&domain).expect("a domain serializes");
        assert_eq!(json, format!("\"{}\"", domain.as_str()));
    }
    for verdict in QaEvidenceVerdict::ALL {
        let json = serde_json::to_string(&verdict).expect("a verdict serializes");
        assert_eq!(json, format!("\"{}\"", verdict.as_str()));
    }
    for violation in QaEvidenceViolation::ALL {
        let json = serde_json::to_string(&violation).expect("a violation serializes");
        assert_eq!(json, format!("\"{}\"", violation.as_str()));
    }
}
