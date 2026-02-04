---
name: fal-image-generation
category: tools
platform: null
confidence: 0.5
status: active
version: 1
tags: [image, fal, carousel, infographic]
---
# fal.ai Image Generation

## When to Use
Apply when generating images for LinkedIn carousels, hero images, or social media visuals.

## Core Patterns
- LinkedIn carousels: generate 5-8 slides with consistent visual style
- Use text-to-image for conceptual illustrations, not for data visualization
- Prompt pattern: "[Subject] in [style], [composition], professional, clean, minimal"
- Consistent color palette across carousel slides (specify hex codes in prompt)
- 1:1 for social posts, 4:5 for LinkedIn carousels, 16:9 for hero images

## API Usage
- Endpoint: fal.ai flux models
- Include style consistency instructions in every prompt
- Request 1024x1024 minimum for quality
- Use negative prompts to avoid: text, watermarks, logos, blurry

## Style Guide for Autopilot Brand
- Colors: dark backgrounds, blue/purple accent (#4F46E5, #7C3AED)
- Style: minimal, technical, clean lines
- Mood: professional, forward-looking, grounded
- Avoid: cartoonish, overly colorful, stock-photo feel

## What to Avoid
- Generating text in images (always broken)
- Photorealistic people (uncanny, rights issues)
- Cluttered compositions
- Inconsistent style across carousel slides

## Performance Notes
<!-- Auto-updated by system -->
Uses: 0 | Success rate: -- | Last validated: never
