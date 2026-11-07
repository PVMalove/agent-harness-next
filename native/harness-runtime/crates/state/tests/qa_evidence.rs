//! `qa.evidence.verify` (`qa_evidence_verify` of ADR 0021, section 7): the verdict on the stored
//! QA evidence of a Release Gate pair and its violations (ADR 0023, section 5; ADR 0026,
//! section 4), on evidence held in memory and on a real store.

mod common;

use std::collections::BTreeMap;

use common::Repo;
use common::qa_store::{
    self, BATCH, CANDIDATE, COMMANDS, QA_DISPATCH, Run, TARGET, TREE, accepted_qa,
    accepted_qa_with, passed_stage, passed_stages,
};
use contracts::{StageEvidence, StageKind, StageResult, StageSelection};
use serde_json::{Map, Value, json};
use state::canonical::{canonical_json, sha256_hex};
use state::qa_evidence::{self, Evidence, Pair};
use state::read::{ReadError, read};

/// Evidence held in memory: JSON records by path and the bytes of the artifacts.
struct Memory {
    records: Map<String, Value>,
    artifacts: BTreeMap<String, Vec<u8>>,
}

impl Evidence for Memory {
    fn records(&self) -> &Map<String, Value> {
        &self.records
    }

    fn artifact(&self, path: &str) -> Result<Option<Vec<u8>>, ReadError> {
        Ok(self.artifacts.get(path).cloned())
    }
}

impl Memory {
    /// The store of `run`: the batch of the fixture with its entry, and its files.
    fn of(run: &Run) -> Self {
        let mut memory = Self {
            records: Map::new(),
            artifacts: BTreeMap::new(),
        };
        memory.records.insert(
            format!("batches/{BATCH}.json"),
            json!({"batch_id": BATCH, "base_commit": TARGET, "dispatches": [run.entry]}),
        );
        for (path, bytes) in &run.files {
            if path.starts_with("qa-artifacts/") {
                memory.artifacts.insert(path.clone(), bytes.clone());
            } else {
                let record = serde_json::from_slice(bytes).unwrap();
                memory.records.insert(path.clone(), record);
            }
        }
        memory
    }

    fn passed() -> Self {
        Self::of(&accepted_qa(passed_stages()))
    }

    fn without_qa() -> Self {
        let mut memory = Self::passed();
        memory.records = memory
            .records
            .into_iter()
            .filter(|(path, _)| path.starts_with("reports/integration-pair/"))
            .collect();
        memory
    }
}

fn pair() -> Pair {
    Pair {
        candidate_sha: CANDIDATE.to_owned(),
        target_sha: TARGET.to_owned(),
    }
}

fn judged(memory: &Memory) -> Value {
    qa_evidence::judge(memory, &pair()).unwrap()
}

fn codes(answer: &Value) -> Vec<String> {
    answer["violations"]
        .as_array()
        .unwrap()
        .iter()
        .map(|violation| violation["code"].as_str().unwrap().to_owned())
        .collect()
}

fn refused_with(answer: &Value, code: &str) {
    assert_eq!(answer["verdict"], "refused", "{answer}");
    assert!(codes(answer).contains(&code.to_owned()), "{answer}");
    assert_eq!(answer["confirmed_by"], Value::Null);
}

fn with_stages(stages: Vec<StageEvidence>) -> Value {
    judged(&Memory::of(&accepted_qa(stages)))
}

#[test]
fn a_full_passed_qa_run_of_exactly_the_pair_is_ok() {
    let answer = judged(&Memory::passed());

    assert_eq!(answer["verdict"], "ok", "{answer}");
    assert_eq!(answer["violations"], json!([]));
    assert_eq!(
        answer["pair"],
        json!({"candidate_sha": CANDIDATE, "target_sha": TARGET, "candidate_tree_sha": TREE})
    );
    assert_eq!(answer["confirmed_by"]["source"], "original-qa");
    assert_eq!(
        answer["confirmed_by"]["evidence"],
        format!("reports/{QA_DISPATCH}.json")
    );
}

