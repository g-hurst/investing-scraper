CREATE TABLE IF NOT EXISTS articles (
    id             SERIAL PRIMARY KEY,
    source         VARCHAR(100) NOT NULL,
    url            TEXT        NOT NULL UNIQUE,
    title          TEXT        NOT NULL,
    published_date DATE,
    author         TEXT,
    content        TEXT,
    scraped_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS article_tickers (
    article_id  INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    ticker      VARCHAR(10) NOT NULL,
    PRIMARY KEY (article_id, ticker)
);

CREATE TABLE IF NOT EXISTS scrape_state (
    source_id   VARCHAR(100) PRIMARY KEY,
    last_scrape DATE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_articles_source_date
    ON articles(source, published_date DESC);

CREATE INDEX IF NOT EXISTS idx_article_tickers_ticker
    ON article_tickers(ticker);
