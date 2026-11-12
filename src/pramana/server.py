"""Read-only HTTP API. Standard library only so any engineer can run it anywhere.

The write path (publishing) is deliberately not exposed here. Publication needs an
authenticated authority and an anchoring step that belong to the deployment, not to a
prototype. See DEPLOYMENT.md.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .ledger import Ledger
from .state import consolidate, exposure, items_from


class App:
    def __init__(self, ledger_path: str, corpus_path: str):
        self.ledger_path, self.corpus_path = ledger_path, corpus_path
        self.reload()

    def reload(self):
        self.ledger = Ledger.load(self.ledger_path)
        self.corpus = json.load(open(self.corpus_path, encoding="utf-8"))
        self.items = items_from(self.ledger, self.corpus.get("shadows", []))


def make_handler(app: App):
    class H(BaseHTTPRequestHandler):
        def _send(self, code: int, body: dict):
            data = json.dumps(body, indent=2).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):  # quiet by default
            if os.environ.get("PRAMANA_LOG"):
                super().log_message(fmt, *args)

        def do_GET(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                if u.path == "/healthz":
                    return self._send(200, {"status": "ok", "entries": len(app.ledger)})
                if u.path == "/head":
                    return self._send(200, app.ledger.anchor())
                if u.path == "/verify":
                    anchor = json.loads(q["anchor"]) if "anchor" in q else None
                    return self._send(200, app.ledger.verify(anchor).as_dict())
                if u.path == "/instruments":
                    return self._send(200, {"instruments": app.corpus["instruments"]})
                if u.path == "/asof":
                    st = consolidate(app.items, q["instrument"], q["at"], q.get("regime", "tora"), known_at=q.get("known_at"))
                    return self._send(200, {"instrument": q["instrument"], "at": q["at"], "clauses": st})
                if u.path == "/exposure":
                    return self._send(200, exposure(app.items, q["instrument"], q["act"], q["hindsight"]))
                return self._send(404, {"error": "not found"})
            except KeyError as exc:
                return self._send(400, {"error": f"missing parameter {exc}"})
            except ValueError as exc:
                return self._send(400, {"error": str(exc)})

    return H


def serve(host: str = "0.0.0.0", port: int = 8080, ledger: str | None = None, corpus: str | None = None):
    app = App(ledger or os.environ.get("PRAMANA_LEDGER", "data/synthetic_ledger.jsonl"),
              corpus or os.environ.get("PRAMANA_CORPUS", "data/synthetic_corpus.json"))
    srv = ThreadingHTTPServer((host, port), make_handler(app))
    print(f"pramana read-only API on {host}:{port} ({len(app.ledger)} entries)")
    srv.serve_forever()


if __name__ == "__main__":
    serve(port=int(os.environ.get("PORT", "8080")))
