from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, Callable, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .hashing import sha256_json

DEFAULT_SESSION_TTL = timedelta(days=7)
MAX_SESSION_TTL = timedelta(days=30)


class EpistemicClass(StrEnum):
    DOCUMENTED_FACT = "DOCUMENTED_FACT"
    CONFIRMED_CONTEXT = "CONFIRMED_CONTEXT"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"
    WORKING_ASSUMPTION = "WORKING_ASSUMPTION"
    STALE_INFORMATION = "STALE_INFORMATION"


class OutputDisposition(StrEnum):
    EPHEMERAL_INFERENCE = "EPHEMERAL_INFERENCE"
    CLAIM_PROPOSAL = "CLAIM_PROPOSAL"
    DECISION_PROPOSAL = "DECISION_PROPOSAL"
    TOOL_REQUEST = "TOOL_REQUEST"


class PolicyAction(StrEnum):
    KEEP_EPHEMERAL = "KEEP_EPHEMERAL"
    PROPOSE_CLAIM = "PROPOSE_CLAIM"
    PROPOSE_DECISION = "PROPOSE_DECISION"
    ALLOW_R1_TOOL_REQUEST = "ALLOW_R1_TOOL_REQUEST"
    HOLD_R2 = "HOLD_R2"
    DENY_ADMISSION = "DENY_ADMISSION"


class CognitiveMessage(BaseModel):
    model_config = ConfigDict(frozen=True)
    role: str = Field(min_length=1)
    content: str = Field(min_length=1)


class CognitiveInvocationRequest(BaseModel):
    """Provider-neutral cognitive invocation contract."""

    model_config = ConfigDict(frozen=True)
    invocation_id: str = Field(min_length=1)
    task_class: str = Field(min_length=1)
    messages: tuple[CognitiveMessage, ...]
    context_refs: tuple[str, ...] = ()
    tool_contracts: tuple[str, ...] = ()
    output_schema: str = Field(min_length=1)
    reasoning_budget: str = Field(min_length=1)
    latency_class: str = Field(min_length=1)
    privacy_class: str = Field(min_length=1)
    max_cost: float = Field(ge=0)
    model_constraints: dict[str, Any] = Field(default_factory=dict)
    trace_context: dict[str, str] = Field(default_factory=dict)

    @field_validator("messages")
    @classmethod
    def require_messages(cls, value: tuple[CognitiveMessage, ...]) -> tuple[CognitiveMessage, ...]:
        if not value:
            raise ValueError("messages must contain at least one item")
        return value


class CognitiveOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    output_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    epistemic_class: EpistemicClass
    disposition: OutputDisposition
    evidence_refs: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()
    tool_name: str | None = None
    material_effect: bool = False


@dataclass(frozen=True)
class SessionBufferItem:
    item_id: str
    session_id: str
    project_scope: str
    payload: dict[str, Any]
    sensitivity: str
    epistemic_class: EpistemicClass
    created_at: datetime
    expires_at: datetime
    canonical: bool = False


class SessionContextBuffer:
    """In-memory Alpha buffer with no persistence/admission method."""

    def __init__(
        self,
        *,
        default_ttl: timedelta = DEFAULT_SESSION_TTL,
        max_ttl: timedelta = MAX_SESSION_TTL,
    ) -> None:
        if default_ttl <= timedelta(0) or default_ttl > max_ttl:
            raise ValueError("default_ttl must be positive and no greater than max_ttl")
        self._default_ttl = default_ttl
        self._max_ttl = max_ttl
        self._items: dict[tuple[str, str], SessionBufferItem] = {}

    def put(
        self,
        *,
        item_id: str,
        session_id: str,
        project_scope: str,
        payload: dict[str, Any],
        created_at: datetime,
        ttl: timedelta | None = None,
        sensitivity: str = "STANDARD",
        epistemic_class: EpistemicClass = EpistemicClass.INFERENCE,
    ) -> SessionBufferItem:
        if not item_id.strip() or not session_id.strip() or not project_scope.strip():
            raise ValueError("item_id, session_id, and project_scope are mandatory")
        active_ttl = ttl or self._default_ttl
        if active_ttl <= timedelta(0) or active_ttl > self._max_ttl:
            raise ValueError("ttl must be positive and no greater than 30 days")
        created = _as_utc(created_at)
        item = SessionBufferItem(
            item_id=item_id,
            session_id=session_id,
            project_scope=project_scope.strip(),
            payload=dict(payload),
            sensitivity=sensitivity,
            epistemic_class=epistemic_class,
            created_at=created,
            expires_at=created + active_ttl,
        )
        self._items[(session_id, item_id)] = item
        return item

    def active(
        self,
        *,
        session_id: str,
        project_scope: str,
        as_of: datetime,
    ) -> tuple[SessionBufferItem, ...]:
        at = _as_utc(as_of)
        return tuple(
            sorted(
                (
                    item
                    for item in self._items.values()
                    if item.session_id == session_id
                    and item.project_scope == project_scope
                    and item.created_at <= at < item.expires_at
                ),
                key=lambda item: (item.created_at, item.item_id),
            )
        )

    def purge_expired(self, *, as_of: datetime) -> tuple[str, ...]:
        at = _as_utc(as_of)
        expired = sorted(key for key, item in self._items.items() if item.expires_at <= at)
        removed: list[str] = []
        for key in expired:
            removed.append(self._items.pop(key).item_id)
        return tuple(removed)

    def purge(self, *, session_id: str) -> tuple[str, ...]:
        keys = sorted(key for key in self._items if key[0] == session_id)
        removed: list[str] = []
        for key in keys:
            removed.append(self._items.pop(key).item_id)
        return tuple(removed)