#[test]
fn a_pair_without_its_record_is_refused() {
    let mut memory = Memory::passed();
    memory
        .records
        .retain(|path, _| !path.starts_with("reports/integration-pair/"));

    refused_with(&judged(&memory), "pair_not_recorded");
}

#[test]
fn a_pair_without_any_qa_run_is_no_full_qa() {
    let answer = judged(&Memory::without_qa());

    refused_with(&answer, "no_full_qa");
    assert_eq!(codes(&answer), ["no_full_qa"]);
}

#[test]
fn passed_developer_or_review_checks_are_a_cache_and_never_confirm_the_pair() {
    let mut memory = Memory::without_qa();
    for role in ["developer", "code-review"] {
        let id = format!("dispatch-{role}");
        memory.records.insert(
            format!("dispatches/{id}.json"),
            json!({"dispatch_id": id, "role": role, "candidate_commit": CANDIDATE,
                   "verification_commands": COMMANDS}),
        );
        memory.records.insert(
            format!("reports/{id}.json"),
            json!({"outcome": "completed", "checks_run": COMMANDS.iter()
                .map(|command| json!({"command": command, "result": "pass"}))
                .collect::<Vec<_>>()}),
        );
    }

    refused_with(&judged(&memory), "no_full_qa");
}

#[test]
fn a_qa_run_of_another_target_does_not_confirm_the_pair() {
    let answer = qa_evidence::judge(
        &Memory::passed(),
        &Pair {
            candidate_sha: CANDIDATE.to_owned(),
            target_sha: "2".repeat(40),
        },
    )
    .unwrap();

    refused_with(&answer, "no_full_qa");
}

#[test]
fn focused_failed_only_and_ticket_diff_stages_are_not_full() {
    for selection in [
        StageSelection::Focused,
        StageSelection::FailedOnly,
        StageSelection::TicketDiff,
    ] {
        let mut stages = passed_stages();
        stages[1].selection = selection;

        refused_with(&with_stages(stages), "selection_not_full");
    }
}

#[test]
fn a_failed_or_missing_stage_is_not_passed() {
    let mut failed = passed_stages();
    failed[0].result = StageResult::Fail;
    failed[0].exit_code = Some(1);
    refused_with(&with_stages(failed), "stage_not_passed");

    let missing = vec![passed_stage("gate-1", CANDIDATE)];
    refused_with(&with_stages(missing), "stage_not_passed");
}

#[test]
fn a_stage_of_another_candidate_is_a_candidate_mismatch() {
    let mut stages = passed_stages();
    stages[0].candidate_sha = "d".repeat(40);

    refused_with(&with_stages(stages), "stage_candidate_mismatch");
}

#[test]
fn a_stage_of_another_plan_or_environment_is_a_plan_mismatch() {
    let mut plan = passed_stages();
    plan[0].plan_sha256 = Some("a".repeat(64));
    refused_with(&with_stages(plan), "plan_mismatch");

    let mut environment = passed_stages();
    environment[1].environment_fingerprint = Some("b".repeat(64));
    refused_with(&with_stages(environment), "plan_mismatch");
}

#[test]
fn a_missing_or_changed_output_stream_is_unverifiable() {
    let stdout = passed_stages()[0].stdout.clone().unwrap().path;
    let mut missing = Memory::passed();
    missing.artifacts.remove(&stdout);
    refused_with(&judged(&missing), "evidence_unverifiable");

    let mut changed = Memory::passed();
    changed
        .artifacts
        .insert(stdout, b"another output\n".to_vec());
    refused_with(&judged(&changed), "evidence_unverifiable");
}

#[test]
fn a_missing_log_or_document_is_unverifiable() {
    for prefix in [".log", ".stage-evidence.json"] {
        let mut memory = Memory::passed();
        memory.artifacts.retain(|path, _| !path.ends_with(prefix));

        refused_with(&judged(&memory), "evidence_unverifiable");
    }
}

