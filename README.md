# EvE-Logistics

A small Streamlit utility app for BobVult logistics workflows in **EVE Online**.

Current scope:
- Track doctrine stock targets
- Estimate hauling / logistics costs from pasted wallet rows
- Show recent logistics history
- Scan wormhole exit arbitrage opportunities against Jita buy orders

## Current architecture

The app is currently a compact prototype built around a single main file:

- `app.py` — Streamlit UI and most application logic
- `bobvult_logistics.json` — doctrine stock state snapshot
- `hauling_history.json` — historical logistics entries
- `logistics.db` — SQLite database created at runtime for stock/history data

Despite the JSON files still being present, the current app logic primarily uses **SQLite** (`logistics.db`) for stock and history.
That means the JSON files should currently be treated as legacy / reference data unless the app is updated to use them again explicitly.

## Features

### 1. Doctrine Tracker
Tracks current stock against doctrine targets for a small set of predefined ships:
- Sabre
- Malediction
- Praxis
- Cyclone

For each doctrine ship, the app shows:
- target count
- current stock
- missing quantity
- fit link
- estimated logistics volume needed

Stock progress is saved into SQLite.

### 2. Wallet Analyzer
Parses pasted wallet rows and estimates logistics cost using:
- flat jump cost
- m3-based transport cost
- risk percentage surcharge

This is useful as a quick operational calculator, but the parsing is currently based on a fairly loose regex and assumes a specific pasted text format.

### 3. Transaction History
Shows the latest stored history rows from SQLite.

### 4. WH Exit Arbitrage Scanner
Scans a watchlist of items using EVE ESI market data and compares:
- local sell orders in a selected system
- against Jita buy orders

The scanner:
- resolves target system + region through ESI
- fetches market pages asynchronously
- calculates how much can fit in a DST
- filters by minimum hold fill percentage
- filters by minimum total profit per DST

## Runtime / dependencies

Current Python dependencies visible from the code:
- `streamlit`
- `pandas`
- `aiohttp`
- standard library modules such as `sqlite3`, `asyncio`, `re`
- `requests` is also used indirectly inside `get_item_vol_sync`

## Review: current strengths

### What is good already
- Clear practical purpose
- Fast to iterate on because the app is small
- Streamlit is a good fit for an internal utility tool
- Async ESI scanning is the right direction for the arbitrage feature
- Doctrine tracker and scanner are immediately useful operationally

## Review: current weaknesses

### 1. Everything lives in `app.py`
UI, persistence, configuration, market scanning, and business logic are all mixed together.
This is fine for a prototype, but it will get harder to maintain quickly.

### 2. Storage model is inconsistent
The repo contains JSON data files, but the running app writes to SQLite.
That creates ambiguity:
- which files are authoritative?
- are the JSON files still used?
- should they be migrated or removed?

### 3. No real project documentation
Until now, the README did not explain:
- what the app does
- how to run it
- what data files mean
- what the roadmap is

### 4. Configuration is hard-coded
A lot of operational values are embedded directly in code:
- watchlist
- doctrine list
- Jita constants
- target counts
- m3 assumptions

That makes changes slower and increases the chance of editing code for what should be config.

### 5. Limited persistence model
The SQLite schema is very small and does not yet reflect all visible app concepts.
For example, transaction history in SQLite currently stores only:
- timestamp
- total

But `hauling_history.json` contains richer fields like:
- jita cost
- fee
- per-unit
- split
- jumps
- volume

So either the SQLite schema is incomplete, or the JSON history is a leftover from an older version.

### 6. Error handling is minimal
Several network/database paths fail silently or return `None` on broad exceptions.
That keeps the UI simple, but it makes debugging and trust harder.

## Recommended improvement plan

### Phase 1 — clean up the project shape
1. Split `app.py` into modules, for example:
   - `ui.py`
   - `market.py`
   - `storage.py`
   - `config.py`
2. Decide on one authoritative persistence model:
   - either SQLite only
   - or JSON only
   - preferably SQLite for app state/history
3. Move hard-coded config into a dedicated config layer

### Phase 2 — improve data quality and observability
1. Expand the history schema so it stores the full logistics calculation
2. Add lightweight logging for failed ESI calls and parsing failures
3. Make scan failures more visible in the UI
4. Add timestamps / provenance to saved stock and scan outputs

### Phase 3 — improve UX
1. Show clearer scan summaries:
   - best opportunity
   - total candidates found
   - average fill/profit
2. Add export options for results
3. Make doctrine editing configurable through the UI or a config file
4. Add validation around pasted wallet input

### Phase 4 — make it easier to operate long-term
1. Add a proper `requirements.txt` or `pyproject.toml`
2. Add setup/run instructions
3. Add screenshots or example workflows to the README
4. Add backups or migration handling for `logistics.db`

## Immediate high-value next changes

If I were prioritizing the next few improvements, I would do these first:

1. **Document how to run the app**
2. **Decide whether SQLite or JSON is the real source of truth**
3. **Move doctrines/watchlist/constants into config**
4. **Expand the history model so saved data matches actual calculations**
5. **Break up `app.py` before feature growth continues**

## Suggested run command

If Streamlit is installed, the app is likely started with something like:

```bash
streamlit run app.py
```

## Open questions

These should be clarified next:
- Is `bobvult_logistics.json` still intended to be live data, or is it legacy?
- Is `hauling_history.json` legacy, backup, or still part of the workflow?
- Should doctrine definitions remain code-based, or become editable config?
- Is the arbitrage scanner intended to remain internal-only, or grow into a broader tool?

## Branch context

Current observed branch:
- `feature/scan-speed-and-config`

That seems consistent with the current needs of the app: faster scanning and cleaner configuration are both legitimate priorities.
