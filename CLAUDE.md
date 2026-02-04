# Content Autopilot PoC

## What This Is

A standalone autonomous content arbitrage system demo for **Autopilot by Kairox AI** investor presentations. No mention of "MailAI" - this is the Autopilot brand. It exploits information latency between platforms: content trends on early platforms (HN, Reddit, ArXiv) before reaching later platforms (LinkedIn, YouTube, TikTok). Being early on "later" platforms = outsized engagement.

**This is a demo project, NOT production code.** It lives at `hack-demo/content-autopilot/` and is intentionally quick-and-dirty. The production codebase is at `../mailAI/` - reference it for patterns but never modify it.

## Stack

- Python 3.11+
- SQLite via SQLAlchemy (async with aiosqlite)
- FastAPI + uvicorn
- httpx for async HTTP
- **Anthropic SDK via AWS Bedrock** (`anthropic[bedrock]`) - NOT direct Anthropic API
- feedparser for RSS
- Pydantic for config/validation

## LLM Access: AWS Bedrock

All LLM calls go through AWS Bedrock, not direct Anthropic API. Use `anthropic.AnthropicBedrock` client.

```python
from anthropic import AnthropicBedrock

client = AnthropicBedrock(
    aws_region="us-east-1",
    aws_access_key="...",
    aws_secret_key="...",
)
response = client.messages.create(
    model="anthropic.claude-sonnet-4-20250514-v1:0",
    max_tokens=4096,
    messages=[...]
)
```

Config vars: `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `BEDROCK_MODEL_ID`.
Do NOT use `ANTHROPIC_API_KEY` - it is not used in this project.

## Port Configuration

**IMPORTANT:** Ports 8000 and 3000 are reserved for other services and MUST NOT be used.

The FastAPI server port is configurable via the `PORT` environment variable in `.env` (defaults to 8001).

```bash
# In .env file
PORT=8001  # Default - avoids conflicts with ports 8000 and 3000
```

On startup, the system will log the actual port being used. If you need to change it, update the `PORT` value in your `.env` file.

## How to Run

```bash
cd hack-demo/content-autopilot
pip install -e .            # or: pip install -r requirements.txt
cp .env.example .env        # Fill in AWS + API keys
python main.py              # Starts FastAPI on localhost:8001 (default)
```

Key endpoints:
- `GET /pipeline` - Pipeline status
- `GET /skills` - All skills with health metrics
- `GET /skills/{name}/history` - Skill version history
- `GET /metrics` - Engagement dashboards
- `GET /experiments` - Active A/B experiments
- `POST /discover` - Manually trigger scout
- `POST /skills/{name}/review` - Force skill health review

## Architecture Overview

```
Sources (7, all scrape-based) → Scout → Analyst → Creator → Approval → Publishers (5) → Engagement
                                                                              ↓
                                                                      Metrics Collector
                                                                              ↓
                                                                      Pattern Analyzer → Skill Updates
                                                                              ↓
                                                                      (feeds back to all agents)
```

### The Big Innovation: Skills-Based Self-Improvement

Instead of a static playbook, the system's knowledge lives in **composable, evolving skills** - markdown files with YAML frontmatter that encode procedural knowledge. Each skill has:

- **Confidence score** (0.0-1.0) - rolling average of success
- **Staleness detection** - flags when skills stop working
- **Version history** - tracks how knowledge evolved
- **Auto-synthesis** - system generates new skills from observed patterns

Skills are in `skills/library/` organized by category: sources, creation, platform, tools, engagement, timing.

### Why Raw LLM via Bedrock (not Claude Code as agent brain)

We use direct Bedrock API calls with skill-injected system prompts rather than Claude Code because:
- **Simpler** - no CLI dependency or subprocess management
- **Cheaper** - single LLM call per agent step vs multi-turn agentic loop
- **Lower latency** - one-shot structured output vs multiple tool-call round-trips
- **More controllable** - deterministic JSON output
- **Easier to demo** - transparent prompt → response

The skill system IS the intelligence layer. Skills injected into prompts make the LLM smarter over time.

For agents needing multi-step reasoning (analyst, creator), use Anthropic tool-use API pattern (tool definitions + tool_choice) rather than full Claude Code.

### Skill Lifecycle
```
[SEED] → [ACTIVE] → [VALIDATED] → [REFINED] → [SUPERSEDED]
              [STALE] → [UNDER_REVIEW] → [UPDATED] or [RETIRED]