fn link(memory: &mut Memory, name: &str, link: Value) {
    memory
        .records
        .insert(format!("reports/integration-evidence/{name}.json"), link);
}

fn ci_link(verification: &str, result: &str) -> Value {
    let collector = json!({"source": "github", "repository": "o/r", "merge_commit_sha": "m"});
    json!({
        "kind": "ci",
        "candidate_sha": CANDIDATE,
        "target_sha": TARGET,
        "result": result,
        "verification": verification,
        "artifact_sha256": sha256_hex(canonical_json(&collector).as_bytes()),
        "collector": collector,
    })
}

#[test]
fn a_ci_check_collect_ci_accepted_confirms_the_pair() {
    let mut memory = Memory::without_qa();
    link(&mut memory, "ci", ci_link("collector-accepted", "passed"));

    let answer = judged(&memory);

    assert_eq!(answer["verdict"], "ok", "{answer}");
    assert_eq!(answer["confirmed_by"]["source"], "ci");
}

#[test]
fn a_ci_check_collect_ci_did_not_accept_never_confirms_the_pair() {
    let hand_linked = json!({"kind": "ci", "candidate_sha": CANDIDATE, "target_sha": TARGET,
        "result": "passed", "verification": "unverified", "artifact_sha256": null});
    for checked in [
        hand_linked,
        ci_link("collector-failed", "failed"),
        ci_link("collector-accepted", "failed"),
    ] {
        let mut memory = Memory::without_qa();
        link(&mut memory, "ci", checked);

        refused_with(&judged(&memory), "ci_not_collected");
    }
    let mut forged = ci_link("collector-accepted", "passed");
    forged["artifact_sha256"] = json!("0".repeat(64));
    let mut memory = Memory::without_qa();
    link(&mut memory, "ci", forged);
    refused_with(&judged(&memory), "ci_not_collected");
}

fn local_qa(memory: &mut Memory, verified: bool) {
    let mut files = qa_store::Files::new();
    let log = qa_store::run_files(passed_stages(), &mut files);
    for (path, bytes) in files {
        memory.artifacts.insert(path, bytes);
    }
    let result = json!({
        "local_qa_id": "local-qa-r",
        "event": "result",
        "request_id": "local-qa-1",
        "candidate_sha": CANDIDATE,
        "target_sha": TARGET,
        "state": "completed",
        "verification": if verified { "verified" } else { "unverified" },
        "checks_run": COMMANDS.iter()
            .map(|command| json!({"command": command, "result": "pass"}))
            .collect::<Vec<_>>(),
        "artifact_sha256": log,
    });
    let digest = sha256_hex(canonical_json(&result).as_bytes());
    memory.records.insert(
        "reports/integration-local-qa/local-qa-r.json".to_owned(),
        result,
    );
    link(
        memory,
        "local",
        json!({"kind": "local-qa", "candidate_sha": CANDIDATE, "target_sha": TARGET,
               "result": "passed", "verification": if verified { "verified" } else { "unverified" },
               "local_qa_request_id": "local-qa-1", "local_qa_result_sha256": digest}),
    );
}

#[test]
fn a_verified_local_qa_run_of_the_pair_confirms_it() {
    let mut memory = Memory::without_qa();
    local_qa(&mut memory, true);

    let answer = judged(&memory);

    assert_eq!(answer["verdict"], "ok", "{answer}");
    assert_eq!(answer["confirmed_by"]["source"], "local-qa");
}

#[test]
fn an_unverified_local_qa_link_never_confirms_the_pair() {
    let mut memory = Memory::without_qa();
    local_qa(&mut memory, false);

    refused_with(&judged(&memory), "evidence_unverifiable");
}

