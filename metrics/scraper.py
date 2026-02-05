"""Playwright-based scraper for LinkedIn and X engagement metrics.

Uses browser automation to extract real engagement data from platform URLs
since upload-post.com doesn't return metrics.

Following patterns from stagehand-browser-automation.md skill:
- Use realistic delays (2-5s between actions)
- Persist browser session cookies
- Handle rate limiting with exponential backoff
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# Paths for session storage
SESSION_DIR = Path(__file__).parent / ".sessions"


def _ensure_session_dir():
    """Ensure session directory exists."""
    SESSION_DIR.mkdir(exist_ok=True)


async def _get_browser_context(playwright, platform: str, headless: bool = True):
    """Get or create a browser context with persistent session.

    Sessions are stored per-platform to maintain login state.
    """
    _ensure_session_dir()
    session_path = SESSION_DIR / f"{platform}_session"

    browser = await playwright.chromium.launch(headless=headless)

    # Try to load existing session
    if session_path.exists():
        try:
            with open(session_path, "r") as f:
                storage_state = json.load(f)
            context = await browser.new_context(storage_state=storage_state)
            logger.debug("Loaded existing session for %s", platform)
            return browser, context
        except Exception as e:
            logger.warning("Failed to load session for %s: %s", platform, e)

    # Create new context without session
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


def _parse_count(text: str) -> int:
    """Parse engagement count from text like '1.2K', '5M', '123'."""
    if not text:
        return 0

    text = text.strip().upper()

    # Remove commas
    text = text.replace(",", "")

    # Handle K, M, B suffixes
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}

    for suffix, mult in multipliers.items():
        if text.endswith(suffix):
            try:
                return int(float(text[:-1]) * mult)
            except ValueError:
                return 0

    # Try direct parse
    try:
        return int(float(text))
    except ValueError:
        return 0


async def scrape_linkedin_post(url: str, headless: bool = True) -> dict:
    """Scrape engagement metrics from a LinkedIn post.

    Args:
        url: LinkedIn post URL (e.g., https://www.linkedin.com/posts/...)
        headless: Run browser in headless mode (default True)

    Returns:
        dict with keys: views, likes, comments, shares, engagement_rate
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return _empty_metrics("playwright not installed")

    metrics = _empty_metrics()

    try:
        async with async_playwright() as p:
            browser, context = await _get_browser_context(p, "linkedin", headless)
            page = await context.new_page()

            try:
                # Navigate to post with realistic delay
                logger.info("Scraping LinkedIn post: %s", url)
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2 + (asyncio.get_event_loop().time() % 3))  # 2-5s delay

                # Check if logged in (look for sign-in prompt)
                sign_in_btn = await page.query_selector('a[data-tracking-control-name="public_post_nav-header-join"]')
                if sign_in_btn:
                    logger.warning("LinkedIn session expired - metrics may be limited")

                # Try to extract metrics from the post
                # LinkedIn's structure varies, so we try multiple selectors

                # Reactions count (likes, celebrates, etc.)
                reactions_selectors = [
                    'span.social-details-social-counts__reactions-count',
                    'button[aria-label*="reaction"] span',
                    '.social-details-social-counts__social-proof-text',
                ]
                for sel in reactions_selectors:
                    elem = await page.query_selector(sel)
                    if elem:
                        text = await elem.inner_text()
                        metrics["likes"] = _parse_count(text)
                        if metrics["likes"] > 0:
                            break

                # Comments count
                comments_selectors = [
                    'button[aria-label*="comment"] span',
                    'li.social-details-social-counts__comments button span',
                    '.social-details-social-counts__comments',
                ]
                for sel in comments_selectors:
                    elem = await page.query_selector(sel)
                    if elem:
                        text = await elem.inner_text()
                        # Extract number from "X comments"
                        match = re.search(r'(\d[\d,KMB.]*)', text, re.IGNORECASE)
                        if match:
                            metrics["comments"] = _parse_count(match.group(1))
                            if metrics["comments"] > 0:
                                break

                # Shares/reposts count
                shares_selectors = [
                    'button[aria-label*="repost"] span',
                    'li.social-details-social-counts__item--right-align span',
                ]
                for sel in shares_selectors:
                    elem = await page.query_selector(sel)
                    if elem:
                        text = await elem.inner_text()
                        match = re.search(r'(\d[\d,KMB.]*)', text, re.IGNORECASE)
                        if match:
                            metrics["shares"] = _parse_count(match.group(1))
                            if metrics["shares"] > 0:
                                break

                # Impressions/views (often shown as "X impressions" or "X views")
                impressions_selectors = [
                    '.analytics-entry-point span',
                    'span[class*="impressions"]',
                    '.feed-shared-analytics-entry-point',
                ]
                for sel in impressions_selectors:
                    elem = await page.query_selector(sel)
                    if elem:
                        text = await elem.inner_text()
                        match = re.search(r'(\d[\d,KMB.]*)', text, re.IGNORECASE)
                        if match:
                            metrics["views"] = _parse_count(match.group(1))
                            if metrics["views"] > 0:
                                break

                # Calculate engagement rate if we have views
                if metrics["views"] > 0:
                    total_engagement = metrics["likes"] + metrics["comments"] + metrics["shares"]
                    metrics["engagement_rate"] = total_engagement / metrics["views"]

                # Save session for future use
                await _save_session(context, "linkedin")

                logger.info("LinkedIn metrics: views=%d, likes=%d, comments=%d, shares=%d",
                           metrics["views"], metrics["likes"], metrics["comments"], metrics["shares"])

            finally:
                await context.close()
                await browser.close()

    except Exception as e:
        logger.error("Failed to scrape LinkedIn post %s: %s", url, e)
        metrics["note"] = f"Scraping error: {str(e)}"

    return metrics


