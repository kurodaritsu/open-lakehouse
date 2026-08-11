"""Fail-closed destructive-operation guard for the TEST HARNESS ONLY.

Implementation plan T-1.5.0b / §1.13.1 / §1.14.3 / §1.17.3.

This guard lives in the pytest layer and **never** inside the production
``./lakehouse reset`` command. Production reset must be able to destroy the real,
configured resources after confirmation (§1.14.3); putting a name-pattern guard
there would disable the feature it protects.

Here, by contrast, every destructive helper a test uses must target only resources
derived from the **current** ``LAKEHOUSE_TEST_RUN_ID``, and must **skip** — never
fall back to a real name — when the run-id is unset (§1.13.1). The guard binds to the
current run-id specifically: a resource that matches the ``ol_test_`` / ``ol-test-``
family but carries a *different* run-id is refused too (§1.17.3), so parallel or stale
runs can never destroy each other's state.
"""

from __future__ import annotations

import os
import re
import tempfile

RUN_ID_ENV = "LAKEHOUSE_TEST_RUN_ID"
RUN_ID_RE = re.compile(r"^[a-z0-9]{8,16}$")

# The PostgreSQL databases and S3 bucket a full test run owns. Kept in sync with the
# per-base overlays under tests/overlays/ and with scripts/lib/overlay.sh.
_DB_SUFFIXES = ("mlflow", "airflow", "iceberg")


class IsolationError(AssertionError):
    """Raised when a destructive test operation targets a non-run-scoped resource."""


def current_run_id() -> str | None:
    """Return the current, well-formed test run-id, or ``None`` (fail closed).

    ``None`` means "no valid run-id" — callers and fixtures must **skip**, never
    substitute a production resource name.
    """
    rid = os.environ.get(RUN_ID_ENV, "")
    return rid if RUN_ID_RE.match(rid) else None


def require_run_id() -> str:
    """Return the current run-id or raise :class:`IsolationError` (fail closed)."""
    rid = current_run_id()
    if rid is None:
        raise IsolationError(
            f"{RUN_ID_ENV} is unset or malformed "
            f"({os.environ.get(RUN_ID_ENV, '')!r}); destructive test helpers must "
            "skip and must never fall back to real resource names"
        )
    return rid


# --- expected run-scoped names (what a test is ALLOWED to touch) -------------------


def expected_databases(run_id: str) -> set[str]:
    return {f"ol_test_{run_id}_{suffix}" for suffix in _DB_SUFFIXES}


def expected_bucket(run_id: str) -> str:
    return f"ol-test-{run_id}"


# --- the guards --------------------------------------------------------------------


def _db_ok(name: str, rid: str) -> bool:
    return re.fullmatch(rf"ol_test_{re.escape(rid)}(_[a-z0-9_]+)?", name) is not None


def _bucket_ok(name: str, rid: str) -> bool:
    return name == f"ol-test-{rid}"


def _volume_ok(name: str, rid: str) -> bool:
    return re.fullmatch(rf"ol-test-{re.escape(rid)}_[a-z0-9_-]+", name) is not None


def _container_ok(name: str, rid: str) -> bool:
    return re.fullmatch(rf"[a-z0-9._-]+-{re.escape(rid)}", name) is not None


def assert_test_database(name: str) -> str:
    """Permit dropping ``name`` only if it is scoped to the current run-id."""
    rid = require_run_id()
    if not _db_ok(name, rid):
        raise IsolationError(
            f"refusing to touch PostgreSQL database {name!r}: not derived from the "
            f"current run-id {rid!r} (allowed e.g. ol_test_{rid}_mlflow)"
        )
    return name


def assert_test_bucket(name: str) -> str:
    """Permit emptying ``name`` only if it is exactly the run-scoped test bucket.

    Also refuses a *prefix inside* another bucket (e.g. ``lakehouse/warehouse``),
    which must never be treated as an emptyable bucket (§1.13.1, U-43).
    """
    rid = require_run_id()
    if "/" in name:
        raise IsolationError(
            f"refusing bucket {name!r}: contains '/', i.e. a prefix inside another "
            "bucket — never empty a prefix inside a real bucket"
        )
    if not _bucket_ok(name, rid):
        raise IsolationError(
            f"refusing to empty S3 bucket {name!r}: not the run-scoped test bucket "
            f"ol-test-{rid}"
        )
    return name


def assert_test_volume(name: str) -> str:
    """Permit removing a Docker volume only if it is run-scoped."""
    rid = require_run_id()
    if not _volume_ok(name, rid):
        raise IsolationError(
            f"refusing to remove volume {name!r}: not derived from the current "
            f"run-id {rid!r} (allowed e.g. ol-test-{rid}_mlflow-data)"
        )
    return name


def assert_test_container(name: str) -> str:
    """Permit acting on a container only if its name is run-scoped."""
    rid = require_run_id()
    if not _container_ok(name, rid):
        raise IsolationError(
            f"refusing to touch container {name!r}: not derived from the current "
            f"run-id {rid!r} (allowed e.g. mlflow-server-{rid})"
        )
    return name


def assert_temp_path(path: str) -> str:
    """Permit an ``rm -rf`` target only if it resolves inside the temp dir.

    No destructive test may ever remove a path outside ``$TMPDIR`` — in particular
    never ``/tmp/seaweedfs``, ``./data``, or a home directory (§1.13.1, U-45).
    """
    real = os.path.realpath(path)
    tmp = os.path.realpath(tempfile.gettempdir())
    if real != tmp and not real.startswith(tmp + os.sep):
        raise IsolationError(
            f"refusing rm -rf {path!r} (resolves to {real!r}): outside the temp dir "
            f"{tmp!r}"
        )
    return path
