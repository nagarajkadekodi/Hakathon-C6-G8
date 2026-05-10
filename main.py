import io
import json
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
app.mount("/sample_logs", StaticFiles(directory="sample_logs"), name="sample_logs")


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
        return {
            "status": "error",
            "error_code": "EMPTY_LOG",
            "message": "Provide a log file or paste log text.",
        }

    if not raw_log.strip():
        return {
            "status": "error",
            "error_code": "EMPTY_LOG",
            "message": "Log content is empty.",
        }

    incident_id = f"inc-{uuid.uuid4().hex[:8]}"
    start = time.time()

    initial: IncidentState = {
        "incident_id": incident_id,
        "raw_log": raw_log,
        "classifications": [],
        "severity": None,
        "remediation": [],
        "artifacts": None,
        "review": None,
    }

    try:
        final = pipeline.invoke(initial)
    except Exception as e:
        return {
            "status": "error",
            "error_code": "PIPELINE_ERROR",
            "message": str(e),
        }

    artifacts = final["artifacts"]
    review = final.get("review")
    ms = int((time.time() - start) * 1000)

    incident_dir = OUTPUTS_DIR / incident_id
    incident_dir.mkdir(exist_ok=True)
    (incident_dir / "summary.txt").write_text(artifacts["summary"], encoding="utf-8")
    (incident_dir / "slack_card.json").write_text(
        json.dumps(artifacts["slack_card"], indent=2), encoding="utf-8"
    )
    (incident_dir / "jira_ticket.json").write_text(
        json.dumps(artifacts["jira_ticket"], indent=2), encoding="utf-8"
    )
    (incident_dir / "checklist.md").write_text(artifacts["checklist"], encoding="utf-8")
    (incident_dir / "analysis.json").write_text(
        json.dumps(artifacts["analysis"], indent=2), encoding="utf-8"
    )
    if review:
        (incident_dir / "review.json").write_text(
            json.dumps(review, indent=2), encoding="utf-8"
        )

    return {
        "incident_id": incident_id,
        "status": "completed",
        "processing_time_ms": ms,
        "artifacts": artifacts,
        "review": review,
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
        headers={
            "Content-Disposition": f"attachment; filename={incident_id}-artifacts.zip"
        },
    )
