# Incident Analysis Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI + LangGraph MVP that accepts a plain-text log file, runs it through a 4-node agent pipeline, and returns 5 structured output artifacts (Slack card, JIRA ticket, checklist, summary, raw analysis) rendered in a styled web UI.

**Architecture:** Single FastAPI process serves the HTML UI and `/analyze` endpoint. LangGraph pipeline runs synchronously inside the request. Artifacts written to `outputs/{incident_id}/` and returned in the JSON response.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, LangGraph, openai SDK (OpenRouter), Pydantic v2, python-multipart, python-dotenv, vanilla HTML/CSS/JS.

---

## File Map

| File | Responsibility |
|------|---------------|
| `requirements.txt` | Pinned dependencies |
| `.env.example` | Env var template |
| `.gitignore` | Ignore outputs/, .env |
| `llm/client.py` | OpenRouter chat wrapper |
| `graph/state.py` | IncidentState TypedDict + Pydantic models |
| `graph/nodes/classifier.py` | Node 1: classify log lines into issue types |
| `graph/nodes/severity.py` | Node 2: P0–P3 severity with justification |
| `graph/nodes/remediation.py` | Node 3: ordered fix steps per issue |
| `graph/nodes/formatter.py` | Node 4: build all 5 artifacts |
| `graph/pipeline.py` | Compile LangGraph StateGraph |
| `main.py` | FastAPI routes + artifact file I/O |
| `static/index.html` | Full upload UI + 5 result cards |
| `sample_logs/incident.log` | Synthetic 3-issue demo log |

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `llm/__init__.py`
- Create: `graph/__init__.py`
- Create: `graph/nodes/__init__.py`
- Create: `sample_logs/` (directory)
- Create: `static/` (directory)

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.5
uvicorn==0.32.1
langgraph==0.2.53
langchain-core==0.3.25
openai==1.58.1
pydantic==2.10.3
python-multipart==0.0.20
python-dotenv==1.0.1
```

- [ ] **Step 2: Create .env.example**

```
OPENROUTER_API_KEY=sk-or-your-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-sonnet-4-6
```

- [ ] **Step 3: Create .gitignore**

```
.env
outputs/
__pycache__/
*.pyc
.venv/
```

- [ ] **Step 4: Create empty __init__.py files and directories**

```bash
mkdir -p llm graph/nodes static sample_logs outputs
touch llm/__init__.py graph/__init__.py graph/nodes/__init__.py
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: All packages install without error.

- [ ] **Step 6: Copy .env.example to .env and fill in your OpenRouter key**

```bash
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY
```

- [ ] **Step 7: Commit scaffold**

```bash
git add requirements.txt .env.example .gitignore llm/__init__.py graph/__init__.py graph/nodes/__init__.py
git commit -m "feat: project scaffold for incident analysis suite"
```

---

## Task 2: LLM Client

**Files:**
- Create: `llm/client.py`

- [ ] **Step 1: Write llm/client.py**

```python
import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=os.getenv("OPENROUTER_API_KEY"),
            default_headers={
                "HTTP-Referer": "https://devops-incident-analyzer.local",
                "X-Title": "DevOps Incident Analyzer",
            },
        )
    return _client


def get_model() -> str:
    return os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-6")


def extract_json(text: str) -> str:
    """Strip markdown code fences if the model wrapped JSON in them."""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    return text.strip()


def chat(messages: list[dict], json_mode: bool = False) -> str:
    """Send messages to OpenRouter and return the response text."""
    client = _get_client()
    kwargs: dict = {
        "model": get_model(),
        "messages": messages,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def chat_json(messages: list[dict]) -> dict:
    """Send messages and parse response as JSON. Retries once on parse failure."""
    for attempt in range(2):
        try:
            raw = chat(messages, json_mode=True)
            return json.loads(extract_json(raw))
        except (json.JSONDecodeError, Exception) as e:
            if attempt == 1:
                raise RuntimeError(f"JSON parse failed after 2 attempts: {e}\nRaw: {raw}")
    return {}
```

- [ ] **Step 2: Smoke-test the client manually**

```bash
python -c "
from llm.client import chat
r = chat([{'role':'user','content':'Say hello in one word.'}])
print(r)
"
```

