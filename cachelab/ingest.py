"""Turn exported gem5 runs into a clean, typed dataset.

Reads only from CacheLab's own ``data/raw_export/`` copy -- never from the
separate gem5 research tree. See :mod:`cachelab.export` for why.

The ROI dump is the only one that matters. Each run writes two dumps: a
sampling window in which the compressor's value-frequency tables fill and every
scheme deliberately reports blocks as uncompressed, then the measured
region-of-interest with the codes frozen. Reading the sampling dump by mistake
yields compression ratios near 1.0 for every scheme -- numbers that parse
perfectly and mean nothing.
"""

from __future__ import annotations

import csv
from pathlib import Path

from cachelab import schema as S
from cachelab.schema import RunNameError, RunRecord, parse_run_name
from cachelab.statsfile import Dump, find_dump, read_dumps


def _mpki(misses: float | None, insts: float | None) -> float | None:
    """Misses per thousand instructions."""
    if misses is None or not insts:
        return None
    return misses / insts * 1000.0


def record_from_dumps(key, dumps: list[Dump], run_dir: str = "") -> RunRecord:
    """Build a :class:`RunRecord` from the dumps of one run."""
    record = RunRecord(
        num_cores=key.num_cores,
        benchmark=key.benchmark,
        scheme=key.scheme,
        run_dir=run_dir,
    )

    roi = find_dump(dumps, S.ROI_LABEL)
    if roi is None:
        return record

    record.roi_dump_present = True
    record.roi_dump_complete = roi.complete

    g = roi.get
    record.ipc = g(S.STAT_IPC)
    record.roi_cycles = g(S.STAT_CYCLES)
    record.roi_insts = g(S.STAT_INSTS)
    record.sampling_end_insts = g(S.STAT_SAMPLING_END_INSTS)

    record.l3_hits = g(S.STAT_L3_HITS)
    record.l3_misses = g(S.STAT_L3_MISSES)
    record.l3_accesses = g(S.STAT_L3_ACCESSES)
    record.l3_miss_rate = g(S.STAT_L3_MISS_RATE)
    record.l3_writebacks = g(S.STAT_L3_WRITEBACKS)
    record.l3_replacements = g(S.STAT_L3_REPLACEMENTS)
    record.l3_mpki = _mpki(record.l3_misses, record.roi_insts)

    record.compressions = g(S.STAT_COMPRESSIONS)
    record.failed_compressions = g(S.STAT_FAILED_COMPRESSIONS)
    record.decompressions = g(S.STAT_DECOMPRESSIONS)
    record.avg_compression_size_bits = g(S.STAT_AVG_COMPRESSION_SIZE_BITS)
    record.compression_ratio_per_set = g(S.STAT_COMPRESSION_RATIO)
    record.databits_ratio = g(S.STAT_DATABITS_RATIO)
    record.resident_blocks = g(S.STAT_RESIDENT_BLOCKS)
    record.occupied_sets = g(S.STAT_OCCUPIED_SETS)
    record.resident_uncompressed_bits = g(S.STAT_RESIDENT_UNCOMPRESSED_BITS)
    record.resident_compressed_bits = g(S.STAT_RESIDENT_COMPRESSED_BITS)

    record.brute_force_accuracy_pct = g(S.STAT_BF_ACCURACY)
    record.brute_force_total_decisions = g(S.STAT_BF_TOTAL_DECISIONS)
    record.brute_force_avg_size_bits = g(S.STAT_BF_AVG_SIZE_BITS)

    for method in S.SELECTION_METHODS:
        value = g(f"{S.COMPRESSOR}.selections::{method}")
        if value is not None:
            record.selections[method] = value

    return record


def load_run(run_dir: Path) -> RunRecord:
    """Parse a single exported run directory."""
    key = parse_run_name(run_dir.name)
    dumps = read_dumps(run_dir / "stats.txt")
    return record_from_dumps(key, dumps, run_dir=run_dir.name)


def default_export_root() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "raw_export"


def load_dataset(export_root: Path | str | None = None) -> list[RunRecord]:
    """Load every exported run, sorted for stable output.

    Directories that do not look like runs are skipped rather than failing the
    whole load -- the export root also holds ``manifest.json``.
    """
    root = Path(export_root or default_export_root())
    if not root.is_dir():
        raise FileNotFoundError(
            f"no export found at {root}. Run: python -m cachelab.cli export"
        )

    records: list[RunRecord] = []
    for run_dir in sorted(root.iterdir()):
        if not run_dir.is_dir() or not (run_dir / "stats.txt").is_file():
            continue
        try:
            records.append(load_run(run_dir))
        except RunNameError:
            continue

    records.sort(key=lambda r: (r.num_cores, r.benchmark, S.SCHEME_ORDER.index(r.scheme)))
    return records


def write_csv(records: list[RunRecord], path: Path | str) -> Path:
    """Write records to CSV using the canonical column order."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=S.CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_dict())
    return path
