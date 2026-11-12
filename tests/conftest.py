import json
from pathlib import Path

import pytest

from pramana.state import items_from
from pramana.synth import SHADOWS, build_ledger

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def ledger():
    return build_ledger()


@pytest.fixture(scope="session")
def items(ledger):
    return items_from(ledger, SHADOWS)


@pytest.fixture(scope="session")
def schemas():
    from referencing import Registry, Resource
    reg, loaded = Registry(), {}
    for f in (ROOT / "schemas").glob("*.json"):
        s = json.loads(f.read_text())
        loaded[f.name] = s
        reg = reg.with_resource(s["$id"], Resource.from_contents(s))
    return loaded, reg
