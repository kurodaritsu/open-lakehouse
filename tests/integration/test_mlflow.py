"""MLflow status integration test (PR #0, Phase 1.5, Checkpoint 6).

    I-48  MLflow reports its TRUE status (§1.13.6 / T-1.5.11). `status --json` must
          report services.mlflow == true when the MLflow container is running. On
          `main` this was always false: the CLI probed a container named `mlflow`
          while Compose names it `mlflow-server`.

The container-name resolution is what the fix turns on, so a stand-in container named
`mlflow-server` is sufficient and deterministic — status only checks whether the
resolved container is running. If the REAL mlflow-server is already up, we assert
against it directly instead.

FAIL-CLOSED on tooling: skips when Docker is unavailable.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LAKEHOUSE = REPO_ROOT / "lakehouse"

pytestmark = [pytest.mark.integration, pytest.mark.merge]

ALPINE = "alpine:latest"
STANDIN = "mlflow-server"


def _docker_ok() -> bool:
    try:
        return (
            subprocess.run(
                ["docker", "info"], capture_output=True, timeout=10
            ).returncode
            == 0
        )
    except Exception:
        return False


def _running(name: str) -> bool:
    out = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True
    ).stdout.split()
    return name in out


def _status_json() -> dict:
    # DEFAULT path (no overlay): status is in the connect-mode bypass list.
    r = subprocess.run(
        [str(LAKEHOUSE), "status", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_i48_mlflow_status_true_when_running():
    if not _docker_ok():
        pytest.skip("Docker not available")

    # If the real mlflow-server is already up, assert against it and do not touch it.
    if _running(STANDIN):
        assert _status_json()["services"]["mlflow"] is True
        return

    # Otherwise stand up a throwaway container named mlflow-server — status only
    # checks whether the resolved container (mlflow -> mlflow-server) is running.
    subprocess.run(["docker", "rm", "-f", STANDIN], capture_output=True)
    subprocess.run(
        ["docker", "run", "-d", "--name", STANDIN, ALPINE, "sleep", "120"],
        capture_output=True,
        check=True,
    )
    try:
        assert _running(STANDIN), "stand-in mlflow-server must be up"
        status = _status_json()
        assert status["services"]["mlflow"] is True, (
            "status --json must report services.mlflow==true when mlflow-server runs "
            "(regression guard for the mlflow vs mlflow-server probe bug)"
        )
    finally:
        subprocess.run(["docker", "rm", "-f", STANDIN], capture_output=True)


def test_i48_mlflow_status_false_when_absent():
    # Negative half: with no mlflow-server container, status reports false (not an
    # error). Skips if the real mlflow-server happens to be running.
    if not _docker_ok():
        pytest.skip("Docker not available")
    if _running(STANDIN):
        pytest.skip("mlflow-server is running; negative case not applicable")
    assert _status_json()["services"]["mlflow"] is False
