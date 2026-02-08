"""FastAPI routes for the content autopilot API."""

import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select, func, desc, update

from db import async_session
from models import (
    ContentDiscovery, ContentCreation, ContentPublication,
    ContentMetric, ContentExperiment, ContentAgentRun,
    ContentPlaybook, SkillRecord, SkillMetric, EngagementAction,
)
from render_hints import (
    build_full_dashboard_hints,
    build_skills_hint,
    build_approval_hint,
    build_media_hint,
    build_comparison_hint,
)
from skills.manager import SkillManager
from skills.evaluator import SkillEvaluator
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# These get set by main.py after orchestrator is created
_orchestrator = None
_skill_manager = None


def set_orchestrator(orch):
    global _orchestrator
    _orchestrator = orch


def set_skill_manager(sm):
    global _skill_manager
    _skill_manager = sm


# ── Pydantic models ─────────────────────────────────────

class PlaybookUpdate(BaseModel):
    brand_name: Optional[str] = None
    voice_guide: Optional[str] = None
    topics: Optional[list[str]] = None
    avoid_topics: Optional[list[str]] = None
    competitors: Optional[list[str]] = None


# ── Chat tool definitions (Anthropic tool_use format) ───

CHAT_TOOLS = [
    {
        "name": "trigger_scout",
        "description": "Trigger the content scout to scan all 7 sources for trending content. Use when the user asks to run the pipeline, scan for content, or discover new topics.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_pipeline_status",
        "description": "Get the current status of the content pipeline including running state, active loops, last run times, and counts of discoveries/creations/publications.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_discoveries",
        "description": "Get recent content discoveries from all sources. Returns titles, scores, risk levels, platform fit, and status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max items to return (default 20)"},
                "status": {"type": "string", "description": "Filter by status: new, analyzed, queued, published, skipped"},
            },
            "required": [],
        },
    },
    {
        "name": "get_skills",
        "description": "Get all skills with their confidence scores, categories, health status, and version info. Use when the user asks about skills, performance, or the system's knowledge.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_skill_detail",
        "description": "Get detailed information about a specific skill including its content, tags, usage stats, and health.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The skill name (e.g. linkedin-hook-writing)"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "approve_content",
        "description": "Approve a content creation for publishing. Use when the user approves a specific piece of content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "The content creation ID to approve"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "reject_content",
        "description": "Reject a content creation. Use when the user wants to reject or skip a piece of content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "The content creation ID to reject"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "update_brand",
        "description": "Update the brand configuration (playbook). Can update brand name, voice guide, topics, avoid topics, and competitors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "brand_name": {"type": "string", "description": "Brand name"},
                "voice_guide": {"type": "string", "description": "Voice and tone guide for content creation"},
                "topics": {"type": "array", "items": {"type": "string"}, "description": "Focus topics"},
                "avoid_topics": {"type": "array", "items": {"type": "string"}, "description": "Topics to avoid"},
                "competitors": {"type": "array", "items": {"type": "string"}, "description": "Competitor names for risk assessment"},
            },
            "required": [],
        },
    },
    {
        "name": "get_publications",
        "description": "Get recently published content with platform, arbitrage window, and publication time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max items to return (default 20)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_arbitrage",
        "description": "Get the arbitrage scoreboard showing time advantage metrics: average minutes ahead, max window, and recent publications with arbitrage data.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_creations",
        "description": "Get content creations with approval status, risk scores, and body previews. Use when the user asks about pending content, content queue, or created content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max items (default 20)"},
                "status": {"type": "string", "description": "Filter by approval_status: pending, approved, rejected, auto_approved"},
            },
            "required": [],
        },
    },
    {
        "name": "get_playbook",
        "description": "Get the current brand configuration including brand name, voice guide, topics, avoid topics, and competitors.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

CHAT_SYSTEM_PROMPT = """You are the Autopilot AI agent for Kairox AI — an autonomous content arbitrage platform.

## What You Are
You are the operator interface for the Autopilot content pipeline. You help users manage and monitor their autonomous content system, which:
- Discovers trending content from 7 sources (Hacker News, Reddit, GitHub Trending, Lobsters, ArXiv, Company Blogs, Product Hunt)
- Analyzes content for relevance, velocity, risk, and platform fit
- Creates optimized content for 5 platforms (LinkedIn, X/Twitter, YouTube Shorts, Medium, TikTok)
- Publishes content with time-arbitrage advantage (being early on later platforms)
- Self-improves through a skills system with confidence scoring

## Your Capabilities
You have access to tools that let you:
- **Monitor**: Check pipeline status, view discoveries, skills, publications, arbitrage scores
- **Act**: Trigger the scout, approve/reject content, update brand configuration
- **Analyze**: Review skill performance, content queue, arbitrage windows

## How to Respond
- Be concise and data-driven. When showing data, format it clearly.
- Use tools proactively when the user asks about data — don't guess, look it up.
- When showing lists of items, format them as clean bullet points or tables.
- After taking actions (scout, approve, reject), report what happened.
- Speak with confidence about the platform's capabilities.
- Use specific numbers and metrics when available.

## Brand Context
This is a demo for investor presentations. The platform is called "Autopilot by Kairox AI". Emphasize:
- Content arbitrage (time advantage over mainstream)
- Self-improving skills system
- Autonomous operation
- Multi-platform reach"""


# ── Chat tool execution ──────────────────────────────────

async def execute_chat_tool(tool_name: str, tool_input: dict) -> dict:
    """Execute a chat tool and return the result."""
    try:
        if tool_name == "trigger_scout":
            if not _orchestrator:
                return {"error": "Orchestrator not running"}
            result = await _orchestrator.trigger_scout()
            return result

        elif tool_name == "get_pipeline_status":
            if not _orchestrator:
                return {"status": "not_started"}
            status = _orchestrator.get_status()
            async with async_session() as session:
                discoveries = (await session.execute(select(func.count(ContentDiscovery.id)))).scalar() or 0
                creations = (await session.execute(select(func.count(ContentCreation.id)))).scalar() or 0
                publications = (await session.execute(select(func.count(ContentPublication.id)))).scalar() or 0
            status["counts"] = {"discoveries": discoveries, "creations": creations, "publications": publications}
            return status

        elif tool_name == "get_discoveries":
            limit = tool_input.get("limit", 20)
            status_filter = tool_input.get("status")
            async with async_session() as session:
                query = select(ContentDiscovery).order_by(desc(ContentDiscovery.discovered_at)).limit(limit)
                if status_filter:
                    query = query.where(ContentDiscovery.status == status_filter)
                result = await session.execute(query)
                items = result.scalars().all()
            return {"discoveries": [
                {"id": d.id, "source": d.source, "title": d.title, "url": d.url,
                 "relevance_score": d.relevance_score, "velocity_score": d.velocity_score,
                 "risk_level": d.risk_level, "platform_fit": d.platform_fit,
                 "status": d.status, "discovered_at": d.discovered_at.isoformat() if d.discovered_at else None}
                for d in items
            ], "total": len(items)}

        elif tool_name == "get_skills":
            if not _skill_manager:
                return {"skills": []}
            evaluator = SkillEvaluator()
            skills = _skill_manager.all_skills()
            return {"skills": [
                {"name": s.name,
                 "category": s.category.value if hasattr(s.category, 'value') else str(s.category),
                 "confidence": round(s.confidence, 2),
                 "status": s.status.value if hasattr(s.status, 'value') else str(s.status),
                 "version": s.version, "total_uses": s.total_uses,
                 "health": evaluator.check_health(s)}
                for s in skills
            ], "total": len(skills)}

        elif tool_name == "get_skill_detail":
            name = tool_input.get("name", "")
            if not _skill_manager:
                return {"error": "Skills not loaded"}
            skill = _skill_manager.get_skill(name)
            if not skill:
                return {"error": f"Skill '{name}' not found"}
            evaluator = SkillEvaluator()
            return {
                "name": skill.name, "category": skill.category.value if hasattr(skill.category, 'value') else str(skill.category),
                "confidence": round(skill.confidence, 2), "version": skill.version,
                "total_uses": skill.total_uses, "success_count": skill.success_count,
                "content": skill.content, "tags": skill.tags,
                "health": evaluator.check_health(skill),
            }

        elif tool_name == "approve_content":
            cid = tool_input.get("id")
            async with async_session() as session:
                creation = (await session.execute(select(ContentCreation).where(ContentCreation.id == cid))).scalar_one_or_none()
                if not creation:
                    return {"error": f"Creation {cid} not found"}
                creation.approval_status = "approved"
                creation.approved_at = datetime.now(timezone.utc)
                await session.commit()
            return {"status": "approved", "id": cid}

        elif tool_name == "reject_content":
            cid = tool_input.get("id")
            async with async_session() as session:
                creation = (await session.execute(select(ContentCreation).where(ContentCreation.id == cid))).scalar_one_or_none()
                if not creation:
                    return {"error": f"Creation {cid} not found"}
                creation.approval_status = "rejected"
                await session.commit()
            return {"status": "rejected", "id": cid}

        elif tool_name == "update_brand":
            async with async_session() as session:
                playbook = (await session.execute(select(ContentPlaybook).limit(1))).scalar_one_or_none()
                if not playbook:
                    playbook = ContentPlaybook(brand_name="Autopilot by Kairox AI")
                    session.add(playbook)
                if "brand_name" in tool_input and tool_input["brand_name"]:
                    playbook.brand_name = tool_input["brand_name"]
                if "voice_guide" in tool_input and tool_input["voice_guide"]:
                    playbook.voice_guide = tool_input["voice_guide"]
                if "topics" in tool_input and tool_input["topics"] is not None:
                    playbook.topics = tool_input["topics"]
                if "avoid_topics" in tool_input and tool_input["avoid_topics"] is not None:
                    playbook.avoid_topics = tool_input["avoid_topics"]
                if "competitors" in tool_input and tool_input["competitors"] is not None:
                    playbook.competitors = tool_input["competitors"]
                playbook.updated_at = datetime.now(timezone.utc)
                await session.commit()
                return {"status": "updated", "brand_name": playbook.brand_name}

        elif tool_name == "get_publications":
            limit = tool_input.get("limit", 20)
            async with async_session() as session:
                result = await session.execute(
                    select(ContentPublication).order_by(desc(ContentPublication.published_at)).limit(limit)
                )
                pubs = result.scalars().all()
            return {"publications": [
                {"id": p.id, "creation_id": p.creation_id, "platform": p.platform,
                 "platform_post_id": p.platform_post_id, "platform_url": p.platform_url,
                 "arbitrage_window_minutes": p.arbitrage_window_minutes,
                 "published_at": p.published_at.isoformat() if p.published_at else None}
                for p in pubs
            ], "total": len(pubs)}

        elif tool_name == "get_arbitrage":
            async with async_session() as session:
                result = await session.execute(
                    select(ContentPublication)
                    .where(ContentPublication.arbitrage_window_minutes.isnot(None))
                    .order_by(desc(ContentPublication.published_at))
                    .limit(50)
                )
                pubs = result.scalars().all()
            windows = [p.arbitrage_window_minutes for p in pubs if p.arbitrage_window_minutes]
            avg_window = sum(windows) / len(windows) if windows else 0
            return {
                "total_publications_with_arbitrage": len(windows),
                "avg_arbitrage_minutes": round(avg_window, 1),
                "max_arbitrage_minutes": max(windows) if windows else 0,
                "recent": [{"platform": p.platform, "arbitrage_minutes": p.arbitrage_window_minutes,
                            "published_at": p.published_at.isoformat() if p.published_at else None}
                           for p in pubs[:10]],
            }

        elif tool_name == "get_creations":
            limit = tool_input.get("limit", 20)
            status_filter = tool_input.get("status")
            async with async_session() as session:
                query = select(ContentCreation).order_by(desc(ContentCreation.created_at)).limit(limit)
                if status_filter:
                    query = query.where(ContentCreation.approval_status == status_filter)
                result = await session.execute(query)
                items = result.scalars().all()
            return {"creations": [
                {"id": c.id, "discovery_id": c.discovery_id, "platform": c.platform,
                 "format": c.format, "title": c.title, "body": (c.body or "")[:200],
                 "media_urls": c.media_urls,
                 "variant_group": c.variant_group, "variant_label": c.variant_label,
                 "risk_score": c.risk_score, "risk_flags": c.risk_flags,
                 "approval_status": c.approval_status,
                 "created_at": c.created_at.isoformat() if c.created_at else None}
                for c in items
            ], "total": len(items)}

        elif tool_name == "get_playbook":
            async with async_session() as session:
                playbook = (await session.execute(select(ContentPlaybook).limit(1))).scalar_one_or_none()
            if not playbook:
                return {"brand_name": "Autopilot by Kairox AI", "voice_guide": None, "topics": None, "avoid_topics": None, "competitors": None}
            return {
                "brand_name": playbook.brand_name, "voice_guide": playbook.voice_guide,
                "topics": playbook.topics, "avoid_topics": playbook.avoid_topics,
                "competitors": playbook.competitors,
            }

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error("Tool %s failed: %s", tool_name, traceback.format_exc())
        return {"error": str(e)}


# ── WebSocket Chat ───────────────────────────────────────

def _make_chat_client():
    """Create the appropriate Bedrock client for chat."""
    if settings.aws_bearer_token_bedrock:
        import boto3
        import os
        os.environ["AWS_BEARER_TOKEN_BEDROCK"] = settings.aws_bearer_token_bedrock
        for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE", "AWS_SESSION_TOKEN"):
            os.environ.pop(key, None)
        return "boto3", boto3.client("bedrock-runtime", region_name=settings.aws_region)
    else:
        from anthropic import AnthropicBedrock
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client = AnthropicBedrock(
                aws_region=settings.aws_region,
                aws_access_key=settings.aws_access_key_id,
                aws_secret_key=settings.aws_secret_access_key,
            )
        else:
            client = AnthropicBedrock(aws_region=settings.aws_region)
        return "anthropic", client


async def _call_bedrock_with_tools(messages: list, system: str) -> dict:
    """Call Bedrock with tool definitions and return the full response."""
    client_type, client = _make_chat_client()

    if client_type == "boto3":
        # Convert tools to boto3 converse format
        boto3_tools = []
        for tool in CHAT_TOOLS:
            boto3_tools.append({
                "toolSpec": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "inputSchema": {"json": tool["input_schema"]},
                }
            })

        # Convert messages to boto3 format
        boto3_messages = []
        for msg in messages:
            if msg["role"] == "user":
                if isinstance(msg["content"], str):
                    boto3_messages.append({"role": "user", "content": [{"text": msg["content"]}]})
                else:
                    # Already structured content (tool results)
                    boto3_content = []
                    for block in msg["content"]:
                        if block.get("type") == "tool_result":
                            boto3_content.append({
                                "toolResult": {
                                    "toolUseId": block["tool_use_id"],
                                    "content": [{"json": json.loads(block["content"]) if isinstance(block["content"], str) else block["content"]}],
                                }
                            })
                        elif block.get("type") == "text":
                            boto3_content.append({"text": block["text"]})
                        else:
                            boto3_content.append({"text": str(block)})
                    boto3_messages.append({"role": "user", "content": boto3_content})
            elif msg["role"] == "assistant":
                if isinstance(msg["content"], str):
                    boto3_messages.append({"role": "assistant", "content": [{"text": msg["content"]}]})
                else:
                    boto3_content = []
                    for block in msg["content"]:
                        if block.get("type") == "text":
                            boto3_content.append({"text": block["text"]})
                        elif block.get("type") == "tool_use":
                            boto3_content.append({
                                "toolUse": {
                                    "toolUseId": block["id"],
                                    "name": block["name"],
                                    "input": block["input"],
                                }
                            })
                    boto3_messages.append({"role": "assistant", "content": boto3_content})

        response = client.converse(
            modelId=settings.bedrock_model_id,
            system=[{"text": system}],
            messages=boto3_messages,
            toolConfig={"tools": boto3_tools},
            inferenceConfig={"maxTokens": 4096},
        )

        # Parse boto3 response into Anthropic-like format
        output_content = response["output"]["message"]["content"]
        stop_reason = response.get("stopReason", "end_turn")
        content_blocks = []
        for block in output_content:
            if "text" in block:
                content_blocks.append({"type": "text", "text": block["text"]})
            elif "toolUse" in block:
                content_blocks.append({
                    "type": "tool_use",
                    "id": block["toolUse"]["toolUseId"],
                    "name": block["toolUse"]["name"],
                    "input": block["toolUse"]["input"],
                })

        return {
            "content": content_blocks,
            "stop_reason": "tool_use" if stop_reason == "tool_use" else "end_turn",
        }

    else:
        # Anthropic SDK
        response = client.messages.create(
            model=settings.bedrock_model_id,
            max_tokens=4096,
            system=system,
            messages=messages,
            tools=CHAT_TOOLS,
        )
        content_blocks = []
        for block in response.content:
            if hasattr(block, "text"):
                content_blocks.append({"type": "text", "text": block.text})
            elif hasattr(block, "name"):
                content_blocks.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        return {
            "content": content_blocks,
            "stop_reason": response.stop_reason,
        }


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """Real-time agent chat via WebSocket."""
    await websocket.accept()
    conversation_history = []

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") != "message":
                continue

            user_content = msg.get("content", "").strip()
            if not user_content:
                continue

            # Add user message to history
            conversation_history.append({"role": "user", "content": user_content})

            # Call Bedrock with tool support in a loop (tool_use → execute → continue)
            try:
                max_tool_rounds = 5
                for _ in range(max_tool_rounds):
                    response = await _call_bedrock_with_tools(conversation_history, CHAT_SYSTEM_PROMPT)

                    # Process response blocks
                    assistant_content = response["content"]
                    has_tool_use = False

                    for block in assistant_content:
                        if block["type"] == "text" and block.get("text"):
                            await websocket.send_text(json.dumps({
                                "type": "text",
                                "content": block["text"],
                            }))
                        elif block["type"] == "tool_use":
                            has_tool_use = True
                            tool_name = block["name"]
                            tool_input = block["input"]
                            tool_id = block["id"]

                            # Send tool_start
                            display = _tool_display_name(tool_name)
                            await websocket.send_text(json.dumps({
                                "type": "tool_start",
                                "name": tool_name,
                                "display": display,
                            }))

                            # Execute tool
                            result = await execute_chat_tool(tool_name, tool_input)

                            # Send tool_end
                            await websocket.send_text(json.dumps({
                                "type": "tool_end",
                                "name": tool_name,
                                "result": result,
                                "success": "error" not in result,
                            }))

                    # Add assistant message to history
                    conversation_history.append({"role": "assistant", "content": assistant_content})

                    # If tool_use, add tool results and continue loop
                    if has_tool_use and response.get("stop_reason") == "tool_use":
                        tool_results = []
                        for block in assistant_content:
                            if block["type"] == "tool_use":
                                result = await execute_chat_tool(block["name"], block["input"])
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": block["id"],
                                    "content": json.dumps(result),
                                })
                        conversation_history.append({"role": "user", "content": tool_results})
                    else:
                        break

            except Exception as e:
                logger.error("Chat error: %s", traceback.format_exc())
                await websocket.send_text(json.dumps({
                    "type": "text",
                    "content": f"I encountered an error: {str(e)}. Please try again.",
                }))

            # Send done
            await websocket.send_text(json.dumps({"type": "done"}))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", traceback.format_exc())


