# EvE-Logistics Refactor Note

## Purpose

This note captures the first cleanup pass for EvE-Logistics so future work stays intentional instead of drifting.

## What changed in this pass

The project was moved from a single-file shape toward a simple modular structure:

- `config.py`
  - central static configuration
  - doctrines
  - watchlist
  - EVE constants
- `storage.py`
  - SQLite setup and read/write helpers
- `wallet.py`
  - wallet parsing and fee calculation helpers
- `doctrine.py`
  - doctrine summary logic
- `market_scan.py`
  - async ESI scan logic and market helpers
- `requirements.txt`
  - baseline runtime dependencies

## What still needs to happen

### 1. Slim down `app.py`
The next code pass should switch `app.py` to importing these modules instead of defining everything inline.

### 2. Clarify storage authority
The repo still contains JSON files alongside SQLite usage.
The intended direction is:
- SQLite = authoritative runtime store
- JSON = legacy snapshot, import/export, or backup only

That decision should be made explicit in code and docs.

### 3. Expand persistence model
Current SQLite history is thinner than the historical JSON data.
Future migration should store richer logistics records.

### 4. Improve observability
Current scanner/network code still catches broad exceptions quietly.
Add lightweight logging and clearer UI feedback.

## Refactor philosophy

This project should stay:
- lightweight
- internal-tool friendly
- easy to iterate on

The goal is not enterprise architecture.
The goal is a cleaner utility app that can grow without turning into spaghetti.