#[test]
fn a_payload_other_than_exactly_the_pair_is_malformed() {
    let good = json!({"candidate_sha": CANDIDATE, "target_sha": TARGET});
    assert_eq!(Pair::parse(Some(&good)).unwrap(), pair());
    for bad in [
        json!({"candidate_sha": CANDIDATE, "target_sha": TARGET, "extra": 1}),
        json!({"candidate_sha": CANDIDATE}),
        json!({"candidate_sha": CANDIDATE.to_uppercase(), "target_sha": TARGET}),
        json!({"candidate_sha": "abc", "target_sha": TARGET}),
        json!([CANDIDATE, TARGET]),
    ] {
        assert!(Pair::parse(Some(&bad)).is_err(), "{bad}");
    }
    assert!(Pair::parse(None).is_err());
}

#[test]
fn the_report_reference_and_the_trailer_follow_the_shared_golden_fixture() {
    let text = include_str!("../../contracts/tests/fixtures/qa-evidence-reference.v1.json");
    let fixture: Value = serde_json::from_str(text).unwrap();
    for case in fixture["report_outputs"].as_array().unwrap() {
        assert_eq!(
            qa_evidence::log_reference(case["output"].as_str().unwrap()),
            case["log_sha256"].as_str().map(str::to_owned),
            "{case}"
        );
    }
    for case in fixture["logs"].as_array().unwrap() {
        let expected = case["trailer"].as_object().map(|t| {
            (
                t["path"].as_str().unwrap().to_owned(),
                t["sha256"].as_str().unwrap().to_owned(),
            )
        });
        assert_eq!(
            qa_evidence::trailer(case["log"].as_str().unwrap()),
            expected,
            "{case}"
        );
    }
}

// -- the store ---------------------------------------------------------------------------------

fn store_with(run: &Run) -> Repo {
    let repo = Repo::new("qa-evidence");
    qa_store::write_legacy(&repo.generation(), run);
    state::migrate::run(&repo.root, &common::approval()).unwrap();
    repo
}

fn revision(repo: &Repo) -> u64 {
    read(&repo.state(), None, None).unwrap().revision
}

#[test]
fn the_store_answers_ok_for_an_imported_qa_run_and_its_revision_does_not_move() {
    let repo = store_with(&accepted_qa(passed_stages()));
    let before = revision(&repo);
    let payload = json!({"candidate_sha": CANDIDATE, "target_sha": TARGET});

    let answer = qa_evidence::verify(&repo.state(), Some(&payload)).unwrap();
    let again = qa_evidence::verify(&repo.state(), Some(&payload)).unwrap();

    assert_eq!(answer["verdict"], "ok", "{answer}");
    assert_eq!(answer["confirmed_by"]["source"], "original-qa");
    assert_eq!(again, answer);
    assert_eq!(revision(&repo), before);
}

#[test]
fn the_store_refuses_a_focused_run() {
    let mut stages = passed_stages();
    stages[0].selection = StageSelection::Focused;
    let repo = store_with(&accepted_qa(stages));
    let payload = json!({"candidate_sha": CANDIDATE, "target_sha": TARGET});

    let answer = qa_evidence::verify(&repo.state(), Some(&payload)).unwrap();

    refused_with(&answer, "selection_not_full");
}

#[test]
fn the_file_ledger_is_not_attached_and_a_bad_payload_is_malformed() {
    let repo = Repo::new("qa-evidence-file-ledger");
    let payload = json!({"candidate_sha": CANDIDATE, "target_sha": TARGET});

    let file_ledger = qa_evidence::verify(&repo.state(), Some(&payload));
    state::migrate::run(&repo.root, &common::approval()).unwrap();
    let malformed = qa_evidence::verify(&repo.state(), Some(&json!({"candidate_sha": CANDIDATE})));

    assert!(
        matches!(file_ledger, Err(ReadError::NotAttached(_))),
        "{file_ledger:?}"
    );
    assert!(
        matches!(malformed, Err(ReadError::Malformed(_))),
        "{malformed:?}"
    );
}