Expected: A single word reply from the model, no errors.

- [ ] **Step 3: Commit**

```bash
git add llm/client.py
git commit -m "feat: OpenRouter LLM client with JSON extraction"
```

---

## Task 3: State Models

**Files:**
- Create: `graph/state.py`

- [ ] **Step 1: Write graph/state.py**

```python
from typing import TypedDict, Optional
from pydantic import BaseModel


class Classification(BaseModel):
    issue_type: str  # OOM_KILL | DB_TIMEOUT | DEPLOY_FAILURE | AUTH_ERROR | DISK_FULL | NETWORK_ERROR | UNKNOWN
    description: str
    affected_services: list[str]
    evidence_lines: list[str]
    confidence: float  # 0.0–1.0


class IssueSeverity(BaseModel):
    issue_type: str
    severity: str  # P0 | P1 | P2 | P3
    justification: str


class SeverityResult(BaseModel):
    per_issue: list[IssueSeverity]
    overall_severity: str
    overall_justification: str


class RemediationStep(BaseModel):
    step_number: int
    action: str
    estimated_time_min: int
    owner_role: str
    runbook_slug: str


class RemediationPlan(BaseModel):
    issue_type: str
    steps: list[RemediationStep]


class IncidentState(TypedDict):
    incident_id: str
    raw_log: str
    classifications: list[dict]   # Classification dicts after Node 1
    severity: Optional[dict]      # SeverityResult dict after Node 2
    remediation: list[dict]       # RemediationPlan dicts after Node 3
    artifacts: Optional[dict]     # ArtifactBundle dict after Node 4
```

- [ ] **Step 2: Verify Pydantic models parse correctly**

```bash
python -c "
from graph.state import Classification
c = Classification(
    issue_type='OOM_KILL',
    description='test',
    affected_services=['svc-a'],
    evidence_lines=['OOMKilled'],
    confidence=0.95
)
print(c.model_dump())
"
```

Expected: Dict printed with all 5 fields.

- [ ] **Step 3: Commit**

```bash
git add graph/state.py
git commit -m "feat: IncidentState TypedDict and Pydantic models"
```

---

## Task 4: Classifier Node

**Files:**
- Create: `graph/nodes/classifier.py`

- [ ] **Step 1: Write graph/nodes/classifier.py**

```python
import json
from graph.state import IncidentState, Classification
from llm.client import chat_json

_SYSTEM = """You are a DevOps incident analyst. Analyze the provided log text and identify all distinct issues.

For EACH issue found return an object with:
- issue_type: one of OOM_KILL, DB_TIMEOUT, DEPLOY_FAILURE, AUTH_ERROR, DISK_FULL, NETWORK_ERROR, UNKNOWN
- description: one sentence describing the issue
- affected_services: list of service/pod names involved
- evidence_lines: 2-3 exact log lines that are the clearest evidence (copy verbatim)
- confidence: float 0.0-1.0

Return ONLY valid JSON: {"classifications": [...]}"""


def classify(state: IncidentState) -> dict:
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"Log to analyze:\n\n{state['raw_log']}"},
    ]
    data = chat_json(messages)
    classifications = [
        Classification(**c).model_dump() for c in data.get("classifications", [])
    ]
    return {"classifications": classifications}
```

- [ ] **Step 2: Quick integration test with sample text**

```bash
python -c "
from graph.nodes.classifier import classify
state = {
    'incident_id': 'test-1',
    'raw_log': '2026-05-09 ERROR payment-service OOMKilled: container exceeded 512Mi\n2026-05-09 WARN kubelet CrashLoopBackOff on payment-service',
    'classifications': [], 'severity': None, 'remediation': [], 'artifacts': None
}
result = classify(state)
import json; print(json.dumps(result, indent=2))
"
```

Expected: JSON with at least 1 classification, `issue_type` = `OOM_KILL`.

- [ ] **Step 3: Commit**

```bash
git add graph/nodes/classifier.py
git commit -m "feat: classifier node — issue type detection"
```

---

## Task 5: Severity Reasoner Node

**Files:**
- Create: `graph/nodes/severity.py`

- [ ] **Step 1: Write graph/nodes/severity.py**

