# investing-scraper

A local news scraper that fetches investing articles from financial sites, stores them in PostgreSQL, and exposes a REST API and MCP server. Three Claude skills use the MCP tools to deliver personalized portfolio briefings, health checks, and macro context from your Fidelity holdings.

---

## Setup

**Prerequisites:** Docker and Docker Compose

```bash
docker-compose up
```

| Service | Port |
|---------|------|
| PostgreSQL | 5433 |
| FastAPI / MCP | 8000 |

**Local dev (API without Docker):**
```bash
pip install -r requirements.txt
docker-compose up postgres -d
uvicorn api.main:app --reload
```

Copy `.env` and fill in credentials (see `.env` for the required variables).

---

## REST API

Base URL: `http://localhost:8000`  
Interactive docs: `http://localhost:8000/docs`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/scrape` | Trigger a background scrape (202 — returns immediately) |
| GET | `/scrape/state` | Last scrape date and article count per source |
| GET | `/articles` | List articles — filter by `ticker`, `source`, `date_from`, `date_to`, `limit`, `offset` |
| GET | `/articles/search` | Keyword search across article titles and body text (`?q=`) |
| GET | `/articles/{id}` | Full article content by ID |
| GET | `/tickers` | All tickers ranked by article coverage count |

---

## MCP (Claude Code)

The `.mcp.json` in the repo root auto-registers the server when you open the project in Claude Code. The server must be running first (`docker-compose up`).

**Manual config:**
```json
{
  "mcpServers": {
    "investing-scraper": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Available tools:**

| Tool | Description |
|------|-------------|
| `stocknews_trigger_scrape` | Start a background scrape |
| `stocknews_get_scrape_state` | Check data freshness per source |
| `stocknews_list_articles` | Filter articles by ticker, source, or date range |
| `stocknews_search_articles` | Keyword search across titles and body text |
| `stocknews_get_article` | Fetch full article body by ID |
| `stocknews_list_tickers` | List all tickers with coverage counts |

---

## Claude Skills

Three skills live in `.claude/skills/`. They require:
- The MCP server running (`docker-compose up`)
- A Fidelity `Portfolio_Positions_*.csv` export in the repo root

| Skill | Trigger phrase | What it does |
|-------|---------------|--------------|
| `/portfolio-brief` | "morning briefing", "portfolio news" | News digest for your holdings over a chosen time window |
| `/portfolio-health` | "portfolio health", "any red flags" | Risk flags (red/yellow/green) per holding based on recent news |
| `/market-context` | "macro picture", "market context" | Macro and sector backdrop mapped to your portfolio's themes |

**Example prompt:**
> "Give me a portfolio brief for the last 3 days"

Claude parses your Fidelity CSV, queries the MCP tools, and returns a formatted digest.

---

## Data Sources

Currently implemented: **Motley Fool** (requires `MOTLEY_FOOL_EMAIL` and `MOTLEY_FOOL_PASSWORD` in `.env`).

To add a source: implement it in `scraper/sources/` and register it in `scraper/main.py`.
