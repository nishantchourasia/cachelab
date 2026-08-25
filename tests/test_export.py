"""Tests for the safe export of gem5 results.

The gem5 research tree is a separate, live project. These tests exist to prove
mechanically that CacheLab cannot damage it: that the exporter refuses unsafe
destinations, never modifies the source, and skips runs that a simulator is
still writing.

Every test builds its own fake source tree in a temporary directory. Nothing
here touches the real research data.
"""

from __future__ import annotations

import json

import pytest

from cachelab.export import (
    ROI_LABEL,
    UnsafeExportError,
    discover_runs,
    export,
)
from cachelab.statsfile import BEGIN_MARKER, END_MARKER


def make_source(tmp_path, runs: dict[str, bool], cores: int = 2):
    """Build a fake gem5 source tree.

    ``runs`` maps a run name to whether the run has finished (i.e. whether its
    final dump is terminated).
    """
    m5out = tmp_path / "source" / f"hycomp_v01_{cores}core" / "gem5" / "m5out"
    m5out.mkdir(parents=True)

    # A checkpoint directory, which must never be exported.
    (m5out / f"CKPT_{cores}core_502.gcc_r").mkdir()

    for name, finished in runs.items():
        run_dir = m5out / name
        run_dir.mkdir()
        body = f"=== {ROI_LABEL} ===\n{BEGIN_MARKER}\nboard.stat 42\n"
        if finished:
            body += f"{END_MARKER}\n"
        (run_dir / "stats.txt").write_text(body)
        (run_dir / "config.ini").write_text("[root]\ntype=Root\n")
        # A large artefact that is deliberately not in RUN_FILES.
        (run_dir / "config.json").write_text("{}")

    return tmp_path / "source"


# --------------------------------------------------------------------------
# Safety: the source tree must never be written to.
# --------------------------------------------------------------------------


def test_refuses_export_into_the_source_tree(tmp_path):
    """A mis-set export path must abort rather than write into the research tree."""
    source = make_source(tmp_path, {"SCHEME_2core_502.gcc_r_none": True})

    with pytest.raises(UnsafeExportError, match="Refusing to run"):
        export(source=source, export_root=source / "exported_here")


def test_refuses_export_directly_onto_the_source_root(tmp_path):
    source = make_source(tmp_path, {"SCHEME_2core_502.gcc_r_none": True})

    with pytest.raises(UnsafeExportError):
        export(source=source, export_root=source)


def test_source_tree_is_byte_identical_after_export(tmp_path):
    """The strongest guarantee: exporting changes nothing at the source."""
    source = make_source(
        tmp_path,
        {"SCHEME_2core_502.gcc_r_none": True, "SCHEME_2core_505.mcf_r_bdi": True},
    )

    before = {
        p.relative_to(source): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in sorted(source.rglob("*"))
        if p.is_file()
    }

    export(source=source, export_root=tmp_path / "export")

    after = {
        p.relative_to(source): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in sorted(source.rglob("*"))
        if p.is_file()
    }

    assert before == after, "export modified the read-only gem5 source tree"


def test_export_creates_no_new_files_in_source(tmp_path):
    source = make_source(tmp_path, {"SCHEME_2core_502.gcc_r_none": True})
    before = {p.relative_to(source) for p in source.rglob("*")}

    export(source=source, export_root=tmp_path / "export")

    after = {p.relative_to(source) for p in source.rglob("*")}
    assert before == after


def test_missing_source_raises_clearly(tmp_path):
    with pytest.raises(FileNotFoundError, match="gem5 source tree not found"):
        export(source=tmp_path / "nope", export_root=tmp_path / "export")


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------


def test_discovers_scheme_runs_and_ignores_checkpoints(tmp_path):
    source = make_source(
        tmp_path,
        {"SCHEME_2core_502.gcc_r_none": True, "SCHEME_2core_502.gcc_r_bdi": True},
    )

    names = [p.name for p in discover_runs(source)]

    assert sorted(names) == ["SCHEME_2core_502.gcc_r_bdi", "SCHEME_2core_502.gcc_r_none"]
    assert not any(n.startswith("CKPT_") for n in names), "checkpoints must never be exported"


