---
name: heygen-video-agent
category: tools
platform: null
confidence: 0.5
status: active
version: 1
tags:
  - video
  - heygen
  - video-agent
  - short-form
  - avatar
---

## When to Use

Use the HeyGen Video Agent for quick, one-shot prompt-to-video generation. Best for:
- Short-form content (TikTok, YouTube Shorts, LinkedIn video)
- Rapid iteration and draft videos
- Automated content pipelines where manual scene control isn't needed
- When you want automatic avatar selection, script, visuals, and captions

Use the standard HeyGen v2 API instead when you need precise control over avatar, script wording, or scene-by-scene composition.

## Core Patterns

### Prompt Structure

Write rich, descriptive prompts. The Video Agent interprets natural language:

1. **Open with the hook** — First 3 seconds determine retention. Start with a direct-to-camera statement or provocative question.
2. **Define the visual style** — Mention colors, aesthetic, energy level.
3. **Structure the narrative** — Break into clear beats: hook, context, insight, takeaway.
4. **Specify the audience** — "For developers", "For startup founders", "For LinkedIn audience."
5. **Include a CTA or closing** — End with a clear takeaway or call to action.

### Platform-Specific Tips

- **TikTok / YouTube Shorts**: Use `orientation: "portrait"`, keep under 60 seconds, fast pacing, bold hook in first 2 seconds.
- **LinkedIn**: Use `orientation: "portrait"` or `"landscape"`, 30-90 seconds, professional tone, insight-driven.
- **YouTube**: Use `orientation: "landscape"`, can be longer (60-180 seconds), deeper content.

### Duration Guidelines

- Aim for ~150 words per minute in the prompt's spoken content.
- 30-second video = ~75 words of VO script.
- 60-second video = ~150 words of VO script.
- Use `config.duration_sec` for predictable length.

### Avatar Selection

- Lock avatar with `config.avatar_id` for brand consistency across videos.
- Omit to let the Agent auto-select based on prompt context.
- Founder avatar works well for thought leadership content.
- Professional avatar suits product explanations and tutorials.

## What to Avoid

- Don't write vague prompts like "make a video about AI." Be specific about the message, audience, and style.
- Don't expect exact script wording — the Agent interprets and adapts.
- Don't use for final production brand videos requiring pixel-perfect control.
- Don't skip specifying orientation — default may not match platform requirements.

## Performance Notes

- Generation typically takes 5-15 minutes depending on complexity and duration.
- Portrait videos perform better on mobile-first platforms (TikTok, YouTube Shorts).
- Direct-to-camera openings retain 40% more viewers than text/visual openings.
- Question hooks ("Did you know...?") consistently outperform statement hooks on LinkedIn.
