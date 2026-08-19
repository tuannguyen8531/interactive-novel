"""LangGraph topology for the bounded turn pipeline."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from src.application.contracts.ai import ConsistencyStatus, CritiqueDecision, CritiqueResult

from .nodes import TurnGraphNodes
from .runtime import TurnGraphRuntime
from .state import TurnGraphState


def build_turn_graph(runtime: TurnGraphRuntime, *, checkpointer: Any = None) -> Any:
    """Compile one graph whose runtime dependencies are closure-owned."""

    nodes = TurnGraphNodes(runtime)
    builder = StateGraph(TurnGraphState)
    builder.add_node("normalize_input", nodes.normalize_input)
    builder.add_node("build_initial_context", nodes.build_initial_context)
    builder.add_node("plan", nodes.plan)
    builder.add_node("simulate", nodes.simulate)
    builder.add_node("extract_claims", nodes.extract_claims)
    builder.add_node("retrieve_targeted_evidence", nodes.retrieve_targeted_evidence)
    builder.add_node("validate_context", nodes.validate_context)
    builder.add_node("guard_state", nodes.guard_state)
    builder.add_node("repair", nodes.repair)
    builder.add_node("write", nodes.write)
    builder.add_node("critique", nodes.critique)
    builder.add_node("revise", nodes.revise)
    builder.add_node("build_canonical_records", nodes.build_canonical_records)
    builder.add_node("commit", nodes.commit)
    builder.add_node("enqueue_derived_jobs", nodes.enqueue_derived_jobs)

    builder.add_edge(START, "normalize_input")
    builder.add_conditional_edges(
        "normalize_input",
        _running_or_finish,
        {"continue": "build_initial_context", "finish": END},
    )
    builder.add_conditional_edges(
        "build_initial_context",
        _running_or_finish,
        {"continue": "plan", "finish": END},
    )
    builder.add_conditional_edges(
        "plan",
        _after_plan,
        {"simulate": "simulate", "extract": "extract_claims", "finish": END},
    )
    builder.add_conditional_edges(
        "simulate",
        _running_or_finish,
        {"continue": "extract_claims", "finish": END},
    )
    builder.add_conditional_edges(
        "extract_claims",
        _running_or_finish,
        {"continue": "retrieve_targeted_evidence", "finish": END},
    )
    builder.add_conditional_edges(
        "retrieve_targeted_evidence",
        _running_or_finish,
        {"continue": "validate_context", "finish": END},
    )
    builder.add_conditional_edges(
        "validate_context",
        lambda state: _after_validate(state, nodes.runtime.max_repair_attempts),
        {"guard": "guard_state", "repair": "repair", "finish": END},
    )
    builder.add_conditional_edges(
        "guard_state",
        lambda state: _after_guard(state, nodes.runtime.max_repair_attempts),
        {"write": "write", "repair": "repair", "finish": END},
    )
    builder.add_conditional_edges(
        "repair",
        _after_repair,
        {"simulate": "simulate", "finish": END},
    )
    builder.add_conditional_edges(
        "write",
        _running_or_finish,
        {"continue": "critique", "finish": END},
    )
    builder.add_conditional_edges(
        "critique",
        lambda state: _after_critique(state, nodes.runtime.max_revision_attempts),
        {"records": "build_canonical_records", "revise": "revise", "finish": END},
    )
    builder.add_conditional_edges(
        "revise",
        _running_or_finish,
        {"continue": "write", "finish": END},
    )
    builder.add_conditional_edges(
        "build_canonical_records",
        _running_or_finish,
        {"continue": "commit", "finish": END},
    )
    builder.add_conditional_edges(
        "commit",
        lambda state: "enqueue" if state.get("commit_done", False) else "finish",
        {"enqueue": "enqueue_derived_jobs", "finish": END},
    )
    builder.add_edge("enqueue_derived_jobs", END)
    return builder.compile(checkpointer=checkpointer, name="turn-pipeline")


def _running_or_finish(state: TurnGraphState) -> str:
    return "continue" if state.get("status", "running") == "running" else "finish"


def _after_plan(state: TurnGraphState) -> str:
    if state.get("status", "running") != "running":
        return "finish"
    return "extract" if state.get("simulation") is not None else "simulate"


def _after_validate(state: TurnGraphState, max_repairs: int) -> str:
    if state.get("status", "running") != "running":
        return "finish"
    report = state.get("consistency_report")
    if report is not None and getattr(report, "status", None) == ConsistencyStatus.PASS:
        return "guard"
    if state.get("retry_counters", {}).get("repair", 0) < max_repairs:
        return "repair"
    return "finish"


def _after_guard(state: TurnGraphState, max_repairs: int) -> str:
    if state.get("status", "running") != "running":
        return "finish"
    if state.get("guard_approved", False):
        return "write"
    if state.get("retry_counters", {}).get("repair", 0) < max_repairs:
        return "repair"
    return "finish"


def _after_repair(state: TurnGraphState) -> str:
    return "simulate" if state.get("status", "running") == "running" else "finish"


def _after_critique(state: TurnGraphState, max_revisions: int) -> str:
    if state.get("status", "running") != "running":
        return "finish"
    critique = state.get("critique")
    if not isinstance(critique, CritiqueResult):
        return "finish"
    if critique.decision == CritiqueDecision.ACCEPT:
        return "records"
    if critique.decision == CritiqueDecision.REVISE and state.get("revision_count", 0) < max_revisions:
        return "revise"
    return "finish"


__all__ = ["build_turn_graph"]
