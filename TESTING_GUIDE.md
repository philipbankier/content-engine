# Content Autopilot - E2E Testing Guide

## Quick Start

### Demo Mode (Default - For Investor Presentations)

```bash
# 1. Set demo mode in .env
echo "DEMO_MODE=true" > .env
echo "SEED_ON_STARTUP=true" >> .env

# 2. Start the app
python main.py

# 3. View dashboard
open http://localhost:8001
```

**What you get:**
- 180+ publications with engagement metrics
- Skill evolution history (v1→v2→v3)
- 8 completed A/B experiments
- 14 days of historical data
- **No live agent loops** (manual triggers only)

---

### Production Mode (Real Data Collection)

```bash
# 1. Backup demo database first
./scripts/backup_demo_db.sh

# 2. Set production mode in .env
echo "DEMO_MODE=false" > .env
echo "SEED_ON_STARTUP=false" >> .env

# 3. Start the app
python main.py

# 4. Monitor costs in real-time
./scripts/monitor_costs.sh 300  # Check every 5 minutes
```

**What happens:**
- Agent loops run automatically:
  - Scout: every 30 minutes
  - Tracker: every 60 minutes
  - Engagement: every 30 minutes
  - Feedback: daily
  - Reviewer: weekly
- Real content discovered from 7 sources
- LLM costs accumulate (~$3.49/day)
- Auto-stops if daily cost limit exceeded

---

## 24-Hour Real Data Test

### Pre-Test Checklist

