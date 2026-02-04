# Content Autopilot - Quick Start Guide

Get the demo running in 5 minutes.

## Prerequisites

- Python 3.11+
- pip or poetry
- AWS Bedrock access (credentials in .env)

## Step 1: Install Dependencies

```bash
cd hack-demo/content-autopilot
pip install -e .
# or: pip install -r requirements.txt
```

## Step 2: Configure Environment

```bash
cp .env.example .env
# Edit .env and add:
# - AWS_ACCESS_KEY_ID
# - AWS_SECRET_ACCESS_KEY
# - AWS_REGION (default: us-east-1)
# - BEDROCK_MODEL_ID (default: anthropic.claude-sonnet-4-20250514-v1:0)
```

## Step 3: Seed Demo Data (First Time Only)

```bash
python scripts/seed_demo_data.py
```

Expected output:
```
✓ Seeded 180 publications
✓ Seeded 8 completed A/B experiments
✓ Seeded 21 skill records
✓ Created skill version files
Demo data seeding complete!
```

## Step 4: Verify Demo Ready

```bash
python scripts/verify_demo_ready.py
```

Should see: `✅ DEMO READY!`

## Step 5: Start the System

```bash
python main.py
```

You should see:
```
Creating database tables...
Loading skills...
Loaded 21 skills
Starting orchestrator...
Autopilot by Kairox AI is running on http://localhost:8001
```

## Step 6: Open Dashboard

Navigate to: **http://localhost:8001**

You should see the Content Autopilot dashboard with:
- Pipeline status
- Recent discoveries
- Skills view (navigate to see evolved skills)
- Metrics and engagement data
- A/B experiments

## Key Demo Views

### 1. Skills View
**Path:** Dashboard → Skills

**What to show:**
- Click on `linkedin-hook-writing` skill
- Show version history: v1 → v2 → v3
- Point out confidence scores increasing
- Explain: "System discovered question hooks work better, updated itself"

### 2. Experiments View
**Path:** Dashboard → Experiments

**What to show:**
- 8 completed A/B tests
- Clear winners (e.g., "Question hooks vs Statement hooks")
- Statistical confidence from sample sizes

### 3. Metrics View
**Path:** Dashboard → Metrics

**What to show:**
- Engagement curves over time
- Platform distribution
- Cost tracking (~$127 for 2 weeks)

### 4. Arbitrage View
**Path:** Dashboard → Arbitrage (or via API: GET /arbitrage)

**What to show:**
- Average time advantage: 3-7 hours ahead
- Specific examples of beating mainstream media

## Testing the Chat Interface

Click "Chat" in the dashboard and try:

```
Show me the pipeline status
```

```
What skills do we have for LinkedIn?
```

```
Show me recent publications
```

The AI agent will use tools to fetch real data from the database.

## Troubleshooting

### "Module not found" errors
```bash
pip install -e .
```

### "Database is locked"
```bash
# Stop any running instances
pkill -f "python main.py"
# Try again
python main.py
```

### Port 8001 already in use
Edit `.env`:
```
PORT=8002
```

### Dashboard shows no data
1. Check seeding: `python scripts/verify_demo_ready.py`
2. If issues, re-run: `python scripts/seed_demo_data.py`
3. Restart system: `python main.py`

### Skills not showing evolved versions
1. Check version files exist: `ls skills/versions/linkedin-hook-writing/`
2. Restart system to reload skills
3. Check API: `curl http://localhost:8001/skills/linkedin-hook-writing`

## API Endpoints

All endpoints available at `http://localhost:8001`:

| Endpoint | Description |
|----------|-------------|
| `GET /pipeline` | Pipeline status |
| `GET /skills` | All skills |
| `GET /skills/{name}` | Skill detail |
| `GET /skills/{name}/history` | Skill usage history |
| `GET /discoveries` | Recent discoveries |
| `GET /publications` | Published content |
| `GET /metrics` | Engagement data |
| `GET /experiments` | A/B tests |
| `GET /arbitrage` | Arbitrage scoreboard |
| `GET /costs` | Cost breakdown |
| `POST /discover` | Trigger scout manually |

## Demo Script

For investor presentations, follow: **DEMO_SCRIPT.md**

**5-minute walkthrough:**
1. Opening hook (30s)
2. Skill evolution - the "aha moment" (90s)
3. Content arbitrage timing (45s)
4. Multi-platform intelligence (45s)
5. A/B testing (30s)
6. Cost efficiency (45s)
7. Closing (30s)

## Next Steps

- [x] System running
- [ ] Practice demo from DEMO_SCRIPT.md
- [ ] Record 5-minute demo video
- [ ] Prepare backup screenshots
- [ ] Send to investors

## Support

**Key Documentation:**
- Architecture: `CLAUDE.md`
- Completion status: `IMPLEMENTATION_COMPLETE.md`
- Demo script: `DEMO_SCRIPT.md`
- Seeding guide: `scripts/README.md`

**System Stats:**
- Lines of code: ~7,000
- Agent runs: 1,097
- Discoveries: 1,970
- Skills: 21 (6 evolved)
- Publications: ~180 (after seeding)
- Cost: ~$127 for 2 weeks

---

**You're ready to demo. 🚀**