```

### Key Directories

| Directory | Purpose |
|-----------|---------|
| `skills/` | Skills infrastructure: manager, evaluator, synthesizer, library of 21 skill files |
| `sources/` | 7 content source clients - ALL scrape/public API based, NO auth keys needed |
| `agents/` | AI agents: scout, analyst, creator, engagement, tracker, reviewer |
| `generators/` | Content generators: text (Claude via Bedrock), image (fal.ai), video (HeyGen, Veo3) |
| `publishers/` | Platform publishers: LinkedIn, X, YouTube, Medium, TikTok |
| `approval/` | Risk assessment + approval queue |
| `learning/` | Self-improvement: metrics, patterns, experiments, feedback loop |

## Sources (7 total, all auth-free)

| Source | Method | Auth | Signal Type |
|--------|--------|------|-------------|
| Hacker News | Algolia API | None | Tech trending, Show HN launches |
| Reddit | JSON API (`/r/{sub}/hot.json`) | None (User-Agent header only) | Community discussions, cross-post velocity |
| GitHub Trending | HTML scrape | None | Open-source momentum |
| Lobsters | JSON endpoint | None | High-quality technical content |
| ArXiv | Atom/XML feed | None | Research papers, AI advances |
| Company Blogs | RSS feeds | None | Announcements from OpenAI, Anthropic, DeepMind, Meta AI |
| Product Hunt | HTML scrape | None | Product launches, AI tools |

**NOT included:** Twitter/X (API requires paid access, scraping unreliable). 7 sources provide sufficient signal.

## Database

SQLite at `./autopilot.db`. 9 tables:

| Table | Purpose |
|-------|---------|
| `content_discoveries` | Raw items from source platforms |
| `content_creations` | Generated content (text, images, video) |
| `content_publications` | Published posts with platform IDs |
| `content_metrics` | Engagement metrics at intervals (1h, 6h, 24h, 48h, 7d) |
| `content_playbook` | Brand identity config (name, voice, topics, avoid_topics) |
| `content_experiments` | A/B test definitions and results |
| `content_agent_runs` | Agent execution logs with cost tracking |
| `skill_records` | Skill metadata, confidence, health status |
| `skill_metrics` | Individual skill usage outcomes |

Tables auto-create on first run via `db.py:create_tables()`.

## Environment Variables

Required - LLM:
- `AWS_REGION` - AWS region for Bedrock (default: us-east-1)
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `BEDROCK_MODEL_ID` - Bedrock model ID (default: `anthropic.claude-sonnet-4-20250514-v1:0`)

Required - Generators:
- `FAL_KEY` - Image generation (fal.ai)
- `HEYGEN_API_KEY` - Avatar video generation
- `HEYGEN_AVATAR_ID_FOUNDER` - Founder persona avatar
- `HEYGEN_AVATAR_ID_PROFESSIONAL` - Professional persona avatar
- `GOOGLE_API_KEY` - Veo3 video generation

Required - Publishing:
- `LINKEDIN_ACCESS_TOKEN` - LinkedIn publishing
- `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET` - X publishing

Optional:
- `YOUTUBE_API_KEY`, `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` - YouTube Shorts

System:
- `DATABASE_URL` - defaults to `sqlite+aiosqlite:///./autopilot.db`
- `LOG_LEVEL` - defaults to `INFO`

**NOTE:** Sources require NO API keys. All 7 sources use public endpoints or scraping.

## Seed Skills (21 total)

Skills are organized in `skills/library/` by category:

| Category | Count | Files |
|----------|-------|-------|
| `sources/` | 4 | hackernews-scoring, reddit-signal-detection, arxiv-mainstream-prediction, company-blog-monitoring |
| `creation/` | 4 | linkedin-hook-writing, twitter-thread-structure, youtube-shorts-scripting, medium-article-format |
| `platform/` | 4 | linkedin-optimization, twitter-optimization, youtube-shorts-optimization, tiktok-optimization |
| `tools/` | 4 | heygen-avatar-video, veo3-visual-generation, fal-image-generation, stagehand-browser-automation |
| `engagement/` | 3 | comment-reply-strategy, proactive-engagement, cold-start-growth |
| `timing/` | 2 | optimal-posting-windows, content-spacing |

All seed skills start at confidence 0.5 and contain detailed procedural knowledge. See `IMPLEMENTATION_PLAN.md` for full skill content specifications.

### Demo Skill Evolution Arcs

These skills are designed to visibly evolve during the demo:

| Skill | Evolution Story |
|-------|----------------|
| `linkedin-hook-writing` | Learns question hooks get 2.1x engagement → v1→v2→v3 genealogy |
| `optimal-posting-windows` | Discovers Tuesday 9am crushes LinkedIn, Thursday wins Twitter → counter-intuitive insight |
| `hackernews-scoring` | Learns "Show HN" + agent framework = highest conversion |
| `heygen-avatar-video` | Learns direct-to-camera opening retains 40% more |
| `arxiv-mainstream-prediction` | Papers cited by 3+ bloggers in 24hrs always go mainstream |
| `content-spacing` | Learns not to post LinkedIn within 4hrs of previous (cannibalization) |

