# DevOps Incident Analyzer

A Python FastAPI application that analyzes raw incident logs using a graph-based AI pipeline.
It uses LangGraph and OpenAI-style LLM prompts to classify issues, determine severity, generate remediation plans, format incident artifacts, and perform an AI review.

## Features

- Upload log files or submit log text
- Classify incident issues with structured issue objects
- Infer severity per issue and overall incident level
- Generate actionable remediation plans
- Produce artifact outputs: summary, Slack card, Jira ticket, checklist, and analysis JSON
- Optional AI reviewer stage for quality assessment

## Project Structure

- `main.py` — FastAPI app entrypoint with endpoints for analysis and downloads
- `graph/` — state graph pipeline and node implementations
  - `graph/pipeline.py` — pipeline definition using `StateGraph`
  - `graph/state.py` — typed state, classification, severity, and remediation models
  - `graph/nodes/` — pipeline nodes for classification, severity reasoning, remediation, formatting, and review
- `llm/` — LLM client wrapper and helper functions
- `outputs/` — generated incident artifact directories
- `static/` — frontend assets
- `sample_logs/` — example input logs
- `requirements.txt` — Python dependencies

## Architecture

```mermaid
graph LR
  A[Client / Browser] -->|POST /analyze| B[FastAPI App (`main.py`)]
  B --> C[Input Validation & Incident State]
  C --> D[StateGraph Pipeline]
  D --> E[classify]
  E --> F[reason_severity]
  F --> G[map_remediation]
  G --> H[format_outputs]
  H --> I[ai_review]
  I --> J[Artifact Generation]
  J --> K[outputs/{incident_id}/]
  B -->|GET /download/{incident_id}| L[ZIP Download Endpoint]
  B -->|GET /health| M[Health Check]
```

This diagram shows how the app accepts log input, passes it through the graph-based pipeline, and writes generated artifacts to the `outputs` directory.

## Getting Started

1. Create a virtual environment:

   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Add environment variables in `.env` as needed for OpenAI or other LLM credentials.

4. Run the app:

   ```bash
   uvicorn main:app --reload
   ```

5. Open `http://127.0.0.1:8000/` in your browser.

## API Endpoints

- `GET /` — serve the HTML frontend
- `GET /health` — health check and model info
- `POST /analyze` — analyze a log file or pasted log text
- `GET /download/{incident_id}` — download generated incident artifacts as a ZIP

## Pipeline Stages

1. `classify` — extract issue types, descriptions, affected services, evidence lines, and confidence
2. `reason_severity` — assign per-issue severity and an overall incident severity
3. `map_remediation` — generate detailed remediation plans for each issue
4. `format_outputs` — build summary, Slack card, Jira ticket, checklist, and analysis payload
5. `ai_review` — review the analysis quality and flag potential issues

## Notes

- The application relies on AI prompt responses returning valid JSON.
- Error handling is basic and assumes the LLM returns properly formatted data.
- Output artifacts are written to `outputs/{incident_id}/`.

## License

MIT
