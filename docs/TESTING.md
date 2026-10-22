# Testing

Run `python3 -m unittest discover -v` from the repository root. The suite uses temporary SQLite files and an ephemeral localhost port; it does not need credentials, external services or third-party packages.

Coverage includes input validation, SKU uniqueness, money representation, receipt records, all-or-nothing multi-item sales, insufficient stock, idempotent retries, conflicting idempotency keys, duplicate sale lines, search and low-stock/value totals. HTTP integration checks exercise health, product creation, receipts, sales, reports, duplicate conflicts and malformed JSON. GitHub Actions runs the same command on pushes and pull requests.

To explore behavior interactively, serve the project root and open `docs/`. The sample UI intentionally has isolated in-memory state; its actions do not modify the API database.
