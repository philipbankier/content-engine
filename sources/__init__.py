from sources.hackernews import HackerNewsSource
from sources.reddit import RedditSource
from sources.product_hunt import ProductHuntSource
from sources.github_trending import GitHubTrendingSource
from sources.lobsters import LobstersSource
from sources.arxiv import ArXivSource
from sources.company_blogs import CompanyBlogsSource

ALL_SOURCES = [
    HackerNewsSource(),
    RedditSource(),
    ProductHuntSource(),
    GitHubTrendingSource(),
    LobstersSource(),
    ArXivSource(),
    CompanyBlogsSource(),
]
