import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import jsonschema
import pytest

from pramana import cli
from pramana.server import App, make_handler
from pramana.synth import build_corpus, write_synthetic


def validator(schemas, name):
    loaded, reg = schemas
    return jsonschema.Draft202012Validator(loaded[name], registry=reg)


def test_every_ledger_entry_matches_schema(ledger, schemas):
    v = validator(schemas, "ledger_entry.schema.json")
    for e in ledger.entries:
        v.validate(e)


def test_shadows_and_corpus_match_schema(schemas):
    validator(schemas, "corpus.schema.json").validate(build_corpus())


def test_schema_rejects_bad_diffs(schemas):
    v = validator(schemas, "diff.schema.json")
    base = {"diff_id": "a", "instrument_id": "i", "op": "repeal", "clause_id": "1", "authority": "x", "source_ref": "y"}
    v.validate(base)
    with pytest.raises(jsonschema.ValidationError):
        v.validate({**base, "op": "erase"})
    with pytest.raises(jsonschema.ValidationError):
        v.validate({**base, "clause": {"text": "a repeal must not carry a body"}})
    with pytest.raises(jsonschema.ValidationError):
        v.validate({**base, "op": "insert"})
    with pytest.raises(jsonschema.ValidationError):
        v.validate({**base, "published_at": "2024-01-01T00:00:00Z"})  # callers cannot set it


@pytest.fixture()
def served(tmp_path):
    lp, cp = write_synthetic(tmp_path)
    app = App(str(lp), str(cp))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def get(url):
    try:
        with urllib.request.urlopen(url) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_server_endpoints(served):
    assert get(served + "/healthz") == (200, {"status": "ok", "entries": 15})
    code, body = get(served + "/verify")
    assert code == 200 and body["ok"]
    code, body = get(served + "/asof?instrument=SYN-FIL-02&at=2024-12-12T17:01:00%2B05:30")
    assert "45 days" in body["clauses"]["1.1"]["text"]
    code, body = get(served + "/exposure?instrument=SYN-FIL-02&act=2024-12-12T16:00:00%2B05:30&hindsight=2025-06-01T00:00:00%2B05:30")
    assert body["tora_delta"] == [] and body["legacy_delta"]


def test_server_errors_are_clean(served):
    assert get(served + "/asof")[0] == 400
    assert get(served + "/nope")[0] == 404
    assert get(served + "/asof?instrument=X&at=not-a-date")[0] == 400


def test_server_has_no_write_path(served):
    req = urllib.request.Request(served + "/head", data=b"{}", method="POST")
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code in (501, 405)


def test_cli_demo_runs(tmp_path, capsys):
    write_synthetic(tmp_path)
    rc = cli.main(["--ledger", str(tmp_path / "synthetic_ledger.jsonl"), "--corpus", str(tmp_path / "synthetic_corpus.json"), "demo"])
    out = capsys.readouterr().out
    assert rc == 0 and "BROKEN" in out and "CHOICE LEFT TO OFFICIAL" in out


def test_cli_verify_exit_code(tmp_path, capsys):
    lp, _ = write_synthetic(tmp_path)
    assert cli.main(["--ledger", str(lp), "verify"]) == 0
    lines = lp.read_text().splitlines()
    lines[3] = lines[3].replace("365 days", "999 days")
    lp.write_text("\n".join(lines) + "\n")
    assert cli.main(["--ledger", str(lp), "verify"]) == 2
