# Content Autopilot PoC - Implementation Plan & Progress Tracker

**Project:** Standalone demo at `hack-demo/content-autopilot/`
**Purpose:** Investor demo for Autopilot - autonomous content arbitrage with skills-based self-improvement
**Stack:** Python 3.11+, SQLite, FastAPI, httpx, Anthropic SDK (via AWS Bedrock), file-based skills
**Reference codebase:** `../mailAI/` (production, read-only reference - do NOT modify)

---

## KEY ARCHITECTURAL DECISIONS

### Decision 1: Standalone project (not in mailAI)
**Why:** mailAI is production code with too much friction for a quick demo. This is a clean standalone project.
**Reference:** Can look at mailAI patterns for inspiration but don't import from it.

### Decision 2: Skills as the self-improvement mechanism (not playbook JSON)
**Why:** Skills are composable, testable, explainable, and have built-in staleness detection. A monolithic playbook JSON degrades silently. Skills can be individually versioned, A/B tested, and evolved.
**Format:** Markdown files with YAML frontmatter. Performance Notes section is auto-updated by the system.

### Decision 3: SQLite (not PostgreSQL)
**Why:** Demo project. Zero setup friction. Good enough for the data volumes we'll see.

### Decision 4: AWS Bedrock (not direct Anthropic API)
**Why:** Production alignment. Use `anthropic.AnthropicBedrock` client with AWS credentials.
**Model IDs:** Use Bedrock model format (e.g., `anthropic.claude-sonnet-4-20250514-v1:0`).
**Config:** `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` instead of `ANTHROPIC_API_KEY`.

### Decision 5: Raw LLM via Bedrock (not Claude Code as agent brain)
**Why:** For this pipeline use case, raw LLM with well-crafted system prompts + skill injection is:
- Simpler (no CLI dependency, no subprocess management)
- Cheaper (single LLM call per agent step vs multi-turn agentic loop)
- Lower latency (one-shot structured output vs multiple tool-call round-trips)
- More controllable (deterministic JSON output via structured prompts)
- Easier to demo (transparent prompt → response, not opaque agent reasoning)

The skill system IS the intelligence layer. Skills get injected into prompts and make the LLM smarter over time. This is conceptually cleaner than "Claude Code runs under the hood."

For analyst/creator agents where multi-step reasoning matters, use Anthropic tool-use API pattern (tool definitions + tool_choice) rather than full Claude Code. This gives tool calling without the CLI dependency.

### Decision 6: Scrape-based sources (no API keys for discovery)
**Why:** Minimize setup friction. These sources work without authentication:
- Hacker News: Algolia API (fully public)
- Reddit: JSON API (`/r/{sub}/hot.json` with User-Agent header, no auth)
- GitHub Trending: HTML scrape (no API)
- Lobsters: JSON endpoint (fully public)
- ArXiv: Atom/XML feed (fully public)
- Company Blogs: RSS feeds (fully public)
- Product Hunt: HTML scrape of homepage (no API key)
- Twitter/X: **SKIP** - scraping is unreliable, API requires paid access. We have 7 other sources.

### Decision 7: Skill file format
**Format:** Markdown files with YAML frontmatter containing:
- name, category, platform, confidence, status, version, created, last_validated, tags
- Body: When to Use, Core Patterns, What to Avoid, Performance Notes
- JSON sidecar files NOT used - keep it simple, all in one .md file
- Performance Notes section is auto-updated by the system

### Decision 8: Brand identity
**Brand:** Autopilot by Kairox AI (usually just "Autopilot")
**No mention of "MailAI"** anywhere in this project. This is a standalone brand demo.
**Voice:** Confident, technical but accessible, forward-thinking about AI agents and automation.

### Decision 9: Live publishing accounts
Test accounts exist for all platforms (LinkedIn, X, YouTube, Medium, TikTok). The system publishes for real.

### Decision 10: Medium instead of Substack
**Why:** Medium has developer-friendly features (API, programmatic publishing). Substack lacks a usable API.
**Change:** All references to "Substack" become "Medium". Publisher is `publishers/medium.py`. Skill is `substack-article-format.md` → `medium-article-format.md`.

### Decision 11: HeyGen avatar setup
HeyGen account exists but avatars are not yet configured. Implementation includes a **setup checklist phase** where the system guides the operator through:
1. Creating a custom avatar (founder persona)
2. Selecting a stock avatar (professional persona)
3. Configuring voice IDs
4. Testing with a sample script
The avatar IDs are then stored in `.env`.

### Decision 12: Demo data strategy
Build the system so it can run live for real days, BUT also design it so a demo data seeder can be easily added later. This means:
- All metric/skill update functions accept timestamps (not just `now()`)
- Skill version history is append-only with timestamps
- A future `scripts/seed_demo_data.py` can inject realistic historical data
- DB schema supports backdated entries

---

## PROGRESS TRACKER

### Phase 1: Foundation + Skills Infrastructure [NOT STARTED]
- [ ] `pyproject.toml` - project deps (including `anthropic[bedrock]`)
- [ ] `config.py` - Pydantic Settings with AWS Bedrock config
- [ ] `db.py` - SQLite + async SQLAlchemy
- [ ] `models.py` - All DB tables (9 tables)
- [ ] `skills/__init__.py`
- [ ] `skills/base.py` - Skill dataclass + lifecycle enums
- [ ] `skills/manager.py` - SkillManager (CRUD, health, evolution)
- [ ] `skills/evaluator.py` - Staleness detection, trend analysis
- [ ] `skills/synthesizer.py` - Auto-generate skills from patterns
- [ ] `skills/library/` - All 21 seed skill files (see Seed Skills section below)
- [ ] `agents/__init__.py`
- [ ] `agents/base.py` - BaseAgent (skill selection, Bedrock LLM calling, outcome recording)
- [ ] `sources/__init__.py`
- [ ] `sources/base.py` - BaseSource ABC
- [ ] `publishers/__init__.py`
- [ ] `publishers/base.py` - BasePublisher ABC
- [ ] `generators/__init__.py`
- [ ] `approval/__init__.py`
- [ ] `learning/__init__.py`
- [ ] `.env.example`

### Phase 2: Sources + Scout Agent [NOT STARTED]
- [ ] `sources/hackernews.py` - HN Algolia API (no auth)
- [ ] `sources/reddit.py` - Reddit JSON API (no auth, public endpoints)
- [ ] `sources/product_hunt.py` - PH homepage scrape (no auth)
- [ ] `sources/github_trending.py` - GitHub trending page scrape (no auth)
- [ ] `sources/lobsters.py` - Lobsters JSON endpoint (no auth)
- [ ] `sources/arxiv.py` - ArXiv Atom feed API (no auth)
- [ ] `sources/company_blogs.py` - RSS feeds: OpenAI, Anthropic, Google DeepMind, Meta AI (no auth)
- [ ] `agents/scout.py` - Scout agent orchestration

### Phase 3: Analyst + Creator Agents [NOT STARTED]
- [ ] `agents/analyst.py` - Relevance scoring, velocity, dedup, risk, platform fit
- [ ] `agents/creator.py` - Multi-format content generation
- [ ] `generators/text.py` - Claude via Bedrock for text content
- [ ] `generators/image.py` - fal.ai Nano Banana Pro
- [ ] `generators/video_heygen.py` - HeyGen avatar videos
- [ ] `generators/video_veo3.py` - Google Veo3 visual content

### Phase 4: Approval + Publishing [NOT STARTED]
- [ ] `approval/risk_assessor.py` - LLM-based risk scoring
- [ ] `approval/queue.py` - Route: low=auto, medium=notify, high=block
- [ ] `publishers/linkedin.py` - LinkedIn API posting
- [ ] `publishers/twitter.py` - X API v2 posting
- [ ] `publishers/youtube.py` - YouTube Data API v3 Shorts upload
- [ ] `publishers/medium.py` - Medium API publishing
- [ ] `publishers/tiktok.py` - TikTok API or Stagehand browser automation fallback
- [ ] `learning/metrics_collector.py` - Poll platforms for engagement data

