"""EngagementAgent: replies to comments and proactively engages on trending posts."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func

from agents.base import BaseAgent
from config import settings
from db import async_session
from models import ContentPublication, EngagementAction

logger = logging.getLogger(__name__)

# Rate limits for engagement
MAX_REPLIES_PER_POST = 5  # Don't reply more than 5 times on a single post
MAX_PROACTIVE_PER_DAY = 10  # Maximum proactive engagements per day
MIN_DELAY_BETWEEN_ENGAGEMENTS = 60  # Minimum seconds between engagements


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
        reply_count = 0

        # Get recent publications (last 7 days) with platform URLs
        async with async_session() as session:
            cutoff = now - timedelta(days=7)
            result = await session.execute(
                select(ContentPublication)
                .where(ContentPublication.published_at >= cutoff)
                .where(ContentPublication.platform_url.isnot(None))
                .order_by(ContentPublication.published_at.desc())
            )
            publications = result.scalars().all()

        if not publications:
            logger.info("No recent publications with URLs to check for comments")
            return 0

        # Check engagement scraping is available
        try:
            from engagement.comment_scraper import CommentScraper
            scraper = CommentScraper(headless=settings.playwright_headless)
        except ImportError:
            logger.warning("Engagement scraper not available - skipping comment replies")
            return 0

        for pub in publications[:10]:  # Limit to 10 most recent posts
            # Check how many replies we've already made on this post
            async with async_session() as session:
                existing_replies = await session.execute(
                    select(func.count(EngagementAction.id))
                    .where(EngagementAction.publication_id == pub.id)
                    .where(EngagementAction.action_type == "reply")
                    .where(EngagementAction.status == "posted")
                )
                reply_count_for_post = existing_replies.scalar() or 0

            if reply_count_for_post >= MAX_REPLIES_PER_POST:
                logger.debug("Already replied %d times on post %d, skipping", reply_count_for_post, pub.id)
                continue

            # Fetch comments on this post
            try:
                comments = await scraper.fetch_comments(pub.platform, pub.platform_url)
            except Exception as e:
                logger.error("Failed to fetch comments for %s: %s", pub.platform_url, e)
                continue

            if not comments:
                continue

            # Filter comments we haven't replied to
            async with async_session() as session:
                existing_targets = await session.execute(
                    select(EngagementAction.target_url)
                    .where(EngagementAction.publication_id == pub.id)
                    .where(EngagementAction.action_type == "reply")
                )
                replied_urls = {row[0] for row in existing_targets}

            # Find unanswered comments
            unanswered = [
                c for c in comments
                if c.text.strip() and
                f"{pub.platform_url}#{c.comment_id}" not in replied_urls
            ]

            if not unanswered:
                continue

            # Generate and post replies (up to limit)
            remaining = MAX_REPLIES_PER_POST - reply_count_for_post
            for comment in unanswered[:remaining]:
                try:
                    # Generate a reply
                    reply_text = await self.generate_reply(
                        comment_text=comment.text,
                        post_context=f"Our {pub.platform} post",
                        platform=pub.platform,
                    )

                    if not reply_text:
                        continue

                    # Record the engagement action (pending)
                    async with async_session() as session:
                        action = EngagementAction(
                            action_type="reply",
                            platform=pub.platform,
                            target_url=f"{pub.platform_url}#{comment.comment_id}",
                            target_author=comment.author,
                            target_text=comment.text[:500],  # Truncate
                            our_text=reply_text,
                            publication_id=pub.id,
                            skills_used=[s.name for s in skills] if skills else [],
                            status="pending",
                            created_at=now,
                        )
                        session.add(action)
                        await session.commit()
                        action_id = action.id

                    # Post the reply
                    result = await scraper.post_reply(pub.platform, pub.platform_url, reply_text)

                    # Update status
                    async with async_session() as session:
                        action = await session.get(EngagementAction, action_id)
                        if result.get("success"):
                            action.status = "posted"
                            action.posted_at = datetime.now(timezone.utc)
                            reply_count += 1
                            logger.info("Posted reply on %s to %s", pub.platform, comment.author)
                        else:
                            action.status = "failed"
                            action.error = result.get("error")
                            logger.warning("Failed to post reply: %s", result.get("error"))
                        await session.commit()

                except Exception as e:
                    logger.error("Error processing comment reply: %s", e)
                    continue

        logger.info("Comment reply scan complete - posted %d replies", reply_count)
        return reply_count

    async def _proactive_engagement(self, skills: list, now: datetime) -> int:
        """Find trending posts and add thoughtful comments.

        Implements "Founder Everywhere" strategy from skills.
        """
        # Check daily limit
        async with async_session() as session:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_count = await session.execute(
                select(func.count(EngagementAction.id))
                .where(EngagementAction.action_type == "proactive")
                .where(EngagementAction.created_at >= today_start)
            )
            proactive_today = today_count.scalar() or 0

        if proactive_today >= MAX_PROACTIVE_PER_DAY:
            logger.info("Daily proactive engagement limit reached (%d/%d)", proactive_today, MAX_PROACTIVE_PER_DAY)
            return 0

        remaining_budget = MAX_PROACTIVE_PER_DAY - proactive_today

        # Find engagement targets from trending content
        targets = await self._find_engagement_targets(remaining_budget, now)

        if not targets:
            logger.info("No engagement targets found")
            return 0

        engagement_count = 0

        for target in targets:
            try:
                # Generate a proactive comment
                comment_text = await self._generate_proactive_comment(
                    target_url=target["url"],
                    target_title=target.get("title", ""),
                    target_content=target.get("content", ""),
                    platform=target["platform"],
                    skills=skills,
                )

                if not comment_text:
                    continue

                # Record the engagement action
                async with async_session() as session:
                    action = EngagementAction(
                        action_type="proactive",
                        platform=target["platform"],
                        target_url=target["url"],
                        target_author=target.get("author"),
                        target_text=target.get("title", "")[:500],
                        our_text=comment_text,
                        skills_used=[s.name for s in skills] if skills else [],
                        status="pending",
                        created_at=now,
                    )
                    session.add(action)
                    await session.commit()
                    action_id = action.id

                # For now, log but don't auto-post proactive comments
                # (too risky without human review)
                logger.info(
                    "Generated proactive comment for %s (queued for review): %s",
                    target["url"],
                    comment_text[:100],
                )

                # Mark as pending review rather than auto-posting
                async with async_session() as session:
                    action = await session.get(EngagementAction, action_id)
                    action.status = "pending_review"
                    await session.commit()

                engagement_count += 1

            except Exception as e:
                logger.error("Error generating proactive engagement: %s", e)
                continue

        logger.info("Proactive engagement scan complete - generated %d comments", engagement_count)
        return engagement_count

    async def _find_engagement_targets(self, max_count: int, now: datetime) -> list[dict]:
        """Find trending posts to engage with.

        Uses source clients (HN, Reddit) to find trending AI/automation content.
        """
        targets = []

        try:
            # Import sources dynamically
            from sources.hackernews import HackerNewsSource
            from sources.reddit import RedditSource

            # Fetch from HN
            hn = HackerNewsSource()
            hn_items = await hn.fetch()

            # Filter for AI/automation topics
            ai_keywords = ["ai", "llm", "gpt", "claude", "automation", "agent", "ml", "machine learning"]
            for item in hn_items[:20]:
                title_lower = item.title.lower()
                if any(kw in title_lower for kw in ai_keywords):
                    # Check we haven't engaged with this already
                    async with async_session() as session:
                        existing = await session.execute(
                            select(EngagementAction)
                            .where(EngagementAction.target_url == item.url)
                        )
                        if existing.scalar_one_or_none():
                            continue

                    targets.append({
                        "url": item.url,
                        "title": item.title,
                        "platform": "hackernews",
                        "content": item.raw_data.get("story_text", ""),
                        "score": item.raw_score,
                    })

                    if len(targets) >= max_count:
                        break

            # Fetch from Reddit if we need more
            if len(targets) < max_count:
                reddit = RedditSource()
                reddit_items = await reddit.fetch()

                for item in reddit_items[:20]:
                    title_lower = item.title.lower()
                    if any(kw in title_lower for kw in ai_keywords):
                        async with async_session() as session:
                            existing = await session.execute(
                                select(EngagementAction)
                                .where(EngagementAction.target_url == item.url)
                            )
                            if existing.scalar_one_or_none():
                                continue

                        targets.append({
                            "url": item.url,
                            "title": item.title,
                            "platform": "reddit",
                            "content": item.raw_data.get("selftext", ""),
                            "author": item.raw_data.get("author"),
                            "score": item.raw_score,
                        })

                        if len(targets) >= max_count:
                            break

        except Exception as e:
            logger.error("Error finding engagement targets: %s", e)

        return targets

    async def _generate_proactive_comment(
        self,
        target_url: str,
        target_title: str,
        target_content: str,
        platform: str,
        skills: list,
    ) -> Optional[str]:
        """Generate a thoughtful comment for proactive engagement."""
        skills_text = self.format_skills_for_prompt(skills)

        system = (
            "You are generating a thoughtful comment on a post in the AI/automation space "
            "on behalf of Autopilot by Kairox AI.\n\n"
            "Brand Voice: Calm, confident, technical, grounded. Builder-to-builder.\n"
            "- Add genuine value - share data, a counter-intuitive observation, or practical experience\n"
            "- No buzzwords, no exclamation points, no self-promotion\n"
            "- 2-4 sentences maximum\n"
            "- Comment should stand alone even if someone doesn't know who we are\n"
            "- Never mention Autopilot or Kairox unless directly relevant\n\n"
            f"## Relevant Skills\n{skills_text}"
        )

        user = (
            f"Post to comment on ({platform}):\n"
            f"Title: {target_title}\n"
            f"Content: {target_content[:500]}\n\n"
            "Generate a 2-4 sentence comment that adds genuine value to the discussion. "
            "Focus on technical insight or practical experience."
        )

        comment = await self.call_llm(system, user, max_tokens=256)
        if skills:
            self.record_outcome(
                [s.name for s in skills],
                "success" if comment else "failure",
                0.7 if comment else 0.0,
                task="proactive_engagement",
            )
        return comment

    async def generate_reply(self, comment_text: str, post_context: str, platform: str) -> str:
        """Generate a single reply to a comment. Can be called directly."""
        skills = self.select_skills("engagement", platform=platform)
        skills_text = self.format_skills_for_prompt(skills)

        system = (
            "You are responding to a comment on content published by Autopilot by Kairox AI.\n\n"
            "Brand Voice: Calm, confident, technical, grounded. Builder-to-builder.\n"
            "- No buzzwords or exclamation points\n"
            "- Match the commenter's depth - short comment gets short reply\n"
            "- Add genuine insight, not just acknowledgment\n"
            "- Never pitch or promote\n\n"
            f"## Relevant Skills\n{skills_text}"
        )
        user = f"Original post context: {post_context}\n\nComment to reply to: {comment_text}\n\nGenerate a reply."

        reply = await self.call_llm(system, user, max_tokens=512)
        if skills:
            self.record_outcome([s.name for s in skills], "success" if reply else "failure", 0.7 if reply else 0.0)
        return reply