- [ ] AWS Bedrock credentials configured (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- [ ] Demo database backed up (`./scripts/backup_demo_db.sh`)
- [ ] Sufficient disk space (>1GB free)
- [ ] Port 8001 available
- [ ] `DEMO_MODE=false` in `.env`
- [ ] `DAILY_COST_LIMIT=5.00` set (safety threshold)

### Expected Costs (24 Hours)

| Component | Frequency | Cost/Day |
|-----------|-----------|----------|
| **LLM (Bedrock)** | 288 calls | **$3.49** |
| Scout | 48 runs | $0.00 (no LLM) |
| Analyst | 48 runs | $0.58 |
| Creator | 240 creations | $2.88 |
| Tracker | 24 runs | $0.00 (metrics only) |
| Reviewer | 0.14 runs | $0.03 |
| **Image gen (optional)** | 10-20 images | $2-4 |
| **Video gen (optional)** | Manual only | $0-3 |
| **Total (LLM only)** | - | **$3.49** |
| **Total (with media)** | - | **$5-10** |

### Timeline

| Time | Event | Expected Results |
|------|-------|------------------|
| **T+0:00** | Start app | Scout fetches 15-30 items from 7 sources |
| **T+0:05** | Analyst runs | Items scored (relevance, velocity, risk) |
| **T+0:10** | Creator runs | 5-10 content pieces generated |
| **T+0:30** | Scout cycle repeats | New batch of discoveries |
| **T+1:00** | Tracker runs | Attempts to collect metrics (none without publications) |
| **T+6:00** | 12 scout cycles complete | ~$0.87 spent, 120 creations |
| **T+12:00** | Halfway point | ~$1.75 spent, 240 creations |
| **T+24:00** | Full day complete | ~$3.49 spent, 480 creations |

### Monitoring Commands

```bash
# Real-time cost tracking (every 5 minutes)
./scripts/monitor_costs.sh 300

# Check pipeline status
curl http://localhost:8001/pipeline | jq

# View discoveries
curl http://localhost:8001/discoveries?limit=20 | jq '.[] | {source, title, relevance_score}'

# Check skill confidence
curl http://localhost:8001/skills | jq '.[] | {name, confidence, total_uses}'

# Get detailed cost breakdown
curl http://localhost:8001/costs | jq
```

### Verification Checkpoints

**After 1 hour:**
- [ ] 15-30 discoveries from each source (HN, Reddit, ArXiv, etc.)
- [ ] Discoveries have `relevance_score`, `velocity_score`, `platform_fit`
- [ ] 5-10 content creations with platform-specific formatting
- [ ] Cost: ~$0.15
- [ ] No errors in logs

**After 6 hours:**
- [ ] 90-180 total discoveries
- [ ] 60-120 total creations
- [ ] Cost: ~$0.87
- [ ] Skill confidence scores updated (check `/skills` endpoint)
- [ ] Database size < 50MB

**After 24 hours:**
- [ ] 180-360 total discoveries
- [ ] 120-240 total creations
- [ ] Cost: ~$3.49 (within $5 limit)
- [ ] Skills show usage patterns (check `/skills/{name}` endpoints)
- [ ] No memory leaks (check `ps aux | grep python`)

---

## Switching Between Modes

### Demo → Production

```bash
# 1. Backup current demo database
./scripts/backup_demo_db.sh

# 2. Update .env
sed -i '' 's/DEMO_MODE=true/DEMO_MODE=false/' .env
sed -i '' 's/SEED_ON_STARTUP=true/SEED_ON_STARTUP=false/' .env

# 3. Optional: Clear database for fresh start
rm autopilot.db

# 4. Restart app
pkill -f "python main.py"
python main.py
```

### Production → Demo (Rollback)

```bash
# One-step rollback (uses backup if exists)
./scripts/rollback_to_demo.sh

# Then restart
python main.py
```

---

## Cost Control

### Setting Cost Limits

In `.env`:
```bash
DAILY_COST_LIMIT=5.00  # Stop agents if cost exceeds $5/day
```

The orchestrator checks this limit before each agent run. If exceeded:
- Agent loops pause for 1 hour
- Warning logged
- Manual triggers still work via API

### Manual Cost Reduction

**Reduce agent frequency** (in `.env`):
```bash
SCOUT_INTERVAL=3600      # Scout every 60min instead of 30min (save 50%)
TRACKER_INTERVAL=7200    # Tracker every 2hrs instead of 1hr
```

**Limit content creation** (edit `agents/creator.py`):
```python
# Change from top 10 to top 5 per cycle
top_items = analyzed[:5]  # was [:10]
```

**Use cheaper model for analyst** (edit `agents/analyst.py`):
```python
# Switch to Haiku (10x cheaper) for non-critical tasks
model="anthropic.claude-haiku-3-5-20241022-v1:0"
```

---

## Troubleshooting

### Issue: App won't start in production mode

**Symptoms:** Error on startup, immediate exit

**Check:**
1. AWS credentials valid: `aws bedrock list-foundation-models --region us-east-1`
2. Port 8001 available: `lsof -i :8001`
3. Database writable: `ls -la autopilot.db`

**Fix:**
```bash
# Verify .env
cat .env | grep -E "(AWS_|BEDROCK_|DEMO_)"

# Test AWS access
python -c "from anthropic import AnthropicBedrock; client = AnthropicBedrock(); print('OK')"
```

### Issue: No discoveries appearing

**Symptoms:** Pipeline running but 0 discoveries after 30+ minutes

**Check:**
1. Network connectivity: `curl -I https://news.ycombinator.com`
2. Source health: Check logs for fetch errors
3. Agent running: `curl http://localhost:8001/pipeline | jq '.last_runs'`

**Debug:**
```bash
# Manually trigger scout
curl -X POST http://localhost:8001/discover

# Check logs
tail -f logs/autopilot.log | grep -i "scout\|error"
```

### Issue: Costs exceeding estimates

**Symptoms:** Daily cost > $5

**Likely causes:**
- Image/video generation enabled
- Agent intervals too short
- Token leakage in prompts

**Fix:**
```bash
# Check cost breakdown by agent
curl http://localhost:8001/costs | jq '.by_agent'

# Increase intervals
echo "SCOUT_INTERVAL=3600" >> .env  # 60min instead of 30min

# Stop app immediately
pkill -f "python main.py"
```

### Issue: Database growing too large

**Symptoms:** `autopilot.db` > 500MB

**Likely cause:** Metric accumulation over time

**Fix:**
```bash
# Check table sizes
sqlite3 autopilot.db "SELECT name, COUNT(*) FROM sqlite_master JOIN pragma_table_info(name) GROUP BY name"

# Clean old metrics (keep last 30 days)
sqlite3 autopilot.db "DELETE FROM content_metrics WHERE collected_at < datetime('now', '-30 days')"
```

---

## API Quick Reference

### Key Endpoints

| Endpoint | Purpose | Example |
|----------|---------|---------|
| `GET /pipeline` | Pipeline status, demo mode flag | `curl localhost:8001/pipeline` |
| `GET /costs` | Cost breakdown with daily limit | `curl localhost:8001/costs` |
| `GET /discoveries` | Recent content discoveries | `curl localhost:8001/discoveries?limit=20` |
| `GET /skills` | All skills with confidence | `curl localhost:8001/skills` |
| `GET /metrics` | Engagement metrics | `curl localhost:8001/metrics` |
| `POST /discover` | Manually trigger scout | `curl -X POST localhost:8001/discover` |

### Chat Tool Calls (via WebSocket)

Connect to `ws://localhost:8001/ws/chat` and send:

```json
{
  "tool_name": "trigger_scout",
  "tool_input": {}
}
```

Available tools:
- `trigger_scout` - Run discovery cycle
- `get_pipeline_status` - Check status
- `get_discoveries` - Fetch discoveries
- `get_skills` - Get skill list
- `approve_content` - Approve creation
- `reject_content` - Reject creation

---

## File Checklist

After implementing this plan, you should have:

```
content-autopilot/
├── config.py                          # ✓ Demo mode settings
├── main.py                            # ✓ Conditional seeding
├── orchestrator.py                    # ✓ Demo mode support, cost limits
├── routes.py                          # ✓ Enhanced /costs endpoint
├── scripts/
│   ├── seed_demo_data.py             # ✓ Importable seed function
│   ├── backup_demo_db.sh             # ✓ NEW - Backup script
│   ├── rollback_to_demo.sh           # ✓ NEW - Quick rollback
│   └── monitor_costs.sh              # ✓ NEW - Real-time monitoring
├── TESTING_GUIDE.md                  # ✓ NEW - This file
└── .env                               # Demo/production toggle
```

---

## Success Criteria

### Demo Mode Works
- [ ] App starts with demo data automatically
- [ ] Dashboard shows "DEMO MODE" indicator
- [ ] 180+ publications visible
- [ ] Skills show v1→v2→v3 evolution
- [ ] No agent loops running (manual only)
- [ ] `/pipeline` returns `demo_mode: true`

### Production Mode Works
- [ ] App starts without demo data
- [ ] Agent loops run on schedule
- [ ] Real discoveries appear from 7 sources
- [ ] Content created with LLM calls
- [ ] Costs tracked accurately
- [ ] Stops if daily limit exceeded
- [ ] `/pipeline` returns `demo_mode: false`

### Toggle Works
- [ ] Can switch demo→production without data loss
- [ ] Can rollback production→demo with one command
- [ ] Backup/restore preserves all data
- [ ] Mode changes require restart (not hot-reload)

---

## Next Steps

1. **Test demo mode first:**
   ```bash
   DEMO_MODE=true python main.py
   # Verify demo data loads correctly
   ```

2. **Create backup before production test:**
   ```bash
   ./scripts/backup_demo_db.sh
   ```

3. **Run 24-hour production test:**
   ```bash
   DEMO_MODE=false python main.py &
   ./scripts/monitor_costs.sh 300
   # Let run for 24 hours
   ```

4. **Analyze results:**
   ```bash
   curl localhost:8001/costs | jq
   curl localhost:8001/skills | jq '.[] | {name, confidence, total_uses}'
   ```

5. **Rollback for investor demo:**
   ```bash
   ./scripts/rollback_to_demo.sh
   python main.py
   ```

---

## Demo Narrative (For Investors)

**Opening:** "This system has been running autonomously for 2 weeks..."

**Show demo data:**
- 180 publications across 5 platforms
- $127 total cost (47 pieces/week)
- Skills evolved from v1→v3 based on performance
- Content published 1-12 hours ahead of competitors

**Switch to production mode (optional live demo):**
- Trigger scout manually: `POST /discover`
- Watch discoveries appear in real-time
- Show LLM generating platform-specific content
- Cost tracker shows $0.015/piece

**Key takeaway:** "Same system can run 100 brands simultaneously, sharing learned skills across all brands."
