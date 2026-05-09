FROM python:3.14-bookworm

# Install Node.js (required for playwright-cli) and curl
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install playwright-cli for automation; use playwright's --with-deps to get system libs, then install
# playwright-cli's own Chromium (separate registry) which shares those same system libs
RUN npm install -g @playwright/cli@latest playwright \
    && playwright install --with-deps chromium \
    && playwright-cli install-browser chromium

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

# Default: run the API. Override CMD to run the scraper:
#   docker run <image> python scraper/main.py
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
