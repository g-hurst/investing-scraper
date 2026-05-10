---
name: market-context
description: Summarize the macro and sector backdrop relevant to the user's holdings from their Fidelity export. Use when the user says "macro picture", "market context", "what's the backdrop", "what's moving markets", or invokes /market-context.
---

You are generating a macro context summary tailored to the user's stock portfolio.

## Step 1: Find and parse the Fidelity portfolio export

Find the most recent file matching `Portfolio_Positions_*.csv` in the project root.

Parse the CSV. The columns are:
`Account Number, Account Name, Symbol, Description, Quantity, Last Price, Last Price Change, Current Value, Today's Gain/Loss Dollar, Today's Gain/Loss Percent, Total Gain/Loss Dollar, Total Gain/Loss Percent, Percent Of Account, Cost Basis Total, Average Cost Basis, Type`

**Skip these rows:**
- Symbol contains `**` (money market: SPAXX**)
- Symbol looks like a CUSIP (contains digits mixed with letters, longer than 5 chars)
- Symbol is a Fidelity mutual fund (FSHOX, FSPSX, FXAIX, FBGRX, FSPGX, FWWFX, or any 5-char ticker starting with F that has no Last Price Change)
- Quantity is blank or zero
- Description contains "Pending activity" or "HELD IN MONEY MARKET"

Aggregate the same Symbol across accounts by summing Current Value.

## Step 2: Map holdings to sectors

Using your knowledge, classify each ticker into a sector. Common mappings for this portfolio:

| Sector | Tickers |
|--------|---------|
| AI / Semiconductors | NVDA, AMD, ANET, INTC |
| Software / Cybersecurity | CRWD, TYL, DOCS, CLBT, U |
| Big Tech / Cloud | AAPL, META, GOOGL, AMZN |
| Healthcare / Biotech | LLY, VRTX, NVO, MCK |
| Financials / Insurance | JPM, V, KNSL, PGR |
| Consumer / Retail | LULU, ONON, CART, CAVA, TOST, DIS, SYY |
| Industrials / Construction | EME, VLTO |
| LatAm E-commerce | MELI |
| Travel | BKNG |
| EV / Mobility | TSLA |
| IT Services | KD |
| Water Infrastructure | P |

For any ticker not listed, infer sector from Description in the CSV.

## Step 3: Search for macro topics

Call `stocknews_search_articles` for topics relevant to the sectors you identified. Use `date_from` set to 14 days ago and `limit=10` per query.

Run only the queries relevant to held sectors:

| Relevant when holding... | Query |
|--------------------------|-------|
| Any | `"interest rates Fed"` |
| Any | `"inflation"` |
| Any | `"earnings guidance"` |
| AI/Semiconductors, Software | `"AI infrastructure"` |
| AI/Semiconductors | `"chip demand semiconductor"` |
| Healthcare | `"pharma biotech"` |
| Financials | `"Goldman Fed rate"` |
| Consumer | `"consumer spending retail"` |
| Any international | `"tariffs trade"` |
| Industrials | `"Amazon logistics"` |

## Step 4: Synthesize by theme

Group findings by macro theme. For each theme that has actual scraped articles:
1. State the key development in one sentence
2. Note which held sectors or specific tickers it is bullish or bearish for

Only include themes with actual scraped data — do not speculate about topics with no articles.

## Step 5: Output

```
📊 Macro context for your holdings — [date]

[Theme]: [One-sentence development]
  → Bullish for: TICKER, TICKER
  → Bearish for: TICKER, TICKER

[Theme]: [One-sentence development]
  → Neutral / monitoring
```

If fewer than 3 themes have data, add:
"⚠️ Limited macro coverage — consider triggering a fresh scrape with the stocknews_trigger_scrape MCP tool."

End with a one-line portfolio tilt summary:
"Overall tilt: [brief characterization, e.g. 'Growth-heavy, rate-sensitive, significant healthcare exposure']"
