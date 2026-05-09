from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

from api.routes.articles import router as articles_router
from api.routes.scrape import router as scrape_router

app = FastAPI(title="Investing Scraper API")

app.include_router(scrape_router, prefix="/scrape", tags=["scrape"])
app.include_router(articles_router, prefix="/articles", tags=["articles"])