### Phase 5: Engagement Agent [NOT STARTED]
- [ ] `agents/engagement.py` - Comment monitoring, auto-reply, proactive engagement
- [ ] Growth tactics: strategic follows, thoughtful comments, quote-tweets
- [ ] "Founder Everywhere" mode

### Phase 6: Learning Loop + Self-Improvement [NOT STARTED]
- [ ] `learning/pattern_analyzer.py` - Find patterns in performance data
- [ ] `learning/experiment_runner.py` - A/B test skill variants
- [ ] `learning/feedback_loop.py` - metrics → skill updates pipeline
- [ ] `skills/synthesizer.py` - Auto-generate new skills from patterns
- [ ] `agents/reviewer.py` - Weekly strategy evolution + learning report
- [ ] Skill confidence auto-updating
- [ ] Staleness detection + auto-flagging

### Phase 7: Orchestrator + Dashboard [NOT STARTED]
- [ ] `orchestrator.py` - Main async loop scheduling all agents
- [ ] `routes.py` - FastAPI endpoints
- [ ] `dashboard.py` - Monitoring UI (simple HTML or JSON-only)
- [ ] `main.py` - FastAPI app entry point

---

## SEED SKILLS SPECIFICATION (21 skills)

These skills are the system's starting knowledge. They're designed to:
1. Be realistic and well-written (an expert content marketer would agree with the advice)
2. Have clear, measurable outcomes (so the system can score them)
3. Start at 0.5 confidence (room to improve or degrade based on real data)
4. Cover the full pipeline (discover → analyze → create → publish → engage → learn)
5. Set up the demo "Aha moments" (some skills will visibly improve, some will get superseded)

### Demo Evolution Story (pre-planned skill arcs)

These are the skill evolution arcs we want the demo to showcase:

| Skill | Starting State | Demo Evolution | Demo Payoff |
|-------|---------------|----------------|-------------|
| `linkedin-hook-writing` | Generic patterns, 0.5 confidence | Learns question hooks get 2.1x engagement | v1→v2→v3 genealogy tree |
| `optimal-posting-windows` | Industry averages | Discovers Tuesday 9am crushes it for AI content on LinkedIn, but Thursday wins on Twitter | "The Aha Moment" - counter-intuitive platform split |
| `hackernews-scoring` | Basic score threshold | Learns "Show HN" + agent framework = highest conversion to good content | Source intelligence improving |
| `heygen-avatar-video` | Default settings | Learns direct-to-camera opening retains 40% more than screen-share opening | Tool skill getting smarter |
| `arxiv-mainstream-prediction` | Simple citation count | Learns that papers cited by 3+ tech bloggers within 24hrs always go mainstream | Predictive accuracy increasing |
| `content-spacing` | Even distribution | Learns not to post LinkedIn within 4hrs of previous post (cannibalization) | Anti-pattern discovery |

---

### sources/ (4 skills)

#### `skills/library/sources/hackernews-scoring.md`

```yaml
---
name: hackernews-scoring
category: source
platform: hackernews
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [hackernews, scoring, discovery, signal-detection]
---
```

**When to Use:** Evaluating whether a Hacker News story is worth converting into content for our audience (AI agents, automation, productivity).

**Core Patterns:**
- Minimum score threshold: 50 points within first 6 hours (indicates traction)
- "Show HN" posts about AI tools/frameworks are highest-signal (builders sharing what they built)
- Comment-to-score ratio > 0.5 indicates controversy or deep engagement (both valuable)
- Stories linking to arxiv.org, github.com, or major AI company blogs have highest content conversion rate
- Ignore: hiring posts, "Ask HN: best laptop?", pure political threads
- Velocity matters more than absolute score: 100 points in 2 hours > 300 points in 24 hours

**Scoring Formula:**
```
relevance = topic_match(0-1) * 0.4 + velocity(0-1) * 0.3 + comment_quality(0-1) * 0.2 + source_authority(0-1) * 0.1
```

**What to Avoid:**
- Don't chase every HN front-page story - filter hard for AI/automation relevance
- Avoid stories that are pure drama (company controversies) unless directly relevant
- Skip stories older than 18 hours - the arbitrage window is closing

**Performance Notes:**
(Auto-updated by system)
- Stories processed: 0
- Avg relevance of selected stories: pending
- Conversion rate to published content: pending
- Best performing story type: pending

---

#### `skills/library/sources/reddit-signal-detection.md`

```yaml
---
name: reddit-signal-detection
category: source
platform: reddit
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [reddit, signal-detection, discovery, subreddits]
---
```

**When to Use:** Monitoring Reddit for AI/automation content signals worth amplifying.

**Core Patterns:**
- Priority subreddits (ordered by signal quality):
  1. r/MachineLearning - academic/research signals, early paper discussions
  2. r/LocalLLaMA - open-source AI tools, practical implementations
  3. r/artificial - general AI news, accessible angles
  4. r/ClaudeAI - Anthropic ecosystem, directly relevant to our audience
  5. r/ChatGPT - mainstream AI adoption signals
  6. r/SaaS - automation tool launches, B2B angles
  7. r/programming - developer tool signals
  8. r/AIAgents - niche but high-signal for our exact topic
- Cross-post detection: same content appearing in 3+ subreddits = high-velocity signal
- Rising posts (under 2 hours old, 50+ upvotes) are better than hot posts (already peaked)
- Self-posts with detailed breakdowns = deep content opportunities
- Link posts to external content = news/announcement coverage opportunities

**Scoring Formula:**
```
signal_strength = upvote_velocity(0-1) * 0.35 + subreddit_relevance(0-1) * 0.25 + comment_depth(0-1) * 0.2 + cross_post_count * 0.1 + award_count * 0.1
```

**What to Avoid:**
- Meme subreddits even if AI-related
- Posts with < 10 comments (low engagement signal)
- Duplicate detection: same GitHub repo or paper posted to multiple subs counts as one signal

**Performance Notes:**
(Auto-updated by system)
- Posts processed: 0
- Avg signal strength of selected posts: pending
- Best performing subreddit: pending
- Cross-post hit rate: pending

---

#### `skills/library/sources/arxiv-mainstream-prediction.md`

```yaml
---
name: arxiv-mainstream-prediction
category: source
platform: arxiv
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [arxiv, research, prediction, mainstream-potential, papers]
---
```

**When to Use:** Predicting which ArXiv papers about AI will become mainstream talking points (and therefore great content opportunities).

**Core Patterns:**
- Watch these ArXiv categories: cs.AI, cs.CL, cs.LG, cs.MA (multi-agent systems), cs.SE (software engineering + AI)
- **Mainstream indicators** (presence of 2+ = likely mainstream):
  1. Paper from major lab (OpenAI, Anthropic, Google DeepMind, Meta FAIR, Microsoft Research)
  2. Introduces a named system/model (people share things with catchy names)
  3. Claims SOTA on a well-known benchmark
  4. Has a public demo, API, or open-source code
  5. Title is understandable by non-researchers
  6. Abstract contains practical implications ("enables", "allows users to", "real-world")
- **Velocity signals**:
  - Paper gets tweeted by 5+ AI researchers within 24 hours
  - Appears on HN front page within 48 hours of publication
  - Gets a "paper explainer" YouTube video within 72 hours
- **Timing**: ArXiv papers drop at ~6PM ET (2AM UTC). Check at 7PM ET for fresh papers.

**What to Avoid:**
- Pure theory papers without practical implications (unless groundbreaking)
- Incremental benchmark improvements (boring for our audience)
- Papers in domains far from our brand (biology, physics, unless AI-applied)

**Performance Notes:**
(Auto-updated by system)
- Papers evaluated: 0
- Mainstream prediction accuracy: pending
- Avg time advantage vs mainstream coverage: pending
- Best performing indicator combination: pending

---

#### `skills/library/sources/company-blog-monitoring.md`

```yaml
---
name: company-blog-monitoring
category: source
platform: rss
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [rss, company-blogs, announcements, ai-companies, breaking-news]
---
```