def _tool_display_name(name: str) -> str:
    """Human-readable display name for tool execution."""
    names = {
        "trigger_scout": "Scanning 7 sources for trending content",
        "get_pipeline_status": "Checking pipeline status",
        "get_discoveries": "Fetching discoveries",
        "get_skills": "Loading skills data",
        "get_skill_detail": "Loading skill details",
        "approve_content": "Approving content",
        "reject_content": "Rejecting content",
        "update_brand": "Updating brand configuration",
        "get_publications": "Fetching publications",
        "get_arbitrage": "Calculating arbitrage scores",
        "get_creations": "Loading content queue",
        "get_playbook": "Loading brand config",
    }
    return names.get(name, f"Running {name}")


# ── Existing REST endpoints ──────────────────────────────

@router.get("/pipeline")
async def get_pipeline_status():
    """Current status of all pipeline stages."""
    if not _orchestrator:
        return {"status": "not_started"}
    status = _orchestrator.get_status()

    # Add counts from DB
    async with async_session() as session:
        discoveries = (await session.execute(select(func.count(ContentDiscovery.id)))).scalar() or 0
        creations = (await session.execute(select(func.count(ContentCreation.id)))).scalar() or 0
        publications = (await session.execute(select(func.count(ContentPublication.id)))).scalar() or 0

    status["counts"] = {
        "discoveries": discoveries,
        "creations": creations,
        "publications": publications,
    }
    return status


