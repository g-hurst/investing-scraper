from fastapi import APIRouter

from api.models import TickerSummary
from scraper.storage import get_conn

router = APIRouter()


@router.get("", response_model=list[TickerSummary], operation_id="stocknews_list_tickers")
def list_tickers():
    """List all stock tickers found in scraped articles, ranked by coverage.

    Returns every unique ticker symbol with a count of how many articles
    mention it. Use this to discover which stocks have available news before
    calling stocknews_list_articles or stocknews_search_articles with a
    specific ticker filter. Results are sorted by article_count descending so
    the most-covered stocks appear first.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ticker, COUNT(DISTINCT article_id) AS article_count
                FROM article_tickers
                GROUP BY ticker
                ORDER BY article_count DESC, ticker ASC
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [TickerSummary(ticker=r[0], article_count=r[1]) for r in rows]
