from langgraph.graph import END, StateGraph

from graph.nodes.classifier import classify
from graph.nodes.formatter import format_outputs
from graph.nodes.remediation import map_remediation
from graph.nodes.reviewer import ai_review
from graph.nodes.severity import reason_severity
from graph.state import IncidentState


def build_pipeline():
    builder = StateGraph(IncidentState)
    builder.add_node("classify", classify)
    builder.add_node("reason_severity", reason_severity)
    builder.add_node("map_remediation", map_remediation)
    builder.add_node("format_outputs", format_outputs)
    builder.add_node("ai_review", ai_review)

    builder.set_entry_point("classify")
    builder.add_edge("classify", "reason_severity")
    builder.add_edge("reason_severity", "map_remediation")
    builder.add_edge("map_remediation", "format_outputs")
    builder.add_edge("format_outputs", "ai_review")
    builder.add_edge("ai_review", END)

    return builder.compile()


pipeline = build_pipeline()