```python
import json
from graph.state import IncidentState, SeverityResult, IssueSeverity
from llm.client import chat_json

_SYSTEM = """You are a senior SRE performing incident severity triage.

Given a list of classified issues, for each one reason about:
1. Environment signals (prod/staging keywords in service names or log text)
2. Service criticality (payment, auth, order = high; notification, logging = lower)
3. Blast radius: how many services/users are affected
4. Error frequency and recency in the log

Assign severity:
- P0: full outage, revenue impact, data loss risk
- P1: major degradation, significant user impact
- P2: partial degradation, some users affected
- P3: minor issue, cosmetic or edge-case

Return ONLY valid JSON:
{
  "per_issue": [{"issue_type": "...", "severity": "P1", "justification": "2-3 sentence reasoning"}],
  "overall_severity": "P1",
  "overall_justification": "1-2 sentences on the worst issue driving overall severity"
}"""


def reason_severity(state: IncidentState) -> dict:
    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": f"Classified issues:\n{json.dumps(state['classifications'], indent=2)}",
        },
    ]
    data = chat_json(messages)
    severity = SeverityResult(
        per_issue=[IssueSeverity(**i) for i in data["per_issue"]],
        overall_severity=data["overall_severity"],
        overall_justification=data["overall_justification"],
    )
    return {"severity": severity.model_dump()}
```

- [ ] **Step 2: Commit**

```bash
git add graph/nodes/severity.py
git commit -m "feat: severity reasoner node — P0-P3 with chain-of-thought"
```

---

## Task 6: Remediation Mapper Node

**Files:**
- Create: `graph/nodes/remediation.py`

- [ ] **Step 1: Write graph/nodes/remediation.py**

```python
import json
from graph.state import IncidentState, RemediationPlan, RemediationStep
from llm.client import chat_json

_SYSTEM = """You are a senior DevOps engineer writing an incident remediation plan.

For each classified issue, produce concrete ordered fix steps grounded in the log evidence.
Each step must have:
- step_number: integer starting at 1
- action: specific, concrete action (not generic advice — reference actual service names and error details)
- estimated_time_min: realistic time in minutes
- owner_role: who executes this (e.g., "On-call engineer", "Platform team", "Service owner")
- runbook_slug: short kebab-case reference (e.g., "k8s-oom-recovery", "pg-pool-exhaustion")

Return ONLY valid JSON:
{
  "plans": [
    {
      "issue_type": "OOM_KILL",
      "steps": [{"step_number": 1, "action": "...", "estimated_time_min": 5, "owner_role": "...", "runbook_slug": "..."}]
    }
  ]
}"""


def map_remediation(state: IncidentState) -> dict:
    payload = {
        "classifications": state["classifications"],
        "severity": state["severity"],
    }
    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": f"Incident data:\n{json.dumps(payload, indent=2)}",
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
```

- [ ] **Step 2: Commit**

```bash
git add graph/nodes/remediation.py
git commit -m "feat: remediation mapper node — ordered fix steps per issue"
```

---

## Task 7: Output Formatter Node

**Files:**
- Create: `graph/nodes/formatter.py`

- [ ] **Step 1: Write graph/nodes/formatter.py**