#[test]
fn a_pair_record_is_checked_field_by_field() {
    let (path, record) = qa_store::pair_record();
    let record = record.as_object().unwrap().clone();
    assert_eq!(qa_evidence::check_pair_record(&path, &record), Ok(()));
    let mut extra = record.clone();
    extra.insert("recorded_at".to_owned(), json!("now"));
    let mut bad_sha = record.clone();
    bad_sha.insert("candidate_tree_sha".to_owned(), json!("XYZ"));
    let mut bad_id = record.clone();
    bad_id.insert(
        "pair_id".to_owned(),
        json!(format!("pair-{}", "0".repeat(32))),
    );
    let mut bad_contract = record.clone();
    bad_contract.insert("contract".to_owned(), json!(3));
    for broken in [extra, bad_sha, bad_id, bad_contract] {
        assert!(
            qa_evidence::check_pair_record(&path, &broken).is_err(),
            "{broken:?}"
        );
    }
    let elsewhere = "reports/integration-pair/pair-00000000000000000000000000000000.json";
    assert!(qa_evidence::check_pair_record(elsewhere, &record).is_err());
}

#[test]
fn a_pair_record_is_checked_by_its_contract() {
    let accepted = [
        qa_store::legacy_pair_record(),
        qa_store::pair_record(),
        qa_store::diff_pair_record(),
    ];
    for (path, record) in &accepted {
        let record = record.as_object().unwrap();

        assert_eq!(
            qa_evidence::check_pair_record(path, record),
            Ok(()),
            "{record:?}"
        );
    }
    let (path, diff) = qa_store::diff_pair_record();
    let with = |key: &str, value: Value| {
        let mut record = diff.as_object().unwrap().clone();
        record.insert(key.to_owned(), value);
        record
    };
    let mut without = diff.as_object().unwrap().clone();
    without.remove("selection");
    let broken = [
        without,
        with("contract", json!(1)),
        with("contract", json!(3)),
        with("selection", json!("focused")),
        with("selection", json!("failed-only")),
        with("selection", json!("Full")),
        with("selection", json!(null)),
        with("requirement", json!("full")),
    ];
    for record in broken {
        assert!(
            qa_evidence::check_pair_record(&path, &record).is_err(),
            "{record:?}"
        );
    }
}

// -- the selection a pair requires (ADR 0023, section 7; ADR 0026, section 4) --------------------

/// The passed stages of a QA run whose second stage selected the tests of the ticket's diff.
fn diff_stages() -> Vec<StageEvidence> {
    let mut stages = passed_stages();
    stages[1].selection = StageSelection::TicketDiff;
    stages[1].nodeids = Some(vec!["tests/test_x.py".to_owned()]);
    stages
}

/// The stage a pytest stage that selected no test of the diff is recorded as.
fn no_tests_stage(stage_id: &str) -> StageEvidence {
    let mut stage = passed_stage(stage_id, CANDIDATE);
    stage.kind = StageKind::Pytest;
    stage.selection = StageSelection::TicketDiff;
    stage.result = StageResult::NotRun;
    stage.exit_code = None;
    stage.stdout = None;
    stage.stderr = None;
    stage.duration_ms = 0;
    stage.nodeids = Some(Vec::new());
    stage
}

fn judged_by(stages: Vec<StageEvidence>, pair: (String, Value)) -> Value {
    judged(&Memory::of(&accepted_qa_with(stages, pair)))
}

#[test]
fn the_required_selection_is_read_from_the_stored_pair_record_and_fails_closed() {
    let required = |record: Option<&Value>| qa_evidence::required_selection(record);
    let (_, diff) = qa_store::diff_pair_record();
    let (_, full) = qa_store::pair_record();
    let (_, legacy) = qa_store::legacy_pair_record();
    let with = |key: &str, value: Value| {
        let mut record = diff.clone();
        record[key] = value;
        record
    };
    let mut no_selection = diff.clone();
    no_selection.as_object_mut().unwrap().remove("selection");

    assert_eq!(required(Some(&diff)), StageSelection::TicketDiff);
    assert_eq!(required(Some(&full)), StageSelection::Full);
    for not_diff in [
        None,
        Some(&legacy),
        Some(&no_selection),
        Some(&with("selection", json!("focused"))),
        Some(&with("selection", json!("Ticket-Diff"))),
        Some(&with("selection", json!(null))),
        Some(&with("contract", json!(1))),
        Some(&with("contract", json!(3))),
        Some(&with("contract", json!("2"))),
    ] {
        assert_eq!(required(not_diff), StageSelection::Full, "{not_diff:?}");
    }
}

