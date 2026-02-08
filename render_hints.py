"""Render hints builder for the extensible autopilot platform.

Converts content-autopilot data structures into render_hints format
that the SmartRenderer on the frontend can interpret and display
as rich, structured visualizations instead of plain markdown.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_pipeline_status_hint(orchestrator_status: dict) -> dict:
    """Build a pipeline_status render hint from orchestrator.get_status()."""
    last_runs = orchestrator_status.get("last_runs", {})
    mode = orchestrator_status.get("operation_mode", "full")

    # Map stages to pipeline stages with status
    stage_names = ["scout", "analyst", "creator", "approval", "tracker", "engagement"]
    stages = []
    for name in stage_names:
        last_run = last_runs.get(name)
        if last_run:
            stages.append({"name": name.capitalize(), "status": "complete"})
        else:
            stages.append({"name": name.capitalize(), "status": "pending"})

    return {
        "type": "pipeline_status",
        "title": f"Content Pipeline ({mode.upper()} mode)",
        "stages": stages,
    }


def build_metrics_hint(
    counts: dict,
    cost_today: float | None = None,
    daily_limit: float | None = None,
    avg_arbitrage: float | None = None,
) -> dict:
    """Build a metrics_grid render hint from pipeline counts and costs."""
    metrics = [
        {"label": "Discoveries", "value": str(counts.get("discoveries", 0))},
        {"label": "Creations", "value": str(counts.get("creations", 0))},
        {"label": "Published", "value": str(counts.get("publications", 0))},
    ]

    if avg_arbitrage is not None and avg_arbitrage > 0:
        metrics.append({
            "label": "Avg Arbitrage",
            "value": f"{avg_arbitrage:.0f} min",
            "trend": "up",
        })

    if cost_today is not None:
        budget_pct = (cost_today / daily_limit * 100) if daily_limit else 0
        metrics.append({
            "label": "Cost Today",
            "value": f"${cost_today:.3f}",
            "change": f"{budget_pct:.0f}% of limit",
            "trend": "up" if budget_pct > 70 else "flat",
        })

    return {
        "type": "metrics_grid",
        "title": "Pipeline Metrics",
        "metrics": metrics,
    }


def build_skills_hint(skills: list[dict]) -> dict:
    """Build a skill_health render hint from skills list."""
    return {
        "type": "skill_health",
        "title": "Skill Confidence",
        "skills": [
            {
                "name": s.get("name", "Unknown"),
                "confidence": s.get("confidence", 0.5),
                "samples": s.get("total_uses", 0),
            }
            for s in skills[:12]  # Limit to top 12 for display
        ],
    }


def build_approval_hint(pending_data: dict) -> dict:
    """Build an approval_list render hint from pending approval data."""
    items = []

    # Add ungrouped items
    for item in pending_data.get("ungrouped", []):
        items.append({
            "id": str(item["id"]),
            "title": item.get("title") or item.get("discovery_title") or "Untitled",
            "description": f"{item.get('platform', '')} • {item.get('format', '')}",
            "status": "pending",
            "preview_url": None,
        })

    # Add variant groups (show group header)
    for group in pending_data.get("variant_groups", []):
        for variant in group.get("variants", []):
            items.append({
                "id": str(variant["id"]),
                "title": f"[{variant.get('variant_label', '?')}] {variant.get('title') or 'Variant'}",
                "description": f"{variant.get('platform', '')} • Group: {group.get('group_id', '')[:8]}",
                "status": "pending",
                "preview_url": None,
            })

    return {
        "type": "approval_list",
        "title": "Pending Approval",
        "items": items,
        "approve_endpoint": "/autopilot/content/creations/{item_id}/approve",
        "reject_endpoint": "/autopilot/content/creations/{item_id}/reject",
    }


def build_media_hint(creations: list[dict]) -> dict:
    """Build a media_gallery render hint from content creations with media."""
    items = []
    for c in creations:
        media_urls = c.get("media_urls") or []
        for media in media_urls:
            if isinstance(media, dict):
                items.append({
                    "url": media.get("url", ""),
                    "thumbnail_url": media.get("thumbnail_url"),
                    "media_type": media.get("type", "image"),
                    "caption": c.get("title", ""),
                    "platform": c.get("platform"),
                })
            elif isinstance(media, str):
                items.append({
                    "url": media,
                    "media_type": "image",
                    "caption": c.get("title", ""),
                    "platform": c.get("platform"),
                })

    if not items:
        return None

    return {
        "type": "media_gallery",
        "title": "Generated Content",
        "items": items[:9],  # Max 9 for 3x3 grid
    }


def build_comparison_hint(variant_group: dict) -> dict | None:
    """Build a comparison_table render hint from a variant group."""
    variants = variant_group.get("variants", [])
    if len(variants) < 2:
        return None

    columns = [v.get("variant_label", f"V{i+1}") for i, v in enumerate(variants)]
    rows = [
        {"label": "Platform", "values": [v.get("platform", "?") for v in variants]},
        {"label": "Risk Score", "values": [f"{v.get('risk_score', 0):.2f}" for v in variants]},
        {"label": "Preview", "values": [(v.get("body_preview", "") or "")[:80] for v in variants]},
    ]

    return {
        "type": "comparison_table",
        "title": f"Variant Comparison — {variant_group.get('group_id', '')[:8]}",
        "columns": columns,
        "rows": rows,
    }


def build_full_dashboard_hints(
    pipeline_status: dict | None = None,
    counts: dict | None = None,
    skills: list[dict] | None = None,
    pending_approval: dict | None = None,
    cost_today: float | None = None,
    daily_limit: float | None = None,
    avg_arbitrage: float | None = None,
) -> list[dict]:
    """Build a complete set of render hints for a dashboard view.

    Returns a list of render hints suitable for result_data.render_hints.
    """
    hints = []

    if pipeline_status:
        hints.append(build_pipeline_status_hint(pipeline_status))

    if counts:
        hints.append(build_metrics_hint(
            counts, cost_today=cost_today,
            daily_limit=daily_limit, avg_arbitrage=avg_arbitrage,
        ))

    if skills:
        hints.append(build_skills_hint(skills))

    if pending_approval and pending_approval.get("total", 0) > 0:
        hints.append(build_approval_hint(pending_approval))

    return hints
