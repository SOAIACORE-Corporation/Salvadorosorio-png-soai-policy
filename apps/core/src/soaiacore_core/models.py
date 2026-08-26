from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectRequest(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    status: str = Field(default="ACTIVE", min_length=1, max_length=40)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CorpusRequest(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdentityResolveRequest(StrictModel):
    observed_actor_id: str
    corpus_id: str
    source_local_ref: str | None = None
    display_label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime | None = None
    canonical_subject_id: str
    identity_resolution_status: str = "ADJUDICATED"
    subject_metadata: dict[str, Any] = Field(default_factory=dict)
    identity_claim_id: str
    claim_type: str = "LINK_CANDIDATE"
    confidence_class: str = "HIGH"
    identity_decision_id: str
    decision_type: Literal[
        "MERGE",
        "SPLIT",
        "LINK",
        "UNLINK",
        "KEEP_SEPARATE",
        "NEVER_MERGE",
        "PROVISIONAL_LINK",
        "REJECT_LINK",
    ] = "LINK"
    decided_by: str = "P0_MOCK"
    rationale_summary: str = "Deterministic P0 identity resolution"
    evidence_refs: list[str] = Field(default_factory=list)


class EvidenceRegisterRequest(StrictModel):
    source_id: str
    corpus_id: str
    source_type: str
    source_locator: str | None = None
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int | None = Field(default=None, ge=0)
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    evidence_id: str
    evidence_state: Literal[
        "REFERENCED",
        "INVENTORIED",
        "ACQUIRED",
        "FIXITY_VERIFIED",
        "PROCESSED",
        "VERIFIED",
        "ADMISSIBLE",
        "QUARANTINED",
        "SUPERSEDED",
        "REJECTED",
    ]
    object_locator: str | None = None
    modality: str = "TEXT"
    evidence_metadata: dict[str, Any] = Field(default_factory=dict)
    evidence_ref_id: str = Field(pattern=r"^evref_[A-Za-z0-9_-]+$")
    locator: str | None = None
    support_type: str = "DIRECT"
    relationship: str = "SUPPORTS"
    admissibility_scope: str = "P0_MOCK"
    excerpt_hash: str | None = None
    provenance_chain_ref: str | None = None


class ContextRequest(StrictModel):
    context_id: str
    project_id: str
    context_type: str
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    dimensions: dict[str, Any] = Field(default_factory=dict)


class ContextCapsuleRequest(StrictModel):
    context_capsule_id: str
    context_id: str
    schema_version: str = "P0-RUNTIME-1"
    payload: dict[str, Any]


class RunRequest(StrictModel):
    context_capsule_id: str
    analysis_profile_id: str = Field(pattern=r"^AP-[0-9]{3}$")
    analysis_profile_version: str
    purpose: str = Field(min_length=1, max_length=200)
    mode: Literal["MOCK", "REPLAY", "LIVE"] = "MOCK"
    mock_fixture_id: str = Field(min_length=1, max_length=100)


class TraverseRequest(StrictModel):
    start_ref: str
    max_depth: int = Field(default=4, ge=1, le=10)

