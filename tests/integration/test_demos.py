"""Integration tests for the demo contract (PR #0, Checkpoint 5).

    I-35  the teardown TEMPLATE cleans its S3 prefix (plan 1.14.9, scope-narrowed).
          Copy demos/_template to a throwaway dir, substitute a TEST-SCOPED prefix,
          create objects under it, run teardown.sh, assert zero residue — and that an
          object OUTSIDE the prefix is untouched. Tests the template's correctness,
          not shipped demos (full per-demo coverage is Phase 5, T-5.9).

FAIL-CLOSED: skips unless LAKEHOUSE_TEST_RUN_ID is set (isolation guard) and host
SeaweedFS/S3 + the aws CLI are reachable. All objects live under the run-scoped bucket
ol-test-<runid>; the real stack is never touched.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE = REPO_ROOT / "demos" / "_template"

sys.path.insert(0, str(REPO_ROOT / "tests"))
import isolation  # noqa: E402

pytestmark = [pytest.mark.integration, pytest.mark.merge, pytest.mark.slow]

S3_KEY = os.environ.get("S3_ACCESS_KEY", "lakehouse_s3")
S3_SECRET = os.environ.get("S3_SECRET_KEY", "lakehouse_s3_secret")
S3_ENDPOINT = "http://localhost:8333"


def _aws(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["aws", "--endpoint-url", S3_ENDPOINT, "s3", *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=90,
        env={
            **os.environ,
            "AWS_ACCESS_KEY_ID": S3_KEY,
            "AWS_SECRET_ACCESS_KEY": S3_SECRET,
        },
    )


def _put(bucket: str, key: str, tries: int = 6) -> None:
    # Local SeaweedFS can return a transient InternalError — e.g. if the host sleeps
    # mid-run (a laptop lid-close pauses the container + drops the connection), or
    # just after a bucket is created. Bounded retry keeps seeding deterministic
    # without masking a durable failure.
    last = None
    for i in range(tries):
        last = _aws("cp", "-", f"s3://{bucket}/{key}", stdin="x")
        if last.returncode == 0:
            return
        time.sleep(1 + i)
    raise AssertionError(f"seeding {key} failed after {tries} tries: {last.stderr}")


def _count(bucket: str, prefix: str) -> int:
    r = _aws("ls", f"s3://{bucket}/{prefix}", "--recursive")
    return len([ln for ln in r.stdout.splitlines() if ln.strip()])


def _count_stable(bucket: str, prefix: str, want: int, tries: int = 10) -> int:
    # SeaweedFS S3 LIST is only eventually consistent (and the host may sleep
    # mid-run); poll briefly so the test asserts on settled state rather than a
    # mid-write listing.
    n = _count(bucket, prefix)
    for _ in range(tries):
        if n == want:
            return n
        time.sleep(0.5)
        n = _count(bucket, prefix)
    return n


@pytest.fixture()
def bucket():
    rid = isolation.current_run_id()
    if rid is None:
        pytest.skip(
            "LAKEHOUSE_TEST_RUN_ID unset/invalid — demo tests skip (fail-closed)"
        )
    if shutil.which("aws") is None:
        pytest.skip("aws CLI not available")
    if _aws("ls").returncode != 0:
        pytest.skip("host SeaweedFS/S3 not reachable")
    b = f"ol-test-{rid}"
    _aws("mb", f"s3://{b}")
    yield b
    _aws("rb", f"s3://{b}", "--force")


def test_i35_template_teardown_cleans_its_prefix(bucket, tmp_path):
    rid = isolation.require_run_id()
    # Instantiate the template into a throwaway demo dir.
    demo = tmp_path / "throwaway-demo"
    shutil.copytree(TEMPLATE, demo)
    teardown = demo / "teardown.sh"
    assert teardown.exists(), "template must ship a teardown.sh"

    # A test-scoped prefix this 'demo' owns, plus an object OUTSIDE it that must
    # survive (teardown clears only its own prefix).
    prefix = f"warehouse/tmpl-{rid}/"
    _put(bucket, f"{prefix}part-0.parquet")
    _put(bucket, f"{prefix}sub/part-1.parquet")
    _put(bucket, "warehouse/other/keep.parquet")
    assert _count_stable(bucket, prefix, 2) == 2
    assert _count_stable(bucket, "warehouse/other/", 1) == 1

    # Run the template's teardown, pointing it at the run-scoped bucket + prefix.
    r = subprocess.run(
        ["bash", str(teardown)],
        cwd=demo,
        capture_output=True,
        text=True,
        timeout=90,
        env={
            **os.environ,
            "S3_BUCKET": bucket,
            "S3_ENDPOINT": S3_ENDPOINT,
            "S3_ACCESS_KEY": S3_KEY,
            "S3_SECRET_KEY": S3_SECRET,
            "DEMO_S3_PREFIX": prefix,
        },
    )
    assert r.returncode == 0, f"teardown must succeed: {r.stderr}"

    # Zero residue under the demo's prefix; the unrelated object is untouched.
    assert _count_stable(bucket, prefix, 0) == 0, "teardown must remove its S3 prefix"
    assert (
        _count_stable(bucket, "warehouse/other/", 1) == 1
    ), "teardown must not touch other data"

    # Idempotent: a second run over the now-clean prefix still succeeds.
    r2 = subprocess.run(
        ["bash", str(teardown)],
        cwd=demo,
        capture_output=True,
        text=True,
        timeout=90,
        env={
            **os.environ,
            "S3_BUCKET": bucket,
            "S3_ENDPOINT": S3_ENDPOINT,
            "S3_ACCESS_KEY": S3_KEY,
            "S3_SECRET_KEY": S3_SECRET,
            "DEMO_S3_PREFIX": prefix,
        },
    )
    assert r2.returncode == 0, "teardown must be safe to re-run"