**When to Use:** Monitoring AI company blogs for announcements, product launches, and thought pieces that become content opportunities.

**Core Patterns:**
- **Tier 1 blogs** (check every 30 min, always create content):
  - Anthropic Blog (blog.anthropic.com) - Claude updates, safety research, model releases
  - OpenAI Blog (openai.com/blog) - GPT updates, product launches, policy
  - Google DeepMind Blog (deepmind.google/blog) - Gemini, research breakthroughs
- **Tier 2 blogs** (check hourly, create content if relevant):
  - Meta AI Blog (ai.meta.com/blog) - Llama, open-source AI
  - Microsoft AI Blog (blogs.microsoft.com/ai) - Copilot, Azure AI
  - Hugging Face Blog (huggingface.co/blog) - open-source ecosystem
  - LangChain Blog (blog.langchain.dev) - agent frameworks
  - Vercel Blog (vercel.com/blog) - AI SDK, developer tools
- **Tier 3 blogs** (check daily, selective):
  - a16z AI (a16z.com/ai) - VC perspective on AI
  - Sequoia (sequoiacap.com/article) - market analysis
  - Individual researcher blogs (Karpathy, etc.)

**Speed is everything:** Company blog posts are the highest-arbitrage source. A new Claude model announcement can be turned into LinkedIn content within 30 minutes, hours before mainstream tech press covers it.

**Content Angle by Blog Type:**
- Model release → "What it means for builders" angle
- Research paper → "Why this matters in plain English" angle
- Product update → "How to use this today" angle
- Safety/policy → "Industry implications" angle

**What to Avoid:**
- Hiring announcements (unless C-level, which signals strategy)
- Routine infrastructure updates
- Content that requires NDA or is under embargo

**Performance Notes:**
(Auto-updated by system)
- Blog posts monitored: 0
- Avg time from blog publish to our content publish: pending
- Best performing company blog for our audience: pending
- Content type conversion rate by blog: pending

---

### creation/ (4 skills)

#### `skills/library/creation/linkedin-hook-writing.md`

```yaml
---
name: linkedin-hook-writing
category: creation
platform: linkedin
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [linkedin, hooks, copywriting, engagement, opening-lines]
---
```

**When to Use:** Writing the opening line/hook for any LinkedIn post. This is the most important line - it determines whether someone clicks "see more."

**Core Patterns:**
- Keep first line under 15 words
- Leave a blank line after the hook (forces "see more" click on mobile)
- Use pattern interrupts: say something unexpected, specific, or contrarian
- Numbers and specifics outperform vague claims ("14 hours" > "a lot of time")
- Format the hook to work as a standalone statement (many people only read the hook)

**Hook Templates (ranked by expected engagement):**

1. **Counter-intuitive opener** (confidence: medium)
   - "Most people think [X]. They're wrong."
   - "Everyone is talking about [X]. Nobody is talking about [Y]."
   - "The biggest lie in [industry] is [common belief]."

2. **Specific result** (confidence: medium)
   - "This [tool/approach] saved me [specific number] hours last week."
   - "I [did X] and [specific surprising result]."
   - "After [time period] of [activity], here's what actually works."

3. **Question hook** (confidence: medium)
   - "What if [provocative possibility]?"
   - "Why does nobody talk about [overlooked thing]?"
   - "Can [AI/tool] actually [ambitious claim]?"

4. **Breaking news** (confidence: medium)
   - "[Company] just [action]. Here's what it means for [audience]."
   - "[Tool/Technology] just changed everything about [topic]."
   - "Breaking: [specific news]. My take 👇"

5. **List/Framework** (confidence: medium)
   - "[N] things I learned about [topic] this week."
   - "The [N]-step framework for [desired outcome]."
   - "[N] tools that [specific benefit] (all free)."

**What to Avoid:**
- "I'm excited to share..." (generic, zero pattern interrupt)
- "I'm pleased to announce..." (corporate, not conversational)
- Starting with hashtags (kills engagement)
- Long first paragraphs (kills mobile readability)
- Humble-brag openings ("I was just named to Forbes 30 under 30...")
- Questions that can be answered with "no" ("Want to hear about my new project?")

**Platform-Specific Notes:**
- LinkedIn truncates at ~210 characters on mobile before "see more"
- First line appears in notification previews - make it count
- Emoji in hook: divisive, test both. Some audiences love 🔥, others find it unprofessional.

**Performance Notes:**
(Auto-updated by system)
- Posts using this skill: 0
- Avg engagement rate by hook type: pending
- Best performing hook template: pending
- Click-through rate (hook → full post): pending

---

#### `skills/library/creation/twitter-thread-structure.md`

```yaml
---
name: twitter-thread-structure
category: creation
platform: twitter
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [twitter, threads, structure, engagement, x]
---
```

**When to Use:** Structuring Twitter/X threads for maximum readability and engagement.

**Core Patterns:**

**Thread Length:**
- Sweet spot: 5-8 tweets
- Under 5 feels thin; over 10 loses readers
- Exception: truly epic breakdowns (new model release, major paper) can go 12-15

**Structure Template:**
1. **Tweet 1 (Hook):** Bold claim or question. Must stand alone as a great tweet. Include "🧵" or "Thread:" to signal thread.
2. **Tweet 2 (Context):** Why this matters. Set up the problem or opportunity.
3. **Tweets 3-N-2 (Body):** One insight per tweet. Use numbered format ("3/ Here's the key insight...").
4. **Tweet N-1 (Takeaway):** The "so what?" - actionable conclusion.
5. **Tweet N (CTA):** "Follow for more [topic]" + retweet request. Link to longer content (blog, video) if available.

**Per-Tweet Rules:**
- One idea per tweet
- Under 240 characters preferred (leaves room for engagement)
- Start each tweet with the number ("3/") for navigation
- Use line breaks between sentences
- Include an image/screenshot in tweet 1 or 2 (increases visibility 2-3x)

**What to Avoid:**
- Walls of text in a single tweet
- Starting thread with "1/" (start with the hook, put "🧵" at the end)
- Hashtags in every tweet (1-2 in first tweet only)
- Self-promotional CTAs in every tweet
- Threads that are just a blog post chopped into 280-char chunks (each tweet should work standalone)

**Performance Notes:**
(Auto-updated by system)
- Threads created: 0
- Avg impressions per thread: pending
- Avg engagement rate: pending
- Optimal thread length: pending
- Best performing hook style: pending

---

#### `skills/library/creation/youtube-shorts-scripting.md`

```yaml
---
name: youtube-shorts-scripting
category: creation
platform: youtube
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [youtube, shorts, scripting, video, tiktok, reels]
---
```

**When to Use:** Writing scripts for short-form video content (YouTube Shorts, TikTok, Reels). Used by HeyGen avatar and visual content generators.

**Core Patterns:**

**Script Structure (45-60 seconds):**
- **Hook (0-3 sec):** Opening line that stops the scroll. Must create curiosity gap.
- **Problem/Context (3-10 sec):** What's happening, why it matters.
- **Key Insight (10-40 sec):** The meat. 2-3 specific points, not abstract claims.
- **Takeaway/CTA (40-55 sec):** What to do with this information. "Follow for more" or "Link in bio."
- **End frame (55-60 sec):** Logo/branding + subscribe prompt.

**Hook Formulas for Video:**
- "This AI tool just [did something impressive] and nobody is talking about it"
- "I found something crazy about [topic]"
- "Stop scrolling if you [work in X / care about Y]"
- "In 45 seconds I'll show you [specific promise]"
- Start mid-sentence as if continuing a thought (pattern interrupt)

**Pacing Rules:**
- One sentence = one on-screen text callout
- Change visual every 5-7 seconds (text overlay, camera angle, B-roll)
- Speak slightly faster than conversational (urgency, energy)
- Pause before the key insight (builds anticipation)
- 130-150 words per minute target speaking rate

