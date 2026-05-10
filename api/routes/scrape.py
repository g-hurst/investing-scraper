import threading

from fastapi import APIRouter, BackgroundTasks

from api.models import ScrapeState, ScrapeStatus
from scraper.main import run
from scraper.storage import get_conn

router = APIRouter()

_scrape_running = False
_lock = threading.Lock()


def _run_scrape() -> None:
    global _scrape_running
    try:
        run()
    finally:
        with _lock:
            _scrape_running = False


@router.post("", status_code=202, response_model=ScrapeStatus, operation_id="stocknews_trigger_scrape")
async def trigger_scrape(background_tasks: BackgroundTasks):
    """Trigger a background news scrape for all configured sources.

    Returns immediately with status "started" or "already_running". Use
    stocknews_get_scrape_state to check when data was last refreshed. A
    concurrent scrape request is rejected while one is already in progress.
    """
    global _scrape_running
    with _lock:
        if _scrape_running:
            return ScrapeStatus(
                status="already_running",
                message="A scrape is already in progress",
            )
        _scrape_running = True
        background_tasks.add_task(_run_scrape)
    return ScrapeStatus(status="started", message="Scrape started in background")


@router.get("/state", response_model=list[ScrapeState], operation_id="stocknews_get_scrape_state")
def get_scrape_state():
    """Return the last scrape date and article count for each news source.

    Use this to determine how fresh the data is before deciding whether to
    trigger a new scrape. Each entry includes the source identifier, the
    date of its most recent completed scrape, and the total number of
    articles stored for that source.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ss.source_id, ss.last_scrape, COUNT(a.id) AS article_count
                FROM scrape_state ss
                LEFT JOIN articles a ON a.source = ss.source_id
                GROUP BY ss.source_id, ss.last_scrape
                ORDER BY ss.source_id
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [ScrapeState(source_id=r[0], last_scrape=r[1], article_count=r[2]) for r in rows]
