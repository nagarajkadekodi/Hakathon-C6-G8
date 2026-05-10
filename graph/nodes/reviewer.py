import json

from graph.state import IncidentState
from llm.client import chat_json, get_reviewer_model

_SYSTEM = """You are a senior incident response expert conducting a peer review of an AI-generated DevOps incident analysis.

A different AI model produced the analysis. Your job is to critically evaluate its quality and flag anything that needs attention.

Review these four dimensions:
1. Classification accuracy — Were all issues correctly identified from the log? Any missed? Any false positives?
2. Severity calibration — Is the severity appropriate given service names, error frequency, and blast radius? Payment/auth/order services are revenue-critical and typically warrant higher severity.
3. Remediation quality — Are fix steps specific and grounded in the actual log evidence? Generic steps ("restart the service") without log-specific context are a red flag.
4. Completeness — Is there anything important missing? Cascading effects between co-occurring issues?

Be a constructive critic. Your review helps an engineer decide how much to trust this analysis.

Return ONLY valid JSON:
{
  "score": 8.5,
  "verdict": "approved",
  "severity_assessment": "accurate",
  "suggested_severity": null,
  "flags": ["..."],
  "missed_issues": ["..."],
  "strengths": ["..."],
  "reviewer_summary": "2-3 sentence overall assessment of the analysis quality"
}

Rules:
- score: float 1.0-10.0
- verdict: "approved" if score >= 7.5 AND severity is not underestimated, else "needs_review"
- severity_assessment: "accurate" | "underestimated" | "overestimated"
- suggested_severity: the P-level you would assign (P0/P1/P2/P3), or null if you agree with the analysis
- flags: list of specific concerns — be precise, reference actual service names and issue types
- missed_issues: issues visible in the log that the classifier did not catch (empty list if none)
- strengths: what the analysis got right (at least 1 item)
- reviewer_summary: plain English verdict for the human reader"""


def ai_review(state: IncidentState) -> dict:
    reviewer_model = get_reviewer_model()
    print(reviewer_model)

    context = {
        "incident_id": state["incident_id"],
        "raw_log_excerpt": "\n".join(state["raw_log"].splitlines()[:60]),
        "classifications": state["classifications"],
        "severity": state["severity"],
        "remediation": state["remediation"],
        "summary": state["artifacts"]["summary"] if state["artifacts"] else "",
    }

    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": f"Review this incident analysis:\n\n{json.dumps(context, indent=2)}",
        },
    ]

    try:
        data = chat_json(messages, model=reviewer_model)
    except Exception as exc:
        print(f"[ai_review] reviewer model failed: {exc}")
        return {"review": None}

    try:
        score = float(data.get("score") or 5.0)
    except (TypeError, ValueError):
        score = 5.0

    review = {
        "score": score,
        "verdict": data.get("verdict") or "needs_review",
        "severity_assessment": data.get("severity_assessment") or "unknown",
        "suggested_severity": data.get("suggested_severity"),
        "flags": data.get("flags") or [],
        "missed_issues": data.get("missed_issues") or [],
        "strengths": data.get("strengths") or [],
        "reviewer_summary": data.get("reviewer_summary") or "",
        "reviewer_model": reviewer_model,
    }

    return {"review": review}
