"""Generate human-readable reports from the validated dataset.

Two audiences are served deliberately differently. The results tables answer
"what did the schemes do?"; the validity report answers "which runs were you
allowed to ask that about, and what happened to the rest?". Keeping the second
question visible is the point -- a results table that silently omits 10 of 82
runs is a misleading table, however correct its arithmetic.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from cachelab.schema import BASELINE_SCHEME, SCHEME_ORDER, RunRecord
from cachelab.validate import FLAG_DESCRIPTIONS, ValidationReport


def _fmt(value: float | None, places: int = 3) -> str:
    if value is None:
        return "—"
    return f"{value:.{places}f}"


def _fmt_count(value: float | None) -> str:
    """Whole-number counts, always thousands-separated."""
    if value is None:
        return "—"
    return f"{value:,.0f}"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def validity_report(records: list[RunRecord], report: ValidationReport) -> str:
    """Markdown report on which runs are usable and why the rest are not."""
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    out: list[str] = [
        "# Data Validity Report",
        "",
        "Which simulated runs CacheLab considers usable, and exactly why each",
        "excluded run was excluded.",
        "",
        "This report exists because a gem5 job that exits 0 has not necessarily",
        "measured anything meaningful. The sweep ledger counts jobs that did not",
        "crash. Validity is a separate question, decided by the rules in",
        "`cachelab/validate.py` and re-checked every time the dataset is rebuilt.",
        "",
        f"Generated: {generated}",
        "",
        "## Summary",
        "",
        _table(
            ["Measure", "Value"],
            [
                ["Runs ingested", str(report.total)],
                ["Valid", f"{report.valid} ({report.valid_fraction:.1%})"],
                ["Excluded", str(report.invalid)],
                [
                    "Target ROI length",
                    f"{report.expected_roi_insts:,.0f} instructions"
                    if report.expected_roi_insts
                    else "—",
                ],
            ],
        ),
        "",
        "All measurements are **Simulated** — produced by gem5, a model of a",
        "machine, not by silicon.",
        "",
    ]

    if report.flag_counts:
        out += [
            "## Why runs were excluded",
            "",
            _table(
                ["Reason", "Runs", "What it means"],
                [
                    [f"`{flag}`", str(count), FLAG_DESCRIPTIONS.get(flag, "—")]
                    for flag, count in report.flag_counts.most_common()
                ],
            ),
            "",
        ]

    if report.cells_excluded:
        out += [
            "## Groups excluded entirely",
            "",
            "A (cores, benchmark) group with no usable runs cannot contribute to",
            "any scheme comparison.",
            "",
            _table(
                ["Cores", "Benchmark", "Reasons"],
                [
                    [str(c), b, ", ".join(f"`{r}`" for r in reasons.split(";"))]
                    for c, b, reasons in report.cells_excluded
                ],
            ),
            "",
        ]

    if report.invalid_runs:
        out += [
            "## Excluded runs",
            "",
            _table(
                ["Run", "Flags"],
                [
                    [f"`{name}`", ", ".join(f"`{f}`" for f in flags)]
                    for name, flags in sorted(report.invalid_runs)
                ],
            ),
            "",
        ]

    out += [
        "## Coverage of valid data",
        "",
        _table(
            ["Cores", "Benchmark", "Valid schemes", "Of"],
            _coverage_rows(records),
        ),
        "",
    ]

    return "\n".join(out) + "\n"


def _coverage_rows(records: list[RunRecord]) -> list[list[str]]:
    cells: dict[tuple[int, str], list[RunRecord]] = defaultdict(list)
    for record in records:
        cells[record.key.cell].append(record)

    rows = []
    for (cores, benchmark), members in sorted(cells.items()):
        valid = sum(1 for m in members if m.valid)
        rows.append([str(cores), benchmark, str(valid), str(len(members))])
    return rows


def results_tables(records: list[RunRecord]) -> str:
    """Markdown tables of the validated measurements, grouped by configuration."""
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    usable = [r for r in records if r.valid]
    cells: dict[tuple[int, str], list[RunRecord]] = defaultdict(list)
    for record in usable:
        cells[record.key.cell].append(record)

    out: list[str] = [
        "# Results",
        "",
        "Every number below is **Simulated**: measured from a gem5 run, over a",
        "250 million instruction region of interest, on the validated subset of",
        "the dataset. Excluded runs are listed in `VALIDITY.md` and appear",
        "nowhere in these tables.",
        "",
        f"Generated: {generated}",
        "",
        "**Reading the columns**",
        "",
        "- **IPC** — instructions per cycle. Higher is faster.",
        "- **MPKI** — last-level-cache misses per thousand instructions. Lower is better.",
        "- **Comp. ratio** — effective cache capacity divided by physical capacity,",
        "  averaged over occupied sets. 1.0 means compression bought nothing.",
        "  The design caps this at 4.0 because a set holds at most 4 tags.",
        "- **Δ IPC** — change against the uncompressed Baseline in the same group.",
        "",
    ]

    if not usable:
        out += ["_No validated runs available yet._", ""]
        return "\n".join(out)

    for (cores, benchmark), members in sorted(cells.items()):
        members.sort(key=lambda r: SCHEME_ORDER.index(r.scheme))
        baseline = next((m for m in members if m.scheme == BASELINE_SCHEME), None)

        rows = []
        for member in members:
            delta = "—"
            if baseline and baseline.ipc and member.ipc is not None:
                change = (member.ipc - baseline.ipc) / baseline.ipc * 100
                delta = f"{change:+.2f}%"
            rows.append(
                [
                    member.scheme,
                    _fmt(member.ipc, 4),
                    _fmt(member.l3_mpki, 2),
                    _fmt(member.compression_ratio_per_set),
                    _fmt(member.avg_compression_size_bits, 1),
                    delta,
                ]
            )

        out += [
            f"## {benchmark} — {cores} cores",
            "",
            _table(
                ["Scheme", "IPC", "MPKI", "Comp. ratio", "Avg comp. bits", "Δ IPC"],
                rows,
            ),
            "",
        ]

    accuracy = [
        r for r in usable if r.scheme == "HyComp" and r.brute_force_accuracy_pct is not None
    ]
    if accuracy:
        out += [
            "## HyComp predictor accuracy",
            "",
            "How often the adaptive scheme chose the same compressor that an",
            "exhaustive search of all candidates would have chosen. Measured only",
            "on runs launched with a brute-force reference.",
            "",
            _table(
                ["Cores", "Benchmark", "Accuracy", "Decisions"],
                [
                    [
                        str(r.num_cores),
                        r.benchmark,
                        f"{r.brute_force_accuracy_pct:.2f}%",
                        _fmt_count(r.brute_force_total_decisions),
                    ]
                    for r in sorted(accuracy, key=lambda r: (r.num_cores, r.benchmark))
                ],
            ),
            "",
        ]

    return "\n".join(out) + "\n"
