"""Bounded LangGraph state for one turn run.

The graph state contains serializable, bounded artifacts only.  The current
``GameState``, provider adapter, ORM session and full transcript are runtime
dependencies owned by the pipeline, never checkpointed as graph state.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class TurnGraphState(TypedDict):
    """The durable hand-off between bounded turn nodes.

    Values are deliberately named after the contracts in ``docs/plan.md``.
    Pydantic/domain objects are allowed as values because the configured
    checkpointer serializes them, but no object here owns an open resource.
    """

    turn_run_id: str
    playthrough_id: str
    branch_id: str
    base_revision: int
    raw_input: str
    actor_id: str
    parent_turn_id: str | None
    config_snapshot_id: str
    retry_counters: dict[str, int]
    errors: tuple[dict[str, Any], ...]
    warnings: tuple[dict[str, Any], ...]
    node_events: tuple[dict[str, Any], ...]
    llm_traces: tuple[dict[str, Any], ...]
    physical_call_traces: tuple[dict[str, Any], ...]
    derived_job_intents: tuple[dict[str, Any], ...]
    status: str
    guard_approved: bool
    guard_error: dict[str, Any] | None
    repair_requested: bool
    repair_feedback: NotRequired[dict[str, Any]]
    revision_count: int
    commit_done: bool
    derived_jobs_queued: bool
    cancellation_requested: bool
    normalized_input: NotRequired[str]
    input_safety: NotRequired[dict[str, Any]]
    context_manifest: NotRequired[dict[str, Any]]
    plan: NotRequired[Any]
    simulation: NotRequired[Any]
    claim_extraction: NotRequired[Any]
    targeted_evidence: NotRequired[tuple[dict[str, Any], ...]]
    consistency_report: NotRequired[Any]
    approved_patch: NotRequired[dict[str, Any] | None]
    scene_spec: NotRequired[Any]
    draft: NotRequired[Any]
    critique: NotRequired[Any]
    final_narrative: NotRequired[str]
    canonical_bundle: NotRequired[Any]
    committed_turn: NotRequired[Any]


def initial_graph_state(
    *,
    turn_run_id: str,
    playthrough_id: str,
    branch_id: str,
    base_revision: int,
    raw_input: str,
    actor_id: str,
    parent_turn_id: str | None = None,
    config_snapshot_id: str = "default",
) -> TurnGraphState:
    """Create the small initial state passed to LangGraph."""

    return {
        "turn_run_id": turn_run_id,
        "playthrough_id": playthrough_id,
        "branch_id": branch_id,
        "base_revision": base_revision,
        "parent_turn_id": parent_turn_id,
        "raw_input": raw_input,
        "actor_id": actor_id,
        "config_snapshot_id": config_snapshot_id,
        "retry_counters": {},
        "errors": (),
        "warnings": (),
        "node_events": (),
        "llm_traces": (),
        "physical_call_traces": (),
        "derived_job_intents": (),
        "status": "running",
        "guard_approved": False,
        "guard_error": None,
        "repair_requested": False,
        "revision_count": 0,
        "commit_done": False,
        "derived_jobs_queued": False,
        "cancellation_requested": False,
    }


__all__ = ["TurnGraphState", "initial_graph_state"]