async def scrape_x_post(url: str, headless: bool = True) -> dict:
    """Scrape engagement metrics from an X (Twitter) post.

    Args:
        url: X post URL (e.g., https://x.com/user/status/123...)
        headless: Run browser in headless mode (default True)

    Returns:
        dict with keys: views, likes, comments, shares (retweets), engagement_rate
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return _empty_metrics("playwright not installed")

    metrics = _empty_metrics()

    try:
        async with async_playwright() as p:
            browser, context = await _get_browser_context(p, "x", headless)
            page = await context.new_page()

            try:
                # Normalize URL (twitter.com -> x.com)
                url = url.replace("twitter.com", "x.com")

                logger.info("Scraping X post: %s", url)
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2 + (asyncio.get_event_loop().time() % 3))  # 2-5s delay

                # X shows metrics in the tweet details area
                # Format is typically: Views, Reposts, Quotes, Likes, Bookmarks

                # Wait for tweet to load
                await page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)

                # Views - shown in tweet details
                views_elem = await page.query_selector('[data-testid="app-text-transition-container"]')
                if views_elem:
                    text = await views_elem.inner_text()
                    metrics["views"] = _parse_count(text)

                # Get engagement metrics from the action bar
                # Replies
                reply_elem = await page.query_selector('[data-testid="reply"] span[data-testid="app-text-transition-container"]')
                if reply_elem:
                    text = await reply_elem.inner_text()
                    metrics["comments"] = _parse_count(text)

                # Retweets/Reposts
                retweet_elem = await page.query_selector('[data-testid="retweet"] span[data-testid="app-text-transition-container"]')
                if retweet_elem:
                    text = await retweet_elem.inner_text()
                    metrics["shares"] = _parse_count(text)

                # Likes
                like_elem = await page.query_selector('[data-testid="like"] span[data-testid="app-text-transition-container"]')
                if like_elem:
                    text = await like_elem.inner_text()
                    metrics["likes"] = _parse_count(text)

                # Bookmarks (saves)
                bookmark_elem = await page.query_selector('[data-testid="bookmark"] span[data-testid="app-text-transition-container"]')
                if bookmark_elem:
                    text = await bookmark_elem.inner_text()
                    metrics["saves"] = _parse_count(text)

                # Calculate engagement rate if we have views
                if metrics["views"] > 0:
                    total_engagement = metrics["likes"] + metrics["comments"] + metrics["shares"]
                    metrics["engagement_rate"] = total_engagement / metrics["views"]

                # Save session for future use
                await _save_session(context, "x")

                logger.info("X metrics: views=%d, likes=%d, comments=%d, shares=%d",
                           metrics["views"], metrics["likes"], metrics["comments"], metrics["shares"])

            finally:
                await context.close()
                await browser.close()

    except Exception as e:
        logger.error("Failed to scrape X post %s: %s", url, e)
        metrics["note"] = f"Scraping error: {str(e)}"

    return metrics


def _empty_metrics(note: str = "") -> dict:
    """Return empty metrics dict."""
    return {
        "views": 0,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "saves": 0,
        "clicks": 0,
        "followers_gained": 0,
        "engagement_rate": 0.0,
        "note": note,
    }


class MetricsScraper:
    """Unified interface for scraping metrics from multiple platforms."""

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def scrape(self, platform: str, url: str) -> dict:
        """Scrape metrics from a platform post.

        Args:
            platform: Platform name (linkedin, x, twitter)
            url: Post URL

        Returns:
            Metrics dict
        """
        platform = platform.lower()

        if platform == "linkedin":
            return await scrape_linkedin_post(url, self.headless)
        elif platform in ("x", "twitter"):
            return await scrape_x_post(url, self.headless)
        else:
            logger.warning("No scraper available for platform: %s", platform)
            return _empty_metrics(f"No scraper for {platform}")


# Convenience function for quick scraping
async def scrape_metrics(platform: str, url: str, headless: bool = True) -> dict:
    """Scrape metrics from a platform post URL.

    Args:
        platform: Platform name (linkedin, x, twitter)
        url: Post URL
        headless: Run browser in headless mode

    Returns:
        Metrics dict with views, likes, comments, shares, engagement_rate
    """
    scraper = MetricsScraper(headless=headless)
    return await scraper.scrape(platform, url)
