"""Decide which simulated runs are scientifically usable.

A gem5 job can exit 0, produce a well-formed stats file, and still be
meaningless. The sweep ledger records 82 jobs as ``OK``; that only means the
process did not crash. Validity is a separate question, and this module answers
it explicitly rather than letting bad rows flow silently into a chart.

The rules below were derived by inspecting the real dataset, not invented. The
most consequential one, :data:`ROI_EQUALS_SAMPLING`, catches a real defect: in
the 2-core ``505.mcf_r`` cell every scheme reports exactly 20,000,000
instructions -- the size of the *sampling* window -- instead of the intended
250,000,000 ROI. Those rows describe the phase in which compression is
deliberately not applied, so their compression ratios (1.0001 for ZCA, 1.0004
for BDI) are artefacts of the wrong measurement window rather than findings.

Nothing is deleted. Invalid runs keep their flags and are reported, because
"we ran it and threw it out, here is why" is a stronger claim than a dataset
that is quietly smaller than the job count.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from cachelab.schema import BASELINE_SCHEME, RunRecord

# --------------------------------------------------------------------------
# Flags. Each is a reason a run cannot be trusted, with a plain explanation.
# --------------------------------------------------------------------------

ROI_DUMP_MISSING = "ROI_DUMP_MISSING"
ROI_DUMP_INCOMPLETE = "ROI_DUMP_INCOMPLETE"
NO_IPC = "NO_IPC"
ROI_BELOW_TARGET = "ROI_BELOW_TARGET"
ROI_EQUALS_SAMPLING = "ROI_EQUALS_SAMPLING"
CELL_WINDOW_MISMATCH = "CELL_WINDOW_MISMATCH"
CELL_MISSING_BASELINE = "CELL_MISSING_BASELINE"
COMPRESSION_RATIO_IMPLAUSIBLE = "COMPRESSION_RATIO_IMPLAUSIBLE"

FLAG_DESCRIPTIONS: dict[str, str] = {
    ROI_DUMP_MISSING: (
        "The run produced no dump labelled 'REFERENCE / ROI STATS', so there is "
        "no measured region of interest to read."
    ),
    ROI_DUMP_INCOMPLETE: (
        "The ROI dump has no terminating marker. The simulation was still "
        "running or was killed part-way through writing it."
    ),
    NO_IPC: (
        "No IPC was recorded for core 0. Usually means the detailed CPU was "
        "never switched in, so nothing was actually measured."
    ),
    ROI_BELOW_TARGET: (
        "The ROI committed fewer instructions than the experiment targets. A "
        "shorter window covers a different part of the program, so the result "
        "is not comparable with full-length runs."
    ),
    ROI_EQUALS_SAMPLING: (
        "The ROI instruction count exactly equals the sampling-window size, "
        "indicating the ROI dump captured the sampling phase instead. During "
        "sampling, compression is deliberately not applied, so any compression "
        "ratio from this run is an artefact."
    ),
    CELL_WINDOW_MISMATCH: (
        "Schemes within this (cores, benchmark) group measured different "
        "instruction windows. Comparing them would attribute a difference in "
        "program phase to a difference in compression scheme."
    ),
    CELL_MISSING_BASELINE: (
        "This group has no valid uncompressed baseline, so no speedup or "
        "improvement can be computed for it."
    ),
    COMPRESSION_RATIO_IMPLAUSIBLE: (
        "The per-set compression ratio falls outside the physically meaningful "
        "range. The design permits at most 4 tags per set, so the ratio cannot "
        "exceed 4.0, and it cannot be below 1.0 because a set always holds at "
        "least as much as its uncompressed capacity."
    ),
}

# The design caps compression ratio at 4x because tags are limited to 4 per set
# (see the gem5 stat description, which cites MICRO-48 Section 5.3).
MAX_COMPRESSION_RATIO = 4.0
MIN_COMPRESSION_RATIO = 1.0

# Runs are allowed to overshoot an instruction target slightly: gem5 stops at
# the end of the instruction that crosses the threshold.
ROI_TOLERANCE = 0.001

# How closely schemes within one (cores, benchmark) group must agree on the
# measurement window before they can be compared.
#
# The real dataset spreads by at most 6 instructions across 250,000,000 -- a
# relative difference of 2.4e-8, caused by gem5 completing the instruction that
# crosses the threshold. That is noise. A genuine mismatch looks nothing like
# it: the 2-core 505.mcf_r cell measured 20,000,000 against a 250,000,000
# target, a relative difference of 0.92. Anything above 0.01% is treated as a
# real disagreement.
CELL_WINDOW_TOLERANCE = 1e-4


@dataclass
class ValidationReport:
    """Outcome of validating a dataset."""

    total: int = 0
    valid: int = 0
    invalid: int = 0
    expected_roi_insts: float | None = None
    flag_counts: Counter = field(default_factory=Counter)
    invalid_runs: list[tuple[str, list[str]]] = field(default_factory=list)
    cells_excluded: list[tuple[int, str, str]] = field(default_factory=list)

    @property
    def valid_fraction(self) -> float:
        return self.valid / self.total if self.total else 0.0


def infer_expected_roi(records: list[RunRecord]) -> float | None:
    """Infer the intended ROI length as the most common value in the dataset.

    Inferring beats hard-coding 250,000,000: if the experiment is re-run with a
    different window, validation follows the data instead of rejecting all of it.
    """
    counts = Counter(
        round(r.roi_insts) for r in records if r.roi_insts and r.roi_insts > 0
    )
    if not counts:
        return None
    return float(counts.most_common(1)[0][0])


def _check_run(record: RunRecord, expected_roi: float | None) -> list[str]:
    flags: list[str] = []

    if not record.roi_dump_present:
        flags.append(ROI_DUMP_MISSING)
        return flags

    if not record.roi_dump_complete:
        flags.append(ROI_DUMP_INCOMPLETE)

    if record.ipc is None or record.ipc <= 0:
        flags.append(NO_IPC)

    insts = record.roi_insts
    sampling = record.sampling_end_insts

    if insts is not None and sampling and abs(insts - sampling) < 1.0:
        flags.append(ROI_EQUALS_SAMPLING)

    if expected_roi and insts is not None:
        if insts < expected_roi * (1.0 - ROI_TOLERANCE):
            flags.append(ROI_BELOW_TARGET)

    ratio = record.compression_ratio_per_set
    if ratio is not None and not (
        MIN_COMPRESSION_RATIO - 1e-6 <= ratio <= MAX_COMPRESSION_RATIO + 1e-6
    ):
        flags.append(COMPRESSION_RATIO_IMPLAUSIBLE)

    return flags


def validate_dataset(
    records: list[RunRecord],
    *,
    expected_roi_insts: float | None = None,
    infer_roi: bool = True,
) -> ValidationReport:
    """Annotate each record with validity flags and summarise the outcome.

    Records are modified in place: ``valid`` and ``validity_flags`` are set.
    """
    report = ValidationReport(total=len(records))

    expected_roi = expected_roi_insts
    if expected_roi is None and infer_roi:
        expected_roi = infer_expected_roi(records)
    report.expected_roi_insts = expected_roi

    # Pass 1: per-run checks. These depend only on the run itself.
    run_flags: dict[int, list[str]] = {}
    for record in records:
        run_flags[id(record)] = _check_run(record, expected_roi)

    # Pass 2: cell-level checks. Schemes are only meaningful relative to each
    # other within the same (cores, benchmark) group.
    #
    # Both checks below deliberately consider only *run-level* flags when
    # deciding which members count. Judging them against the combined flag list
    # would let one cell-level failure cascade into the other -- a group with a
    # window mismatch would mark its own baseline unusable, which would then
    # raise CELL_MISSING_BASELINE, and every group would fail for both reasons.
    cells: dict[tuple[int, str], list[RunRecord]] = defaultdict(list)
    for record in records:
        cells[record.key.cell].append(record)

    cell_flags: dict[int, list[str]] = {id(r): [] for r in records}

    for members in cells.values():
        sound = [m for m in members if not run_flags[id(m)] and m.roi_insts]

        windows = [m.roi_insts for m in sound]
        if windows:
            low, high = min(windows), max(windows)
            if high > 0 and (high - low) / high > CELL_WINDOW_TOLERANCE:
                for member in members:
                    cell_flags[id(member)].append(CELL_WINDOW_MISMATCH)

        if not any(m.scheme == BASELINE_SCHEME for m in sound):
            for member in members:
                cell_flags[id(member)].append(CELL_MISSING_BASELINE)

    for record in records:
        record.validity_flags = run_flags[id(record)] + cell_flags[id(record)]

    # Finalise.
    for record in records:
        record.valid = not record.validity_flags
        if record.valid:
            report.valid += 1
        else:
            report.invalid += 1
            report.invalid_runs.append((record.run_dir or str(record.key), list(record.validity_flags)))
            report.flag_counts.update(record.validity_flags)

    excluded: set[tuple[int, str, str]] = set()
    for cell, members in cells.items():
        if all(not m.valid for m in members):
            reasons = sorted({f for m in members for f in m.validity_flags})
            excluded.add((cell[0], cell[1], ";".join(reasons)))
    report.cells_excluded = sorted(excluded)

    return report


def valid_records(records: list[RunRecord]) -> list[RunRecord]:
    """Return only the runs that passed validation."""
    return [r for r in records if r.valid]
