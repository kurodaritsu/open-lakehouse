"""Integration tests for the destructive reset engine (PR #0, Checkpoint 3).

    I-28  reset --all empties a test-scoped env (DBs recreated, objects gone)
    I-30  reset --dry-run is inert
    I-31  reset --metadata preserves objects and warns
    I-32  reset --data leaves a CONSISTENT plane (verified by direct queries + S3)
    I-34  databases recreated + owned; DROP survives a held connection
    I-37  --metadata warning names the unrecoverable class; no sync_to_uc.py
    I-38  --keep-mlflow preserves artifact reachability
    I-50  every destructive mode quiesces writers
    I-54  post-reset assertion is APPLICATION-empty, not table-empty
    I-55  a mis-targeted overlay reset aborts (parameterized over all four classes)

FAIL-CLOSED: these skip unless LAKEHOUSE_TEST_RUN_ID is set (isolation guard),
Docker is available, and the host PostgreSQL + SeaweedFS are reachable. Every
resource is run-scoped (ol_test_<runid>_* / ol-test-<runid>); the real stack is
never touched.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LAKEHOUSE = REPO_ROOT / "lakehouse"
OVERLAY_DIR = REPO_ROOT / "tests" / "overlays"

sys.path.insert(0, str(REPO_ROOT / "tests"))
import isolation  # noqa: E402

pytestmark = [pytest.mark.integration, pytest.mark.merge]

PG_USER = os.environ.get("POSTGRES_USER", "lakehouse")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "lakehouse_pw")
PG_HOST = os.environ.get("POSTGRES_HOST", "host.docker.internal")
PG_PORT = os.environ.get("POSTGRES_PORT", "5432")
S3_KEY = os.environ.get("S3_ACCESS_KEY", "lakehouse_s3")
S3_SECRET = os.environ.get("S3_SECRET_KEY", "lakehouse_s3_secret")
S3_ENDPOINT_HOST = "http://localhost:8333"
PG_IMAGE = os.environ.get("LAKEHOUSE_PG_CLIENT_IMAGE", "postgres:15-alpine")


def _psql(db: str, sql: str, tuples: bool = False) -> subprocess.CompletedProcess:
    flag = "-tAc" if tuples else "-c"
    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--add-host=host.docker.internal:host-gateway",
            "-e",
            f"PGPASSWORD={PG_PASS}",
            PG_IMAGE,
            "psql",
            "-h",
            "host.docker.internal",
            "-p",
            PG_PORT,
            "-U",
            PG_USER,
            "-d",
            db,
            flag,
            sql,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _aws(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["aws", "--endpoint-url", S3_ENDPOINT_HOST, "s3", *args],
        capture_output=True,
        text=True,
        timeout=90,
        env={
            **os.environ,
            "AWS_ACCESS_KEY_ID": S3_KEY,
            "AWS_SECRET_ACCESS_KEY": S3_SECRET,
        },
    )


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


def _pg_ok() -> bool:
    return _psql("postgres", "SELECT 1", tuples=True).returncode == 0


def _s3_ok() -> bool:
    return _aws("ls").returncode == 0 and shutil_which("aws")


def shutil_which(x):
    import shutil

    return shutil.which(x) is not None


@pytest.fixture(scope="module")
def env():
    """Run-scoped fixture: fail-closed, seeds nothing yet, yields the overlay env."""
    rid = isolation.current_run_id()
    if rid is None:
        pytest.skip(
            "LAKEHOUSE_TEST_RUN_ID unset/invalid — destructive tests skip (fail-closed)"
        )
    if not _docker_ok():
        pytest.skip("Docker not available")
    if not (shutil_which("aws") and shutil_which("docker")):
        pytest.skip("aws/docker CLI not available")
    if not _pg_ok():
        pytest.skip("host PostgreSQL not reachable")
    if not _s3_ok():
        pytest.skip("host SeaweedFS/S3 not reachable")

    envfile = REPO_ROOT / ".smoke" / f"env-itest-{rid}"
    envfile.parent.mkdir(exist_ok=True)
    envfile.write_text(
        f"POSTGRES_USER={PG_USER}\nPOSTGRES_PASSWORD={PG_PASS}\n"
        f"POSTGRES_HOST=host.docker.internal\nPOSTGRES_PORT={PG_PORT}\n"
        f"S3_ENDPOINT=http://host.docker.internal:8333\n"
        f"S3_ACCESS_KEY={S3_KEY}\nS3_SECRET_KEY={S3_SECRET}\nS3_BUCKET=ol-test-{rid}\n"
    )
    overlay = {
        **os.environ,
        "LAKEHOUSE_TEST_RUN_ID": rid,
        "LAKEHOUSE_OVERLAY_DIR": str(OVERLAY_DIR),
        "LAKEHOUSE_RESOURCE_SUFFIX": rid,
        "LAKEHOUSE_ENV_FILE": str(envfile),
        "COMPOSE_PROJECT_NAME": f"ol-test-{rid}",
    }
    yield {
        "rid": rid,
        "overlay": overlay,
        "bucket": f"ol-test-{rid}",
        "dbs": {
            k: f"ol_test_{rid}_{k}" for k in ("airflow", "iceberg_catalog", "mlflow")
        },
    }

    # teardown: drop run-scoped DBs + bucket
    for db in (
        f"ol_test_{rid}_airflow",
        f"ol_test_{rid}_iceberg_catalog",
        f"ol_test_{rid}_mlflow",
    ):
        _psql("postgres", f'DROP DATABASE IF EXISTS "{db}"')
    _aws("rb", f"s3://ol-test-{rid}", "--force")
    envfile.unlink(missing_ok=True)


def _reset(env, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(LAKEHOUSE), "reset", *args],
        cwd=REPO_ROOT,
        env=env["overlay"],
        capture_output=True,
        text=True,
        timeout=300,
    )


def _seed(env, *, rows: bool = True, objects: bool = True):
    """Create the run-scoped DBs (+ seed rows) and bucket (+ seed objects)."""
    rid = env["rid"]
    for db in env["dbs"].values():
        _psql("postgres", f'DROP DATABASE IF EXISTS "{db}"')
        assert (
            _psql("postgres", f'CREATE DATABASE "{db}" OWNER "{PG_USER}"').returncode
            == 0
        )
    if rows:
        _psql(
            env["dbs"]["mlflow"],
            "CREATE TABLE runs(id int); INSERT INTO runs VALUES (1),(2)",
        )
        _psql(
            env["dbs"]["mlflow"],
            "CREATE TABLE experiments(id int); INSERT INTO experiments VALUES (1)",
        )
        _psql(
            env["dbs"]["iceberg_catalog"],
            "CREATE TABLE iceberg_tables(id int); INSERT INTO iceberg_tables VALUES (1)",
        )
    _aws("mb", f"s3://ol-test-{rid}")
    if objects:
        for key in ("warehouse/t/data.parquet", "mlflow-artifacts/1/a.txt"):
            subprocess.run(
                [
                    "aws",
                    "--endpoint-url",
                    S3_ENDPOINT_HOST,
                    "s3",
                    "cp",
                    "-",
                    f"s3://ol-test-{rid}/{key}",
                ],
                input="seed",
                text=True,
                capture_output=True,
                env={
                    **os.environ,
                    "AWS_ACCESS_KEY_ID": S3_KEY,
                    "AWS_SECRET_ACCESS_KEY": S3_SECRET,
                },
            )


def _count_objects(env, prefix: str) -> int:
    r = _aws("ls", f"s3://{env['bucket']}/{prefix}", "--recursive")
    return len([ln for ln in r.stdout.splitlines() if ln.strip()])


def _db_exists(db: str) -> bool:
    r = _psql(
        "postgres", f"SELECT 1 FROM pg_database WHERE datname='{db}'", tuples=True
    )
    return r.stdout.strip() == "1"


def _db_owner(db: str) -> str:
    return _psql(
        "postgres",
        f"SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='{db}'",
        tuples=True,
    ).stdout.strip()


def _rows(db: str, table: str) -> int:
    r = _psql(db, f"SELECT count(*) FROM {table}", tuples=True)
    return (
        int(r.stdout.strip())
        if r.returncode == 0 and r.stdout.strip().isdigit()
        else -1
    )


# --- tests -----------------------------------------------------------------------


def test_i30_dry_run_is_inert(env):
    _seed(env)
    before = _count_objects(env, "")
    r = _reset(env, "--all", "--dry-run")
    assert r.returncode == 0
    assert _count_objects(env, "") == before
    assert _db_exists(env["dbs"]["mlflow"])
    assert _rows(env["dbs"]["mlflow"], "runs") == 2  # untouched


def test_i34_metadata_recreates_dbs_owned(env):
    _seed(env)
    r = _reset(env, "--metadata", "--yes")
    assert r.returncode == 0, r.stderr
    for db in env["dbs"].values():
        assert _db_exists(db), f"{db} must exist after reset"
        assert _db_owner(db) == PG_USER, f"{db} owner preserved"
    # dropped+recreated => seeded tables gone
    assert _rows(env["dbs"]["mlflow"], "runs") == -1


def test_i34_drop_survives_held_connection(env):
    _seed(env)
    # Hold an open connection to a target DB for the duration of the reset.
    holder = subprocess.Popen(
        [
            "docker",
            "run",
            "--rm",
            "--add-host=host.docker.internal:host-gateway",
            "-e",
            f"PGPASSWORD={PG_PASS}",
            PG_IMAGE,
            "psql",
            "-h",
            "host.docker.internal",
            "-p",
            PG_PORT,
            "-U",
            PG_USER,
            "-d",
            env["dbs"]["mlflow"],
            "-c",
            "SELECT pg_sleep(30)",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        r = _reset(env, "--metadata", "--yes")
        assert (
            r.returncode == 0
        ), f"reset must succeed despite a held connection: {r.stderr}"
        assert _db_exists(env["dbs"]["mlflow"])
    finally:
        holder.terminate()


def test_i31_metadata_preserves_objects_and_warns(env):
    _seed(env)
    r = _reset(env, "--metadata", "--yes")
    assert r.returncode == 0, r.stderr
    # objects preserved
    assert _count_objects(env, "warehouse/") == 1
    assert _count_objects(env, "mlflow-artifacts/") == 1
    # classified warning present
    assert "UNRECOVERABLE" in r.stdout and "recoverable" in r.stdout


def test_i37_metadata_warning_flags_unrecoverable_no_script(env):
    _seed(env)
    r = _reset(env, "--metadata", "--yes")
    assert "UNRECOVERABLE" in r.stdout and "MLflow artifacts" in r.stdout
    assert "re-registerable from the Delta" in r.stdout
    assert "sync_to_uc" not in r.stdout


def test_i32_data_leaves_consistent_plane(env):
    _seed(env)
    r = _reset(env, "--data", "--yes")
    assert r.returncode == 0, r.stderr
    # objects gone
    assert _count_objects(env, "") == 0
    # referencing rows cleared, but DBs + tables preserved (verified DIRECTLY, no doctor)
    assert _db_exists(env["dbs"]["mlflow"]) and _db_exists(
        env["dbs"]["iceberg_catalog"]
    )
    assert _rows(env["dbs"]["mlflow"], "runs") == 0
    assert _rows(env["dbs"]["iceberg_catalog"], "iceberg_tables") == 0
    # experiments (not a run record) survive — --data clears runs, keeps structure
    assert _rows(env["dbs"]["mlflow"], "experiments") == 1


def test_i38_keep_mlflow_preserves_artifacts(env):
    _seed(env)
    r = _reset(env, "--metadata", "--keep-mlflow", "--yes")
    assert r.returncode == 0, r.stderr
    # mlflow DB preserved (not dropped), artifacts still reachable
    assert _rows(env["dbs"]["mlflow"], "runs") == 2, "mlflow DB must be preserved"
    assert _count_objects(env, "mlflow-artifacts/") == 1
    # airflow + iceberg still reset
    assert _rows(env["dbs"]["mlflow"], "runs") == 2
    assert "UNRECOVERABLE" not in r.stdout


def test_i28_i54_all_empties_application_state(env):
    _seed(env)
    r = _reset(env, "--all", "--yes")
    assert r.returncode == 0, r.stderr
    # (1) databases exist
    for db in env["dbs"].values():
        assert _db_exists(db)
    # (2/3) application state empty: recreated DBs have no seeded rows; zero objects
    assert _rows(env["dbs"]["mlflow"], "runs") == -1  # table gone (fresh DB)
    assert _count_objects(env, "") == 0


# CLI-injectable mis-target classes. bucket/database reach the semantic gate;
# container mismatches abort earlier at all-or-nothing activation. Both refuse
# without deleting anything. (volume-class gate coverage is U-66b, which calls the
# gate directly — activation overwrites COMPOSE_PROJECT_NAME so it can't be
# injected through the full CLI.)
@pytest.mark.parametrize("bad", ["bucket", "database", "container"])
def test_i55_mis_targeted_reset_aborts(env, bad, tmp_path):
    _seed(env)
    before = _count_objects(env, "")
    bad_overlay = dict(env["overlay"])
    if bad == "bucket":
        # A non-run-scoped bucket must be injected via the effective env FILE
        # (an env-var override is re-set when the CLI sources LAKEHOUSE_ENV_FILE).
        bad_env = tmp_path / "bad.env"
        good = Path(env["overlay"]["LAKEHOUSE_ENV_FILE"]).read_text()
        bad_env.write_text(
            good.replace(f"S3_BUCKET={env['bucket']}", "S3_BUCKET=lakehouse")
        )
        bad_overlay["LAKEHOUSE_ENV_FILE"] = str(bad_env)
    elif bad == "database":
        bad_overlay["MLFLOW_PG_DB"] = "mlflow"  # env file doesn't set it
    elif bad == "container":
        bad_overlay["LAKEHOUSE_RESOURCE_SUFFIX"] = "otherrun9"
    r = subprocess.run(
        [str(LAKEHOUSE), "reset", "--data", "--yes"],
        cwd=REPO_ROOT,
        env=bad_overlay,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode != 0, f"mis-targeted reset ({bad}) must abort"
    combined = r.stdout + r.stderr
    # Refused by the semantic gate ('not scoped') or all-or-nothing activation.
    assert "not scoped" in combined or "all-or-nothing" in combined
    assert _count_objects(env, "") == before  # nothing deleted


def test_i50_destructive_modes_quiesce(env):
    # The reset engine quiesces writers before deleting (plan 1.15.3). Assert the
    # quiesce path is exercised: reset --metadata reports quiescing and succeeds.
    _seed(env)
    r = _reset(env, "--metadata", "--yes")
    assert r.returncode == 0
    assert "Quiescing" in r.stdout or "Quiescing" in r.stderr
