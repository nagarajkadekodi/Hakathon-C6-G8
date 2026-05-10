import json

from graph.state import IncidentState, RemediationPlan, RemediationStep
from llm.client import chat_json

_SYSTEM = """You are a senior DevOps engineer writing incident remediation plans.

For each classified issue produce concrete, ordered fix steps grounded in the actual log evidence.
Reference actual service names and error details from the data — never give generic advice.

Each step must have:
- step_number: integer starting at 1
- action: specific concrete action (mention real service names, values from the log)
- estimated_time_min: realistic time in minutes
- owner_role: who executes this (e.g. "On-call engineer", "Platform team", "Service owner")
- runbook_slug: short kebab-case reference slug (e.g. "k8s-oom-recovery", "pg-pool-exhaustion")

Return ONLY valid JSON:
{
  "plans": [
    {
      "issue_type": "OOM_KILL",
      "steps": [
        {"step_number": 1, "action": "...", "estimated_time_min": 5, "owner_role": "...", "runbook_slug": "..."}
      ]
    }
  ]
}

Order steps by urgency: immediate mitigation first, root cause investigation last."""


def map_remediation(state: IncidentState) -> dict:
    payload = {
        "classifications": state["classifications"],
        "severity": state["severity"],
    }
    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": f"Create remediation plans for:\n{json.dumps(payload, indent=2)}",
        },
    ]
    data = chat_json(messages)
    plans = [
        RemediationPlan(
            issue_type=p["issue_type"],
            steps=[RemediationStep(**s) for s in p["steps"]],
        ).model_dump()
        for p in data.get("plans", [])
    ]
    return {"remediation": plans}