**Script Format (for HeyGen):**
```
[HOOK - direct to camera, energetic]
"OpenAI just dropped something that changes everything about AI agents."

[CONTEXT - slight lean in, serious tone]
"Their new Agents SDK lets developers build multi-step autonomous agents with built-in tool use."

[INSIGHT - gestures, emphasis]
"Here's what nobody is saying: this is a direct competitor to LangChain, CrewAI, and every agent framework out there. And it's free."

[TAKEAWAY - direct to camera]
"If you're building AI agents, you need to look at this today. Link in bio."
```

**What to Avoid:**
- Scripts over 60 seconds (retention drops off a cliff)
- Slow intros ("Hey guys, welcome back...")
- Abstract/theoretical content without concrete examples
- Reading from a teleprompter monotonically (varies with avatar limitations)
- Clickbait hooks that don't deliver

**Performance Notes:**
(Auto-updated by system)
- Videos using this skill: 0
- Avg view retention rate: pending
- Avg watch time: pending
- Best performing hook formula: pending
- Optimal video length: pending

---

#### `skills/library/creation/medium-article-format.md`

```yaml
---
name: medium-article-format
category: creation
platform: medium
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [medium, blog, long-form, seo, articles, publication]
---
```

**When to Use:** Structuring long-form content for Medium publication and distribution.

**Core Patterns:**

**Article Structure:**
1. **Headline:** Specific, benefits-focused, under 70 chars for SEO. Include a number or strong verb.
2. **Subtitle/Kicker:** Expands on headline with "so what" context. 100-150 chars.
3. **Opening paragraph (The Hook):** Start with a story, surprising stat, or bold claim. NOT a summary.
4. **"Why This Matters" section:** Context for why the reader should care.
5. **Body (3-5 sections with H2 headers):** One key point per section. Use subheadings.
6. **Practical takeaway:** What can the reader DO with this information today?
7. **Closing:** Brief, forward-looking, invites discussion (claps + comments).

**Length Guidelines:**
- Sweet spot: 1000-1500 words (7-10 min read, Medium shows read time)
- Under 800 feels thin; Medium audience expects substance
- Over 2000 only for truly deep technical breakdowns
- 7-minute read time is the Medium sweet spot per their internal data

**SEO & Medium Distribution:**
- Include target keyword in title, first paragraph, one H2, and naturally in body
- Add 3-5 Medium tags (these determine distribution in topics)
- Priority tags: "Artificial Intelligence", "AI Agents", "Automation", "Productivity", "Technology"
- Medium's algorithm rewards: read ratio (% who finish), claps, highlights, responses
- Submit to relevant publications (Towards AI, Better Programming, etc.) for distribution boost

**Medium-Specific:**
- Use code blocks with syntax highlighting (Medium supports this well)
- Include at least one image/diagram (breaks up text, increases shares)
- Pull quotes (highlight key sentences) encourage reader highlights
- End with a question to drive responses
- Cross-post to LinkedIn with a teaser + link (put link in first comment, not post body)
- Use the Medium API for programmatic publishing (POST to `/v1/users/{userId}/posts`)

**Medium API Integration:**
```
POST https://api.medium.com/v1/users/{userId}/posts
Headers: Authorization: Bearer {token}, Content-Type: application/json
Body: { title, contentFormat: "markdown", content, tags, publishStatus: "draft"|"public" }
```

**What to Avoid:**
- Generic "state of AI" overviews (too broad, everyone writes these)
- Pure news recaps without unique angle
- Listicles (save those for LinkedIn/Twitter)
- Jargon without explanation (Medium audience is broader than HN)
- Paywalled articles initially (build audience first with free content)

**Performance Notes:**
(Auto-updated by system)
- Articles using this skill: 0
- Avg read ratio: pending
- Avg claps per article: pending
- Avg new followers per article: pending
- Best performing article type: pending

---

### platform/ (4 skills)

#### `skills/library/platform/linkedin-optimization.md`

```yaml
---
name: linkedin-optimization
category: platform
platform: linkedin
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [linkedin, optimization, posting, hashtags, formatting, algorithm]
---
```

**When to Use:** Optimizing any content for LinkedIn's algorithm and audience behavior.

**Core Patterns:**

**Algorithm Signals (ranked by importance):**
1. **Dwell time** - how long people spend reading your post (long-form wins)
2. **Comments** - especially multi-word comments, not just "Great post!"
3. **Shares/Reposts** - strongest signal, hardest to get
4. **Reactions** - likes are baseline, other reactions (insightful, celebrate) weighted higher
5. **"See more" clicks** - hook quality signal

