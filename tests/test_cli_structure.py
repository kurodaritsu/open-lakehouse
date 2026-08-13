"""CLI structure tests for the lifecycle commands (PR #0, Phase 1.5).

    U-28  reset/backup/doctor are TOP-LEVEL COMMANDS (4 sites), not services.

The 4 sites (plan 1.13.3): argument parsing (the connect-mode bypass), a
cmd_<name>() function, the top-level case dispatch, and cmd_help().
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LAKEHOUSE = REPO_ROOT / "lakehouse"
TEXT = LAKEHOUSE.read_text()


def _func_body(name: str) -> str:
    """Return the body of a `name() { ... }` bash function (brace at col 0 close)."""
    m = re.search(rf"^{re.escape(name)}\(\) \{{\n(.*?)^\}}", TEXT, re.M | re.S)
    assert m, f"function {name}() not found"
    return m.group(1)


def _run(*args: str, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(LAKEHOUSE), *args],
        cwd=REPO_ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestU28LifecycleCommandsAreTopLevel:
    COMMANDS = ("reset", "backup", "doctor")

    def test_cmd_functions_exist(self):
        for c in self.COMMANDS:
            assert f"cmd_{c}()" in TEXT, f"cmd_{c}() function missing"

    def test_top_level_case_dispatch(self):
        # Each command dispatches from the top-level case to its cmd_ function.
        for c in self.COMMANDS:
            assert re.search(
                rf"^\s*{c}\)\s+cmd_{c}", TEXT, re.M
            ), f"{c}) not dispatched to cmd_{c} in the top-level case"

    def test_arg_parsing_bypass_site(self):
        # The connect-mode bypass case (argument parsing) lists the commands.
        m = re.search(r"help\|status\|__resolve\|([a-z|]*)\|''", TEXT)
        assert m, "connect-mode bypass case not found"
        for c in self.COMMANDS:
            assert c in m.group(0), f"{c} missing from the arg-parsing bypass case"

    def test_listed_in_help(self):
        help_out = _run("help").stdout
        for c in self.COMMANDS:
            assert re.search(rf"^\s*{c}\b", help_out, re.M), f"{c} missing from help"

    def test_not_in_service_dispatch(self):
        # Must NOT appear in the start/stop/logs service `case $service in` blocks.
        for fn in ("cmd_start", "cmd_stop", "cmd_logs"):
            body = _func_body(fn)
            for c in self.COMMANDS:
                assert not re.search(
                    rf"^\s*{c}\)", body, re.M
                ), f"{c}) leaked into {fn} service dispatch"

    def test_rejects_all_without_yes_noninteractive(self):
        # Non-interactive destructive reset without --yes is rejected.
        r = _run("reset", "--all", stdin="")
        assert r.returncode != 0, "reset --all without --yes should be rejected"

    def test_dry_run_is_exempt_from_confirmation(self):
        r = _run("reset", "--all", "--dry-run", stdin="")
        assert r.returncode == 0, f"reset --all --dry-run should succeed: {r.stderr}"
        assert "DRY RUN" in r.stdout


class TestContainerRefsAreOverlayResolved:
    """Regression guard (plan 1.17.4): every docker exec/logs/ps container
    reference resolves through resolve_container_name so an active test overlay
    never probes or execs the wrong (production) stack. Base container literals
    may appear ONLY as an argument to resolve_container_name."""

    BASE_NAMES = (
        "spark-master-41",
        "spark-worker-41",
        "spark-connect-41",
        "kafka",
        "zookeeper",
        "unity-catalog",
        "airflow-webserver",
        "airflow-scheduler",
        "airflow-triggerer",
        "jupyter",
    )

    def test_no_raw_literal_in_docker_exec_or_logs(self):
        alt = "|".join(re.escape(n) for n in self.BASE_NAMES)
        bad = re.findall(rf"docker (?:exec|logs)(?:\s+-\S+)*\s+({alt})\b", TEXT)
        assert not bad, f"raw literal container names in docker exec/logs: {bad}"

    def test_no_raw_literal_in_docker_ps_grep(self):
        alt = "|".join(re.escape(n) for n in self.BASE_NAMES)
        # `grep -q '^<base>$'` against `docker ps` must use the resolved name var.
        bad = re.findall(rf"grep -q ['\"]\^(?:{alt})\$['\"]", TEXT)
        assert not bad, f"raw literal container names in docker ps greps: {bad}"
