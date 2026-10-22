# Interview guide

Use this guide to understand and explain the project in your own words. Run the tests, make a small change and describe what you observed before discussing the design.

## A concise walkthrough

“Stockroom is a small inventory and sales ledger. The Python API stores products and signed stock movements in SQLite. A sale may contain several products, so the service checks stock and writes the sale in one transaction. Prices are integer cents. An idempotency key makes retries safe. The static dashboard demonstrates the workflow with synthetic sample data; it is independent of the API so it can run on static hosting.”

## Questions to practise

- Why store prices as integer cents rather than floating-point numbers?
- What could go wrong if stock validation happened outside the database transaction?
- How does `BEGIN IMMEDIATE` help when two sale requests arrive at nearly the same time?
- What is the difference between retrying the same idempotency key and reusing it with a changed payload?
- Why retain movement rows instead of only changing the product quantity?
- Which constraints belong in Python and which are also enforced by SQLite?
- What would you change before supporting multiple stores, users and public deployment?

## Suggested next improvement

Implement a concurrency test with two threads trying to sell the final unit. Assert that only one succeeds and the stored quantity remains zero. Then add a migration strategy and an authenticated user model before adding production deployment.
