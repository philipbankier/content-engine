# Scripts

Utility scripts for Content Autopilot demo setup and maintenance.

## Demo Data Seeding

### `seed_demo_data.py`

Generates 14 days of realistic historical data for investor demos.

**What it creates:**
- ~180 publications across 5 platforms
- ~1,000 engagement metric data points at intervals (1h, 6h, 24h, 48h, 7d)
- 8 completed A/B experiments with results
- 21 skill records with evolved versions (6 skills have v2/v3)
- ~500 skill usage metrics
- ~1,000 agent execution logs with cost tracking
- Content arbitrage timing data (1-12 hours ahead of competitors)
- Skill version files in `skills/versions/`

**How to run:**

```bash
# From project root
python scripts/seed_demo_data.py
```

**Expected output:**
```
======================================================================
Content Autopilot Demo Data Seeder
======================================================================
Demo period: 2026-01-15 to 2026-01-29 (14 days)

Initializing database...

Clearing existing demo data...
✓ Cleared tables

Updating playbook configuration...
✓ Playbook configured: Autopilot by Kairox AI

Seeding discoveries (14 days)...
✓ Seeded 268 discoveries

Seeding publications and metrics...
  Progress: 20/180 publications
  Progress: 40/180 publications
  ... (continues)
✓ Seeded 180 publications with engagement metrics

Seeding A/B experiments...
✓ Seeded 8 completed A/B experiments

Seeding skill records...
✓ Seeded 21 skill records

Seeding skill usage metrics...
✓ Seeded 478 skill usage metrics

Seeding agent execution logs...
✓ Seeded 1092 agent runs
  Total cost: $127.34 over 14 days

Creating skill version files...
✓ Created skill version files in skills/versions

======================================================================
Demo data seeding complete!
======================================================================

Next steps:
1. Start the system: python main.py
2. Open dashboard: http://localhost:8001
3. Navigate to Skills view to see evolution
4. Check Metrics view for engagement data
5. Review Experiments view for A/B test results
```

**What to verify after running:**

```bash
# Check database has data
sqlite3 autopilot.db "SELECT COUNT(*) FROM content_publications;" # Should show ~180
sqlite3 autopilot.db "SELECT COUNT(*) FROM content_metrics;" # Should show ~1000
sqlite3 autopilot.db "SELECT COUNT(*) FROM content_experiments;" # Should show 8
sqlite3 autopilot.db "SELECT COUNT(*) FROM skill_records;" # Should show 21

# Check skill versions created
ls skills/versions/linkedin-hook-writing/ # Should show v2.md, v3.md
ls skills/versions/optimal-posting-windows/ # Should show v2.md
```

**When to run:**
- **Once** before investor demo
- After any major database schema changes (to repopulate)
- When you need fresh demo data

**Important notes:**
- Script clears existing publications/metrics/experiments to ensure clean demo data
- Preserves existing discoveries (adds more if needed)
- Takes ~30-60 seconds to run depending on system
- Safe to run multiple times (idempotent)

## Troubleshooting

**Error: "No module named 'frontmatter'"**
```bash
pip install python-frontmatter
```

**Error: "database is locked"**
- Stop the main application first: `pkill -f "python main.py"`
- Run seeding script
- Restart application

**Seeding succeeds but dashboard shows no data:**
- Check database file: `ls -lh autopilot.db`
- Verify tables have data: `sqlite3 autopilot.db ".tables"`
- Check browser console for API errors

**Skill versions not showing:**
- Check files created: `find skills/versions -name "*.md"`
- Restart application to reload skill manager
- Check skill detail API: `curl http://localhost:8001/skills/linkedin-hook-writing`