@dataclass(frozen=True)
class ContextBundle:
    project_scope: str
    valid_at: datetime
    recorded_at: datetime
    memory: tuple[dict[str, Any], ...]
    evidence_refs: tuple[str, ...]
    session_items: tuple[SessionBufferItem, ...]

    @property
    def context_refs(self) -> tuple[str, ...]:
        memory_refs = tuple(
            f"memory:{row['memory_id']}" for row in self.memory if row.get("memory_id")
        )
        evidence = tuple(f"evidence:{ref}" for ref in self.evidence_refs)
        ephemeral = tuple(f"session:{item.item_id}" for item in self.session_items)
        return memory_refs + evidence + ephemeral


MemoryReader = Callable[..., list[dict[str, Any]]]


class ContextBuilder:
    """Build situated context with fail-closed scope and bitemporal guards."""

    def __init__(
        self,
        *,
        memory_reader: MemoryReader,
        session_buffer: SessionContextBuffer,
    ) -> None:
        self._memory_reader = memory_reader
        self._session_buffer = session_buffer

    def build(
        self,
        *,
        project_scope: str,
        valid_at: datetime,
        recorded_at: datetime,
        session_id: str,
        evidence_refs: tuple[str, ...] = (),
        now: datetime | None = None,
    ) -> ContextBundle:
        scope = project_scope.strip()
        if not scope:
            raise ValueError("project_scope is mandatory")
        valid = _as_utc(valid_at)
        recorded = _as_utc(recorded_at)
        rows = self._memory_reader(
            project_scope=scope,
            valid_at=valid,
            recorded_at=recorded,
        )
        safe_rows: list[dict[str, Any]] = []
        for raw in rows:
            row = dict(raw)
            if row.get("project_scope") != scope:
                raise ValueError("memory reader returned cross-project data")
            row_recorded = row.get("recorded_time")
            if row_recorded is not None and _as_utc(row_recorded) > recorded:
                continue
            valid_from = row.get("valid_from")
            valid_until = row.get("valid_until")
            if valid_from is not None and _as_utc(valid_from) > valid:
                continue
            if valid_until is not None and valid >= _as_utc(valid_until):
                continue
            safe_rows.append(row)
        active_session = self._session_buffer.active(
            session_id=session_id,
            project_scope=scope,
            as_of=now or datetime.now(timezone.utc),
        )
        return ContextBundle(
            project_scope=scope,
            valid_at=valid,
            recorded_at=recorded,
            memory=tuple(safe_rows),
            evidence_refs=tuple(evidence_refs),
            session_items=active_session,
        )


class CognitiveAdapter(Protocol):
    def invoke(
        self,
        request: CognitiveInvocationRequest,
        context: ContextBundle,
    ) -> CognitiveOutput: ...