```python
import json
from graph.state import IncidentState
from llm.client import chat

_SUMMARY_SYSTEM = """You are writing a concise incident summary for a technical on-call audience.
Write exactly 3-5 sentences covering: what happened, which services are affected, overall severity, and immediate next step.
Be specific — reference actual service names, error types, and severity levels from the data. No generic filler."""


def format_outputs(state: IncidentState) -> dict:
    context = {
        "incident_id": state["incident_id"],
        "classifications": state["classifications"],
        "severity": state["severity"],
        "remediation": state["remediation"],
    }

    summary = _generate_summary(context)
    slack_card = _build_slack_card(context, summary)
    jira_ticket = _build_jira_ticket(context, summary)
    checklist = _build_checklist(context)
    analysis = {**context, "summary": summary}

    artifacts = {
        "summary": summary,
        "slack_card": slack_card,
        "jira_ticket": jira_ticket,
        "checklist": checklist,
        "analysis": analysis,
    }
    return {"artifacts": artifacts}


def _generate_summary(ctx: dict) -> str:
    messages = [
        {"role": "system", "content": _SUMMARY_SYSTEM},
        {"role": "user", "content": f"Incident data:\n{json.dumps(ctx, indent=2)}"},
    ]
    return chat(messages)


def _build_slack_card(ctx: dict, summary: str) -> dict:
    sev = ctx["severity"]["overall_severity"]
    emoji = {"P0": ":rotating_light:", "P1": ":red_circle:", "P2": ":large_yellow_circle:", "P3": ":large_green_circle:"}.get(sev, ":white_circle:")

    issue_lines = []
    for c in ctx["classifications"]:
        sev_item = next((i for i in ctx["severity"]["per_issue"] if i["issue_type"] == c["issue_type"]), {})
        issue_lines.append(f"• *{c['issue_type']}* on `{', '.join(c['affected_services'])}` — {sev_item.get('severity', '?')} (confidence: {int(c['confidence']*100)}%)")

    return {
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"{emoji} {sev} Incident — {ctx['incident_id']}"}},
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": summary}},
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Issues Identified:*\n" + "\n".join(issue_lines)}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Overall Severity:*\n{sev}"},
                    {"type": "mrkdwn", "text": f"*Issues Found:*\n{len(ctx['classifications'])}"},
                ],
            },
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "View Runbook"}, "style": "primary", "value": "view_runbook"},
                    {"type": "button", "text": {"type": "plain_text", "text": "Acknowledge"}, "value": "acknowledge"},
                    {"type": "button", "text": {"type": "plain_text", "text": "Escalate"}, "style": "danger", "value": "escalate"},
                ],
            },
        ],
        "text": f"{sev} Incident: {ctx['incident_id']}",
    }


def _build_jira_ticket(ctx: dict, summary: str) -> dict:
    sev = ctx["severity"]["overall_severity"]
    priority_map = {"P0": "Critical", "P1": "High", "P2": "Medium", "P3": "Low"}
    affected = list({svc for c in ctx["classifications"] for svc in c["affected_services"]})

    desc_lines = [
        "h2. Incident Summary", summary, "",
        "h2. Issues Detected",
    ]
    for c in ctx["classifications"]:
        sev_item = next((i for i in ctx["severity"]["per_issue"] if i["issue_type"] == c["issue_type"]), {})
        desc_lines += [
            f"h3. {c['issue_type']} — {sev_item.get('severity', '?')}",
            f"*Services:* {', '.join(c['affected_services'])}",
            f"*Description:* {c['description']}",
            f"*Justification:* {sev_item.get('justification', '')}",
            "",
        ]
    desc_lines += ["h2. Remediation", "See attached checklist for ordered fix steps."]

    return {
        "fields": {
            "project": {"key": "OPS"},
            "summary": f"[{sev}] {ctx['incident_id']} — {len(ctx['classifications'])} issues on {', '.join(affected[:3])}",
            "description": "\n".join(desc_lines),
            "issuetype": {"name": "Incident"},
            "priority": {"name": priority_map.get(sev, "Medium")},
            "labels": ["incident", sev.lower(), "auto-generated"] + [c["issue_type"].lower() for c in ctx["classifications"]],
            "components": [{"name": "Platform"}, {"name": "On-Call"}],
            "customfield_affected_services": affected,
        }
    }


def _build_checklist(ctx: dict) -> str:
    sev = ctx["severity"]["overall_severity"]
    lines = [
        f"# Remediation Checklist — {ctx['incident_id']}",
        f"**Overall Severity:** {sev}  |  **Issues:** {len(ctx['classifications'])}",
        "", "---", "",
    ]
    for plan in ctx["remediation"]:
        cls = next((c for c in ctx["classifications"] if c["issue_type"] == plan["issue_type"]), {})
        sev_item = next((i for i in ctx["severity"]["per_issue"] if i["issue_type"] == plan["issue_type"]), {})
        lines += [
            f"## {plan['issue_type']} — {sev_item.get('severity', '?')}",
            f"**Services:** {', '.join(cls.get('affected_services', []))}",
            "",
        ]
        for step in plan["steps"]:
            lines += [
                f"- [ ] **Step {step['step_number']}:** {step['action']}",
                f"  - Owner: {step['owner_role']}  |  Est. time: {step['estimated_time_min']} min  |  Runbook: `{step['runbook_slug']}`",
                "",
            ]
        lines.append("")
    lines += [
        "---", "", "## Post-Incident", "",
        "- [ ] Confirm all services are stable",
        "- [ ] Write post-mortem within 48 hours",
        "- [ ] Update runbooks with learnings",
        "- [ ] Schedule blameless retrospective", "",
    ]
    return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add graph/nodes/formatter.py
git commit -m "feat: output formatter node — 5 artifacts (Slack, JIRA, checklist, summary, analysis)"
```

