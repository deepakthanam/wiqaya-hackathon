"""Shared fixtures: a small cohort generated into a temp dir (never touches data/)."""

from __future__ import annotations

import os

os.environ.setdefault("PYTHONUTF8", "1")

import pytest

from wiqaya.fhir import ndjson
from wiqaya.fhir.resources import to_resources
from wiqaya.generator.run import generate
from wiqaya.store.flatten import flatten


@pytest.fixture(scope="session")
def small_cohort():
    return generate(42, 600)


@pytest.fixture(scope="session")
def small_tables(small_cohort, tmp_path_factory):
    out = tmp_path_factory.mktemp("ndjson")
    ndjson.write_all(to_resources(small_cohort), out)
    return flatten(out)


@pytest.fixture(autouse=True)
def _reset_guest_rate_limit():
    """Each test starts with a fresh guest-session rate limit (30/min per IP would trip across test modules)."""
    yield
    from wiqaya.api.security import guest_limiter

    guest_limiter.hits.clear()
