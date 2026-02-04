"""EngagementAgent: replies to comments and proactively engages on trending posts."""

import logging
from datetime import datetime, timezone

from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class EngagementAgent(BaseAgent):
    """Monitor and respond to engagement across platforms."""

    def __init__(self):
        super().__init__(name="engagement")

    async def run(self, at: datetime | None = None) -> dict:
        """Run engagement cycle: reply to comments, proactive engagement."""
        now = at or datetime.now(timezone.utc)
        skills = self.select_skills("engagement")

        # Phase 1: Reply to comments on our posts
        reply_count = await self._reply_to_comments(skills, now)

        # Phase 2: Proactive engagement on trending content
        proactive_count = await self._proactive_engagement(skills, now)

        return {
            "replies_generated": reply_count,
            "proactive_engagements": proactive_count,
            "timestamp": now.isoformat(),
        }

    async def _reply_to_comments(self, skills: list, now: datetime) -> int:
        """Generate replies to comments on our published content."""
        # In a full implementation, this would:
        # 1. Fetch recent comments from each publisher's API
        # 2. Filter for unanswered comments
        # 3. Generate replies using engagement skills + brand voice
        # 4. Post replies via publisher APIs
        # For now, log and return 0 (requires live platform data)
        logger.info("Comment reply scan complete (no pending comments in demo mode)")
        return 0

    async def _proactive_engagement(self, skills: list, now: datetime) -> int:
        """Find trending posts and add thoughtful comments."""
        # In a full implementation, this would:
        # 1. Use source clients to find trending posts
        # 2. Identify posts where our comment would add value
        # 3. Generate thoughtful, on-brand comments using skills
        # 4. Post comments via platform APIs
        logger.info("Proactive engagement scan complete (demo mode)")
        return 0

    async def generate_reply(self, comment_text: str, post_context: str, platform: str) -> str:
        """Generate a single reply to a comment. Can be called directly."""
        skills = self.select_skills("engagement", platform=platform)
        skills_text = self.format_skills_for_prompt(skills)

        system = (
            "You are responding to a comment on content published by Autopilot by Kairox AI.\n\n"
            "Brand Voice: Calm, confident, technical, grounded. Builder-to-builder.\n"
            "- No buzzwords or exclamation points\n"
            "- Match the commenter's depth — short comment gets short reply\n"
            "- Add genuine insight, not just acknowledgment\n"
            "- Never pitch or promote\n\n"
            f"## Relevant Skills\n{skills_text}"
        )
        user = f"Original post context: {post_context}\n\nComment to reply to: {comment_text}\n\nGenerate a reply."

        reply = await self.call_bedrock(system, user, max_tokens=512)
        if skills:
            self.record_outcome([s.name for s in skills], "success" if reply else "failure", 0.7 if reply else 0.0)
        return reply
