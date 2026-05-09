from datetime import date, datetime

from pydantic import BaseModel


class ScrapeStatus(BaseModel):
    status: str
    message: str


class ScrapeState(BaseModel):
    source_id: str
    last_scrape: date


class ArticleSummary(BaseModel):
    id: int
    source: str
    url: str
    title: str
    published_date: date | None
    author: str | None
    scraped_at: datetime
    tickers: list[str]


class ArticleDetail(ArticleSummary):
    content: str | None


class ArticleList(BaseModel):
    total: int
    items: list[ArticleSummary]
