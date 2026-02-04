---
name: stagehand-browser-automation
category: tools
platform: null
confidence: 0.5
status: active
version: 1
tags: [browser, automation, stagehand, tiktok]
---
# Stagehand Browser Automation

## When to Use
Apply when a platform lacks an official publishing API (e.g., TikTok posting).

## Core Patterns
- Stagehand provides AI-powered browser automation via Playwright
- Use for: TikTok uploads, platform actions without API access
- Flow: launch browser → navigate to platform → authenticate → perform action
- Add delays between actions (1-3 seconds) to avoid detection
- Always verify action completion with visual confirmation

## TikTok Upload Flow
1. Navigate to tiktok.com/creator
2. Click upload button
3. Select video file
4. Wait for upload completion
5. Add caption/description
6. Set visibility settings
7. Click post
8. Verify post appeared in profile

## Error Handling
- Retry failed actions up to 3 times with increasing delay
- Screenshot on failure for debugging
- Fall back to manual notification if automation fails
- Check for CAPTCHAs (notify human operator)

## What to Avoid
- Rapid-fire actions (triggering bot detection)
- Running multiple sessions simultaneously on same account
- Skipping verification steps
- Ignoring rate limits

## Performance Notes
<!-- Auto-updated by system -->
Uses: 0 | Success rate: -- | Last validated: never