class DeterministicReferenceAdapter:
    """Offline reference adapter used only for Alpha evaluation."""

    def __init__(
        self,
        *,
        content: str,
        epistemic_class: EpistemicClass,
        disposition: OutputDisposition,
        evidence_refs: tuple[str, ...] = (),
        material_effect: bool = False,
        tool_name: str | None = None,
    ) -> None:
        self._content = content
        self._epistemic_class = epistemic_class
        self._disposition = disposition
        self._evidence_refs = evidence_refs
        self._material_effect = material_effect
        self._tool_name = tool_name

    def invoke(
        self,
        request: CognitiveInvocationRequest,
        context: ContextBundle,
    ) -> CognitiveOutput:
        seed = {
            "request": request.model_dump(mode="json"),
            "context_refs": context.context_refs,
            "content": self._content,
            "epistemic_class": self._epistemic_class.value,
            "disposition": self._disposition.value,
            "evidence_refs": self._evidence_refs,
            "material_effect": self._material_effect,
            "tool_name": self._tool_name,
        }
        return CognitiveOutput(
            output_id=f"cout-{sha256_json(seed)[:24]}",
            content=self._content,
            epistemic_class=self._epistemic_class,
            disposition=self._disposition,
            evidence_refs=self._evidence_refs,
            provenance_refs=context.context_refs,
            tool_name=self._tool_name,
            material_effect=self._material_effect,
        )


@dataclass(frozen=True)
class CognitivePolicyDecision:
    action: PolicyAction
    canonical_write_allowed: bool
    material_action_executed: bool
    reason_codes: tuple[str, ...]


def evaluate_cognitive_output(output: CognitiveOutput) -> CognitivePolicyDecision:
    if output.disposition is OutputDisposition.TOOL_REQUEST:
        if output.material_effect:
            return CognitivePolicyDecision(
                PolicyAction.HOLD_R2,
                False,
                False,
                ("MATERIAL_EFFECT_REQUIRES_SEPARATE_R2",),
            )
        return CognitivePolicyDecision(
            PolicyAction.ALLOW_R1_TOOL_REQUEST,
            False,
            False,
            ("R1_NON_MATERIAL_TOOL_REQUEST_ONLY",),
        )
    if output.disposition is OutputDisposition.DECISION_PROPOSAL:
        return CognitivePolicyDecision(
            PolicyAction.PROPOSE_DECISION,
            False,
            False,
            ("DECISION_REMAINS_PROPOSED",),
        )
    if output.epistemic_class in {
        EpistemicClass.INFERENCE,
        EpistemicClass.HYPOTHESIS,
        EpistemicClass.WORKING_ASSUMPTION,
    }:
        if output.disposition is OutputDisposition.CLAIM_PROPOSAL:
            return CognitivePolicyDecision(
                PolicyAction.PROPOSE_CLAIM,
                False,
                False,
                ("INFERENCE_FREEDOM_CANONICAL_RESTRAINT",),
            )
        return CognitivePolicyDecision(
            PolicyAction.KEEP_EPHEMERAL,
            False,
            False,
            ("INFERENCE_STAYS_EPHEMERAL",),
        )
    if output.disposition is OutputDisposition.CLAIM_PROPOSAL:
        if (
            output.epistemic_class is EpistemicClass.DOCUMENTED_FACT
            and not output.evidence_refs
        ):
            return CognitivePolicyDecision(
                PolicyAction.DENY_ADMISSION,
                False,
                False,
                ("DOCUMENTED_FACT_REQUIRES_EVIDENCE",),
            )
        return CognitivePolicyDecision(
            PolicyAction.PROPOSE_CLAIM,
            False,
            False,
            ("MEMORY_ADMISSION_GATE_REQUIRED",),
        )
    return CognitivePolicyDecision(
        PolicyAction.KEEP_EPHEMERAL,
        False,
        False,
        ("NO_CANONICAL_TARGET_REQUESTED",),
    )


def execute_reference_cognitive_loop(
    *,
    request: CognitiveInvocationRequest,
    context: ContextBundle,
    adapter: CognitiveAdapter,
) -> dict[str, Any]:
    output = adapter.invoke(request, context)
    policy = evaluate_cognitive_output(output)
    body = {
        "invocation_id": request.invocation_id,
        "project_scope": context.project_scope,
        "valid_at": context.valid_at.isoformat(),
        "recorded_at": context.recorded_at.isoformat(),
        "context_refs": list(context.context_refs),
        "output": output.model_dump(mode="json"),
        "policy": {
            "action": policy.action.value,
            "canonical_write_allowed": policy.canonical_write_allowed,
            "material_action_executed": policy.material_action_executed,
            "reason_codes": list(policy.reason_codes),
        },
        "external_provider_calls": 0,
    }
    return {**body, "receipt_sha256": sha256_json(body)}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime values must be timezone-aware")
    return value.astimezone(timezone.utc)
