import json

from graph.state import IncidentState
from llm.client import chat

_SUMMARY_SYSTEM = """You are writing a concise incident summary for a technical on-call audience.
Write exactly 3-5 sentences covering:
1. What happened (issue types and error details)
2. Which services are affected
3. Overall severity and immediate impact on users
4. The single most critical next step

Be specific — reference actual service names, error types, and severity levels from the data.
No filler phrases like "It appears that" or "It seems". State facts directly."""


def format_outputs(state: IncidentState) -> dict:
    ctx = {
        "incident_id": state["incident_id"],
        "classifications": state["classifications"],
        "severity": state["severity"],
        "remediation": state["remediation"],
    }

    summary = _generate_summary(ctx)
    artifacts = {
        "summary": summary,
        "slack_card": _build_slack_card(ctx, summary),
        "jira_ticket": _build_jira_ticket(ctx, summary),
        "checklist": _build_checklist(ctx),
        "analysis": {**ctx, "summary": summary},
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
    emoji = {
        "P0": ":rotating_light:",
        "P1": ":red_circle:",
        "P2": ":large_yellow_circle:",
        "P3": ":large_green_circle:",
    }.get(sev, ":white_circle:")

    issue_lines = []
    for c in ctx["classifications"]:
        sev_item = next(
            (i for i in ctx["severity"]["per_issue"] if i["issue_type"] == c["issue_type"]), {}
        )
        pct = int(c["confidence"] * 100)
        issue_lines.append(
            f"• *{c['issue_type']}* on `{', '.join(c['affected_services'])}` "
            f"— {sev_item.get('severity', '?')} (confidence: {pct}%)"
        )

    return {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} {sev} Incident — {ctx['incident_id']}"},
            },
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": summary}},
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Issues Identified:*\n" + "\n".join(issue_lines),
                },
            },
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
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Runbook"},
                        "style": "primary",
                        "value": "view_runbook",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Acknowledge"},
                        "value": "acknowledge",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Escalate"},
                        "style": "danger",
                        "value": "escalate",
                    },
                ],
            },
        ],
        "text": f"{sev} Incident: {ctx['incident_id']}",
    }


def _build_jira_ticket(ctx: dict, summary: str) -> dict:
    sev = ctx["severity"]["overall_severity"]
    priority_map = {"P0": "Critical", "P1": "High", "P2": "Medium", "P3": "Low"}
    affected = list({svc for c in ctx["classifications"] for svc in c["affected_services"]})

    desc_lines = ["h2. Incident Summary", summary, "", "h2. Issues Detected"]
    for c in ctx["classifications"]:
        sev_item = next(
            (i for i in ctx["severity"]["per_issue"] if i["issue_type"] == c["issue_type"]), {}
        )
        desc_lines += [
            f"h3. {c['issue_type']} — {sev_item.get('severity', '?')}",
            f"*Services:* {', '.join(c['affected_services'])}",
            f"*Description:* {c['description']}",
            f"*Severity Justification:* {sev_item.get('justification', '')}",
            "",
        ]
    desc_lines += ["h2. Remediation", "See attached checklist for ordered fix steps."]

    labels = (
        ["incident", sev.lower(), "auto-generated"]
        + [c["issue_type"].lower().replace("_", "-") for c in ctx["classifications"]]
    )

    return {
        "fields": {
            "project": {"key": "OPS"},
            "summary": (
                f"[{sev}] {ctx['incident_id']} — "
                f"{len(ctx['classifications'])} issues on {', '.join(affected[:3])}"
            ),
            "description": "\n".join(desc_lines),
            "issuetype": {"name": "Incident"},
            "priority": {"name": priority_map.get(sev, "Medium")},
            "labels": labels,
            "components": [{"name": "Platform"}, {"name": "On-Call"}],
            "customfield_affected_services": affected,
        }
    }


def _build_checklist(ctx: dict) -> str:
    sev = ctx["severity"]["overall_severity"]
    lines = [
        f"# Remediation Checklist — {ctx['incident_id']}",
        f"**Overall Severity:** {sev}  |  **Issues:** {len(ctx['classifications'])}",
        "",
        "---",
        "",
    ]
    for plan in ctx["remediation"]:
        cls = next(
            (c for c in ctx["classifications"] if c["issue_type"] == plan["issue_type"]), {}
        )
        sev_item = next(
            (i for i in ctx["severity"]["per_issue"] if i["issue_type"] == plan["issue_type"]), {}
        )
        lines += [
            f"## {plan['issue_type']} — {sev_item.get('severity', '?')}",
            f"**Services:** {', '.join(cls.get('affected_services', []))}",
            "",
        ]
        for step in plan["steps"]:
            lines += [
                f"- [ ] **Step {step['step_number']}:** {step['action']}",
                f"  - Owner: `{step['owner_role']}`  |  Est. time: {step['estimated_time_min']} min  |  Runbook: `{step['runbook_slug']}`",
                "",
            ]
        lines.append("")

    lines += [
        "---",
        "",
        "## Post-Incident",
        "",
        "- [ ] Confirm all services are stable and error rate is back to baseline",
        "- [ ] Write post-mortem document within 48 hours",
        "- [ ] Update runbooks with any new learnings",
        "- [ ] Schedule blameless retrospective with team",
        "",
    ]
    return "\n".join(lines)