# --------------------------------------------------------------------------
# Copying behaviour
# --------------------------------------------------------------------------


def test_exports_expected_files_only(tmp_path):
    source = make_source(tmp_path, {"SCHEME_2core_502.gcc_r_none": True})
    dest = tmp_path / "export"

    export(source=source, export_root=dest)

    run = dest / "SCHEME_2core_502.gcc_r_none"
    assert (run / "stats.txt").is_file()
    assert (run / "config.ini").is_file()
    # config.json is large and unused, so it is not copied.
    assert not (run / "config.json").exists()


def test_skips_runs_still_being_written(tmp_path):
    """A simulation in flight has an unterminated final dump."""
    source = make_source(
        tmp_path,
        {"SCHEME_2core_502.gcc_r_none": True, "SCHEME_2core_505.mcf_r_bdi": False},
    )
    dest = tmp_path / "export"

    result = export(source=source, export_root=dest)

    assert result["runs_exported"] == 1
    assert result["runs_skipped_unfinished"] == 1
    assert (dest / "SCHEME_2core_502.gcc_r_none").is_dir()
    assert not (dest / "SCHEME_2core_505.mcf_r_bdi").exists()


def test_unfinished_run_is_picked_up_once_it_completes(tmp_path):
    source = make_source(tmp_path, {"SCHEME_2core_505.mcf_r_bdi": False})
    dest = tmp_path / "export"

    assert export(source=source, export_root=dest)["runs_exported"] == 0

    # The simulation finishes and terminates its dump.
    stats = source / "hycomp_v01_2core/gem5/m5out/SCHEME_2core_505.mcf_r_bdi/stats.txt"
    stats.write_text(stats.read_text() + f"{END_MARKER}\n")

    assert export(source=source, export_root=dest)["runs_exported"] == 1


# --------------------------------------------------------------------------
# Manifest and provenance
# --------------------------------------------------------------------------


def test_manifest_records_provenance(tmp_path):
    source = make_source(tmp_path, {"SCHEME_2core_502.gcc_r_none": True})
    dest = tmp_path / "export"

    export(source=source, export_root=dest)
    manifest = json.loads((dest / "manifest.json").read_text())

    assert manifest["source"] == str(source.resolve())
    assert manifest["runs_exported"] == 1
    entry = next(f for f in manifest["files"] if f["name"] == "stats.txt")
    assert len(entry["sha256"]) == 64
    assert entry["size_bytes"] > 0
    assert entry["source_mtime"].startswith("20")


def test_reexport_is_incremental(tmp_path):
    source = make_source(tmp_path, {"SCHEME_2core_502.gcc_r_none": True})
    dest = tmp_path / "export"

    first = export(source=source, export_root=dest)
    second = export(source=source, export_root=dest)

    assert first["files_copied"] == 2 and first["files_reused"] == 0
    assert second["files_copied"] == 0 and second["files_reused"] == 2


def test_changed_source_file_is_recopied(tmp_path):
    source = make_source(tmp_path, {"SCHEME_2core_502.gcc_r_none": True})
    dest = tmp_path / "export"
    export(source=source, export_root=dest)

    stats = source / "hycomp_v01_2core/gem5/m5out/SCHEME_2core_502.gcc_r_none/stats.txt"
    stats.write_text(f"=== {ROI_LABEL} ===\n{BEGIN_MARKER}\nboard.stat 99\n{END_MARKER}\n")

    result = export(source=source, export_root=dest)

    assert result["files_copied"] >= 1
    assert "99" in (dest / "SCHEME_2core_502.gcc_r_none" / "stats.txt").read_text()


def test_force_recopies_everything(tmp_path):
    source = make_source(tmp_path, {"SCHEME_2core_502.gcc_r_none": True})
    dest = tmp_path / "export"
    export(source=source, export_root=dest)

    result = export(source=source, export_root=dest, force=True)

    assert result["files_copied"] == 2
    assert result["files_reused"] == 0