**Post Format Rules:**
- Optimal length: 150-300 words (enough for dwell time, not so long it's skipped)
- Use line breaks every 1-2 sentences (mobile readability)
- Leave blank line after first line (forces "see more" on mobile)
- Use bold text sparingly for key phrases
- End with a question (drives comments, algorithm loves it)

**Hashtag Strategy:**
- Use 3-5 hashtags (more looks spammy, fewer misses discoverability)
- Place at end of post, not inline
- Mix: 1 broad (#AI), 2 medium (#AIAgents, #Automation), 1-2 niche (#ContentAutopilot, #AgentFrameworks)
- Check hashtag follower counts: aim for mix of 10K+ and 1K-10K

**Image/Carousel Guidelines:**
- Single image posts get 2x engagement vs text-only
- Carousels (PDF uploads) get 3x engagement vs text-only
- Carousel sweet spot: 7-10 slides
- First slide must be scroll-stopping (title + bold visual)
- Last slide: CTA + "Follow for more"

**What to Avoid:**
- External links in post body (algorithm suppresses reach 40-50%)
- Put links in first comment instead
- Posting more than 2x per day (cannibalization)
- Editing post within first hour (resets algorithm distribution)
- Tagging people who won't engage (looks desperate, no algorithm boost)

**Performance Notes:**
(Auto-updated by system)
- Posts optimized: 0
- Avg engagement rate: pending
- Avg impressions: pending
- Best performing format: pending
- Link-in-comment vs in-post performance: pending

---

#### `skills/library/platform/twitter-optimization.md`

```yaml
---
name: twitter-optimization
category: platform
platform: twitter
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [twitter, x, optimization, posting, algorithm, engagement]
---
```

**When to Use:** Optimizing content for Twitter/X's algorithm and audience behavior.

**Core Patterns:**

**Algorithm Signals:**
1. **Reply engagement** - replies from accounts with followers matter most
2. **Retweets/Quotes** - distribution mechanism, get content in front of new audiences
3. **Bookmark** - strong "this is valuable" signal
4. **Dwell time** - time spent on tweet (images/threads increase this)
5. **Profile clicks** - signals curiosity about the author

**Tweet Format Rules:**
- Under 240 characters performs better than full 280 (feels punchy)
- One idea per tweet
- Use line breaks between sentences
- Images increase engagement 2-3x
- Polls get high engagement but lower quality interaction

**Thread Strategy:**
- First tweet must work as a standalone banger
- Include image in first tweet (increases visibility in feed)
- Numbered format (1/, 2/, etc.) or use 🧵 emoji
- Sweet spot: 5-8 tweets
- Last tweet: CTA + "Follow for more [topic]"

**Quote Tweet Strategy:**
- Quote tweeting trending content in your niche = free distribution
- Add a non-obvious insight (not just "This is great!")
- QTs of threads perform especially well
- QT major AI announcements with "Here's what this means for [audience]"

**What to Avoid:**
- Hashtags in every tweet (1-2 max, in first tweet only)
- Self-promotional threads without value
- Tweeting external links as standalone tweets (algorithm suppresses)
- Long reply chains to your own tweets (looks like talking to yourself)
- Engagement bait ("Like if you agree") - algorithm penalizes this

**Performance Notes:**
(Auto-updated by system)
- Tweets optimized: 0
- Avg impressions: pending
- Avg engagement rate: pending
- Best performing tweet format: pending
- QT vs original content performance: pending

---

#### `skills/library/platform/youtube-shorts-optimization.md`

```yaml
---
name: youtube-shorts-optimization
category: platform
platform: youtube
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [youtube, shorts, optimization, titles, tags, thumbnails, retention]
---
```

**When to Use:** Optimizing YouTube Shorts for the Shorts shelf algorithm.

**Core Patterns:**

**Title Rules:**
- Under 50 characters (truncated on mobile)
- Include primary keyword in first 3 words
- Use numbers when possible ("3 AI Tools...", "In 45 Seconds...")
- Create curiosity gap without being clickbait
- Avoid: ALL CAPS, excessive emoji, "YOU WON'T BELIEVE"

**Description:**
- First line = title keyword expansion
- Include 3-5 relevant keywords naturally
- Add "Shorts" and "shorts" somewhere (helps algorithm categorize)
- Link to full-length content if available
- Include social links

**Tags (still matter for Shorts):**
- 5-10 tags, mix of broad and specific
- First tag = primary keyword
- Include: topic, subtopic, audience, format
- Example: "AI agents, AI automation, Claude AI, productivity AI, AI tools 2026, tech shorts"

**Retention Strategy:**
- First 3 seconds determine if viewer stays (the hook)
- Change visual every 5-7 seconds
- Add on-screen text for key points (many watch muted)
- End with a loop-friendly moment (encourages rewatch)
- Don't fade to black (signals "end" to algorithm)

**Upload Timing:**
- Post when your audience is active (check analytics)
- Default: 12pm-3pm EST weekdays, 10am-1pm weekends
- YouTube distributes Shorts over 48-72 hours, so exact timing matters less than regular cadence

**What to Avoid:**
- Horizontal video (must be 9:16 vertical, under 60 seconds)
- Watermarks from other platforms (TikTok logo = suppressed)
- Poor audio quality (instant skip)
- Ending with "subscribe" before delivering value

**Performance Notes:**
(Auto-updated by system)
- Shorts optimized: 0
- Avg views: pending
- Avg watch time: pending
- Avg retention rate: pending
- Best performing title pattern: pending

---

#### `skills/library/platform/tiktok-optimization.md`

```yaml
---
name: tiktok-optimization
category: platform
platform: tiktok
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [tiktok, optimization, posting, algorithm, viral, discovery]
---
```

**When to Use:** Optimizing content for TikTok's For You Page algorithm.

**Core Patterns:**

**Algorithm Signals (ranked):**
1. **Watch time / completion rate** - #1 signal. If people watch to end, TikTok distributes more.
2. **Rewatch rate** - loops/rewatches = viral potential
3. **Shares** - strongest distribution signal
4. **Comments** - quantity and quality
5. **Follows from video** - "this creator is worth following" signal

**Content Rules for AI/Tech Niche:**
- TikTok's AI audience skews younger and less technical than LinkedIn
- Explain concepts simply, use analogies
- "Wow factor" matters more than depth
- Demonstrations > explanations (show the AI doing something cool)
- Face-to-camera builds trust faster than voiceover

**Format Guidelines:**
- Optimal length: 30-45 seconds (short enough for completion, long enough for substance)
- Hook in first 1-2 seconds (even more aggressive than YouTube)
- Vertical 9:16, 1080x1920
- Add captions/subtitles (80%+ watch muted initially)
- Use trending sounds when appropriate (but not forced)

**Caption & Hashtag Strategy:**
- Short caption that adds context or creates curiosity
- 3-5 hashtags: #AI, #AIAgents, #TechTok, #Automation, plus 1 niche
- Don't stuff hashtags in caption - looks spammy

**What to Avoid:**
- Reposting YouTube Shorts with YouTube watermark (heavily suppressed)
- Long intros or slow buildups
- Text-heavy slides without voiceover
- Controversial AI takes without nuance (TikTok comments can be brutal)
- Posting frequency > 3/day (diminishing returns)

**Performance Notes:**
(Auto-updated by system)
- Videos optimized: 0
- Avg views: pending
- Avg completion rate: pending
- Avg share rate: pending
- Best performing content type: pending

---

### tools/ (4 skills)

#### `skills/library/tools/heygen-avatar-video.md`

```yaml
---
name: heygen-avatar-video
category: tool
platform: heygen
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [heygen, avatar, video, generation, api, talking-head]
---
```

**When to Use:** Generating avatar-based talking-head videos via HeyGen API for YouTube Shorts, TikTok, and LinkedIn video.

**Core Patterns:**

**API Workflow:**
1. POST `/v2/video/generate` with script, avatar_id, voice config
2. Poll `/v1/video_status.get?video_id={id}` until status = "completed" (typically 2-5 min)
3. Download from the returned URL
4. Post-process: add captions, B-roll overlays if needed

**Avatar Selection:**
- **Founder persona** (`HEYGEN_AVATAR_ID_FOUNDER`): Use for opinion pieces, hot takes, personal stories. Casual, direct-to-camera.
- **Professional persona** (`HEYGEN_AVATAR_ID_PROFESSIONAL`): Use for news explainers, tutorials, data breakdowns. Polished, authoritative.
- Match persona to content type, not platform

**Script Optimization for HeyGen:**
- Keep scripts under 200 words (60-second target)
- Use simple sentence structure (avatar lip-sync is better with clear enunciation)
- Avoid: jargon clusters, very long words, rapid-fire lists
- Include natural pauses: use periods instead of commas for breathing room
- Write how people speak, not how they write ("Here's the thing" > "It is noteworthy that")

**Video Settings:**
- Dimension: 1080x1920 (vertical for Shorts/TikTok/Reels)
- For LinkedIn: 1920x1080 (horizontal)
- Avatar style: "normal" (not "circle" or "closeup" - these look gimmicky)
- Background: clean, branded, or contextual (office for professional, casual for founder)

**Quality Tips:**
- Direct-to-camera opening (first 3 seconds = avatar looking at viewer)
- Avoid starting with avatar looking away then turning (feels robotic)
- Script should specify gesture cues in brackets: [lean in], [gesture to side]
- Test different voice speeds: 1.0x for explanations, 1.1x for energy

**What to Avoid:**
- Scripts over 250 words (video will exceed 60s, bad for Shorts)
- Complex pronunciation (API names like "gRPC" may sound wrong)
- Monotone scripts without emotional variation
- Requesting multiple avatars in one video (not supported, creates uncanny effect)

**Error Handling:**
- If generation fails: retry once, then fall back to text-over-image video
- If video quality is poor: regenerate with simplified script
- Common error: "voice_id not found" - check voice is compatible with selected avatar

**Performance Notes:**
(Auto-updated by system)
- Videos generated: 0
- Avg generation time: pending
- Failure rate: pending
- Best performing avatar persona: pending
- Avg viewer retention: pending

---

#### `skills/library/tools/veo3-visual-generation.md`

```yaml
---
name: veo3-visual-generation
category: tool
platform: google
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [veo3, google, video, visual, generation, b-roll]
---
```

**When to Use:** Generating AI visual content (B-roll, transitions, abstract visuals) via Google Veo3 for use in video content alongside or instead of avatar footage.

**Core Patterns:**

**Best Use Cases:**
- B-roll footage for video content (abstract AI visualizations, data flows, futuristic interfaces)
- Intro/outro sequences for branded video content
- Visual metaphors for abstract concepts (neural networks, automation flows)
- Background visuals for voiceover content

**Prompt Engineering for Veo3:**
- Be specific about motion: "camera slowly zooms into", "particles flowing left to right"
- Specify style: "photorealistic", "3D render", "motion graphics", "cinematic"
- Include lighting: "soft ambient lighting", "neon glow", "studio lighting"
- Specify duration: "5 second clip" (shorter = higher quality)
- Include camera movement: "dolly forward", "orbit around", "static shot"

**Prompt Templates:**
```
B-roll: "A {style} visualization of {concept}, {camera_movement}, {lighting}, {duration}"
Example: "A cinematic 3D render of neural network nodes pulsing with data, slow dolly forward through the network, soft blue and purple neon lighting, 5 second clip"

Transition: "Abstract {style} transition from {state_a} to {state_b}, smooth morphing, {duration}"
Example: "Abstract motion graphics transition from scattered data points to organized grid pattern, smooth morphing animation, 3 second clip"
```

**Quality Settings:**
- Resolution: 1080p minimum
- Aspect ratio: Match target platform (9:16 for Shorts, 16:9 for YouTube/LinkedIn)
- Duration: 3-8 seconds per clip (shorter = better quality)

**What to Avoid:**
- Generating content with text/UI overlays (text will be garbled)
- Photorealistic human faces (uncanny valley)
- Very long clips (>10s quality degrades)
- Copying specific branded interfaces

**Performance Notes:**
(Auto-updated by system)
- Clips generated: 0
- Avg generation time: pending
- Quality acceptance rate: pending
- Best performing visual style: pending

---

#### `skills/library/tools/fal-image-generation.md`

```yaml
---
name: fal-image-generation
category: tool
platform: fal
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [fal, image, generation, nano-banana, carousel, social-media]
---
```

**When to Use:** Generating images via fal.ai for social media posts, carousel slides, and article illustrations.

**Core Patterns:**

**API Workflow:**
1. POST to `https://fal.run/fal-ai/fast-sdxl` (or appropriate model endpoint)
2. Include prompt, image_size, num_images, style preset
3. Response includes image URLs (hosted temporarily on fal CDN)
4. Download and store images for publishing

**Prompt Engineering for Social Media Images:**
- Start with the subject, then style, then details
- Include "social media" or "digital marketing" in style for appropriate aesthetic
- Specify exact dimensions for platform (1200x1200 LinkedIn, 1080x1080 Instagram, 1200x675 Twitter)
- Use negative prompts to avoid: "text, words, letters, watermark, logo, blurry, low quality"

**Prompt Templates by Content Type:**

**Carousel Slide Background:**
```
"Clean modern {color_scheme} gradient background with subtle geometric patterns, professional tech aesthetic, suitable for text overlay, {dimensions}"
```

**Infographic/Data Visual:**
```
"Professional infographic-style illustration showing {concept}, modern flat design, {brand_colors}, clean white space, no text, {dimensions}"
```

**Quote Card Background:**
```
"Minimalist abstract background with {mood} energy, soft gradients in {colors}, suitable for overlaid text, Instagram-ready, {dimensions}"
```

**Blog Post Hero Image:**
```
"Wide cinematic illustration of {concept}, modern tech aesthetic, {style: photorealistic|3d render|illustration}, {dimensions}"
```

**Brand Color Palette:**
- Primary: Blues (#1E40AF, #3B82F6) and purples (#7C3AED, #A78BFA)
- Accent: Clean whites (#FFFFFF, #F8FAFC)
- Energy: Teal (#14B8A6), warm orange (#F97316) for CTAs
- Avoid: Red (aggressive), yellow (cheap), neon (garish)

**What to Avoid:**
- Generating images with text (AI text is always garbled - add text in post-processing)
- Overly busy compositions (needs to read at mobile size)
- Stock photo aesthetic (generic business people, handshake shots)
- Copyrighted character or brand lookalikes

**Performance Notes:**
(Auto-updated by system)
- Images generated: 0
- Avg generation time: pending
- Quality acceptance rate: pending
- Best performing image type by platform: pending

---

#### `skills/library/tools/stagehand-browser-automation.md`

```yaml
---
name: stagehand-browser-automation
category: tool
platform: stagehand
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [stagehand, browser, automation, tiktok, instagram, publishing, fallback]
---
```

**When to Use:** When a platform lacks API access and we need browser automation to publish content. Primary use: TikTok, Instagram. Fallback for any platform where API is down.

**Core Patterns:**

**When to Use Stagehand vs API:**
- API available and working → always use API
- API down or rate-limited → Stagehand as fallback
- No API exists (TikTok creator, Instagram feed) → Stagehand is primary
- Complex multi-step workflows → Stagehand

**Stagehand Workflow for Publishing:**
1. Launch browser session with saved cookies/auth
2. Navigate to platform upload page
3. Upload media (image/video)
4. Fill in caption, hashtags, settings
5. Submit/publish
6. Verify publication success
7. Extract post ID/URL

**Reliability Patterns:**
- Always screenshot before and after actions (debugging)
- Wait for page load with explicit element checks, not timers
- Retry failed clicks up to 3 times
- If upload fails: clear form, re-navigate, try again
- Maximum 2 full retries before marking as "failed - manual needed"

**TikTok-Specific:**
- Use TikTok Creator Portal (web) not mobile
- Upload flow: click upload → select file → wait for processing → add caption → adjust settings → post
- Caption max: 4000 chars (but keep under 300 for engagement)
- Check "allow duets" and "allow stitches" = on (increases distribution)

**Instagram-Specific:**
- Use Instagram web (instagram.com)
- Upload flow: click + icon → select file → crop/filter → next → caption → share
- Carousel: select multiple files before crop step
- Reels: upload vertical video, add caption
- Note: Instagram web is limited vs mobile - some features missing

**What to Avoid:**
- Running Stagehand too frequently (platform may flag as bot)
- Skipping wait times between actions (looks automated)
- Uploading content with other platform watermarks (e.g., TikTok logo on Instagram)
- Using Stagehand during platform maintenance windows

**Error Recovery:**
- CAPTCHA detected → abort, mark as "manual needed", alert operator
- Login required → re-authenticate from saved credentials
- Upload timeout → retry with smaller file size
- Element not found → screenshot, log, try alternative selector

**Performance Notes:**
(Auto-updated by system)
- Automation runs: 0
- Success rate: pending
- Avg time per publish: pending
- Failure reasons breakdown: pending

---

### engagement/ (3 skills)

#### `skills/library/engagement/comment-reply-strategy.md`

```yaml
---
name: comment-reply-strategy
category: engagement
platform: all
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [engagement, comments, replies, community, growth, all-platforms]
---
```

**When to Use:** Replying to comments on our published content across all platforms.

**Core Patterns:**

**Reply Priority (which comments to reply to first):**
1. Questions about the content (shows interest, easy to add value)
2. Thoughtful disagreements (shows depth, algorithm loves debate)
3. Comments from accounts with large followings (visibility multiplier)
4. "Tag a friend" or sharing intent comments (encourage them)
5. Simple positive comments ("Great post!") - reply briefly to first few, then focus on substantive ones

**Reply Tone by Platform:**
- **LinkedIn:** Professional but warm. Add extra insight. Ask follow-up questions to drive deeper conversation.
- **Twitter/X:** Casual, punchy. Brevity wins. Drop a relevant link or stat. Use humor when appropriate.
- **YouTube:** Friendly, creator-to-viewer feel. Pin the best comment. Heart comments liberally.
- **TikTok:** Casual, emoji-friendly, generational-aware. Short replies. Consider "reply with video" for great questions.

**Reply Templates:**

**Adding value:**
```
"Great question! [Direct answer]. [Extra insight they didn't ask for but will find valuable]. What's your experience with [related topic]?"
```

**Handling disagreement:**
```
"Interesting perspective. [Acknowledge their point]. I see it differently because [reason + data]. What do you think about [specific aspect]?"
```

**Engagement driver:**
```
"Exactly! [Validate their point]. This connects to [broader topic]. I'm actually writing more about this - [tease next content]."
```

**Timing:**
- Reply to first 5-10 comments within 30 minutes of posting (signals to algorithm that post is generating conversation)
- Don't reply to ALL comments at once (spread over hours for sustained engagement signal)
- Reply to high-quality comments within 2 hours
- Batch remaining replies at 6h and 24h marks

**What to Avoid:**
- Generic replies ("Thanks!", "Appreciate it!") for every comment
- Arguing with trolls (one thoughtful reply max, then disengage)
- Reply-spamming your own post (looks desperate)
- Ignoring legitimate criticism (builds trust to address it)
- Using the same reply template visibly across comments

**Performance Notes:**
(Auto-updated by system)
- Comments replied to: 0
- Avg follow-on engagement after reply: pending
- Reply-to-conversion rate (commenter → follower): pending
- Best performing reply style: pending

---

#### `skills/library/engagement/proactive-engagement.md`

```yaml
---
name: proactive-engagement
category: engagement
platform: all
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [engagement, proactive, growth, networking, visibility, all-platforms]
---
```

**When to Use:** Proactively engaging on other people's content to build visibility and followers (not just replying to our own posts).

**Core Patterns:**

**"Founder Everywhere" Strategy:**
The brand/founder should be visible in conversations happening across the AI/automation space. Not self-promotional - genuinely adding value.

**Who to Engage With:**
1. AI thought leaders (Karpathy, Altman, Dario Amodei, Yann LeCun posts)
2. AI tool builders announcing products
3. People asking questions about AI agents/automation
4. Journalists covering AI (build relationships pre-need)
5. Potential customers discussing pain points we solve

**Engagement Types (ranked by value):**
1. **Insightful reply to a trending post** - adds data, personal experience, or a non-obvious angle. Highest ROI.
2. **Quote tweet with added context** - takes someone's insight and builds on it. Good distribution.
3. **Thoughtful comment on LinkedIn post** - 3-5 sentences that add value. Not "Great post!"
4. **Answering someone's question** - genuinely helpful, builds authority.
5. **Sharing someone's content with credit** - builds relationships with creators.

**Quality Bar:**
Every proactive engagement should pass this test:
- Would the original poster be glad we commented? (adds value, not noise)
- Does it subtly demonstrate our expertise? (without being salesy)
- Could a reader learn something from our comment alone?
- Is it specific to the content, not a generic template?

**Frequency:**
- LinkedIn: 5-10 proactive engagements per day
- Twitter: 10-20 per day (lower bar, faster pace)
- YouTube: 3-5 per day
- Don't cluster - spread throughout the day

**What to Avoid:**
- "Great post! We do something similar at [Company]..." (nobody likes this)
- Commenting on every post from one person (stalkerish)
- Generic motivational comments ("Keep going! 💪")
- Engaging with controversial political takes (brand risk)
- Negative comments about competitors

**Performance Notes:**
(Auto-updated by system)
- Proactive engagements: 0
- Avg profile visits from engagements: pending
- New followers attributed to proactive engagement: pending
- Best performing engagement type: pending

---

#### `skills/library/engagement/cold-start-growth.md`

```yaml
---
name: cold-start-growth
category: engagement
platform: all
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [growth, cold-start, followers, zero-to-one, bootstrap, all-platforms]
---
```

**When to Use:** Growing from zero (or near-zero) followers on a new platform account. Different tactics than accounts with existing audience.

**Core Patterns:**

**Phase 1: First 100 followers (Week 1-2)**
- Post 1-2x daily, high quality > high frequency
- Engage proactively 3x more than you post (10-15 comments/day)
- Find and engage in 3-5 community threads/posts daily
- Follow 20-30 relevant accounts per day (some will follow back)
- Share genuine reactions to trending AI news (ride the wave)
- Cross-promote: "Also posting about this on [other platform]"

**Phase 2: 100-500 followers (Week 3-6)**
- Increase posting to 2-3x daily
- Start creating original frameworks/lists ("My 5-step process for X")
- Tag relevant people in posts (not spam - genuine mentions)
- Engage with every comment on your posts (algorithm signal)
- Begin tracking what content types get most engagement
- Start threads/carousels (higher effort = higher engagement)

**Phase 3: 500-1000 followers (Week 7-12)**
- Establish consistent posting schedule
- Develop signature content series (weekly, recurring)
- Collaborate: co-create with similar-sized accounts
- Use platform-specific growth features (LinkedIn newsletter, Twitter Spaces, YouTube community)
- Start A/B testing content formats

**Cold Start Hacks (ethical):**
- Reply to viral tweets/posts in first 30 minutes (your reply gets seen by thousands)
- Create content that references influential people (they may engage)
- Join and actively participate in relevant groups/communities
- Share behind-the-scenes of building with AI (authenticity wins)
- Celebrate milestones publicly ("Just hit 100 followers! Here's what I've learned...")

**What to Avoid:**
- Buying followers (kills engagement rate, platforms detect it)
- Follow-for-follow schemes (low quality audience)
- Posting identical content across all platforms (each needs native feel)
- Giving up at day 10 (cold start is slow, exponential growth comes later)
- Comparing to established accounts (unfair benchmark)

**Performance Notes:**
(Auto-updated by system)
- Current follower counts by platform: pending
- Growth rate by platform: pending
- Best performing cold start tactic: pending
- Days to 100 followers by platform: pending

---

### timing/ (2 skills)

#### `skills/library/timing/optimal-posting-windows.md`

```yaml
---
name: optimal-posting-windows
category: timing
platform: all
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [timing, posting, schedule, optimal-times, all-platforms]
---
```

**When to Use:** Determining when to publish content on each platform for maximum reach.

**Core Patterns:**

**Starting Defaults (will be refined by performance data):**

| Platform | Best Days | Best Times (EST) | Worst Times |
|----------|-----------|-------------------|-------------|
| LinkedIn | Tue, Wed, Thu | 8-10am, 12pm | Weekends, after 6pm |
| Twitter/X | Mon-Fri | 9am, 12pm, 5pm | 1-4am |
| YouTube Shorts | Wed-Fri | 12-3pm, 7-9pm | Mon morning |
| TikTok | Tue-Thu | 7-9pm, 12pm | Early morning |
| Medium | Tue, Thu | 9-10am | Weekends, Friday PM |

**Time Zone Strategy:**
- Primary audience: US (ET/CT/PT)
- Post at ET-friendly times (8-10am ET hits EST, CST starts working, PST wakes up)
- For global content: consider 12pm ET (evening in Europe)

**Breaking News Exception:**
- If content is time-sensitive (new model release, major announcement): post IMMEDIATELY regardless of optimal time
- Arbitrage value of being first > timing optimization
- After breaking news post, return to optimal scheduling

**Content Type Timing:**
- Long-form (Substack, LinkedIn articles): Morning (people read with coffee)
- Short-form (tweets, shorts): Lunch and evening (snackable content)
- Video: Evening (more likely to watch with sound)
- Threads: Morning or lunch (reading time)

**Posting Cadence by Platform:**
- LinkedIn: 1-2 posts/day max, 5-7 days/week
- Twitter: 3-5 tweets/day, 7 days/week
- YouTube Shorts: 1/day, 5-7 days/week
- TikTok: 1-2/day, 5-7 days/week
- Medium: 2-3 articles/week

**What to Avoid:**
- Posting at the same exact time every day (looks automated)
- Posting multiple pieces within 30 minutes on same platform (cannibalization)
- Scheduling long-form content for Friday evening (nobody reads it)
- Ignoring platform analytics data once available

**Performance Notes:**
(Auto-updated by system)
- Posts tracked with timing data: 0
- Best performing time window by platform: pending
- Worst performing time window: pending
- Breaking news vs scheduled performance: pending

---

#### `skills/library/timing/content-spacing.md`

```yaml
---
name: content-spacing
category: timing
platform: all
confidence: 0.5
status: active
version: 1
created: 2026-01-28
last_validated: null
tags: [timing, spacing, cadence, cannibalization, frequency, all-platforms]
---
```

**When to Use:** Determining how to space multiple pieces of content to avoid cannibalization and maintain consistent presence.

**Core Patterns:**

**Minimum Spacing Rules (same platform):**
- LinkedIn: 4+ hours between posts (posting sooner cannibalizes reach of first post)
- Twitter: 1+ hour between tweets, 4+ hours between threads
- YouTube Shorts: 6+ hours between uploads
- TikTok: 3+ hours between posts
- Medium: 2+ days between articles

**Cross-Platform Coordination:**
- When covering the same topic across platforms, stagger:
  1. Twitter first (fastest platform, breaking news)
  2. LinkedIn 1-2 hours later (professional audience, deeper take)
  3. YouTube Short 2-4 hours later (requires video generation time anyway)
  4. TikTok same day or next day (can reuse YouTube content)
  5. Medium 1-2 days later (deep dive version, references social performance)

**Topic Fatigue Prevention:**
- Don't post about the same topic more than 2x in a day (even across platforms)
- Rotate between topic categories: AI news, how-to, opinion, tool review, meta-learning
- Follow the 4-1-1 rule: 4 value posts, 1 soft-sell, 1 direct promotion

**Content Queue Management:**
- Maintain a queue of 5-10 pieces ready to publish
- Priority order: time-sensitive > high-relevance > evergreen
- If queue is empty: create evergreen content (not time-dependent)
- If queue is full (10+): prioritize ruthlessly, expire items older than 72 hours

**What to Avoid:**
- Publishing everything as soon as it's created (wasteful, cannibalizes)
- Saving great content for "the right time" too long (it goes stale)
- Irregular posting (3 posts Monday, nothing until Thursday)
- Posting same format repeatedly (carousel, carousel, carousel - mix it up)

**Performance Notes:**
(Auto-updated by system)
- Content spacing tracked: 0
- Cannibalization detected: pending
- Optimal spacing by platform: pending
- Cross-platform stagger effectiveness: pending

---

## ENV VARS NEEDED (UPDATED FOR BEDROCK)

```bash
# LLM (AWS Bedrock)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514-v1:0

# Image Generation
FAL_KEY=

# Video - HeyGen
HEYGEN_API_KEY=
HEYGEN_AVATAR_ID_FOUNDER=
HEYGEN_AVATAR_ID_PROFESSIONAL=

# Video - Veo3
GOOGLE_API_KEY=

# Publishing - LinkedIn
LINKEDIN_ACCESS_TOKEN=

# Publishing - X/Twitter
X_API_KEY=
X_API_SECRET=
X_ACCESS_TOKEN=
X_ACCESS_TOKEN_SECRET=

# Publishing - YouTube (optional)
YOUTUBE_API_KEY=
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=

# System
DATABASE_URL=sqlite+aiosqlite:///./autopilot.db
CONTENT_AUTOPILOT_ENABLED=true
LOG_LEVEL=INFO
```

Note: Sources (HN, Reddit, GitHub, Lobsters, ArXiv, Company Blogs, Product Hunt) are all scrape-based and require NO API keys.

---

## DATABASE SCHEMA (SQLite)

9 tables. Unchanged from original plan:

1. **content_discoveries** - Raw items from sources
2. **content_creations** - Generated content (text, images, video)
3. **content_publications** - Published posts with platform IDs + `arbitrage_window_minutes`
4. **content_metrics** - Engagement metrics at intervals (1h, 6h, 24h, 48h, 7d)
5. **content_playbook** - Brand identity config (name, voice, topics, avoid_topics)
6. **content_experiments** - A/B test definitions and results
7. **content_agent_runs** - Agent execution logs with cost tracking
8. **skill_records** - Skill metadata, confidence, health status
9. **skill_metrics** - Individual skill usage outcomes

---

## FILE STRUCTURE

```
hack-demo/content-autopilot/
├── pyproject.toml
├── .env.example
├── main.py
├── config.py
├── db.py
├── models.py
├── skills/
│   ├── __init__.py
│   ├── base.py
│   ├── manager.py
│   ├── evaluator.py
│   ├── synthesizer.py
│   ├── library/
│   │   ├── sources/          (4 skill files)
│   │   │   ├── hackernews-scoring.md
│   │   │   ├── reddit-signal-detection.md
│   │   │   ├── arxiv-mainstream-prediction.md
│   │   │   └── company-blog-monitoring.md
│   │   ├── creation/         (4 skill files)
│   │   │   ├── linkedin-hook-writing.md
│   │   │   ├── twitter-thread-structure.md
│   │   │   ├── youtube-shorts-scripting.md
│   │   │   └── medium-article-format.md
│   │   ├── platform/         (4 skill files)
│   │   │   ├── linkedin-optimization.md
│   │   │   ├── twitter-optimization.md
│   │   │   ├── youtube-shorts-optimization.md
│   │   │   └── tiktok-optimization.md
│   │   ├── tools/            (4 skill files)
│   │   │   ├── heygen-avatar-video.md
│   │   │   ├── veo3-visual-generation.md
│   │   │   ├── fal-image-generation.md
│   │   │   └── stagehand-browser-automation.md
│   │   ├── engagement/       (3 skill files)
│   │   │   ├── comment-reply-strategy.md
│   │   │   ├── proactive-engagement.md
│   │   │   └── cold-start-growth.md
│   │   └── timing/           (2 skill files)
│   │       ├── optimal-posting-windows.md
│   │       └── content-spacing.md
│   └── versions/             (auto-populated by system)
├── sources/
│   ├── __init__.py
│   ├── base.py
│   ├── hackernews.py          # HN Algolia API (no auth)
│   ├── reddit.py              # Reddit JSON (no auth)
│   ├── product_hunt.py        # PH homepage scrape (no auth)
│   ├── github_trending.py     # GitHub scrape (no auth)
│   ├── lobsters.py            # Lobsters JSON (no auth)
│   ├── arxiv.py               # ArXiv Atom feed (no auth)
│   └── company_blogs.py       # RSS feeds (no auth)
├── agents/
│   ├── __init__.py
│   ├── base.py
│   ├── scout.py
│   ├── analyst.py
│   ├── creator.py
│   ├── engagement.py
│   ├── tracker.py
│   └── reviewer.py
├── generators/
│   ├── __init__.py
│   ├── text.py
│   ├── image.py
│   ├── video_heygen.py
│   └── video_veo3.py
├── publishers/
│   ├── __init__.py
│   ├── base.py
│   ├── linkedin.py
│   ├── twitter.py
│   ├── youtube.py
│   ├── medium.py
│   └── tiktok.py
├── approval/
│   ├── __init__.py
│   ├── risk_assessor.py
│   └── queue.py
├── learning/
│   ├── __init__.py
│   ├── metrics_collector.py
│   ├── pattern_analyzer.py
│   ├── experiment_runner.py
│   └── feedback_loop.py
├── orchestrator.py
├── routes.py
└── dashboard.py
```

Total: ~60 Python/config files + 21 seed skill markdown files = ~81 files

---

## DEMO-AMPLIFYING IDEAS

1. **Skill Genealogy** - Show version tree of how each skill evolved
2. **Time Machine Replay** - Fast-forward through system's learning over time
3. **Multi-Brand Config Swap** - Skills transfer between brands instantly
4. **Arbitrage Scoreboard** - "We posted 4.2 hrs before TechCrunch"
5. **Cost Comparison** - "47 pieces this week. Human equivalent: $45K/mo. Our cost: $127"
6. **The Aha Moment** - System discovers counter-intuitive insight autonomously (e.g., posting schedule split by platform)
7. **Skills as Platform Play** - Marketplace narrative for investors
8. **Claude Code Export** - Export skills as Claude Code compatible SKILL.md files

---

## RESOLVED QUESTIONS

1. **Brand identity** - RESOLVED: "Autopilot by Kairox AI" (usually just "Autopilot"). No mention of MailAI.
2. **Live publishing accounts** - RESOLVED: Test accounts exist for all platforms. System publishes for real.
3. **HeyGen avatars** - RESOLVED: Account exists, avatars not yet configured. Plan includes setup steps where Claude Code guides the operator through avatar creation.
4. **Demo data strategy** - RESOLVED: Run live for real days. Build system so demo data seeder can be added later (timestamped entries, append-only skill history).
5. **Blog platform** - RESOLVED: Medium instead of Substack (Medium has developer-friendly API, Substack does not).
6. **LLM access** - RESOLVED: AWS Bedrock, not direct Anthropic API.
7. **Sources** - RESOLVED: All scrape-based, no API keys for discovery. Twitter/X skipped.

## REMAINING OPEN QUESTIONS

1. **Demo audience** - Investors only, or also technical co-founders/engineers? Affects emphasis.
2. **Notification channel** - For approval queue alerts: dashboard-only, Slack, email?
3. **Demo timeline** - Any specific date the demo needs to be ready by?
4. **Medium publication** - Should we publish to a Medium publication (e.g., "Towards AI") or standalone profile? Publications get more distribution but require approval.
5. **Brand voice examples** - Any existing content that exemplifies the ideal Autopilot voice/tone? Would help calibrate the creation skills.