@router.get("/skills")
async def get_skills():
    """All skills with confidence, status, health - merged from DB and files."""
    if not _skill_manager:
        return []

    evaluator = SkillEvaluator()
    skills = _skill_manager.all_skills()

    # Get skill data from database to show evolved versions
    async with async_session() as session:
        result = await session.execute(select(SkillRecord))
        db_skills = {s.name: s for s in result.scalars().all()}

    return [
        {
            "name": s.name,
            "category": s.category.value if hasattr(s.category, 'value') else str(s.category),
            "platform": s.platform,
            # Use database values if available (shows evolved skills)
            "confidence": db_skills[s.name].confidence if s.name in db_skills else s.confidence,
            "status": db_skills[s.name].status if s.name in db_skills else (s.status.value if hasattr(s.status, 'value') else str(s.status)),
            "version": db_skills[s.name].version if s.name in db_skills else s.version,
            "total_uses": db_skills[s.name].total_uses if s.name in db_skills else s.total_uses,
            "health": evaluator.check_health(s),
        }
        for s in skills
    ]


@router.get("/skills/{name}")
async def get_skill(name: str):
    """Single skill detail."""
    if not _skill_manager:
        raise HTTPException(404, "Skills not loaded")
    skill = _skill_manager.get_skill(name)
    if not skill:
        raise HTTPException(404, f"Skill '{name}' not found")
    evaluator = SkillEvaluator()
    return {
        "name": skill.name,
        "category": skill.category.value if hasattr(skill.category, 'value') else str(skill.category),
        "platform": skill.platform,
        "confidence": skill.confidence,
        "status": skill.status.value if hasattr(skill.status, 'value') else str(skill.status),
        "version": skill.version,
        "total_uses": skill.total_uses,
        "success_count": skill.success_count,
        "failure_streak": skill.failure_streak,
        "content": skill.content,
        "tags": skill.tags,
        "health": evaluator.check_health(skill),
    }


@router.get("/skills/{name}/history")
async def get_skill_history(name: str):
    """Skill usage history (recent outcomes from SkillMetric)."""
    async with async_session() as session:
        result = await session.execute(
            select(SkillMetric)
            .where(SkillMetric.skill_name == name)
            .order_by(desc(SkillMetric.recorded_at))
            .limit(50)
        )
        metrics = result.scalars().all()

    # Compute stats
    scores = [m.score for m in metrics]
    outcomes = [m.outcome for m in metrics]

    return {
        "skill_name": name,
        "total_records": len(metrics),
        "avg_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
        "success_rate": round(outcomes.count("success") / len(outcomes), 3) if outcomes else 0.0,
        "history": [
            {
                "agent": m.agent,
                "task": m.task,
                "outcome": m.outcome,
                "score": m.score,
                "context": m.context,
                "recorded_at": m.recorded_at.isoformat() if m.recorded_at else None,
            }
            for m in metrics
        ],
    }


@router.get("/skills/{name}/versions")
async def get_skill_versions(name: str):
    """Skill version history (genealogy) from archived version files.

    Shows the v1→v2→v3 evolution of a skill over time.
    """
    from pathlib import Path
    import frontmatter

    # Look for archived versions
    versions_dir = Path(__file__).parent / "skills" / "versions"
    versions = []

    if versions_dir.exists():
        for md_file in sorted(versions_dir.glob(f"{name}_v*.md")):
            try:
                post = frontmatter.load(str(md_file))
                meta = post.metadata
                versions.append({
                    "version": meta.get("version", 1),
                    "confidence": meta.get("confidence", 0.5),
                    "change_reason": meta.get("change_reason", ""),
                    "updated_at": meta.get("updated_at", ""),
                    "total_uses": meta.get("total_uses", 0),
                    "success_count": meta.get("success_count", 0),
                    "file": md_file.name,
                })
            except Exception:
                pass

    # Get current version from skill manager
    current = None
    if _skill_manager:
        skill = _skill_manager.get_skill(name)
        if skill:
            current = {
                "version": skill.version,
                "confidence": skill.confidence,
                "status": skill.status.value if hasattr(skill.status, 'value') else str(skill.status),
                "total_uses": skill.total_uses,
                "success_count": skill.success_count,
                "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
            }

    return {
        "skill_name": name,
        "current": current,
        "version_count": len(versions) + (1 if current else 0),
        "archived_versions": sorted(versions, key=lambda x: x["version"], reverse=True),
    }


