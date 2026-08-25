"""Tests for run validity rules.

These encode the judgements CacheLab makes about which simulated runs may be
compared. Each test states the scientific reason, not just the expected value,
because these rules decide what the published results are allowed to say.
"""

from __future__ import annotations

import pytest

from cachelab.schema import RunRecord
from cachelab.validate import (
    CELL_MISSING_BASELINE,
    CELL_WINDOW_MISMATCH,
    COMPRESSION_RATIO_IMPLAUSIBLE,
    FLAG_DESCRIPTIONS,
    NO_IPC,
    ROI_BELOW_TARGET,
    ROI_DUMP_INCOMPLETE,
    ROI_DUMP_MISSING,
    ROI_EQUALS_SAMPLING,
    infer_expected_roi,
    valid_records,
    validate_dataset,
)

TARGET = 250_000_000
SAMPLING = 20_000_000


def run(
    scheme="Baseline",
    *,
    cores=2,
    benchmark="502.gcc_r",
    insts=TARGET,
    ipc=2.0,
    sampling=SAMPLING,
    ratio=1.5,
    present=True,
    complete=True,
) -> RunRecord:
    return RunRecord(
        num_cores=cores,
        benchmark=benchmark,
        scheme=scheme,
        run_dir=f"SCHEME_{cores}core_{benchmark}_{scheme}",
        roi_insts=insts,
        roi_cycles=1e8,
        ipc=ipc,
        sampling_end_insts=sampling,
        compression_ratio_per_set=ratio,
        roi_dump_present=present,
        roi_dump_complete=complete,
    )


def full_cell(**overrides) -> list[RunRecord]:
    """A complete, healthy (cores, benchmark) group of eight schemes."""
    schemes = ["Baseline", "ZCA", "BDI", "SC2", "FP-H", "C-PACK+Z", "Brute-F", "HyComp"]
    return [run(s, **overrides) for s in schemes]


# --------------------------------------------------------------------------
# Healthy data must pass
# --------------------------------------------------------------------------


def test_healthy_cell_is_fully_valid():
    records = full_cell()
    report = validate_dataset(records)

    assert report.valid == 8
    assert report.invalid == 0
    assert all(r.valid for r in records)


def test_tiny_instruction_overshoot_is_not_a_mismatch():
    """gem5 stops at the end of the instruction crossing the threshold.

    A spread of a few instructions in 250 million is measurement granularity,
    not a difference in what was measured. The real dataset spreads by up to 6.
    """
    records = full_cell()
    for offset, record in enumerate(records):
        record.roi_insts = TARGET + offset  # 250000000 .. 250000007

    report = validate_dataset(records)

    assert report.valid == 8
    assert not any(CELL_WINDOW_MISMATCH in r.validity_flags for r in records)


# --------------------------------------------------------------------------
# Per-run rules
# --------------------------------------------------------------------------


def test_missing_roi_dump_is_invalid():
    records = full_cell()
    records[3].roi_dump_present = False

    validate_dataset(records)

    assert ROI_DUMP_MISSING in records[3].validity_flags
    assert not records[3].valid


def test_incomplete_roi_dump_is_invalid():
    """A run still being written has an unterminated dump."""
    records = full_cell()
    records[2].roi_dump_complete = False

    validate_dataset(records)

    assert ROI_DUMP_INCOMPLETE in records[2].validity_flags


def test_missing_ipc_is_invalid():
    records = full_cell()
    records[1].ipc = None

    validate_dataset(records)

    assert NO_IPC in records[1].validity_flags


def test_short_roi_is_invalid():
    """A shorter window covers a different program phase."""
    records = full_cell()
    records[5].roi_insts = 100_000_000

    validate_dataset(records)

    assert ROI_BELOW_TARGET in records[5].validity_flags


def test_roi_equal_to_sampling_window_is_invalid():
    """The defect actually present in the 2-core 505.mcf_r cell.

    When the ROI instruction count equals the sampling-window size, the ROI
    dump captured the sampling phase -- during which compression is not applied
    -- so its compression ratios are artefacts.

    The target is passed explicitly: with a one-run dataset, inference would
    take that single short window to be the intended one.
    """
    record = run(insts=SAMPLING, sampling=SAMPLING)

    validate_dataset([record], expected_roi_insts=TARGET)

    assert ROI_EQUALS_SAMPLING in record.validity_flags
    assert ROI_BELOW_TARGET in record.validity_flags


@pytest.mark.parametrize("ratio", [0.5, 0.999, 4.5, 12.0])
def test_impossible_compression_ratio_is_invalid(ratio):
    """The design caps the ratio at 4.0 (max 4 tags per set) and floors it at 1.0."""
    records = full_cell()
    records[4].compression_ratio_per_set = ratio

    validate_dataset(records)

    assert COMPRESSION_RATIO_IMPLAUSIBLE in records[4].validity_flags


@pytest.mark.parametrize("ratio", [1.0, 2.07, 4.0])
def test_plausible_compression_ratios_pass(ratio):
    records = full_cell()
    records[4].compression_ratio_per_set = ratio

    validate_dataset(records)

    assert COMPRESSION_RATIO_IMPLAUSIBLE not in records[4].validity_flags


