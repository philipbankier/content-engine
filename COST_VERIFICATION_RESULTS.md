# Cost Verification Test Results

**Date:** 2026-02-04
**Test Type:** Test 1 - Typical Run (No Video)

---

## Summary

| Metric | Estimated | Actual |
|--------|-----------|--------|
| Per-run cost (1-2 pieces) | $0.08-0.15 | ~$0.04 |
| Per-content piece | ~$0.05-0.08 | ~$0.018 |

**Result:** Actual costs are ~50% LOWER than estimated. Cost tracking is working correctly.

---

## Test Details

### What Was Executed

1. **Scout Cycle**: 139 discoveries from 7 sources (HN, Reddit, GitHub, Lobsters, ArXiv, Company Blogs, Product Hunt)
2. **Analyst Batch**: 139 items analyzed for relevance, velocity, risk, and platform fit
3. **Creator Batch**: 76 content pieces from 10 top discoveries

### Content Created

| Platform | Count | Format |
|----------|-------|--------|
| LinkedIn | 14 | posts |
| Twitter | 14 | threads |
| YouTube | 12 | shorts |
| TikTok | 10 | shorts |
| **Total** | **50** | mixed |

(Note: 76 pieces created, 50 unique after variants)

---

## Cost Breakdown

### LLM Costs (Tracked via `/costs`)

| Agent | Runs | Cost | Input Tokens | Output Tokens |
|-------|------|------|--------------|---------------|
| Analyst | 7 | $0.42 | 20,578 | 23,752 |
| Creator | 76 | $0.59 | 43,688 | 30,679 |
| **Total** | **83** | **$1.01** | **64,266** | **54,431** |

### Image Generation Costs (fal.ai - NOT tracked)

- 76 images generated @ ~$0.005 each = ~$0.38

### Total Actual Cost

```
LLM (Bedrock):     $1.01
Images (fal.ai):   $0.38
--------------------------------
TOTAL:             ~$1.39
```

---

## Per-Unit Cost Analysis

| Metric | Value |
|--------|-------|
| Cost per discovery analyzed | $0.003 |
| Cost per content piece (LLM only) | $0.008 |
| Cost per content piece (full) | ~$0.018 |
| Analyst cost per batch (20 items) | ~$0.06 |

---

## Extrapolation to Estimated Scenario

The plan estimated $0.08-0.15 for a "typical run" of 1-2 content pieces.

**Extrapolated actual cost for 2 pieces:**
- LLM: ~$0.026 (prorated from batch)
- Images: ~$0.01 (2 images)
- **Total: ~$0.04**

**Conclusion:** Original estimates were conservative. Actual per-piece cost is ~50% lower than estimated low-end.

---

## Test 2: High Run (With Video) - Not Yet Executed

**Required Setup:**
- `HEYGEN_API_KEY` is configured ✓
- `HEYGEN_AVATAR_ID_FOUNDER` is configured ✓
- `HEYGEN_AVATAR_ID_PROFESSIONAL` is configured ✓

**To Execute:**
1. Find a creation with `video_script`: `curl localhost:8001/creations | jq '.[] | select(.video_script != null)'`
2. Trigger video generation through approval queue
3. Expected additional cost per video: ~$0.70-1.00 (HeyGen)

---

## Verification Checklist

- [x] Run Test 1 (typical) and record cost
- [ ] Run Test 2 (high) and record cost
- [x] Compare actual vs estimated costs
- [x] Verify cost tracking shows correct breakdown
- [ ] Confirm mode degradation works if limit exceeded

---

## Recommendations

1. **Update cost estimates** in documentation to reflect lower actual costs:
   - Typical run: $0.03-0.05 (not $0.08-0.15)
   - With video: $0.70-1.10 (HeyGen dominates)

2. **Add image generation cost tracking** to `/costs` endpoint:
   - Currently only LLM costs are tracked
   - fal.ai costs (~$0.005/image) should be added

3. **Test mode degradation** by:
   - Setting `DAILY_COST_LIMIT=1.00`
   - Running multiple cycles
   - Verifying system switches to REDUCED → MINIMAL → PAUSED modes

---

## Raw Data

```json
{
    "total_cost_usd": 1.0093,
    "cost_today_usd": 1.0093,
    "daily_cost_limit_usd": 5.0,
    "total_input_tokens": 64266,
    "total_output_tokens": 54431,
    "by_agent": [
        {
            "agent": "analyst",
            "runs": 7,
            "cost_usd": 0.418
        },
        {
            "agent": "creator",
            "runs": 76,
            "cost_usd": 0.5912
        }
    ]
}
```