@router.get("/skills/{name}/confidence-trend")
async def get_skill_confidence_trend(name: str, limit: int = 50):
    """Skill confidence trend over time (for visualization).

    Returns timestamped confidence changes derived from SkillMetric.
    """
    async with async_session() as session:
        result = await session.execute(
            select(SkillMetric)
            .where(SkillMetric.skill_name == name)
            .order_by(SkillMetric.recorded_at)  # Chronological order
            .limit(limit)
        )
        metrics = result.scalars().all()

    # Simulate confidence evolution
    confidence = 0.5  # Start at initial
    trend = []
    for m in metrics:
        confidence = 0.7 * confidence + 0.3 * m.score  # Same formula as SkillManager
        trend.append({
            "timestamp": m.recorded_at.isoformat() if m.recorded_at else None,
            "confidence": round(confidence, 4),
            "score": m.score,
            "outcome": m.outcome,
        })

    return {
        "skill_name": name,
        "initial_confidence": 0.5,
        "current_confidence": round(confidence, 4) if trend else 0.5,
        "data_points": len(trend),
        "trend": trend,
    }


@router.get("/discoveries")
async def get_discoveries(limit: int = 50, status: str | None = None):
    """Recent discoveries with scores."""
    async with async_session() as session:
        query = select(ContentDiscovery).order_by(desc(ContentDiscovery.discovered_at)).limit(limit)
        if status:
            query = query.where(ContentDiscovery.status == status)
        result = await session.execute(query)
        items = result.scalars().all()
    return [
        {
            "id": d.id,
            "source": d.source,
            "title": d.title,
            "url": d.url,
            "raw_score": d.raw_score,
            "relevance_score": d.relevance_score,
            "velocity_score": d.velocity_score,
            "risk_level": d.risk_level,
            "platform_fit": d.platform_fit,
            "status": d.status,
            "discovered_at": d.discovered_at.isoformat() if d.discovered_at else None,
        }
        for d in items
    ]


@router.get("/publications")
async def get_publications(limit: int = 50):
    """Published content with metrics."""
    async with async_session() as session:
        result = await session.execute(
            select(ContentPublication).order_by(desc(ContentPublication.published_at)).limit(limit)
        )
        pubs = result.scalars().all()
    return [
        {
            "id": p.id,
            "creation_id": p.creation_id,
            "platform": p.platform,
            "platform_post_id": p.platform_post_id,
            "platform_url": p.platform_url,
            "arbitrage_window_minutes": p.arbitrage_window_minutes,
            "published_at": p.published_at.isoformat() if p.published_at else None,
        }
        for p in pubs
    ]


@router.get("/metrics")
async def get_metrics(limit: int = 100):
    """Engagement data."""
    async with async_session() as session:
        result = await session.execute(
            select(ContentMetric).order_by(desc(ContentMetric.collected_at)).limit(limit)
        )
        metrics = result.scalars().all()
    return [
        {
            "id": m.id,
            "publication_id": m.publication_id,
            "interval": m.interval,
            "views": m.views,
            "likes": m.likes,
            "comments": m.comments,
            "shares": m.shares,
            "engagement_rate": m.engagement_rate,
            "collected_at": m.collected_at.isoformat() if m.collected_at else None,
        }
        for m in metrics
    ]


@router.get("/experiments")
async def get_experiments():
    """Active A/B tests."""
    async with async_session() as session:
        result = await session.execute(
            select(ContentExperiment).order_by(desc(ContentExperiment.started_at))
        )
        exps = result.scalars().all()
    return [
        {
            "id": e.id,
            "skill_name": e.skill_name,
            "variant_a": e.variant_a,
            "variant_b": e.variant_b,
            "metric_target": e.metric_target,
            "sample_size": e.sample_size,
            "variant_a_score": e.variant_a_score,
            "variant_b_score": e.variant_b_score,
            "winner": e.winner,
            "status": e.status,
            "started_at": e.started_at.isoformat() if e.started_at else None,
        }
        for e in exps
    ]


@router.get("/arbitrage")
async def get_arbitrage():
    """Arbitrage scoreboard — time advantage over mainstream."""
    async with async_session() as session:
        result = await session.execute(
            select(ContentPublication)
            .where(ContentPublication.arbitrage_window_minutes.isnot(None))
            .order_by(desc(ContentPublication.published_at))
            .limit(50)
        )
        pubs = result.scalars().all()

    windows = [p.arbitrage_window_minutes for p in pubs if p.arbitrage_window_minutes]
    avg_window = sum(windows) / len(windows) if windows else 0

    return {
        "total_publications_with_arbitrage": len(windows),
        "avg_arbitrage_minutes": round(avg_window, 1),
        "max_arbitrage_minutes": max(windows) if windows else 0,
        "recent": [
            {
                "platform": p.platform,
                "arbitrage_minutes": p.arbitrage_window_minutes,
                "published_at": p.published_at.isoformat() if p.published_at else None,
            }
            for p in pubs[:20]
        ],
    }


@router.get("/costs")
async def get_costs():
    """LLM/generator cost tracking with daily breakdown."""
    from datetime import timedelta

    async with async_session() as session:
        # Overall stats by agent
        result = await session.execute(
            select(
                ContentAgentRun.agent,
                func.count(ContentAgentRun.id).label("runs"),
                func.sum(ContentAgentRun.input_tokens).label("input_tokens"),
                func.sum(ContentAgentRun.output_tokens).label("output_tokens"),
                func.sum(ContentAgentRun.estimated_cost_usd).label("total_cost"),
            ).group_by(ContentAgentRun.agent)
        )
        rows = result.all()

        # Today's cost
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_result = await session.execute(
            select(func.coalesce(func.sum(ContentAgentRun.estimated_cost_usd), 0.0))
            .where(ContentAgentRun.started_at >= today_start)
        )
        cost_today = today_result.scalar() or 0.0

        # Last 7 days breakdown
        seven_days_ago = today_start - timedelta(days=7)
        daily_result = await session.execute(
            select(
                func.date(ContentAgentRun.started_at).label("date"),
                func.sum(ContentAgentRun.estimated_cost_usd).label("cost"),
                func.count(ContentAgentRun.id).label("runs"),
            )
            .where(ContentAgentRun.started_at >= seven_days_ago)
            .group_by(func.date(ContentAgentRun.started_at))
            .order_by(desc(func.date(ContentAgentRun.started_at)))
        )
        daily_rows = daily_result.all()

    total_cost = sum(r.total_cost or 0 for r in rows)
    total_input = sum(r.input_tokens or 0 for r in rows)
    total_output = sum(r.output_tokens or 0 for r in rows)

    return {
        "total_cost_usd": round(total_cost, 4),
        "cost_today_usd": round(cost_today, 4),
        "daily_cost_limit_usd": settings.daily_cost_limit,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "by_agent": [
            {
                "agent": r.agent,
                "runs": r.runs,
                "input_tokens": r.input_tokens or 0,
                "output_tokens": r.output_tokens or 0,
                "cost_usd": round(r.total_cost or 0, 4),
            }
            for r in rows
        ],
        "last_7_days": [
            {
                "date": str(r.date),
                "cost_usd": round(r.cost or 0, 4),
                "runs": r.runs,
            }
            for r in daily_rows
        ],
    }


# ── New REST endpoints ───────────────────────────────────