---

## Task 8: LangGraph Pipeline

**Files:**
- Create: `graph/pipeline.py`

- [ ] **Step 1: Write graph/pipeline.py**

```python
from langgraph.graph import StateGraph, END
from graph.state import IncidentState
from graph.nodes.classifier import classify
from graph.nodes.severity import reason_severity
from graph.nodes.remediation import map_remediation
from graph.nodes.formatter import format_outputs


def build_pipeline():
    builder = StateGraph(IncidentState)
    builder.add_node("classify", classify)
    builder.add_node("reason_severity", reason_severity)
    builder.add_node("map_remediation", map_remediation)
    builder.add_node("format_outputs", format_outputs)

    builder.set_entry_point("classify")
    builder.add_edge("classify", "reason_severity")
    builder.add_edge("reason_severity", "map_remediation")
    builder.add_edge("map_remediation", "format_outputs")
    builder.add_edge("format_outputs", END)

    return builder.compile()


pipeline = build_pipeline()
```

- [ ] **Step 2: Smoke-test the full pipeline end-to-end**

```bash
python -c "
from graph.pipeline import pipeline
state = {
    'incident_id': 'test-e2e',
    'raw_log': '''2026-05-09T07:46:23Z ERROR payment-service OOMKilled: container exceeded 512Mi
2026-05-09T07:47:12Z ERROR order-service PostgreSQL pool exhausted max=20 active=20''',
    'classifications': [], 'severity': None, 'remediation': [], 'artifacts': None
}
result = pipeline.invoke(state)
print('Severity:', result['severity']['overall_severity'])
print('Artifacts keys:', list(result['artifacts'].keys()))
"
```

Expected output:
```
Severity: P1
Artifacts keys: ['summary', 'slack_card', 'jira_ticket', 'checklist', 'analysis']
```

- [ ] **Step 3: Commit**

```bash
git add graph/pipeline.py
git commit -m "feat: LangGraph 4-node pipeline — classify → severity → remediate → format"
```

---

## Task 9: Sample Log File

**Files:**
- Create: `sample_logs/incident.log`

- [ ] **Step 1: Write sample_logs/incident.log**

