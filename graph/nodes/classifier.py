from graph.state import Classification, IncidentState
from llm.client import chat_json

_SYSTEM = """You are a DevOps incident analyst. Analyze the provided log text and identify all distinct issues.

For EACH issue found return an object with:
- issue_type: one of OOM_KILL, DB_TIMEOUT, DEPLOY_FAILURE, AUTH_ERROR, DISK_FULL, NETWORK_ERROR, UNKNOWN
- description: one clear sentence describing the issue
- affected_services: list of service/pod names involved (extract from log lines)
- evidence_lines: 2-3 exact log lines that are the strongest evidence (copy verbatim from the log)
- confidence: float 0.0-1.0 reflecting how certain you are

Return ONLY valid JSON: {"classifications": [...]}

Rules:
- Each distinct issue gets its own entry — do not merge unrelated issues
- Only include issues with actual log evidence, not inferred problems
- affected_services must be actual names found in the log, not generic names"""


def classify(state: IncidentState) -> dict:
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"Analyze this log:\n\n{state['raw_log']}"},
    ]
    data = chat_json(messages)
    classifications = [
        Classification(**c).model_dump() for c in data.get("classifications", [])
    ]
    return {"classifications": classifications}
