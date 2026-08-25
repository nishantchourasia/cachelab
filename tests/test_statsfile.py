"""Tests for the gem5 stats.txt parser.

These use small synthetic fixtures rather than real 1 MB stats files, so the
suite stays fast and does not depend on the separate gem5 research tree being
present. The fixtures reproduce the exact quirks observed in the real data:
labelled dumps, ``nan`` values, ``::``-suffixed names, and files that are still
being written.
"""

from __future__ import annotations

import math

import pytest

from cachelab.statsfile import (
    BEGIN_MARKER,
    END_MARKER,
    Dump,
    find_dump,
    read_dumps,
)


def write_stats(tmp_path, body: str):
    path = tmp_path / "stats.txt"
    path.write_text(body)
    return path


def make_dump(label: str | None, stats: dict[str, str]) -> str:
    lines = []
    if label:
        lines.append(f"\n=== {label} ===")
    lines.append(BEGIN_MARKER)
    for name, value in stats.items():
        lines.append(f"{name}{' ' * 8}{value}                       # a description (Count)")
    lines.append(END_MARKER)
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Basic parsing
# --------------------------------------------------------------------------


def test_parses_single_dump(tmp_path):
    path = write_stats(tmp_path, make_dump(None, {"simInsts": "20000000"}))
    dumps = read_dumps(path)

    assert len(dumps) == 1
    assert dumps[0].index == 0
    assert dumps[0].complete is True
    assert dumps[0].stats["simInsts"] == 20000000


def test_parses_multiple_dumps_in_order(tmp_path):
    body = make_dump("WARMUP STATS", {"x": "1"}) + make_dump("REFERENCE / ROI STATS", {"x": "2"})
    dumps = read_dumps(write_stats(tmp_path, body))

    assert [d.index for d in dumps] == [0, 1]
    assert [d.label for d in dumps] == ["WARMUP STATS", "REFERENCE / ROI STATS"]
    assert [d.stats["x"] for d in dumps] == [1, 2]


def test_label_attaches_to_following_dump(tmp_path):
    """A label line precedes the dump it describes, and must not leak forward."""
    body = make_dump(None, {"x": "1"}) + make_dump("REFERENCE / ROI STATS", {"x": "2"})
    dumps = read_dumps(write_stats(tmp_path, body))

    assert dumps[0].label is None
    assert dumps[1].label == "REFERENCE / ROI STATS"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("42", 42.0),
        ("0.718431", 0.718431),
        ("-1.5", -1.5),
        ("1.2e-05", 1.2e-05),
        ("266554498", 266554498.0),
    ],
)
def test_parses_numeric_formats(tmp_path, raw, expected):
    dumps = read_dumps(write_stats(tmp_path, make_dump(None, {"stat": raw})))
    assert dumps[0].stats["stat"] == pytest.approx(expected)


def test_parses_names_with_double_colon_suffix(tmp_path):
    """gem5 uses ``::`` for per-requestor and per-method breakdowns."""
    body = make_dump(
        None,
        {
            "l3-cache.overallMisses::total": "441570",
            "compressor.selections::FP-H": "134673",
        },
    )
    dumps = read_dumps(write_stats(tmp_path, body))

    assert dumps[0].stats["l3-cache.overallMisses::total"] == 441570
    assert dumps[0].stats["compressor.selections::FP-H"] == 134673


# --------------------------------------------------------------------------
# nan handling -- gem5 emits nan for ratios over a zero denominator, e.g. the
# IPC of a CPU that was switched out and never ran.
# --------------------------------------------------------------------------


def test_nan_is_preserved_in_stats_but_hidden_by_get(tmp_path):
    body = make_dump(None, {"switched_out.core.ipc": "nan", "real.core.ipc": "0.718431"})
    dump = read_dumps(write_stats(tmp_path, body))[0]

    assert math.isnan(dump.stats["switched_out.core.ipc"])
    # get() treats nan as absent, so it cannot silently poison later arithmetic.
    assert dump.get("switched_out.core.ipc") is None
    assert dump.get("switched_out.core.ipc", default=0.0) == 0.0
    assert dump.get("real.core.ipc") == pytest.approx(0.718431)


def test_get_returns_default_for_missing_stat(tmp_path):
    dump = read_dumps(write_stats(tmp_path, make_dump(None, {"x": "1"})))[0]
    assert dump.get("does.not.exist") is None
    assert dump.get("does.not.exist", default=-1) == -1


# --------------------------------------------------------------------------
# Robustness: the dataset is parsed while a multi-day sweep is still running.
# --------------------------------------------------------------------------


def test_unterminated_dump_is_returned_but_flagged_incomplete(tmp_path):
    """A running simulation leaves the final dump unterminated."""
    body = make_dump("WARMUP STATS", {"x": "1"})
    body += f"\n=== REFERENCE / ROI STATS ===\n{BEGIN_MARKER}\npartial.stat 7\n"
    dumps = read_dumps(write_stats(tmp_path, body))

    assert len(dumps) == 2
    assert dumps[0].complete is True
    assert dumps[1].complete is False
    assert dumps[1].stats["partial.stat"] == 7


def test_empty_file_yields_no_dumps(tmp_path):
    assert read_dumps(write_stats(tmp_path, "")) == []


def test_non_stat_lines_are_ignored(tmp_path):
    """Simulator warnings are interleaved with statistics in real files."""
    body = (
        f"{BEGIN_MARKER}\n"
        "build/X86/arch/x86/generated/exec-ns.cc.inc:27: warn: instruction unimplemented\n"
        "real.stat 5\n"
        f"{END_MARKER}\n"
    )
    dump = read_dumps(write_stats(tmp_path, body))[0]

    assert dump.stats == {"real.stat": 5}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def test_find_dump_returns_last_match(tmp_path):
    body = (
        make_dump("REFERENCE / ROI STATS", {"x": "1"})
        + make_dump("REFERENCE / ROI STATS", {"x": "2"})
    )
    dumps = read_dumps(write_stats(tmp_path, body))

    assert find_dump(dumps, "REFERENCE / ROI STATS").stats["x"] == 2
    assert find_dump(dumps, "NO SUCH LABEL") is None


def test_find_matches_by_regex(tmp_path):
    body = make_dump(
        None,
        {
            "board.processor.switch0.core.ipc": "0.71",
            "board.processor.switch1.core.ipc": "0.26",
            "board.processor.start0.core.ipc": "nan",
        },
    )
    dump = read_dumps(write_stats(tmp_path, body))[0]

    matches = dump.find(r"switch\d+\.core\.ipc$")
    assert set(matches) == {
        "board.processor.switch0.core.ipc",
        "board.processor.switch1.core.ipc",
    }


def test_dump_len_counts_stats():
    assert len(Dump(index=0, stats={"a": 1, "b": 2})) == 2
