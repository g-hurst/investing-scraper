from dotenv import load_dotenv

load_dotenv()

from fastmcp import FastMCP
from api.main import app

mcp = FastMCP.from_fastapi(app=app, name="Investing Scraper")

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8001)
