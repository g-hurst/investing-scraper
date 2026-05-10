---
name: portfolio-health
description: Check portfolio health and flag risks per holding using scraped news. Use when the user says "check my portfolio", "portfolio health", "any red flags", "how are my holdings doing", or invokes /portfolio-health.
---

You are performing a health check on the user's stock portfolio using recent news articles.

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

**Aggregate across accounts:** If the same Symbol appears in multiple accounts, sum the Current Value, sum Today's Gain/Loss Dollar, sum Total Gain/Loss Dollar.

**Sort** holdings by total Current Value descending.

## Step 2: Fetch recent news per holding

For each ticker, call `stocknews_list_articles` with:
- `ticker`: the symbol
- `date_from`: 14 days ago (today minus 14 days, format YYYY-MM-DD)

For any articles found, call `stocknews_get_article` with the article's `id` to retrieve full content.

## Step 3: Analyze each holding

Read each article's full content. Look for these signals:

**Red flags → 🔴:**
- Earnings miss or EPS below consensus
- Revenue guidance cut for next quarter
- CEO/CFO departure or unexpected management change
- Loss of a major customer, contract, or partnership
- Regulatory action, lawsuit, or government investigation
- Analyst downgrade or significant price target cut
- Direct competitive threat gaining meaningful market share

**Yellow flags → 🟡:**
- Mixed results (beat on one metric, miss on another)
- Macro headwind affecting the sector broadly
- Cautious or vague language from management about near-term outlook
- Peer company disappointment that may signal industry slowdown

**Green signals → 🟢:**
- Beat on revenue and EPS
- Guidance raised
- New major contract, partnership, or market expansion
- Analyst upgrades or price target increases
- Strong industry tailwinds confirmed

**No articles found → 🟡** and note "[no recent articles — unable to assess]"

Rate each holding 🟢 🟡 or 🔴.

## Step 4: Output

Header line: `Portfolio Health Check — [date]`

List holdings sorted by concern level (🔴 first, then 🟡, then 🟢). Within each level, sort by Current Value descending:

```
TICKER  🔴  $X,XXX current  (+X.X% / -X.X% total)  One-line reason
TICKER  🟡  $X,XXX current  One-line reason
TICKER  🟢  $X,XXX current  One-line reason
```

End with:
```
⚠️  Top concern: [1–2 sentence summary of the biggest portfolio-wide risk, if any]
💡  Bright spot: [1 sentence on the strongest positive signal, if any]
```

Omit "Top concern" if all holdings are 🟢. Omit "Bright spot" if no clear positive signals.
