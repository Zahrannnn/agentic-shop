"""Graph assembly: the fixed 7-node backbone (DECISIONS.md D6, research R3).

::

    START → intent → clarify_gate ──(ask)───────→ ui_agent_ask ──→ END   (US2)
                        │
                        ├────────(disclose)─────→ ui_plan ──→ respond → END  (US4)
                        │
                 (proceed)→ search → research → recommend → ui_plan → respond → END

``clarify_gate`` is the only conditional edge. Its router
(:func:`app.graph.nodes.clarify_decision`) implements the R7 rule table:
unknown/missing category asks exactly once (the ask turn ends the turn), and
``asked_clarification`` forces every later turn to proceed. A US4 follow-up
whose targets cannot be resolved routes straight to ``ui_plan`` for the clean
deterministic disclosure — the intermediate nodes are skipped so their
budget/category defaults never record spurious assumptions into the session
intent. Resolvable follow-ups ride the normal proceed pipeline.

The compiled graph uses ``MemorySaver`` keyed on ``thread_id`` = session id
(in-memory by design; a restart means fresh sessions). ``get_graph`` caches
the compiled instance module-wide; ``reset_graph_cache`` exists for tests.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes import (
    clarify_decision,
    clarify_gate,
    intent_node,
    recommend_node,
    research_node,
    respond_node,
    search_node,
    ui_agent_ask,
    ui_plan_node,
)
from app.graph.state import ShoppingState

_compiled_graph: CompiledStateGraph | None = None


def build_graph() -> CompiledStateGraph:
    """Wire the backbone and compile it with an in-memory checkpointer."""
    graph: StateGraph = StateGraph(ShoppingState)
    graph.add_node("intent", intent_node)
    graph.add_node("clarify_gate", clarify_gate)
    graph.add_node("ui_agent_ask", ui_agent_ask)
    graph.add_node("search", search_node)
    graph.add_node("research", research_node)
    graph.add_node("recommend", recommend_node)
    graph.add_node("ui_plan", ui_plan_node)
    graph.add_node("respond", respond_node)

    graph.add_edge(START, "intent")
    graph.add_edge("intent", "clarify_gate")
    graph.add_conditional_edges(
        "clarify_gate",
        clarify_decision,
        {"ask": "ui_agent_ask", "disclose": "ui_plan", "proceed": "search"},
    )
    graph.add_edge("ui_agent_ask", END)
    graph.add_edge("search", "research")
    graph.add_edge("research", "recommend")
    graph.add_edge("recommend", "ui_plan")
    graph.add_edge("ui_plan", "respond")
    graph.add_edge("respond", END)

    return graph.compile(checkpointer=MemorySaver())


def get_graph() -> CompiledStateGraph:
    """Return the cached compiled graph, building it on first use."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def reset_graph_cache() -> None:
    """Drop the cached compiled graph (test hook)."""
    global _compiled_graph
    _compiled_graph = None