def test_absent_compression_ratio_is_not_penalised():
    """The uncompressed baseline has no ratio, which is expected, not a fault."""
    record = run("Baseline", ratio=None)

    validate_dataset([record])

    assert record.valid


# --------------------------------------------------------------------------
# Cell-level rules
# --------------------------------------------------------------------------


def test_a_single_short_run_is_dropped_without_condemning_its_group():
    """One bad run is excluded on its own merit; the rest stay comparable.

    Discarding the other seven would throw away sound measurements to punish a
    neighbour.
    """
    records = full_cell()
    records[1].roi_insts = TARGET // 2

    report = validate_dataset(records)

    assert ROI_BELOW_TARGET in records[1].validity_flags
    assert report.valid == 7
    assert not any(CELL_WINDOW_MISMATCH in r.validity_flags for r in records)


def test_genuinely_different_windows_invalidate_the_whole_cell():
    """Comparing schemes measured over different windows would attribute a
    phase difference to the compression scheme.

    The odd run here is *longer* than the target, so it carries no run-level
    fault of its own -- yet the comparison it takes part in is still unsound,
    which is exactly what this cell-level rule exists to catch.
    """
    records = full_cell()
    records[1].roi_insts = TARGET * 2

    validate_dataset(records)

    # Every member is flagged: the comparison itself is unsound.
    assert all(CELL_WINDOW_MISMATCH in r.validity_flags for r in records)


def test_cell_without_baseline_cannot_be_compared():
    records = [r for r in full_cell() if r.scheme != "Baseline"]

    report = validate_dataset(records)

    assert all(CELL_MISSING_BASELINE in r.validity_flags for r in records)
    assert report.valid == 0


def test_cell_with_broken_baseline_cannot_be_compared():
    """A baseline that is itself invalid is no baseline at all."""
    records = full_cell()
    records[0].ipc = None  # the Baseline run

    validate_dataset(records)

    assert all(CELL_MISSING_BASELINE in r.validity_flags for r in records)


def test_cell_failures_do_not_cascade_into_each_other():
    """A window mismatch must not also manufacture a missing-baseline error.

    Regression test: judging cell membership by combined flags made one
    cell-level failure trigger the other, and every group failed for both
    reasons.
    """
    records = full_cell()
    records[1].roi_insts = TARGET * 2

    validate_dataset(records)

    assert all(CELL_WINDOW_MISMATCH in r.validity_flags for r in records)
    assert not any(CELL_MISSING_BASELINE in r.validity_flags for r in records)


def test_cells_are_independent():
    """A broken group must not invalidate a healthy one."""
    good = full_cell(benchmark="502.gcc_r")
    bad = full_cell(benchmark="505.mcf_r", insts=SAMPLING)

    report = validate_dataset(good + bad)

    assert report.valid == 8
    assert all(r.valid for r in good)
    assert not any(r.valid for r in bad)


# --------------------------------------------------------------------------
# ROI inference and reporting
# --------------------------------------------------------------------------


def test_expected_roi_is_inferred_from_the_majority():
    """Inferring beats hard-coding, so a re-run with a different window still
    validates instead of rejecting everything."""
    records = full_cell() + [run("ZCA", benchmark="505.mcf_r", insts=SAMPLING)]

    assert infer_expected_roi(records) == TARGET


def test_explicit_roi_target_overrides_inference():
    records = full_cell(insts=100_000_000)

    report = validate_dataset(records, expected_roi_insts=TARGET)

    assert report.expected_roi_insts == TARGET
    assert all(ROI_BELOW_TARGET in r.validity_flags for r in records)


def test_infer_returns_none_for_empty_dataset():
    assert infer_expected_roi([]) is None


def test_report_counts_and_lists_failures():
    records = full_cell() + full_cell(benchmark="505.mcf_r", insts=SAMPLING)

    report = validate_dataset(records)

    assert report.total == 16
    assert report.valid == 8
    assert report.invalid == 8
    assert report.valid_fraction == pytest.approx(0.5)
    assert report.flag_counts[ROI_BELOW_TARGET] == 8
    assert len(report.invalid_runs) == 8
    assert [cell[1] for cell in report.cells_excluded] == ["505.mcf_r"]


def test_valid_records_filters():
    records = full_cell() + full_cell(benchmark="505.mcf_r", insts=SAMPLING)

    validate_dataset(records)

    assert len(valid_records(records)) == 8


def test_every_flag_has_a_plain_english_description():
    """The data-validity page explains each exclusion to a reader."""
    flags = {
        ROI_DUMP_MISSING,
        ROI_DUMP_INCOMPLETE,
        NO_IPC,
        ROI_BELOW_TARGET,
        ROI_EQUALS_SAMPLING,
        CELL_WINDOW_MISMATCH,
        CELL_MISSING_BASELINE,
        COMPRESSION_RATIO_IMPLAUSIBLE,
    }

    assert flags <= set(FLAG_DESCRIPTIONS)
    assert all(len(FLAG_DESCRIPTIONS[f]) > 40 for f in flags)