#[test]
fn diff_stages_confirm_only_a_pair_that_requires_the_diff_selection() {
    let accepted = judged_by(diff_stages(), qa_store::diff_pair_record());
    assert_eq!(accepted["verdict"], "ok", "{accepted}");
    assert_eq!(accepted["confirmed_by"]["source"], "original-qa");

    for (name, pair) in [
        ("full pair", qa_store::pair_record()),
        ("pair of the first contract", qa_store::legacy_pair_record()),
    ] {
        let answer = judged_by(diff_stages(), pair);

        refused_with(&answer, "selection_not_full");
        assert!(answer["violations"][0]["detail"].is_string(), "{name}");
    }
}

#[test]
fn full_stages_confirm_every_pair() {
    for pair in [
        qa_store::diff_pair_record(),
        qa_store::pair_record(),
        qa_store::legacy_pair_record(),
    ] {
        let answer = judged_by(passed_stages(), pair);

        assert_eq!(answer["verdict"], "ok", "{answer}");
    }
}

#[test]
fn focused_and_failed_only_stages_never_confirm_a_diff_pair() {
    for selection in [StageSelection::Focused, StageSelection::FailedOnly] {
        let mut stages = diff_stages();
        stages[0].selection = selection;

        refused_with(
            &judged_by(stages, qa_store::diff_pair_record()),
            "selection_not_full",
        );
    }
}

#[test]
fn a_pytest_stage_without_tests_in_the_diff_is_accepted_only_for_a_diff_pair() {
    for id in ["no-tests-in-diff", "no-tests-in-diff-2"] {
        let mut stages = diff_stages();
        stages.push(no_tests_stage(id));

        let accepted = judged_by(stages.clone(), qa_store::diff_pair_record());
        let refused = judged_by(stages, qa_store::pair_record());

        assert_eq!(accepted["verdict"], "ok", "{id}: {accepted}");
        refused_with(&refused, "selection_not_full");
        assert!(codes(&refused).contains(&"stage_not_passed".to_owned()));
    }
}

#[test]
fn only_the_recorded_shape_of_a_stage_without_tests_is_accepted() {
    let named = |id: &str| no_tests_stage(id);
    let mut custom = named("no-tests-in-diff");
    custom.kind = StageKind::Custom;
    let mut full = named("no-tests-in-diff");
    full.selection = StageSelection::Full;
    // It has an exit code, so the schema also wants its output streams.
    let mut ran = named("no-tests-in-diff");
    ran.exit_code = Some(1);
    ran.stdout = passed_stage("gate-1", CANDIDATE).stdout;
    ran.stderr = passed_stage("gate-1", CANDIDATE).stderr;
    let mut selected = named("no-tests-in-diff");
    selected.nodeids = Some(vec!["tests/test_x.py".to_owned()]);
    let mut failed = named("no-tests-in-diff");
    failed.result = StageResult::Fail;
    failed.exit_code = Some(1);
    failed.stdout = passed_stage("gate-1", CANDIDATE).stdout;
    failed.stderr = passed_stage("gate-1", CANDIDATE).stderr;
    let unrelated = named("lint-later");
    let near = named("no-test-in-diff");

    for (name, stage) in [
        ("custom kind", custom),
        ("full selection", full),
        ("exit code", ran),
        ("node ids", selected),
        ("failed", failed),
        ("another id", unrelated),
        ("near id", near),
    ] {
        let mut stages = diff_stages();
        stages.push(stage);

        let answer = judged_by(stages, qa_store::diff_pair_record());

        assert_eq!(answer["verdict"], "refused", "{name}: {answer}");
        assert!(
            codes(&answer).contains(&"stage_not_passed".to_owned()),
            "{name}: {answer}"
        );
    }
}

