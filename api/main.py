from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

from api.routes.articles import router as articles_router
from api.routes.scrape import router as scrape_router
from api.routes.tickers import router as tickers_router

api = FastAPI(title="Investing Scraper API")

api.include_router(scrape_router, prefix="/scrape", tags=["scrape"])
api.include_router(articles_router, prefix="/articles", tags=["articles"])
api.include_router(tickers_router, prefix="/tickers", tags=["tickers"])


mcp = FastMCP.from_fastapi(app=api, name="Investing Scraper MCP")
mcp_app = mcp.http_app(path="/mcp")

app = FastAPI(
    title="Investing Scraper",
    routes=[
        *mcp_app.routes,
        *api.routes,
    ],
    lifespan=mcp_app.lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
