# Stockroom Ledger

A compact inventory and sales ledger for an independent retailer. It demonstrates transactional stock receipts, atomic multi-item sales, an auditable movement ledger and safe retries through idempotency keys.

**Stack:** Python 3.11+, SQLite, the Python standard library and plain JavaScript. No third-party runtime packages.

## Interactive demo

Open the [browser demo](docs/index.html) or serve the repository with Python:

    python3 -m http.server 8080

Then visit /docs/. The demo uses synthetic in-memory products and resets when reloaded. It is a standalone interface and does not call the API.

## Run the API

From the repository root:

    python3 -m stockroom.server --host 127.0.0.1 --port 8060 --database stockroom.sqlite3

The database is created locally. Prices use integer cents. Example:

    curl -s -X POST http://127.0.0.1:8060/api/products -H 'Content-Type: application/json' -d '{"sku":"BEAN-250","name":"House Blend Coffee","unit_price_cents":8900,"reorder_level":5}'

Sales require a unique idempotency_key. Replaying the same key and payload returns the original sale; using the key with different items is rejected.

## API

- GET /api/health — health check
- GET /api/products?q=bean — search catalog
- POST /api/products — add product
- POST /api/stock — receive stock and record movement
- POST /api/sales — sell products atomically
- GET /api/movements?limit=50 — recent movement ledger
- GET /api/reports/stock — totals and reorder list

## Tests

Run python3 -m unittest discover -v. The suite covers API behavior, transaction rollback, idempotent retries and competing sales for the final unit.

See [architecture](docs/ARCHITECTURE.md), [testing](docs/TESTING.md), [deployment](docs/DEPLOYMENT.md) and the [interview guide](docs/INTERVIEW_GUIDE.md).

This is a learning project, not production retail software. It has no authentication, multi-user controls, payment processing, tax rules or backup system. The API binds to localhost by default. The demo contains only synthetic data.

## Inspiration

This original small-retailer exercise explores commerce patterns also found in [Saleor](https://github.com/saleor/saleor). It does not copy Saleor source or branding. Created with AI assistance; the repository owner should review the code and be ready to explain its design.
