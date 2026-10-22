# Local run and static demo

The browser demo is a static site. GitHub Pages can serve the `docs/` directory from the default branch. It needs no build step and uses only browser APIs. Its inventory is synthetic and resets on reload.

The Python service is for local learning and portfolio review. Run `python3 -m stockroom.server --host 127.0.0.1 --port 8060 --database stockroom.sqlite3`. To use a different database path, pass `--database` or set `STOCKROOM_DB`. The server has no login, TLS, rate limits or hardened production configuration; do not expose it to the public internet.

To inspect without installing anything, use Python's built-in file server: `python3 -m http.server 8080`, then visit `http://127.0.0.1:8080/docs/`.
