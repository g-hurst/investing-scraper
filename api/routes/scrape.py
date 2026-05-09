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
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT source_id, last_scrape FROM scrape_state ORDER BY source_id")
            rows = cur.fetchall()
    finally:
        conn.close()
    return [ScrapeState(source_id=r[0], last_scrape=r[1]) for r in rows]
