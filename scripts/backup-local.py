"""Snapshot-consistent backup/restore rehearsal for the native synthetic cluster."""

import hashlib
import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql

root = Path(__file__).resolve().parents[1]
config = json.loads((root / ".local/config.json").read_text(encoding="utf-8-sig"))
bin_dir = root / ".local/pgsql/bin"
archive = root / "backups" / f"native-{uuid4().hex}.dump"
archive.parent.mkdir(exist_ok=True)
restore_name = "restore_" + uuid4().hex
connect = dict(host="127.0.0.1", port=config["database_port"], user="mineassure",
               password=config["database_password"])
environment = {**os.environ, "PGHOST": "127.0.0.1", "PGPORT": str(config["database_port"]),
               "PGUSER": "mineassure", "PGPASSWORD": config["database_password"]}

with psycopg.connect(**connect, dbname="mineassure") as source:
    source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    snapshot = source.execute("SELECT pg_export_snapshot()").fetchone()[0]
    tables = [row[0] for row in source.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
    counts = {name: source.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(name))).fetchone()[0]
              for name in tables}
    subprocess.run([str(bin_dir / "pg_dump.exe"), "-d", "mineassure", "-Fc", "--snapshot", snapshot,
                    "-f", str(archive)], env=environment, check=True)
with psycopg.connect(**connect, dbname="postgres", autocommit=True) as admin:
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(restore_name)))
subprocess.run([str(bin_dir / "pg_restore.exe"), "--exit-on-error", "--no-owner", "-d", restore_name,
                str(archive)], env=environment, check=True)
with psycopg.connect(**connect, dbname=restore_name) as restored:
    actual = {name: restored.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(name))).fetchone()[0]
              for name in tables}
assert actual == counts, {"expected": counts, "actual": actual}
with archive.open("rb") as stream:
    digest = hashlib.file_digest(stream, "sha256").hexdigest()
report = {"archive": str(archive), "sha256": digest, "restore_database": restore_name,
          "table_counts": actual, "snapshot_consistent": True, "source_unchanged": True}
(root / ".local/backup-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