@router.get("/creations")
async def get_creations(limit: int = 50, status: str | None = None):
    """List content creations with approval status, risk info, body preview."""
    async with async_session() as session:
        query = select(ContentCreation).order_by(desc(ContentCreation.created_at)).limit(limit)
        if status:
            query = query.where(ContentCreation.approval_status == status)
        result = await session.execute(query)
        items = result.scalars().all()

        # Batch-fetch discovery titles
        disc_ids = list({c.discovery_id for c in items if c.discovery_id})
        disc_titles = {}
        if disc_ids:
            disc_result = await session.execute(
                select(ContentDiscovery.id, ContentDiscovery.title)
                .where(ContentDiscovery.id.in_(disc_ids))
            )
            disc_titles = {row.id: row.title for row in disc_result}

    return [
        {
            "id": c.id,
            "discovery_id": c.discovery_id,
            "discovery_title": disc_titles.get(c.discovery_id),
            "platform": c.platform,
            "format": c.format,
            "title": c.title,
            "body_preview": (c.body or "")[:200],
            "body": c.body,
            "media_urls": c.media_urls,
            "video_script": c.video_script,
            "skills_used": c.skills_used,
            "risk_score": c.risk_score,
            "risk_flags": c.risk_flags,
            "quality_score": c.quality_score,
            "quality_issues": c.quality_issues,
            "approval_status": c.approval_status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "approved_at": c.approved_at.isoformat() if c.approved_at else None,
        }
        for c in items
    ]


@router.get("/creations/{creation_id}")
async def get_creation_detail(creation_id: int):
    """Full creation detail with discovery info and publications."""
    async with async_session() as session:
        creation = (await session.execute(
            select(ContentCreation).where(ContentCreation.id == creation_id)
        )).scalar_one_or_none()

        if not creation:
            raise HTTPException(404, f"Creation {creation_id} not found")

        # Get discovery
        discovery = None
        if creation.discovery_id:
            disc = (await session.execute(
                select(ContentDiscovery).where(ContentDiscovery.id == creation.discovery_id)
            )).scalar_one_or_none()
            if disc:
                discovery = {
                    "id": disc.id, "source": disc.source, "title": disc.title,
                    "url": disc.url, "relevance_score": disc.relevance_score,
                }

        # Get publications
        pubs = (await session.execute(
            select(ContentPublication).where(ContentPublication.creation_id == creation_id)
        )).scalars().all()

    return {
        "id": creation.id,
        "discovery_id": creation.discovery_id,
        "discovery": discovery,
        "platform": creation.platform,
        "format": creation.format,
        "title": creation.title,
        "body": creation.body,
        "media_urls": creation.media_urls,
        "video_script": creation.video_script,
        "skills_used": creation.skills_used,
        "risk_score": creation.risk_score,
        "risk_flags": creation.risk_flags,
        "approval_status": creation.approval_status,
        "created_at": creation.created_at.isoformat() if creation.created_at else None,
        "approved_at": creation.approved_at.isoformat() if creation.approved_at else None,
        "publications": [
            {"id": p.id, "platform": p.platform, "platform_url": p.platform_url,
             "arbitrage_window_minutes": p.arbitrage_window_minutes,
             "published_at": p.published_at.isoformat() if p.published_at else None}
            for p in pubs
        ],
    }


@router.post("/creations/{creation_id}/approve")
async def approve_creation(creation_id: int):
    """Approve a content creation."""
    async with async_session() as session:
        creation = (await session.execute(
            select(ContentCreation).where(ContentCreation.id == creation_id)
        )).scalar_one_or_none()
        if not creation:
            raise HTTPException(404, f"Creation {creation_id} not found")
        creation.approval_status = "approved"
        creation.approved_at = datetime.now(timezone.utc)
        await session.commit()
    return {"status": "approved", "id": creation_id}


@router.post("/creations/{creation_id}/reject")
async def reject_creation(creation_id: int):
    """Reject a content creation."""
    async with async_session() as session:
        creation = (await session.execute(
            select(ContentCreation).where(ContentCreation.id == creation_id)
        )).scalar_one_or_none()
        if not creation:
            raise HTTPException(404, f"Creation {creation_id} not found")
        creation.approval_status = "rejected"
        await session.commit()
    return {"status": "rejected", "id": creation_id}


@router.get("/playbook")
async def get_playbook():
    """Current brand configuration."""
    async with async_session() as session:
        playbook = (await session.execute(select(ContentPlaybook).limit(1))).scalar_one_or_none()
    if not playbook:
        return {
            "brand_name": "Autopilot by Kairox AI",
            "voice_guide": None,
            "topics": None,
            "avoid_topics": None,
            "competitors": None,
        }
    return {
        "brand_name": playbook.brand_name,
        "voice_guide": playbook.voice_guide,
        "topics": playbook.topics,
        "avoid_topics": playbook.avoid_topics,
        "competitors": playbook.competitors,
        "updated_at": playbook.updated_at.isoformat() if playbook.updated_at else None,
    }


@router.put("/playbook")
async def update_playbook(data: PlaybookUpdate):
    """Update brand configuration."""
    async with async_session() as session:
        playbook = (await session.execute(select(ContentPlaybook).limit(1))).scalar_one_or_none()
        if not playbook:
            playbook = ContentPlaybook(brand_name="Autopilot by Kairox AI")
            session.add(playbook)

        if data.brand_name is not None:
            playbook.brand_name = data.brand_name
        if data.voice_guide is not None:
            playbook.voice_guide = data.voice_guide
        if data.topics is not None:
            playbook.topics = data.topics
        if data.avoid_topics is not None:
            playbook.avoid_topics = data.avoid_topics
        if data.competitors is not None:
            playbook.competitors = data.competitors
        playbook.updated_at = datetime.now(timezone.utc)

        await session.commit()

    return {"status": "updated", "brand_name": playbook.brand_name}


