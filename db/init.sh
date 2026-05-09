#!/usr/bin/env bash
# Apply schema to an existing Postgres instance.
# Requires DATABASE_URL to be set, e.g.:
#   export DATABASE_URL=postgresql://scraper:scraper@localhost:5432/investing_scraper
#   bash db/init.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
psql "$DATABASE_URL" -f "$SCRIPT_DIR/schema.sql"
echo "Schema applied."
