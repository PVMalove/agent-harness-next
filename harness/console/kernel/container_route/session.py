"""The operator's route session: the selection and the last document of every stage."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from ..coordinator_api import ApiResult, CoordinatorApi, CoordinatorCalls
from ..json_fields import items_or_empty
from ..json_fields import mapping_or_empty
from ..runner import CommandRunner, capturing_runner
from .model import (
    NEED_BATCH,
    STAGE_TITLES,
    JsonObject,
    Selection,
    Stage,
    StageView,
    State,
    Tab,
    _text,
)
from .config import Authored, read_authored
from .preflight_stage import (
    _packet,
    preflight_tab_state,
    preflight_view,
    verification_status,
)
from .setup_stage import setup_view
from .plan_stage import Proposal, plan_view
from .worker_stage import _LIVENESS, _mapping_text, worker_entry, worker_view
from .qa_stage import QaState, qa_view
from .cleanup_stage import CleanupState, cleanup_view, plan_digest_of


def read_report(path: str) -> JsonObject | None:
    """A completion report file the core named; unreadable means `None`, never a guess."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


class RouteSession:
    """The operator's selection and the last document of every stage. All process work goes
    through the injected client; no method here starts a worker on its own."""

    def __init__(
        self,
        repo: Path,
        runner: CommandRunner = capturing_runner,
        *,
        api: CoordinatorCalls | None = None,
        load_authored: Callable[[Path], Authored] = read_authored,
        load_report: Callable[[str], JsonObject | None] = read_report,
        now: Callable[[], str] = lambda: datetime.now(UTC).isoformat(
            timespec="seconds"
        ),
    ) -> None:
        self.repo = repo
        self.api: CoordinatorCalls = api or CoordinatorApi(repo, runner)
        self._load_authored = load_authored
        self._load_report = load_report
        self._now = now
        self.selection = Selection()
        self.preflight: ApiResult | None = None
        self.proposal: Proposal | None = None
        self.proposal_result: ApiResult | None = None
        self.created: ApiResult | None = None
        self.worker: ApiResult | None = None
        self.qa = QaState()
        self.cleanup = CleanupState()

    def select(
        self, batch: str = "", role: str = "developer", runtime: str = ""
    ) -> None:
        """Choose the batch, role and runtime; a different choice drops what belonged to the old."""
        chosen = (batch.strip(), role.strip() or "developer", runtime.strip())
        current = (self.selection.batch, self.selection.role, self.selection.runtime)
        if chosen != current:
            same_batch = chosen[0] == self.selection.batch
            self.selection = Selection(
                *chosen,
                dispatch=self.selection.dispatch if same_batch else "",
                qa_dispatch=self.selection.qa_dispatch if same_batch else "",
            )
            self.preflight = None
            self.proposal = None
            self.proposal_result = None
            self.created = None
            self.worker = None
            self.qa = QaState()
            self.cleanup = CleanupState()

    def _preflight_values(self) -> dict[str, str]:
        values = {"batch": self.selection.batch, "role": self.selection.role}
        if self.selection.runtime:
            values["runtime"] = self.selection.runtime
        return values

    def recheck(self) -> ApiResult:
        """`dispatch preflight`: read-only for the executor; it builds and pulls nothing."""
        self.preflight = self.api.call(
            ("dispatch", "preflight"), self._preflight_values()
        )
        self._detect_drift()
        return self.preflight

    def _detect_drift(self) -> None:
        """A held proposal no longer matches a plan the core now reports: it needs a new propose."""
        held = self.proposal
        if held is None or held.stale:
            return
        plan, _ = _packet(self.preflight)
        if verification_status(self.preflight) != "verified":
            reason = "preflight больше не verified"
        elif _text(plan.get("plan_digest")) != held.plan_digest:
            reason = "plan_digest изменился после propose"
        else:
            return
        self.proposal = replace(
            held, stale=f"{reason}: нужны новый propose и новое одобрение"
        )

    def _dispatch_values(self, held: Proposal) -> dict[str, str]:
        values = {"batch": held.batch, "role": held.role, "purpose": held.purpose}
        if held.runtime:
            values["runtime"] = held.runtime
        return values

    def _propose(self, role: str) -> tuple[Proposal | None, ApiResult]:
        """One `dispatch propose` for `role`; the proposal is held only with a transition digest."""
        values = {
            "batch": self.selection.batch,
            "role": role,
            "purpose": "work",
        }
        if self.selection.runtime:
            values["runtime"] = self.selection.runtime
        result = self.api.call(("dispatch", "propose"), values)
        document = result.document if result.ok else None
        digest = _text(mapping_or_empty(document).get("transition_digest"))
        if document is None or not digest:
            return None, result
        plan = mapping_or_empty(document.get("runtime_access"))
        held = Proposal(
            self.selection.batch,
            role,
            self.selection.runtime,
            "work",
            digest,
            _text(plan.get("plan_digest")),
            document,
        )
        return held, result

    def _approve(self, held: Proposal, approved_by: str) -> ApiResult:
        """`dispatch create` carrying only the digest of the proposal that was displayed."""
        approver = approved_by.strip()
        if not approver:
            raise ValueError("approved_by is required")
        values = {
            **self._dispatch_values(held),
            "approved_by": approver,
            "approved_at": self._now(),
            "transition_digest": held.transition_digest,
        }
        return self.api.call(("dispatch", "create"), values)

    def propose(self) -> ApiResult:
        """`dispatch propose`: the core records a proposal; nothing is approved or started. It runs
        only after a verified preflight, so a blocked route never reaches an approval."""
        if verification_status(self.preflight) != "verified":
            raise PermissionError("dispatch propose requires a verified preflight")
        self.created = None
        held, result = self._propose(self.selection.role)
        self.proposal, self.proposal_result = (
            held,
            result,
        )  # any outcome replaces the held one
        return result

    def create(self, approved_by: str) -> ApiResult:
        """`dispatch create` with the explicit approval bound to the held proposal's own
        `transition_digest`. Any outcome consumes the proposal: a refusal makes it stale and a
        success is not repeatable, so a drifted transition always needs a new propose."""
        held = self.proposal
        if held is None or held.stale:
            raise PermissionError("no live proposal to approve")
        result = self._approve(held, approved_by)
        self.created = result
        if result.ok:
            dispatch = _text(mapping_or_empty(result.document).get("dispatch_id"))
            if dispatch:
                self.selection.dispatch = dispatch
            self.proposal = None
        else:
            self.proposal = replace(
                held,
                stale="отказ ядра: " + (result.problem_text or result.outcome.value),
            )
        return result

    def propose_qa(self) -> ApiResult:
        """`dispatch propose --role qa`: QA's own proposal and digest, never the worker's."""
        if not self.selection.batch:
            raise PermissionError("no batch selected")
        self.qa.created = None
        held, result = self._propose("qa")
        self.qa.proposal, self.qa.proposal_result = held, result
        return result

    def create_qa(self, approved_by: str) -> ApiResult:
        """The explicit approval of the QA proposal, bound to its own transition digest."""
        held = self.qa.proposal
        if held is None or held.stale:
            raise PermissionError("no live QA proposal to approve")
        result = self._approve(held, approved_by)
        self.qa.created = result
        if result.ok:
            dispatch = _text(mapping_or_empty(result.document).get("dispatch_id"))
            if dispatch:
                self.selection.qa_dispatch = dispatch
            self.qa.proposal = None
        else:
            self.qa.proposal = replace(
                held,
                stale="отказ ядра: " + (result.problem_text or result.outcome.value),
            )
        return result

    def run_qa(self) -> ApiResult:
        """`qa run --dispatch`: gates run in a container. It needs the QA dispatch, which only
        its own approval creates; a worker approval never reaches this."""
        if not self.selection.qa_dispatch:
            raise PermissionError("no approved QA dispatch")
        result = self.api.call(("qa", "run"), {"dispatch": self.selection.qa_dispatch})
        self.qa.run = result
        path = (
            _text(mapping_or_empty(result.document).get("report")) if result.ok else ""
        )
        self.qa.report = self._load_report(path) if path else None
        return result

    def refresh_qa(self) -> ApiResult:
        """`qa status`: the lane lease and queue, read-only."""
        self.qa.status = self.api.call(("qa", "status"))
        return self.qa.status

    def preview_cleanup(self) -> ApiResult:
        """`harness cleanup <repo>` without --apply: a plan for the whole repository; it removes
        nothing. Its digest is what a later apply is bound to."""
        result = self.api.cleanup()
        plan = mapping_or_empty(result.section("plan")) if result.ok else {}
        self.cleanup = CleanupState(
            preview=result,
            plan=plan or None,
            digest=plan_digest_of(plan) if plan else "",
        )
        return result

    def apply_cleanup(self) -> ApiResult:
        """`--apply --plan-digest <digest of the previewed plan>`: any outcome spends the digest,
        so a changed plan or a refusal always needs a new preview."""
        state = self.cleanup
        if not state.digest or state.stale:
            raise PermissionError("no live cleanup preview to apply")
        result = self.api.cleanup(apply_digest=state.digest)
        state.apply = result
        state.stale = "применение выполнено или отклонено: нужно новое превью"
        return result

    def refresh_worker(self) -> ApiResult:
        """`dispatch status --dispatch`: not read-only, since the core may react to an ended
        execution; it runs only on the operator's explicit button, never from a timer or a tab."""
        if not self.selection.dispatch:
            raise PermissionError("no worker dispatch to observe")
        self.worker = self.api.call(
            ("dispatch", "status"), {"dispatch": self.selection.dispatch}
        )
        return self.worker

    def executor_context(self) -> tuple[tuple[str, str], ...]:
        """Worker, QA and the engine labels for the strip above the tabs; never a secret."""
        selection = self.selection
        entry = worker_entry(self.worker, selection.dispatch) or {}
        labels = _mapping_text(
            mapping_or_empty(
                mapping_or_empty(entry.get("execution")).get("launch")
            ).get("labels")
        )
        return (
            ("Worker", selection.dispatch or "не создан"),
            ("QA", selection.qa_dispatch or "не создан"),
            ("Метки", labels.replace("\n", ", ") or "не сообщаются"),
        )

    def tabs(self) -> tuple[Tab, ...]:
        """Every stage with its state and the reason it cannot proceed. A tab stays selectable:
        choosing it only draws its view, so availability is shown, never enforced by hiding."""
        selection = self.selection
        verified = verification_status(self.preflight) == "verified"
        if not selection.batch:
            pre = Tab(
                Stage.PREFLIGHT,
                STAGE_TITLES[Stage.PREFLIGHT],
                State.NOT_CHECKED,
                NEED_BATCH,
            )
        else:
            pre = Tab(
                Stage.PREFLIGHT,
                STAGE_TITLES[Stage.PREFLIGHT],
                *preflight_tab_state(self.preflight),
            )
        title = STAGE_TITLES[Stage.PLAN]
        if self.created is not None and self.created.ok:
            plan = Tab(Stage.PLAN, title, State.OK, "dispatch создан")
        elif self.proposal is not None and self.proposal.stale:
            plan = Tab(Stage.PLAN, title, State.WARN, self.proposal.stale)
        elif self.proposal is not None:
            plan = Tab(Stage.PLAN, title, State.PENDING, "предложение ждёт одобрения")
        else:
            plan = Tab(Stage.PLAN, title, State.PENDING, "предложение не запрашивалось")
        if not verified and self.proposal is None and self.created is None:
            plan = Tab(
                Stage.PLAN,
                STAGE_TITLES[Stage.PLAN],
                State.BLOCKED,
                "сначала Preflight со статусом verified",
            )
        worker = Tab(
            Stage.WORKER,
            STAGE_TITLES[Stage.WORKER],
            State.PENDING,
            "dispatch ещё не создан",
        )
        if selection.dispatch:
            worker = Tab(
                Stage.WORKER, STAGE_TITLES[Stage.WORKER], *self._worker_tab_state()
            )
        qa = (
            Tab(Stage.QA, STAGE_TITLES[Stage.QA], State.NOT_CHECKED, NEED_BATCH)
            if not selection.batch
            else Tab(
                Stage.QA,
                STAGE_TITLES[Stage.QA],
                State.PENDING,
                "отдельный dispatch роли qa ещё не создан",
            )
        )
        if selection.batch and self.qa.run is not None:
            qa = Tab(Stage.QA, STAGE_TITLES[Stage.QA], *self._qa_tab_state())
        elif selection.batch and selection.qa_dispatch:
            qa = Tab(
                Stage.QA,
                STAGE_TITLES[Stage.QA],
                State.PENDING,
                "dispatch QA создан, QA не запускался",
            )
        cleanup = Tab(
            Stage.CLEANUP,
            STAGE_TITLES[Stage.CLEANUP],
            State.INFO,
            "превью не запрашивалось",
        )
        if self.cleanup.preview is not None and not self.cleanup.preview.ok:
            cleanup = Tab(
                Stage.CLEANUP,
                STAGE_TITLES[Stage.CLEANUP],
                State.FAILED,
                self.cleanup.preview.problem_text,
            )
        elif self.cleanup.preview is not None:
            cleanup = Tab(
                Stage.CLEANUP,
                STAGE_TITLES[Stage.CLEANUP],
                State.INFO,
                "превью получено",
            )
        setup = Tab(Stage.SETUP, STAGE_TITLES[Stage.SETUP], State.INFO)
        return (setup, pre, plan, worker, qa, cleanup)

    def _qa_tab_state(self) -> tuple[State, str]:
        run = self.qa.run
        if run is None or not run.ok:
            return State.FAILED, (run.problem_text if run is not None else "")
        stages = mapping_or_empty(mapping_or_empty(self.qa.report).get("qa_stages"))
        if self.qa.report is None:
            return State.NOT_REPORTED, "отчёт QA не прочитан"
        if _text(stages.get("failed_stage")):
            return (
                State.FAILED,
                f"остановилась на стадии {_text(stages.get('failed_stage'))}",
            )
        checks = items_or_empty(self.qa.report.get("checks_run"))
        if any(mapping_or_empty(item).get("result") == "fail" for item in checks):
            return State.FAILED, "есть проваленная проверка"
        outcome = _text(self.qa.report.get("outcome"))
        if outcome == "failed":
            return State.FAILED, "исход отчёта: failed"
        if outcome == "blocked":
            return State.BLOCKED, "исход отчёта: blocked"
        document = mapping_or_empty(run.document)
        if document.get("transition_blocked"):
            return State.BLOCKED, _text(
                document.get("diagnostic"), "переход заблокирован ядром"
            )
        if any(mapping_or_empty(item).get("result") == "not_run" for item in checks):
            return State.NOT_CHECKED, "часть проверок не выполнена"
        if outcome != "completed":
            return State.NOT_REPORTED, "исход отчёта не сообщается"
        if not checks:
            return State.NOT_REPORTED, "в отчёте нет выполненных проверок"
        return State.OK, ""

    def _worker_tab_state(self) -> tuple[State, str]:
        if self.worker is None:
            return State.NOT_CHECKED, "статус ещё не запрашивался"
        if not self.worker.ok:
            return State.FAILED, self.worker.problem_text or self.worker.outcome.value
        entry = worker_entry(self.worker, self.selection.dispatch)
        execution = mapping_or_empty(mapping_or_empty(entry).get("execution"))
        if not execution:
            return State.NOT_REPORTED, ""
        state, label = _LIVENESS.get(
            _text(execution.get("state")), (State.NOT_REPORTED, "")
        )
        return state, label

    def view(self, stage: Stage) -> StageView:
        if stage is Stage.SETUP:
            return setup_view(
                self._load_authored(self.repo), self.preflight, self.selection
            )
        if stage is Stage.PREFLIGHT:
            return preflight_view(self.preflight, self.selection)
        if stage is Stage.CLEANUP:
            return cleanup_view(self.cleanup, self.selection, self.worker)
        if stage is Stage.QA:
            return qa_view(self.qa, self.selection)
        if stage is Stage.WORKER:
            return worker_view(self.worker, self.selection)
        if stage is Stage.PLAN:
            return plan_view(
                self.preflight,
                self.proposal,
                self.proposal_result,
                self.created,
                self.selection,
            )
        raise KeyError(stage)
