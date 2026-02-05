"""Playwright-based scraper for fetching and posting comments on LinkedIn/X.

Uses browser automation to:
1. Fetch comments on our published posts
2. Post replies to comments
3. Post proactive comments on trending content

Following patterns from stagehand-browser-automation.md skill:
- Use realistic delays (2-5s between actions)
- Persist browser session cookies
- Handle rate limiting with exponential backoff
"""

import asyncio
import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# Paths for session storage (shared with metrics scraper)
SESSION_DIR = Path(__file__).parent.parent / "metrics" / ".sessions"


@dataclass
class Comment:
    """Represents a comment on a post."""

    comment_id: str
    author: str
    author_url: Optional[str]
    text: str
    timestamp: Optional[datetime]
    likes: int = 0
    replies: int = 0


def _ensure_session_dir():
    """Ensure session directory exists."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)


async def _get_browser_context(playwright, platform: str, headless: bool = True):
    """Get or create a browser context with persistent session."""
    _ensure_session_dir()
    session_path = SESSION_DIR / f"{platform}_session"

    browser = await playwright.chromium.launch(headless=headless)

    if session_path.exists():
        try:
            with open(session_path, "r") as f:
                storage_state = json.load(f)
            context = await browser.new_context(storage_state=storage_state)
            logger.debug("Loaded existing session for %s", platform)
            return browser, context
        except Exception as e:
            logger.warning("Failed to load session for %s: %s", platform, e)

    context = await browser.new_context()
    return browser, context


async def _save_session(context, platform: str):
    """Save browser session for future use."""
    _ensure_session_dir()
    session_path = SESSION_DIR / f"{platform}_session"
    try:
        storage_state = await context.storage_state()
        with open(session_path, "w") as f:
            json.dump(storage_state, f)
        logger.debug("Saved session for %s", platform)
    except Exception as e:
        logger.warning("Failed to save session for %s: %s", platform, e)


def _random_delay(min_sec: float = 2.0, max_sec: float = 5.0):
    """Generate random delay to avoid detection."""
    return random.uniform(min_sec, max_sec)


async def fetch_linkedin_comments(post_url: str, headless: bool = True) -> list[Comment]:
    """Fetch comments from a LinkedIn post.

    Args:
        post_url: LinkedIn post URL
        headless: Run browser in headless mode

    Returns:
        List of Comment objects
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed")
        return []

    comments = []

    try:
        async with async_playwright() as p:
            browser, context = await _get_browser_context(p, "linkedin", headless)
            page = await context.new_page()

            try:
                logger.info("Fetching LinkedIn comments: %s", post_url)
                await page.goto(post_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(_random_delay())

                # Wait for comments to load
                await page.wait_for_selector('.comments-comments-list', timeout=10000)

                # Get all comment elements
                comment_elements = await page.query_selector_all('.comments-comment-item')

                for elem in comment_elements[:20]:  # Limit to 20 comments
                    try:
                        # Extract author
                        author_elem = await elem.query_selector('.comments-post-meta__name-text')
                        author = await author_elem.inner_text() if author_elem else "Unknown"

                        # Extract author URL
                        author_link = await elem.query_selector('a.comments-post-meta__profile-link')
                        author_url = await author_link.get_attribute('href') if author_link else None

                        # Extract comment text
                        text_elem = await elem.query_selector('.comments-comment-item__main-content')
                        text = await text_elem.inner_text() if text_elem else ""

                        # Extract comment ID from data attribute or aria-label
                        comment_id = await elem.get_attribute('data-id') or str(hash(text))[:12]

                        # Extract likes
                        likes_elem = await elem.query_selector('.comments-comment-social-bar__reactions-count')
                        likes_text = await likes_elem.inner_text() if likes_elem else "0"
                        try:
                            likes = int(likes_text.replace(",", ""))
                        except ValueError:
                            likes = 0

                        comments.append(Comment(
                            comment_id=comment_id,
                            author=author.strip(),
                            author_url=author_url,
                            text=text.strip(),
                            timestamp=None,  # Would need more parsing
                            likes=likes,
                        ))

                    except Exception as e:
                        logger.warning("Failed to parse LinkedIn comment: %s", e)
                        continue

                await _save_session(context, "linkedin")
                logger.info("Fetched %d LinkedIn comments", len(comments))

            finally:
                await context.close()
                await browser.close()

    except Exception as e:
        logger.error("Failed to fetch LinkedIn comments from %s: %s", post_url, e)

    return comments


async def fetch_x_replies(post_url: str, headless: bool = True) -> list[Comment]:
    """Fetch replies from an X (Twitter) post.

    Args:
        post_url: X post URL
        headless: Run browser in headless mode

    Returns:
        List of Comment objects
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed")
        return []

    comments = []

    try:
        async with async_playwright() as p:
            browser, context = await _get_browser_context(p, "x", headless)
            page = await context.new_page()

            try:
                # Normalize URL
                post_url = post_url.replace("twitter.com", "x.com")

                logger.info("Fetching X replies: %s", post_url)
                await page.goto(post_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(_random_delay())

                # Wait for tweet thread to load
                await page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)

                # Get all reply tweets (skip the first one which is the original)
                tweet_elements = await page.query_selector_all('article[data-testid="tweet"]')

                for i, elem in enumerate(tweet_elements[1:21]):  # Skip original, limit to 20
                    try:
                        # Extract author
                        author_elem = await elem.query_selector('[data-testid="User-Name"] span')
                        author = await author_elem.inner_text() if author_elem else "Unknown"

                        # Extract text
                        text_elem = await elem.query_selector('[data-testid="tweetText"]')
                        text = await text_elem.inner_text() if text_elem else ""

                        # Try to get tweet ID from the link
                        link_elem = await elem.query_selector('a[href*="/status/"]')
                        comment_id = ""
                        author_url = None
                        if link_elem:
                            href = await link_elem.get_attribute('href')
                            if "/status/" in href:
                                comment_id = href.split("/status/")[-1].split("?")[0]
                            author_url = href.split("/status/")[0] if "/status/" in href else None

                        if not comment_id:
                            comment_id = str(hash(text))[:12]

                        # Extract likes
                        like_elem = await elem.query_selector('[data-testid="like"] span')
                        likes_text = await like_elem.inner_text() if like_elem else "0"
                        try:
                            likes = int(likes_text.replace(",", "").replace("K", "000").replace("M", "000000"))
                        except ValueError:
                            likes = 0

                        comments.append(Comment(
                            comment_id=comment_id,
                            author=author.strip(),
                            author_url=author_url,
                            text=text.strip(),
                            timestamp=None,
                            likes=likes,
                        ))

                    except Exception as e:
                        logger.warning("Failed to parse X reply: %s", e)
                        continue

                await _save_session(context, "x")
                logger.info("Fetched %d X replies", len(comments))

            finally:
                await context.close()
                await browser.close()

    except Exception as e:
        logger.error("Failed to fetch X replies from %s: %s", post_url, e)

    return comments


async def post_linkedin_reply(
    post_url: str,
    reply_text: str,
    headless: bool = True,
) -> dict:
    """Post a reply to a LinkedIn comment.

    Args:
        post_url: LinkedIn post URL
        reply_text: Text to post as a comment
        headless: Run browser in headless mode

    Returns:
        {"success": bool, "error": str | None}
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"success": False, "error": "Playwright not installed"}

    try:
        async with async_playwright() as p:
            browser, context = await _get_browser_context(p, "linkedin", headless)
            page = await context.new_page()

            try:
                logger.info("Posting LinkedIn comment to: %s", post_url)
                await page.goto(post_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(_random_delay())

                # Check if logged in
                sign_in_btn = await page.query_selector('a[data-tracking-control-name="public_post_nav-header-join"]')
                if sign_in_btn:
                    return {"success": False, "error": "Not logged in to LinkedIn"}

                # Find and click the comment box
                comment_box = await page.wait_for_selector(
                    '.comments-comment-box__form-container [contenteditable="true"]',
                    timeout=10000
                )
                await comment_box.click()
                await asyncio.sleep(_random_delay(1, 2))

                # Type the reply with realistic typing speed
                await comment_box.type(reply_text, delay=50)
                await asyncio.sleep(_random_delay(1, 2))

                # Find and click the Post button
                post_btn = await page.query_selector('button.comments-comment-box__submit-button')
                if post_btn:
                    await post_btn.click()
                    await asyncio.sleep(_random_delay(2, 4))
                    await _save_session(context, "linkedin")
                    logger.info("Successfully posted LinkedIn comment")
                    return {"success": True, "error": None}
                else:
                    return {"success": False, "error": "Post button not found"}

            finally:
                await context.close()
                await browser.close()

    except Exception as e:
        logger.error("Failed to post LinkedIn reply: %s", e)
        return {"success": False, "error": str(e)}


async def post_x_reply(
    post_url: str,
    reply_text: str,
    headless: bool = True,
) -> dict:
    """Post a reply to an X post.

    Args:
        post_url: X post URL
        reply_text: Text to post as a reply
        headless: Run browser in headless mode

    Returns:
        {"success": bool, "error": str | None}
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"success": False, "error": "Playwright not installed"}

    try:
        async with async_playwright() as p:
            browser, context = await _get_browser_context(p, "x", headless)
            page = await context.new_page()

            try:
                post_url = post_url.replace("twitter.com", "x.com")

                logger.info("Posting X reply to: %s", post_url)
                await page.goto(post_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(_random_delay())

                # Find the reply compose area
                reply_box = await page.wait_for_selector(
                    '[data-testid="tweetTextarea_0"]',
                    timeout=10000
                )
                if not reply_box:
                    return {"success": False, "error": "Reply box not found - may not be logged in"}

                await reply_box.click()
                await asyncio.sleep(_random_delay(1, 2))

                # Type the reply
                await reply_box.type(reply_text, delay=50)
                await asyncio.sleep(_random_delay(1, 2))

                # Click the Reply button
                reply_btn = await page.query_selector('[data-testid="tweetButtonInline"]')
                if reply_btn:
                    await reply_btn.click()
                    await asyncio.sleep(_random_delay(2, 4))
                    await _save_session(context, "x")
                    logger.info("Successfully posted X reply")
                    return {"success": True, "error": None}
                else:
                    return {"success": False, "error": "Reply button not found"}

            finally:
                await context.close()
                await browser.close()

    except Exception as e:
        logger.error("Failed to post X reply: %s", e)
        return {"success": False, "error": str(e)}


class CommentScraper:
    """Unified interface for comment scraping and posting."""

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def fetch_comments(self, platform: str, post_url: str) -> list[Comment]:
        """Fetch comments from a platform post."""
        platform = platform.lower()
        if platform == "linkedin":
            return await fetch_linkedin_comments(post_url, self.headless)
        elif platform in ("x", "twitter"):
            return await fetch_x_replies(post_url, self.headless)
        else:
            logger.warning("No comment scraper for platform: %s", platform)
            return []

    async def post_reply(self, platform: str, post_url: str, reply_text: str) -> dict:
        """Post a reply to a platform post."""
        platform = platform.lower()
        if platform == "linkedin":
            return await post_linkedin_reply(post_url, reply_text, self.headless)
        elif platform in ("x", "twitter"):
            return await post_x_reply(post_url, reply_text, self.headless)
        else:
            return {"success": False, "error": f"No reply poster for platform: {platform}"}