#[test]
fn a_not_run_stage_of_a_command_stays_not_passed_for_a_diff_pair() {
    let mut stages = diff_stages();
    stages[0].result = StageResult::NotRun;
    stages[0].exit_code = None;
    stages[0].stdout = None;
    stages[0].stderr = None;

    let answer = judged_by(stages, qa_store::diff_pair_record());

    refused_with(&answer, "stage_not_passed");
}

#[test]
fn one_store_judges_each_target_by_the_pair_record_of_that_target() {
    let other = "2".repeat(40);
    let run = accepted_qa_with(diff_stages(), qa_store::diff_pair_record());
    let mut memory = Memory::of(&run);
    memory.records.insert(
        "batches/batch-bbbbbbbb-0000-4000-8000-000000000002.json".to_owned(),
        json!({"batch_id": "batch-bbbbbbbb-0000-4000-8000-000000000002",
               "base_commit": other, "dispatches": [run.entry]}),
    );
    let (path, record) = qa_store::pair_record_of(&other, Some("full"));
    memory.records.insert(path, record);

    let into_integration = judged(&memory);
    let into_default = qa_evidence::judge(
        &memory,
        &Pair {
            candidate_sha: CANDIDATE.to_owned(),
            target_sha: other,
        },
    )
    .unwrap();

    assert_eq!(into_integration["verdict"], "ok", "{into_integration}");
    refused_with(&into_default, "selection_not_full");
}

#[test]
fn the_store_judges_the_selection_by_the_stored_pair_record() {
    let payload = json!({"candidate_sha": CANDIDATE, "target_sha": TARGET});
    let diff = store_with(&accepted_qa_with(
        diff_stages(),
        qa_store::diff_pair_record(),
    ));
    let full = store_with(&accepted_qa_with(diff_stages(), qa_store::pair_record()));
    let legacy = store_with(&accepted_qa_with(
        diff_stages(),
        qa_store::legacy_pair_record(),
    ));

    let accepted = qa_evidence::verify(&diff.state(), Some(&payload)).unwrap();
    let into_default = qa_evidence::verify(&full.state(), Some(&payload)).unwrap();
    let old_contract = qa_evidence::verify(&legacy.state(), Some(&payload)).unwrap();

    assert_eq!(accepted["verdict"], "ok", "{accepted}");
    refused_with(&into_default, "selection_not_full");
    refused_with(&old_contract, "selection_not_full");
}

#[test]
fn the_request_carries_exactly_the_pair_and_no_requirement() {
    let valid = json!({"candidate_sha": CANDIDATE, "target_sha": TARGET});
    assert_eq!(Pair::parse(Some(&valid)), Ok(pair()));

    for field in ["requirement", "selection", "required_selection", "fallback"] {
        for value in [
            json!("full"),
            json!("ticket-diff"),
            json!(null),
            json!(true),
        ] {
            let mut payload = valid.clone();
            payload[field] = value;

            let parsed = Pair::parse(Some(&payload));

            assert!(
                parsed.as_ref().is_err_and(|reason| reason.contains(field)),
                "{field}: {parsed:?}"
            );
        }
    }
}

#[test]
fn a_request_with_a_requirement_is_malformed_and_never_judged() {
    let repo = store_with(&accepted_qa_with(diff_stages(), qa_store::pair_record()));
    let before = revision(&repo);
    let weaker = json!({"candidate_sha": CANDIDATE, "target_sha": TARGET,
                         "requirement": "ticket-diff"});

    let answer = qa_evidence::verify(&repo.state(), Some(&weaker));

    assert!(matches!(answer, Err(ReadError::Malformed(_))), "{answer:?}");
    assert_eq!(revision(&repo), before);
}
