import json

from graph.state import IncidentState, IssueSeverity, SeverityResult
from llm.client import chat_json

_SYSTEM = """You are a senior SRE performing incident severity triage.

Given classified issues from a production log, assess severity for each one by reasoning about:
1. Environment signals — "prod", "production" in names = higher severity
2. Service criticality — payment, auth, order = critical; notification, logging = lower
3. Blast radius — how many services/users are affected (look at cascading errors)
4. Error frequency and persistence in the log

Severity levels:
- P0: full outage, revenue blocked, data loss risk — escalate immediately
- P1: major degradation, significant user impact, SLA at risk
- P2: partial degradation, subset of users affected, workarounds exist
- P3: minor issue, cosmetic or rare edge case

Return ONLY valid JSON:
{
  "per_issue": [
    {"issue_type": "OOM_KILL", "severity": "P1", "justification": "2-3 sentence chain-of-thought reasoning"}
  ],
  "overall_severity": "P1",
  "overall_justification": "1-2 sentences identifying the worst issue driving overall severity"
}"""


def reason_severity(state: IncidentState) -> dict:
    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": f"Classified issues to triage:\n{json.dumps(state['classifications'], indent=2)}",
        },
    ]
    data = chat_json(messages)
    severity = SeverityResult(
        per_issue=[IssueSeverity(**i) for i in data["per_issue"]],
        overall_severity=data["overall_severity"],
        overall_justification=data["overall_justification"],
    )
    return {"severity": severity.model_dump()}
