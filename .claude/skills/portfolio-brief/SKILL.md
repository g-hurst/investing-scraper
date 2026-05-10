---
name: portfolio-brief
description: Show a personalized news digest for the user's stock holdings from their Fidelity export. Use when the user says "morning briefing", "portfolio news", "what's happening with my holdings", "brief me on the last N days", or invokes /portfolio-brief.
---

You are generating a personalized news digest for the user's stock portfolio.

## Step 1: Get the time window

If the user hasn't specified a time window, ask:
"How far back should I look — last 24 hours, 3 days, or a week?"

Convert their answer to a start date: today minus N days, formatted as YYYY-MM-DD.

## Step 2: Find and parse the Fidelity portfolio export

Find the most recent file matching `Portfolio_Positions_*.csv` in the project root.

Parse the CSV. The columns are:
`Account Number, Account Name, Symbol, Description, Quantity, Last Price, Last Price Change, Current Value, Today's Gain/Loss Dollar, Today's Gain/Loss Percent, Total Gain/Loss Dollar, Total Gain/Loss Percent, Percent Of Account, Cost Basis Total, Average Cost Basis, Type`

**Skip these rows:**
- Symbol contains `**` (money market: SPAXX**)
- Symbol looks like a CUSIP (contains digits mixed with letters and is longer than 5 chars, e.g. `89580DCG5`)
- Symbol is a Fidelity mutual fund (FSHOX, FSPSX, FXAIX, FBGRX, FSPGX, FWWFX, FSPGX, FWWFX, or any 5-char ticker starting with F that has no Last Price Change)
- Quantity is blank or zero
- Description contains "Pending activity" or "HELD IN MONEY MARKET"

**Aggregate across accounts:** If the same Symbol appears in multiple accounts, sum the Current Value and compute a weighted average of Average Cost Basis (weighted by Quantity).

**Sort** the resulting holdings by total Current Value descending (largest dollar position first).

## Step 3: Fetch news per holding

For each stock ticker (in Current Value order), call the MCP tool `stocknews_list_articles` with:
- `ticker`: the symbol (e.g. "NVDA")
- `date_from`: the start date from Step 1

## Step 4: Deduplicate cross-holding articles

If an article's ticker list includes multiple held symbols, assign it to the holding with the largest current value. Do not show the same article under more than one holding.

## Step 5: Format and output

For each holding, output:

```
TICKER  (N shares · $X.XX avg · $X,XXX current)
  • Article Title — one-sentence summary of why this matters for this holding
  • Article Title — one-sentence summary
  [no new articles in this window]   ← if none found
```

Sort holdings by current value (largest first). Skip holdings with no articles only if the list would be very long — include them with the "[no new articles]" note otherwise so the user knows coverage is complete.

End with a one-line count: "Covered X of Y holdings · Z articles found"
