---
name: heygen-avatar-video
category: tools
platform: null
confidence: 0.5
status: active
version: 1
tags: [video, avatar, heygen, talking-head]
---
# HeyGen Avatar Video

## When to Use
Apply when generating avatar talking-head videos for YouTube Shorts or TikTok.

## Core Patterns
- Direct-to-camera opening retains 40% more viewers than text-only intro
- Use founder avatar for opinion/insight content, professional avatar for tutorials
- Script must be conversational — written-for-reading sounds unnatural when spoken
- Keep videos 30-55 seconds for Shorts, 15-45 for TikTok
- Natural pauses improve believability — add "..." in scripts for brief pauses
- Pair with B-roll cuts every 8-12 seconds to maintain visual interest

## API Flow
1. POST /v2/video/generate with avatar_id, voice_id, script
2. Poll GET /v1/video_status.get?video_id={id} until status="completed"
3. Download from result URL
4. Post-process: add captions, trim silence

## Voice Selection
- Male voices: "Josh" or "Adam" for calm technical tone
- Female voices: "Rachel" or "Sarah" for professional warmth
- Match voice to avatar appearance

## What to Avoid
- Scripts over 160 words (rushed delivery)
- Complex sentences (avatar stumbles on subordinate clauses)
- Technical jargon without natural phrasing
- Monotone scripts — vary sentence length for natural rhythm

## Performance Notes
<!-- Auto-updated by system -->
Uses: 0 | Success rate: -- | Last validated: never