@router.get("/approval/pending")
async def get_pending_approval():
    """Returns pending creations grouped by variant_group, with media previews."""
    async with async_session() as session:
        result = await session.execute(
            select(ContentCreation)
            .where(ContentCreation.approval_status.in_(["pending", "pending_review"]))
            .order_by(desc(ContentCreation.created_at))
        )
        items = result.scalars().all()

        # Batch-fetch discovery titles
        disc_ids = list({c.discovery_id for c in items if c.discovery_id})
        disc_titles = {}
        if disc_ids:
            disc_result = await session.execute(
                select(ContentDiscovery.id, ContentDiscovery.title)
                .where(ContentDiscovery.id.in_(disc_ids))
            )
            disc_titles = {row.id: row.title for row in disc_result}

    # Group by variant_group
    groups: dict[str, list] = {}
    ungrouped: list = []

    for c in items:
        entry = {
            "id": c.id,
            "discovery_id": c.discovery_id,
            "discovery_title": disc_titles.get(c.discovery_id),
            "platform": c.platform,
            "format": c.format,
            "title": c.title,
            "body_preview": (c.body or "")[:300],
            "body": c.body,
            "media_urls": c.media_urls,
            "video_script": c.video_script,
            "variant_group": c.variant_group,
            "variant_label": c.variant_label,
            "risk_score": c.risk_score,
            "risk_flags": c.risk_flags,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        if c.variant_group:
            groups.setdefault(c.variant_group, []).append(entry)
        else:
            ungrouped.append(entry)

    return {
        "variant_groups": [
            {"group_id": gid, "variants": variants}
            for gid, variants in groups.items()
        ],
        "ungrouped": ungrouped,
        "total": len(items),
    }


@router.post("/approval/{creation_id}/select")
async def select_variant(creation_id: int):
    """Approve selected variant, reject siblings, and trigger deferred video generation."""
    async with async_session() as session:
        creation = (await session.execute(
            select(ContentCreation).where(ContentCreation.id == creation_id)
        )).scalar_one_or_none()
        if not creation:
            raise HTTPException(404, f"Creation {creation_id} not found")

        now = datetime.now(timezone.utc)
        creation.approval_status = "approved"
        creation.approved_at = now

        rejected_count = 0
        if creation.variant_group:
            # Reject siblings
            siblings = (await session.execute(
                select(ContentCreation)
                .where(ContentCreation.variant_group == creation.variant_group)
                .where(ContentCreation.id != creation_id)
            )).scalars().all()
            for sibling in siblings:
                sibling.approval_status = "rejected"
                rejected_count += 1

        await session.commit()

        # Capture fields needed for video generation outside the session
        video_script = creation.video_script
        video_type = creation.video_type
        video_prompt = creation.video_prompt
        video_composition = creation.video_composition
        creation_format = creation.format
        creation_platform = creation.platform
        creation_title = creation.title
        creation_body = creation.body

    # Extract image_url for image-to-video types
    creation_media_urls = None
    async with async_session() as session:
        creation_obj = (await session.execute(
            select(ContentCreation).where(ContentCreation.id == creation_id)
        )).scalar_one_or_none()
        if creation_obj:
            creation_media_urls = creation_obj.media_urls

    image_url = None
    if creation_media_urls:
        for media in creation_media_urls:
            if isinstance(media, dict) and media.get("type") == "image":
                image_url = media["url"]
                break

    # Stage 2: trigger deferred video generation if content has video fields
    video_triggered = False
    has_video_content = video_script or video_prompt or video_composition
    if has_video_content and video_type:
        import asyncio
        asyncio.create_task(_generate_video_for_creation(
            creation_id, video_type, video_script, video_prompt,
            video_composition, creation_platform, creation_title, creation_body,
            image_url=image_url,
        ))
        video_triggered = True
        logger.info(
            "Triggered deferred video generation (%s) for creation %d",
            video_type, creation_id,
        )

    return {
        "status": "approved",
        "id": creation_id,
        "siblings_rejected": rejected_count,
        "video_generation_triggered": video_triggered,
    }


async def _generate_video_for_creation(
    creation_id: int,
    video_type: str,
    video_script: str | None,
    video_prompt: str | None,
    video_composition: list | None,
    platform: str,
    title: str,
    body: str,
    image_url: str | None = None,
):
    """Background task: generate video via VideoRouter and update media_urls."""
    from generators.video_router import VideoRouter
    from generators.video_types import VideoType

    router = VideoRouter()
    video_result = await router.generate(
        video_type=VideoType.from_string(video_type),
        video_script=video_script,
        video_prompt=video_prompt,
        video_composition=video_composition,
        platform=platform,
        title=title,
        body=body,
        image_url=image_url,
    )

    if video_result.get("error"):
        logger.warning(
            "Video generation failed for creation %d (%s): %s",
            creation_id, video_type, video_result["error"],
        )
        return

    logger.info(
        "Deferred video generated (%s via %s) for creation %d",
        video_type, video_result.get("source", "unknown"), creation_id,
    )

    # Update creation media_urls in DB
    from sqlalchemy.orm.attributes import flag_modified
    async with async_session() as session:
        creation = (await session.execute(
            select(ContentCreation).where(ContentCreation.id == creation_id)
        )).scalar_one_or_none()
        if creation:
            existing = list(creation.media_urls or [])
            existing.append(video_result)
            creation.media_urls = existing
            flag_modified(creation, "media_urls")
            await session.commit()
            logger.info("Updated media_urls for creation %d with video", creation_id)


@router.post("/approval/{creation_id}/reject-group")
async def reject_variant_group(creation_id: int):
    """Reject all variants in a group."""
    async with async_session() as session:
        creation = (await session.execute(
            select(ContentCreation).where(ContentCreation.id == creation_id)
        )).scalar_one_or_none()
        if not creation:
            raise HTTPException(404, f"Creation {creation_id} not found")

        rejected_count = 1
        creation.approval_status = "rejected"

        if creation.variant_group:
            siblings = (await session.execute(
                select(ContentCreation)
                .where(ContentCreation.variant_group == creation.variant_group)
                .where(ContentCreation.id != creation_id)
            )).scalars().all()
            for sibling in siblings:
                sibling.approval_status = "rejected"
                rejected_count += 1

        await session.commit()

    return {"status": "rejected", "total_rejected": rejected_count}


@router.post("/create")
async def trigger_create():
    """Manually trigger the creator agent to generate content from analyzed discoveries."""
    if not _orchestrator:
        raise HTTPException(503, "Orchestrator not running")
    try:
        from agents.creator import CreatorAgent
        creator = CreatorAgent()
        if _skill_manager:
            creator.skill_manager = _skill_manager
        result = await creator.run(limit=5)
        return result
    except Exception as e:
        logger.error("Manual create failed: %s", traceback.format_exc())
        raise HTTPException(500, str(e))


@router.post("/discover")
async def trigger_discover():
    """Manual scout trigger."""
    if not _orchestrator:
        raise HTTPException(503, "Orchestrator not running")
    result = await _orchestrator.trigger_scout()
    return result


@router.get("/sources/health")
async def get_sources_health():
    """Get health status for all content sources.

    Shows:
    - Consecutive/total failures
    - Success rate
    - Backoff status
    - Last success/failure timestamps
    """
    if not _orchestrator:
        raise HTTPException(503, "Orchestrator not running")

    health = _orchestrator.scout.get_source_health_summary()

    # Compute aggregate stats
    total_sources = len(health)
    healthy_count = sum(1 for h in health.values() if h["healthy"])
    skipped_count = sum(1 for h in health.values() if h["should_skip"])

    return {
        "summary": {
            "total_sources": total_sources,
            "healthy": healthy_count,
            "degraded": total_sources - healthy_count - skipped_count,
            "skipped": skipped_count,
        },
        "sources": health,
    }


@router.post("/sources/{name}/reset")
async def reset_source_health(name: str):
    """Manually reset health for a source to recover from backoff."""
    if not _orchestrator:
        raise HTTPException(503, "Orchestrator not running")

    success = _orchestrator.scout.reset_source_health(name)
    if not success:
        raise HTTPException(404, f"Source '{name}' not found")

    return {"status": "reset", "source": name}


@router.post("/skills/{name}/review")
async def force_skill_review(name: str):
    """Force skill health review."""
    if not _skill_manager:
        raise HTTPException(503, "Skills not loaded")
    skill = _skill_manager.get_skill(name)
    if not skill:
        raise HTTPException(404, f"Skill '{name}' not found")
    evaluator = SkillEvaluator()
    health = evaluator.check_health(skill)
    is_stale = evaluator.detect_staleness(skill)
    if is_stale:
        _skill_manager.mark_stale(name)
    return {
        "name": name,
        "health": health,
        "stale": is_stale,
        "action_taken": "marked_stale" if is_stale else "none",
    }


@router.post("/feedback")
async def trigger_feedback():
    """Manually trigger a feedback cycle to update skill confidence and analyze patterns.

    This runs the full learning loop:
    1. Analyze patterns from SkillMetric data
    2. Update skill confidence scores
    3. Detect stale skills
    4. Run synthesizer to propose skill updates
    5. Check experiments for winners
    """
    if not _orchestrator:
        raise HTTPException(503, "Orchestrator not running")
    try:
        result = await _orchestrator.feedback_loop.run_cycle()
        return result
    except Exception as e:
        logger.error("Manual feedback failed: %s", traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/learning/summary")
async def get_learning_summary():
    """Summary of the learning system state.

    Shows overview of skill health, patterns found, and recent learning activity.
    """
    if not _skill_manager:
        return {"error": "Skills not loaded"}

    evaluator = SkillEvaluator()
    skills = _skill_manager.all_skills()

    # Skill health breakdown
    healthy = sum(1 for s in skills if evaluator.check_health(s) == "healthy")
    needs_attention = sum(1 for s in skills if evaluator.check_health(s) == "needs_attention")
    stale = sum(1 for s in skills if evaluator.detect_staleness(s))

    # Get recent metrics
    async with async_session() as session:
        metric_count = (await session.execute(
            select(func.count(SkillMetric.id))
        )).scalar() or 0

        # Skills with most recent activity
        recent_skills = await session.execute(
            select(SkillMetric.skill_name, func.count(SkillMetric.id).label("count"))
            .group_by(SkillMetric.skill_name)
            .order_by(desc(func.count(SkillMetric.id)))
            .limit(10)
        )
        active_skills = [{"name": r.skill_name, "usage_count": r.count} for r in recent_skills]

        # Average scores by skill
        avg_scores = await session.execute(
            select(
                SkillMetric.skill_name,
                func.avg(SkillMetric.score).label("avg_score"),
                func.count(SkillMetric.id).label("count")
            )
            .group_by(SkillMetric.skill_name)
            .having(func.count(SkillMetric.id) >= 3)
            .order_by(desc(func.avg(SkillMetric.score)))
        )
        top_performers = [
            {"name": r.skill_name, "avg_score": round(r.avg_score, 3), "sample_size": r.count}
            for r in avg_scores.fetchall()
        ]

    return {
        "skills_summary": {
            "total": len(skills),
            "healthy": healthy,
            "needs_attention": needs_attention,
            "stale": stale,
        },
        "metrics_collected": metric_count,
        "most_active_skills": active_skills[:5],
        "top_performers": top_performers[:5],
        "underperformers": list(reversed(top_performers[-5:])) if len(top_performers) >= 5 else [],
    }


# ── Quality gating endpoints ──────────────────────────────


class QualityPreviewRequest(BaseModel):
    title: str = ""
    body: str
    platform: str = "linkedin"


@router.post("/quality/preview")
async def preview_quality(data: QualityPreviewRequest):
    """Preview quality check results without saving.

    Useful for testing content before submission to see if it would pass quality gating.
    """
    from approval.queue import QualityChecker

    # Create a mock creation object for checking
    class MockCreation:
        def __init__(self, title, body, platform):
            self.title = title
            self.body = body
            self.platform = platform

    checker = QualityChecker()
    mock = MockCreation(data.title, data.body, data.platform)
    result = checker.check(mock)

    return {
        "score": result["score"],
        "passed": result["passed"],
        "would_be_auto_rejected": not result["passed"],
        "warning": result.get("warning", False),
        "issues": result["issues"],
        "metrics": result["metrics"],
        "thresholds": {
            "auto_reject_below": 0.4,
            "warning_below": 0.6,
        },
    }


@router.get("/quality/rejected")
async def get_quality_rejected(limit: int = 50):
    """Get content that was rejected due to quality issues.

    Shows what content failed quality gating and why.
    """
    async with async_session() as session:
        result = await session.execute(
            select(ContentCreation)
            .where(ContentCreation.approval_status == "quality_rejected")
            .order_by(desc(ContentCreation.created_at))
            .limit(limit)
        )
        items = result.scalars().all()

    return {
        "total": len(items),
        "items": [
            {
                "id": c.id,
                "discovery_id": c.discovery_id,
                "platform": c.platform,
                "format": c.format,
                "title": c.title,
                "body_preview": (c.body or "")[:200],
                "quality_score": c.quality_score,
                "quality_issues": c.quality_issues,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in items
        ],
    }


@router.get("/learning/failure-patterns")
async def get_failure_patterns(platform: str | None = None, refresh: bool = False):
    """Get failure patterns learned from low-engagement content.

    These patterns are injected into creator prompts to avoid repeating mistakes.

    Args:
        platform: Optional filter by platform
        refresh: If True, re-analyze failures (otherwise use cached data)
    """
    from learning.failure_patterns import get_failure_tracker

    tracker = get_failure_tracker()

    if refresh:
        result = await tracker.analyze_failures(lookback_days=14)
    else:
        result = {
            "patterns": tracker._cached_patterns or {},
            "failure_count": 0,
            "analysis_timestamp": (
                tracker._last_analysis.isoformat()
                if tracker._last_analysis else None
            ),
            "cache_status": "cached" if tracker._cached_patterns else "empty",
        }

    # If platform filter, narrow down
    if platform and result.get("patterns"):
        patterns = result["patterns"]
        filtered = {
            "hook_patterns": patterns.get("hook_patterns", []),
            "length_patterns": {
                platform: patterns.get("length_patterns", {}).get(platform, [])
            },
            "timing_patterns": {
                platform: patterns.get("timing_patterns", {}).get(platform, [])
            },
            "format_patterns": [
                p for p in patterns.get("format_patterns", [])
                if p.get("platform") == platform
            ],
            "skill_patterns": patterns.get("skill_patterns", []),
        }
        result["patterns"] = filtered
        result["filtered_by"] = platform

    return result


@router.get("/learning/failure-patterns/prompt-preview")
async def preview_failure_prompt(platform: str = "linkedin", format: str = "post"):
    """Preview the avoid guidance that would be injected into creator prompts.

    Shows exactly what the LLM sees when creating content.
    """
    from learning.failure_patterns import get_failure_tracker

    tracker = get_failure_tracker()
    prompt_text = tracker.get_avoid_patterns_for_prompt(platform, format)

    return {
        "platform": platform,
        "format": format,
        "prompt_text": prompt_text if prompt_text else "(no patterns to avoid yet)",
        "has_patterns": bool(prompt_text),
    }


@router.get("/quality/stats")
async def get_quality_stats():
    """Get quality gating statistics.

    Shows how many pieces of content passed vs failed quality checks.
    """
    async with async_session() as session:
        # Count by approval status
        result = await session.execute(
            select(
                ContentCreation.approval_status,
                func.count(ContentCreation.id).label("count"),
                func.avg(ContentCreation.quality_score).label("avg_score")
            )
            .group_by(ContentCreation.approval_status)
        )
        rows = result.all()

        # Get quality rejected count
        quality_rejected = next(
            (r for r in rows if r.approval_status == "quality_rejected"), None
        )
        total_checked = sum(r.count for r in rows if r.avg_score is not None)

        # Distribution of quality scores
        score_dist = await session.execute(
            select(
                func.count(ContentCreation.id).label("count")
            )
            .where(ContentCreation.quality_score.isnot(None))
            .where(ContentCreation.quality_score >= 0.6)
        )
        high_quality = score_dist.scalar() or 0

        score_dist_low = await session.execute(
            select(
                func.count(ContentCreation.id).label("count")
            )
            .where(ContentCreation.quality_score.isnot(None))
            .where(ContentCreation.quality_score < 0.4)
        )
        low_quality = score_dist_low.scalar() or 0

    return {
        "total_checked": total_checked,
        "quality_rejected": quality_rejected.count if quality_rejected else 0,
        "rejection_rate": round(
            (quality_rejected.count / total_checked) if quality_rejected and total_checked else 0, 3
        ),
        "high_quality_count": high_quality,
        "low_quality_count": low_quality,
        "by_status": [
            {
                "status": r.approval_status,
                "count": r.count,
                "avg_quality_score": round(r.avg_score, 3) if r.avg_score else None,
            }
            for r in rows
        ],
    }


# ── Engagement endpoints ──────────────────────────────────


@router.get("/engagements")
async def get_engagements(limit: int = 50, action_type: str | None = None, status: str | None = None):
    """Get engagement actions (replies and proactive comments).

    Args:
        limit: Maximum number to return
        action_type: Filter by type (reply, proactive)
        status: Filter by status (pending, pending_review, posted, failed)
    """
    async with async_session() as session:
        query = select(EngagementAction).order_by(desc(EngagementAction.created_at)).limit(limit)
        if action_type:
            query = query.where(EngagementAction.action_type == action_type)
        if status:
            query = query.where(EngagementAction.status == status)
        result = await session.execute(query)
        actions = result.scalars().all()

    return {
        "total": len(actions),
        "engagements": [
            {
                "id": a.id,
                "action_type": a.action_type,
                "platform": a.platform,
                "target_url": a.target_url,
                "target_author": a.target_author,
                "target_text_preview": (a.target_text or "")[:100],
                "our_text": a.our_text,
                "publication_id": a.publication_id,
                "skills_used": a.skills_used,
                "status": a.status,
                "posted_at": a.posted_at.isoformat() if a.posted_at else None,
                "error": a.error,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in actions
        ],
    }


@router.get("/engagements/pending")
async def get_pending_engagements():
    """Get engagement actions pending review (proactive comments that need human approval)."""
    async with async_session() as session:
        result = await session.execute(
            select(EngagementAction)
            .where(EngagementAction.status == "pending_review")
            .order_by(EngagementAction.created_at)
        )
        actions = result.scalars().all()

    return {
        "total": len(actions),
        "pending": [
            {
                "id": a.id,
                "action_type": a.action_type,
                "platform": a.platform,
                "target_url": a.target_url,
                "target_author": a.target_author,
                "target_text": a.target_text,
                "our_text": a.our_text,
                "skills_used": a.skills_used,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in actions
        ],
    }


@router.post("/engagements/{engagement_id}/approve")
async def approve_engagement(engagement_id: int):
    """Approve and post a pending engagement action."""
    async with async_session() as session:
        action = (await session.execute(
            select(EngagementAction).where(EngagementAction.id == engagement_id)
        )).scalar_one_or_none()

        if not action:
            raise HTTPException(404, f"Engagement {engagement_id} not found")

        if action.status not in ("pending", "pending_review"):
            raise HTTPException(400, f"Engagement {engagement_id} is not pending (status: {action.status})")

        # Try to post the engagement
        try:
            from engagement.comment_scraper import CommentScraper
            scraper = CommentScraper(headless=settings.playwright_headless)

            # For proactive engagements, we need to post to the target URL
            result = await scraper.post_reply(action.platform, action.target_url, action.our_text)

            if result.get("success"):
                action.status = "posted"
                action.posted_at = datetime.now(timezone.utc)
                await session.commit()
                return {"status": "posted", "id": engagement_id}
            else:
                action.status = "failed"
                action.error = result.get("error")
                await session.commit()
                return {"status": "failed", "id": engagement_id, "error": result.get("error")}

        except ImportError:
            raise HTTPException(503, "Playwright not installed - cannot post engagement")
        except Exception as e:
            action.status = "failed"
            action.error = str(e)
            await session.commit()
            raise HTTPException(500, str(e))


@router.post("/engagements/{engagement_id}/reject")
async def reject_engagement(engagement_id: int):
    """Reject a pending engagement action."""
    async with async_session() as session:
        action = (await session.execute(
            select(EngagementAction).where(EngagementAction.id == engagement_id)
        )).scalar_one_or_none()

        if not action:
            raise HTTPException(404, f"Engagement {engagement_id} not found")

        action.status = "rejected"
        await session.commit()

    return {"status": "rejected", "id": engagement_id}


@router.post("/engage")
async def trigger_engagement():
    """Manually trigger an engagement cycle (replies + proactive).

    This will:
    1. Scan recent publications for new comments and generate replies
    2. Find trending content and generate proactive engagement (queued for review)
    """
    if not _orchestrator:
        raise HTTPException(503, "Orchestrator not running")
    try:
        from agents.engagement import EngagementAgent
        agent = EngagementAgent()
        result = await agent.run()
        return result
    except Exception as e:
        logger.error("Manual engagement failed: %s", traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/engagements/stats")
async def get_engagement_stats():
    """Get engagement statistics."""
    async with async_session() as session:
        # Count by action type and status
        result = await session.execute(
            select(
                EngagementAction.action_type,
                EngagementAction.status,
                func.count(EngagementAction.id).label("count")
            )
            .group_by(EngagementAction.action_type, EngagementAction.status)
        )
        rows = result.all()

        # Count by platform
        platform_result = await session.execute(
            select(
                EngagementAction.platform,
                func.count(EngagementAction.id).label("count")
            )
            .where(EngagementAction.status == "posted")
            .group_by(EngagementAction.platform)
        )
        platform_rows = platform_result.all()

        # Today's count
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_result = await session.execute(
            select(func.count(EngagementAction.id))
            .where(EngagementAction.created_at >= today_start)
            .where(EngagementAction.action_type == "proactive")
        )
        proactive_today = today_result.scalar() or 0

    # Organize by type
    by_type = {}
    for row in rows:
        if row.action_type not in by_type:
            by_type[row.action_type] = {}
        by_type[row.action_type][row.status] = row.count

    return {
        "by_type": by_type,
        "by_platform": {r.platform: r.count for r in platform_rows},
        "proactive_today": proactive_today,
        "proactive_daily_limit": settings.engagement_max_proactive_per_day,
        "proactive_remaining": max(0, settings.engagement_max_proactive_per_day - proactive_today),
    }


# ── Render hints endpoint (for main platform integration) ────


@router.get("/dashboard/render-hints")
async def get_dashboard_render_hints():
    """Return a full dashboard payload with render_hints for SmartRenderer.

    This endpoint is designed to be called by the main platform's autopilot
    proxy to populate result_data.render_hints on AutomatedJobResult records.
    """
    # Gather all data needed for the dashboard
    pipeline_status = None
    if _orchestrator:
        pipeline_status = _orchestrator.get_status()

    # Counts
    async with async_session() as session:
        discoveries = (await session.execute(select(func.count(ContentDiscovery.id)))).scalar() or 0
        creations = (await session.execute(select(func.count(ContentCreation.id)))).scalar() or 0
        publications = (await session.execute(select(func.count(ContentPublication.id)))).scalar() or 0

        # Cost today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        cost_result = await session.execute(
            select(func.coalesce(func.sum(ContentAgentRun.estimated_cost_usd), 0.0))
            .where(ContentAgentRun.started_at >= today_start)
        )
        cost_today = cost_result.scalar() or 0.0

        # Avg arbitrage
        arb_result = await session.execute(
            select(func.avg(ContentPublication.arbitrage_window_minutes))
            .where(ContentPublication.arbitrage_window_minutes.isnot(None))
        )
        avg_arbitrage = arb_result.scalar() or 0.0

        # Pending approval
        pending_result = await session.execute(
            select(ContentCreation)
            .where(ContentCreation.approval_status.in_(["pending", "pending_review"]))
            .order_by(desc(ContentCreation.created_at))
        )
        pending_items = pending_result.scalars().all()

    counts = {"discoveries": discoveries, "creations": creations, "publications": publications}

    # Skills
    skills_data = []
    if _skill_manager:
        evaluator = SkillEvaluator()
        for s in _skill_manager.all_skills():
            skills_data.append({
                "name": s.name,
                "confidence": round(s.confidence, 2),
                "total_uses": s.total_uses,
                "health": evaluator.check_health(s),
            })

    # Format pending approval
    pending_approval = {
        "ungrouped": [
            {
                "id": c.id,
                "title": c.title,
                "platform": c.platform,
                "format": c.format,
            }
            for c in pending_items if not c.variant_group
        ],
        "variant_groups": [],
        "total": len(pending_items),
    }

    # Build render hints
    hints = build_full_dashboard_hints(
        pipeline_status=pipeline_status,
        counts=counts,
        skills=skills_data,
        pending_approval=pending_approval,
        cost_today=cost_today,
        daily_limit=settings.daily_cost_limit,
        avg_arbitrage=avg_arbitrage,
    )

    return {
        "render_hints": hints,
        "result_summary": (
            f"Content pipeline: {discoveries} discoveries, {creations} created, "
            f"{publications} published. {len(pending_items)} pending approval."
        ),
    }


# ── Smoke test endpoints ─────────────────────────────────────

# In-memory storage for smoke test runs (fine for single-process demo)
_smoke_test_runs: dict[str, dict] = {}


@router.post("/smoke-test")
async def start_smoke_test(
    type: str | None = None,
    dry_run: bool = False,
):
    """Kick off an end-to-end smoke test of video generators.

    Returns a run_id to poll for results. Video generation can take 5-20 min per type.

    Args:
        type: Optional single video type to test (e.g. "cinematic_broll")
        dry_run: If True, show plan + costs without calling APIs
    """
    import uuid

    run_id = str(uuid.uuid4())[:8]
    types_filter = [type] if type else None

    _smoke_test_runs[run_id] = {
        "status": "started",
        "dry_run": dry_run,
        "types_filter": types_filter,
        "video_results": [],
        "format_results": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }

    async def _run_smoke_test():
        from scripts.smoke_test import (
            run_video_smoke_test,
            run_content_format_test,
            check_prerequisites,
        )

        entry = _smoke_test_runs[run_id]
        try:
            entry["status"] = "running"
            entry["prerequisites"] = check_prerequisites()

            video_results = await run_video_smoke_test(
                types_filter=types_filter, dry_run=dry_run,
            )
            entry["video_results"] = video_results

            if not dry_run:
                entry["format_results"] = run_content_format_test()

            entry["status"] = "completed"
        except Exception as e:
            entry["status"] = "failed"
            entry["error"] = str(e)
            logger.error("Smoke test %s failed: %s", run_id, traceback.format_exc())
        finally:
            entry["completed_at"] = datetime.now(timezone.utc).isoformat()

    import asyncio
    asyncio.create_task(_run_smoke_test())

    return {
        "run_id": run_id,
        "status": "started",
        "dry_run": dry_run,
        "poll_url": f"/smoke-test/{run_id}",
    }


@router.get("/smoke-test/{run_id}")
async def get_smoke_test_status(run_id: str):
    """Poll for smoke test results.

    Returns current status and any results collected so far.
    """
    entry = _smoke_test_runs.get(run_id)
    if not entry:
        raise HTTPException(404, f"Smoke test run '{run_id}' not found")
    return entry
