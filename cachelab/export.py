"""Safe, one-way export of gem5 results into CacheLab's own workspace.

**Policy: the gem5 research tree is a separate, live project and is treated as
strictly read-only.** A 128-job sweep runs there for days at a time; corrupting
or even touching it would destroy work that cannot be cheaply recreated.

Nothing downstream of this module is permitted to read the source tree. The
exporter copies what it needs into CacheLab's own ``data/raw_export/``
directory, and every later stage -- ingestion, validation, the dashboard --
reads only from that copy. If the source disappeared tomorrow, CacheLab would
still build and still produce identical results.

Three mechanical guarantees back that policy up:

1. Source files are opened read-only, and only ever with ``read``. The module
   contains no code path that writes, moves, deletes or locks anything under
   the source root.
2. :func:`_assert_disjoint` refuses to run at all if the export directory is
   inside the source tree, so a mis-set path cannot cause a write-back.
3. Every exported file is recorded in a manifest with its SHA-256, size and
   modification time, so the copy's provenance is provable and a re-export can
   skip files that have not changed.

Runs that are still being written by a live simulation are detected and skipped
rather than half-copied.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

# Default location of the (separate, read-only) gem5 research project.
# Override with the CACHELAB_GEM5_SOURCE environment variable.
DEFAULT_SOURCE = Path("/data/nishant/Nishant/Nishant/HyComp")

# Files worth copying out of a run directory. stats.txt carries the
# measurements; config.ini records the exact simulated machine, which is what
# makes a result reproducible rather than merely reported.
RUN_FILES = ("stats.txt", "config.ini")

ROI_LABEL = "REFERENCE / ROI STATS"


@dataclass(frozen=True)
class ExportedFile:
    """Provenance record for one copied file."""

    run: str
    name: str
    sha256: str
    size_bytes: int
    source_mtime: str


class UnsafeExportError(RuntimeError):
    """Raised when an export would risk writing into the source tree."""


def _assert_disjoint(source: Path, export: Path) -> None:
    """Refuse to proceed unless the export directory is outside the source."""
    source = source.resolve()
    export = export.resolve()
    if source == export or source in export.parents:
        raise UnsafeExportError(
            f"export directory {export} is inside the read-only gem5 source "
            f"tree {source}. Refusing to run: CacheLab must never write there."
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_run_finished(stats_path: Path) -> bool:
    """True if the run's ROI dump has been written and terminated.

    A simulation that is still running has a stats.txt that grows under us.
    Copying it would capture a torn, half-written dump, so those runs are
    skipped and picked up on a later export instead.

    The check reads only the tail of the file, because stats.txt is ~1 MB per
    run and there are well over a hundred of them.
    """
    if not stats_path.is_file():
        return False
    try:
        with stats_path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 4096))
            tail = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return False
    return "End Simulation Statistics" in tail


def discover_runs(source: Path) -> list[Path]:
    """Find every scheme-sweep run directory under the source tree.

    Only ``SCHEME_*`` directories are of interest. ``CKPT_*`` directories hold
    multi-gigabyte checkpoint images with no measurements in them, and are
    deliberately never copied.
    """
    runs: list[Path] = []
    for m5out in sorted(source.glob("hycomp_v01_*core/gem5/m5out")):
        for run_dir in sorted(m5out.glob("SCHEME_*")):
            if run_dir.is_dir():
                runs.append(run_dir)
    return runs


def export(
    source: Path | str | None = None,
    export_root: Path | str | None = None,
    *,
    force: bool = False,
) -> dict:
    """Copy finished gem5 run outputs into CacheLab's workspace.

    Returns a summary dict. Safe to re-run: unchanged files are skipped.
    """
    source = Path(source or os.environ.get("CACHELAB_GEM5_SOURCE") or DEFAULT_SOURCE)
    if export_root is None:
        export_root = Path(__file__).resolve().parent.parent / "data" / "raw_export"
    export_root = Path(export_root)

    if not source.is_dir():
        raise FileNotFoundError(f"gem5 source tree not found: {source}")

    _assert_disjoint(source, export_root)
    export_root.mkdir(parents=True, exist_ok=True)

    manifest_path = export_root / "manifest.json"
    previous: dict[str, dict] = {}
    if manifest_path.is_file() and not force:
        try:
            previous = {
                f"{e['run']}/{e['name']}": e
                for e in json.loads(manifest_path.read_text())["files"]
            }
        except (KeyError, ValueError):
            previous = {}

    exported: list[ExportedFile] = []
    skipped_unfinished: list[str] = []
    copied = 0
    reused = 0

    for run_dir in discover_runs(source):
        run = run_dir.name
        stats_path = run_dir / "stats.txt"

        if not _is_run_finished(stats_path):
            skipped_unfinished.append(run)
            continue

        dest_dir = export_root / run
        dest_dir.mkdir(parents=True, exist_ok=True)

        for name in RUN_FILES:
            src = run_dir / name
            if not src.is_file():
                continue

            stat = src.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
            key = f"{run}/{name}"
            prior = previous.get(key)
            dest = dest_dir / name

            # Skip files that are already exported and unchanged at source.
            if (
                prior
                and dest.is_file()
                and prior.get("source_mtime") == mtime
                and prior.get("size_bytes") == stat.st_size
            ):
                exported.append(ExportedFile(**{k: prior[k] for k in ExportedFile.__annotations__}))
                reused += 1
                continue

            # copy2 reads the source and writes the destination. The source is
            # never opened for writing.
            shutil.copy2(src, dest)
            exported.append(
                ExportedFile(
                    run=run,
                    name=name,
                    sha256=_sha256(dest),
                    size_bytes=stat.st_size,
                    source_mtime=mtime,
                )
            )
            copied += 1

    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source.resolve()),
        "export_root": str(export_root.resolve()),
        "policy": "source tree is read-only; CacheLab reads only this export",
        "runs_exported": len({e.run for e in exported}),
        "files_copied": copied,
        "files_reused": reused,
        "runs_skipped_unfinished": sorted(skipped_unfinished),
        "files": [asdict(e) for e in sorted(exported, key=lambda e: (e.run, e.name))],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    return {
        "runs_exported": manifest["runs_exported"],
        "files_copied": copied,
        "files_reused": reused,
        "runs_skipped_unfinished": len(skipped_unfinished),
        "export_root": export_root,
        "manifest": manifest_path,
    }