```
2026-05-09T07:45:32Z INFO  payment-service     Deployment payment-service:v2.4.1 started by CI pipeline
2026-05-09T07:45:45Z INFO  payment-service     Container started, memory limit: 512Mi
2026-05-09T07:46:02Z WARN  payment-service     Memory usage at 89% (456Mi/512Mi)
2026-05-09T07:46:15Z WARN  payment-service     Memory usage at 97% (497Mi/512Mi)
2026-05-09T07:46:23Z ERROR payment-service     OOMKilled: container exceeded memory limit of 512Mi
2026-05-09T07:46:24Z ERROR payment-service     Pod payment-service-7d9f8b-xk2p9 terminated: OOMKilled
2026-05-09T07:46:25Z WARN  kubelet             Pod payment-service-7d9f8b-xk2p9 restarting (CrashLoopBackOff)
2026-05-09T07:46:30Z ERROR payment-service     OOMKilled: container exceeded memory limit of 512Mi
2026-05-09T07:46:31Z ERROR payment-service     Pod payment-service-7d9f8b-xk2p9 terminated: OOMKilled
2026-05-09T07:46:35Z WARN  kubelet             CrashLoopBackOff: back-off 30s restarting failed container
2026-05-09T07:46:40Z ERROR payment-service     OOMKilled: container exceeded memory limit of 512Mi
2026-05-09T07:46:41Z ERROR payment-service     Pod payment-service-7d9f8b-xk2p9 terminated: OOMKilled (restart #3)
2026-05-09T07:47:00Z INFO  prometheus          Alert FIRING: PodCrashLoopBackOff{service="payment-service", env="prod"}
2026-05-09T07:47:12Z ERROR order-service       Failed to acquire DB connection from pool: timeout after 5000ms
2026-05-09T07:47:12Z ERROR order-service       PostgreSQL connection pool exhausted (max=20, active=20, waiting=47)
2026-05-09T07:47:13Z ERROR order-service       Failed to acquire DB connection from pool: timeout after 5000ms
2026-05-09T07:47:14Z WARN  order-service       Retrying database connection (attempt 1/3)
2026-05-09T07:47:15Z ERROR order-service       Failed to acquire DB connection from pool: timeout after 5000ms
2026-05-09T07:47:16Z WARN  order-service       Retrying database connection (attempt 2/3)
2026-05-09T07:47:17Z ERROR order-service       Failed to acquire DB connection from pool: timeout after 5000ms
2026-05-09T07:47:18Z ERROR order-service       Max retries exceeded. Order creation failed for user_id=38291
2026-05-09T07:47:19Z ERROR order-service       Max retries exceeded. Order creation failed for user_id=29183
2026-05-09T07:47:20Z ERROR order-service       Max retries exceeded. Order creation failed for user_id=19283
2026-05-09T07:47:21Z ERROR order-service       Max retries exceeded. Order creation failed for user_id=84729
2026-05-09T07:47:22Z WARN  api-gateway         Upstream order-service returning 500: opening circuit breaker
2026-05-09T07:47:30Z INFO  order-service       Attempting to release idle connections from pool
2026-05-09T07:47:35Z ERROR order-service       Failed to acquire DB connection from pool: timeout after 5000ms
2026-05-09T07:47:36Z INFO  prometheus          Alert FIRING: DBConnectionPoolExhausted{service="order-service", env="prod"}
2026-05-09T07:48:01Z INFO  notification-service Deployment notification-service:v1.2.3 started
2026-05-09T07:48:05Z ERROR notification-service Failed to pull image: registry.prod.internal/notification-service:v1.2.3
2026-05-09T07:48:05Z ERROR notification-service ErrImagePull: rpc error: code=Unknown desc=failed to pull and unpack image: not found
2026-05-09T07:48:10Z WARN  kubelet             Back-off pulling image "registry.prod.internal/notification-service:v1.2.3"
2026-05-09T07:48:10Z ERROR notification-service ImagePullBackOff: waiting to retry image pull
2026-05-09T07:48:30Z ERROR notification-service Failed to pull image: registry.prod.internal/notification-service:v1.2.3
2026-05-09T07:48:30Z ERROR notification-service ErrImagePull: rpc error: code=Unknown desc=failed to pull and unpack image: not found
2026-05-09T07:48:35Z WARN  kubelet             Back-off pulling image "registry.prod.internal/notification-service:v1.2.3"
2026-05-09T07:48:50Z ERROR notification-service ImagePullBackOff: max retries exceeded, pod stuck in Pending
2026-05-09T07:49:01Z INFO  prometheus          Alert FIRING: ImagePullBackOff{service="notification-service", env="prod"}
2026-05-09T07:49:10Z INFO  alertmanager        Routing 3 alerts to #incidents channel
2026-05-09T07:49:10Z INFO  pagerduty           Paging on-call engineer: 3 simultaneous prod alerts
```

- [ ] **Step 2: Commit**

```bash
git add sample_logs/incident.log
git commit -m "feat: synthetic 3-issue demo log (OOMKill, DB pool exhaustion, ImagePullBackOff)"
```

---

## Task 10: FastAPI Application

**Files:**
- Create: `main.py`

- [ ] **Step 1: Write main.py**

