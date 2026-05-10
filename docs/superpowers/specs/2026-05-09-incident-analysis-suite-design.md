# Design Spec: Multi-Agent DevOps Incident Analysis Suite (MVP)

**Date:** 2026-05-09  
**Target build time:** 4–5 hours  
**Status:** Approved

---

## 1. Goal

A user uploads a plain-text log file via a web UI. A LangGraph multi-agent pipeline classifies issues, reasons about severity, maps remediation steps, and produces 5 structured output artifacts — formatted exactly as they would be sent to Slack, JIRA, and a runbook system — without making any real external API calls.

---

## 2. Scope (MVP)

**In scope:**
- Plain-text log file upload (drag-and-drop or file picker)
- 4-node LangGraph pipeline
- 5 output artifacts per analysis
- Styled result cards in UI
- Configurable LLM model via OpenRouter

**Out of scope:**
- Real Slack / JIRA / PagerDuty API calls
- Authentication / multi-tenancy
- Database / persistent storage (artifacts written to local disk only; no DB)
- Streaming / async job queue
- Docker / cloud deployment

---

## 3. Architecture

### Single FastAPI app — monorepo

```
hackathon/
├── main.py                        # FastAPI app: serves UI + POST /analyze
├── graph/
│   ├── state.py                   # IncidentState TypedDict
│   ├── nodes/
│   │   ├── classifier.py          # Node 1: issue classification
│   │   ├── severity.py            # Node 2: P0–P3 severity reasoning
│   │   ├── remediation.py         # Node 3: fix steps + runbook refs
│   │   └── formatter.py           # Node 4: render all 5 artifacts
│   └── pipeline.py                # LangGraph graph assembly
├── llm/
│   └── client.py                  # OpenRouter client (openai-compatible)
├── outputs/                       # Per-incident artifact files (gitignored)
├── static/
│   └── index.html                 # Upload UI + result card renderer
├── sample_logs/
│   └── incident.log               # Synthetic 3-issue demo log
├── .env.example
└── requirements.txt
```

### Data flow

```
Upload (UI)
  → POST /analyze (multipart or text body)
  → parse raw log text
  → LangGraph pipeline:
      Node 1: Classify   → list of Classification objects
      Node 2: Severity   → per-issue P0–P3 + overall_severity
      Node 3: Remediate  → ordered fix steps per issue
      Node 4: Format     → 5 artifact strings
  → write artifacts to outputs/{incident_id}/
  → return all artifact content in JSON response
  → UI renders 5 styled cards
```

---

## 4. Agent State

```python
class IncidentState(TypedDict):
    incident_id: str
    raw_log: str
    classifications: list[Classification]   # set by Node 1
    severity: SeverityResult                # set by Node 2
    remediation: list[RemediationPlan]      # set by Node 3
    artifacts: ArtifactBundle               # set by Node 4
```

---

## 5. LangGraph Nodes

### Node 1 — Classifier
- Input: `raw_log`
- Prompt: identify distinct issues; label each with `issue_type` (OOM_KILL, DB_TIMEOUT, DEPLOY_FAILURE, AUTH_ERROR, DISK_FULL, UNKNOWN); extract evidence lines; list affected services
- Output: `list[Classification]` — validated via Pydantic; retries once on parse failure
- Each `Classification`: `issue_type`, `description`, `affected_services`, `evidence_lines`, `confidence` (0–1)

### Node 2 — Severity Reasoner
- Input: `classifications`
- Prompt: for each issue, reason chain-of-thought about environment signals, blast radius, recency; assign P0–P3 with written justification; derive `overall_severity`
- Output: `SeverityResult` — `per_issue: list[IssueSeverity]`, `overall_severity: str`, `overall_justification: str`

### Node 3 — Remediation Mapper
- Input: `classifications + severity`
- Prompt: for each issue, produce ordered fix steps grounded in log evidence; include estimated time, suggested owner role, runbook reference slug
- Output: `list[RemediationPlan]` — one per classified issue