## Key Patterns

### Adding a New Source
1. Create `sources/my_source.py` implementing `BaseSource` from `sources/base.py`
2. Implement `fetch()` → returns list of normalized `DiscoveryItem`
3. Register in `sources/__init__.py`
4. Create a seed skill in `skills/library/sources/my-source-scoring.md`

### Adding a New Publisher
1. Create `publishers/my_platform.py` implementing `BasePublisher` from `publishers/base.py`
2. Implement `publish(content)` and `get_metrics(post_id)`
3. Register in `publishers/__init__.py`
4. Create skills in `skills/library/platform/my-platform-optimization.md`

### Adding a New Skill
1. Create markdown file in appropriate `skills/library/{category}/` directory
2. Include YAML frontmatter: name, category, platform, confidence (start at 0.5), status (active), version (1), tags
3. Body: "When to Use", "Core Patterns", "What to Avoid", "Performance Notes"
4. SkillManager auto-discovers new files on load

### How Agents Use Skills
1. Agent calls `skill_manager.get_skills_for_task(task_type, platform=None)`
2. Returns relevant skills sorted by confidence
3. Skill content is injected into LLM system prompt (sent to Bedrock)
4. After task execution, agent calls `skill_manager.record_outcome(skill_name, outcome)`
5. SkillManager updates confidence scores

## Demo Data Seeding

Before running the demo for investors, seed the database with 14 days of realistic historical data:

```bash
python scripts/seed_demo_data.py
```

This script will:
- Populate 180+ publications with realistic engagement metrics
- Create skill evolution history (v1→v2→v3 for 6 key skills)
- Generate 8 completed A/B experiments with results
- Backdate agent runs with cost tracking (~$127 over 14 days)
- Show content arbitrage timing advantages (1-12 hours ahead of competitors)
- Demonstrate multi-platform coordination

The seeded data is designed to be discoverable - investors can explore and "find" the key insights that drove skill evolution.

**Important:** Run this script only once before the demo. It clears existing publications/metrics to ensure clean demo data.

## Common Development Tasks

```bash
# Seed demo data (run once before demo)
python scripts/seed_demo_data.py

# Run the full system
python main.py

# Run just the scout (useful for testing sources)
python -c "import asyncio; from agents.scout import ScoutAgent; asyncio.run(ScoutAgent().run())"

# Check skill health
curl localhost:8000/skills | python -m json.tool

# Trigger a discovery cycle
curl -X POST localhost:8000/discover

# View pipeline status
curl localhost:8000/pipeline
```

## Pre-Run Setup (HeyGen Avatars)

Before first run, the operator needs to configure HeyGen avatars. The system will guide through:
1. Log into HeyGen account
2. Create a custom avatar (founder persona) - upload video/photo of founder
3. Select a stock avatar (professional persona) - pick from HeyGen library
4. Note down avatar IDs and voice IDs
5. Add to `.env` as `HEYGEN_AVATAR_ID_FOUNDER` and `HEYGEN_AVATAR_ID_PROFESSIONAL`
6. Test with a sample 15-second script to verify quality

## Demo Data Design

The system is designed so demo data can be seeded later:
- All metric/skill update functions accept explicit timestamps (not just `now()`)
- Skill version history is append-only with timestamps
- A future `scripts/seed_demo_data.py` can inject realistic historical data
- DB schema supports backdated entries
- This allows us to show "the system has been running for 2 weeks" in the demo even if we seed data

## What NOT to Do

- Do NOT mention "MailAI" anywhere - this is the Autopilot brand
- Do NOT modify `../mailAI/` - that's production code
- Do NOT use PostgreSQL - SQLite is intentional for zero-friction demo
- Do NOT use direct Anthropic API - use AWS Bedrock
- Do NOT add Twitter/X as a source - API requires paid access
- Do NOT over-engineer - this is a demo, not production
- Do NOT add authentication - this runs locally
- Do NOT worry about rate limits in demo mode - we'll hit APIs gently

## Investor Demo Narrative

The demo tells this story:
1. **Content Arbitrage** - "We publish trending content hours before competitors"
2. **Skills Self-Improvement** - "The system literally gets smarter over time" (show skill genealogy)
3. **Cost Efficiency** - "47 pieces/week for $127 vs. $45K/month in human labor"
4. **Platform Scale** - "Now imagine 100 brands on this, sharing learned skills"

Key demo moments:
- Skill confidence scores changing in real-time
- Arbitrage scoreboard showing time advantage
- The "Aha moment" - system discovers a counter-intuitive insight
- Config swap showing multi-brand potential

## Progress Tracking

See `IMPLEMENTATION_PLAN.md` for detailed phase-by-phase progress with checkboxes and full seed skill specifications.