```python
import io
import json
import os
import time
import uuid
import zipfile
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from graph.pipeline import pipeline
from graph.state import IncidentState
from llm.client import get_model

app = FastAPI(title="DevOps Incident Analyzer")

OUTPUTS_DIR = Path("outputs")
OUTPUTS_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    return Path("static/index.html").read_text(encoding="utf-8")


@app.get("/health")
async def health():
    return {"status": "ok", "model": get_model()}


@app.post("/analyze")
async def analyze(
    file: Optional[UploadFile] = File(default=None),
    log_text: Optional[str] = Form(default=None),
):
    if file and file.filename:
        raw_bytes = await file.read()
        raw_log = raw_bytes.decode("utf-8", errors="replace")
    elif log_text:
        raw_log = log_text
    else:
        return {"status": "error", "error_code": "EMPTY_LOG", "message": "Provide a file or paste log text."}

    if not raw_log.strip():
        return {"status": "error", "error_code": "EMPTY_LOG", "message": "Log content is empty."}

    incident_id = f"inc-{uuid.uuid4().hex[:8]}"
    start = time.time()

    initial: IncidentState = {
        "incident_id": incident_id,
        "raw_log": raw_log,
        "classifications": [],
        "severity": None,
        "remediation": [],
        "artifacts": None,
    }

    try:
        final = pipeline.invoke(initial)
    except Exception as e:
        return {"status": "error", "error_code": "PIPELINE_ERROR", "message": str(e)}

    artifacts = final["artifacts"]
    ms = int((time.time() - start) * 1000)

    incident_dir = OUTPUTS_DIR / incident_id
    incident_dir.mkdir(exist_ok=True)
    (incident_dir / "summary.txt").write_text(artifacts["summary"], encoding="utf-8")
    (incident_dir / "slack_card.json").write_text(json.dumps(artifacts["slack_card"], indent=2), encoding="utf-8")
    (incident_dir / "jira_ticket.json").write_text(json.dumps(artifacts["jira_ticket"], indent=2), encoding="utf-8")
    (incident_dir / "checklist.md").write_text(artifacts["checklist"], encoding="utf-8")
    (incident_dir / "analysis.json").write_text(json.dumps(artifacts["analysis"], indent=2), encoding="utf-8")

    return {
        "incident_id": incident_id,
        "status": "completed",
        "processing_time_ms": ms,
        "artifacts": artifacts,
    }


@app.get("/download/{incident_id}")
async def download(incident_id: str):
    incident_dir = OUTPUTS_DIR / incident_id
    if not incident_dir.exists():
        raise HTTPException(status_code=404, detail="Incident not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in incident_dir.iterdir():
            zf.write(f, f.name)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={incident_id}-artifacts.zip"},
    )
```

- [ ] **Step 2: Start the server and verify /health**

```bash
uvicorn main:app --reload --port 8000
```

In another terminal:
```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok","model":"anthropic/claude-sonnet-4-6"}`

- [ ] **Step 3: Test /analyze with curl using the sample log**

```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@sample_logs/incident.log" | python -m json.tool | head -40
```

Expected: JSON with `"status": "completed"` and 5 keys under `"artifacts"`.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: FastAPI app with /analyze, /health, /download endpoints"
```

---

## Task 11: Web UI

**Files:**
- Create: `static/index.html`

- [ ] **Step 1: Write static/index.html**

See full HTML in the implementation — covers:
- Dark-theme professional layout
- Drag-and-drop upload zone + paste area
- 4-step animated progress bar
- 5 collapsible result cards
- Slack Block Kit visual renderer
- JIRA ticket styled card
- Interactive markdown checkboxes
- Copy raw JSON/MD button per card
- Download all artifacts button

Full file content is in Task 11 Step 1 of the executed plan.

- [ ] **Step 2: Open browser at http://localhost:8000 and verify upload flow end-to-end**

1. Drag `sample_logs/incident.log` onto the drop zone
2. Click Analyze — progress steps should animate
3. Results appear — verify all 5 cards render
4. Check Slack preview looks like a Slack message
5. Check JIRA preview shows priority badge and labels
6. Check checkboxes are interactive
7. Click "Copy raw" on one card — verify clipboard
8. Click "Download all artifacts" — zip should download

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat: full upload UI with 5 styled result cards and Slack/JIRA previews"
```

---

## Task 12: Final Wiring & Demo Verification

- [ ] **Step 1: Full demo dry-run**

1. Restart server: `uvicorn main:app --reload --port 8000`
2. Open `http://localhost:8000`
3. Use sample log — verify clean end-to-end run
4. Note processing time displayed in UI header
5. Open `outputs/` folder — verify 5 artifact files written to disk

- [ ] **Step 2: Commit any fixes and tag**

```bash
git add -A
git commit -m "fix: demo dry-run fixes"
git tag v0.1.0-mvp
```
