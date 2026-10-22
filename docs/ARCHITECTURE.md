# Architecture and decisions

Stockroom has a small domain layer (`stockroom/store.py`), a JSON adapter (`stockroom/server.py`) and an independent static sample UI (`docs/`). SQLite is the persistence boundary. The sample page is deliberately disconnected from the API so GitHub Pages can host it without a server; its in-memory data resets on reload.

## Data model

- `products` stores a case-insensitive unique SKU, display name, integer-cent unit price, on-hand count and reorder level. Database checks reinforce non-negative money and quantities.
- `movements` appends receipts and sales with a signed quantity delta, price snapshot, reference and timestamp. Existing movements are not edited by stock operations.
- `sales` records each idempotency key and a hash of normalized line items. This prevents retries from decrementing stock twice and detects reuse of a key for different contents.

## Transaction boundary

Every write uses `BEGIN IMMEDIATE`, so SQLite acquires the writer lock before reading and checking stock. A sale validates all lines first, writes one sale record, then updates each product and adds movement rows. Any failure rolls back the entire transaction. This avoids a partial checkout when one line is unavailable. The products table also has a non-negative `CHECK` as a final invariant guard.

## Money and input

The API accepts integer cents and formats amounts only for display. It does not use floating-point values for calculations. SKUs, names, quantities, references and request sizes receive explicit validation. Search values are passed as bound SQL parameters.

## API and boundary

The standard-library HTTP server provides JSON routes for health, catalog search, stock receipt, sales, movement history and a low-stock/value report. It binds to `127.0.0.1` by default. There is no authentication, CORS policy or production deployment support; keep it local. A production version would need an authenticated application server, database backups, audit retention policy, permissions, operational monitoring and documented accounting rules.