### Node 4 — Output Formatter
- Input: full state
- Produces all 5 artifacts as strings:
  1. `slack_card.json` — Slack Block Kit payload
  2. `jira_ticket.json` — JIRA create-issue API payload
  3. `checklist.md` — markdown remediation checklist with checkboxes
  4. `analysis.json` — full raw agent state dump
  5. `summary.txt` — plain English 3–5 sentence incident narrative

---

## 6. LLM Client

**Provider:** OpenRouter (OpenAI-compatible API)

```
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-sonnet-4-6
```

`llm/client.py` instantiates `openai.OpenAI(base_url=..., api_key=...)`. All nodes call a single `chat(messages, response_model)` function. Switching models = changing `LLM_MODEL` in `.env`. Zero provider-specific branching anywhere else.

---

## 7. UI

**Single HTML file — two states, zero build tooling.**

### State 1: Upload
- Drag-and-drop zone + file picker
- Optional paste-text area for direct log input
- "Analyze" button
- Simulated step progress bar while API call runs: `Classifying → Reasoning Severity → Mapping Remediation → Formatting Outputs`

### State 2: Results (5 collapsible cards)

| Card | Content |
|------|---------|
| Incident Summary | Plain English narrative + color-coded severity badge (P0=red, P1=orange, P2=yellow, P3=green) |
| Classifications | Table: Issue Type / Service / Confidence / Evidence |
| Remediation Checklist | Rendered markdown with interactive checkboxes |
| Slack Card Preview | Visual replica of Slack Block Kit message (not raw JSON) |
| JIRA Ticket Preview | Styled card: summary, priority badge, labels, description |

Each card has a "Copy raw" button. Top-level "Download all artifacts" button.

---

## 8. API Contract

### POST /analyze

**Request:** `multipart/form-data` with `file` field (`.log` text file) OR `application/json` with `{ "log_text": "..." }`

**Response:**
```json
{
  "incident_id": "inc-20260509-abc123",
  "status": "completed",
  "processing_time_ms": 4200,
  "artifacts": {
    "summary": "...",
    "slack_card": { ... },
    "jira_ticket": { ... },
    "checklist": "...",
    "analysis": { ... }
  }
}
```

**Error response:**
```json
{
  "status": "error",
  "error_code": "PARSE_FAILURE | LOW_CONFIDENCE | EMPTY_LOG",
  "message": "..."
}
```

### GET /health
Returns `{ "status": "ok", "model": "anthropic/claude-sonnet-4-6" }`

### GET /outputs/{incident_id}/{filename}
Serves individual artifact files from disk.

### GET /download/{incident_id}
Returns a `.zip` of all 5 artifact files for the given incident. Used by the "Download all artifacts" button.

---

## 9. Sample Log

`sample_logs/incident.log` — synthetic 80-line plain-text log covering:
1. OOMKill on `payment-service` (P1)
2. DB connection pool exhaustion on `order-service` (P2)
3. Failed image pull on `notification-service` (P2)

Guarantees a consistent, demo-ready result without needing a real incident.

---

## 10. Demo Scenario

1. Open UI → drag `incident.log` onto upload zone
2. Watch step progress animate through 4 agent nodes
3. Results appear — read Incident Summary card (narrative + P1 badge)
4. Open Classifications card — 3 issues in table
5. Open Remediation Checklist — check off steps live
6. Open Slack Preview — show formatted message exactly as it would appear in `#incidents`
7. Open JIRA Preview — show auto-generated ticket
8. Click "Download all artifacts" — zip downloads

**Callout:** "From log upload to JIRA-ready ticket in under 15 seconds."

---

## 11. Dependencies

```
fastapi
uvicorn
langgraph
langchain-core
openai          # used as OpenRouter client
pydantic
python-multipart
python-dotenv
```

---

## 12. Non-Goals (explicit)

- No real Slack/JIRA/PagerDuty calls
- No auth
- No database
- No Docker
- No streaming
- No multi-file upload
- No fine-tuning or eval framework (post-MVP)
