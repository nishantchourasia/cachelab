"""Canonical schema: what a run is, and which gem5 statistics define it.

Every statistic name here was verified against real exported runs rather than
taken from documentation. Where a name is subtle, the reason is recorded --
those notes are the difference between a number that means something and a
number that merely parses.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

# --------------------------------------------------------------------------
# Statistic names, verified against exported runs on 2026-08-25
# --------------------------------------------------------------------------

L3 = "board.cache_hierarchy.l3-cache"
COMPRESSOR = f"{L3}.compressor"
TAGS = f"{L3}.tags"

# The benchmark under study always runs on core 0. gem5 creates two CPU objects
# per core: "start<N>" (fast-forward) and "switch<N>" (the detailed O3 core that
# is switched in for measurement). Only the switch cores execute during the ROI
# -- the start cores report nan IPC and zero cycles, which is why reading the
# wrong one silently yields nothing.
CORE0 = "board.processor.switch0.core"

STAT_IPC = f"{CORE0}.ipc"
STAT_CYCLES = f"{CORE0}.numCycles"

# Committed instructions. This is the exact integer (e.g. 250000000). An
# earlier ad-hoc analysis derived instruction count as ipc x cycles, which is
# algebraically equivalent but returns a rounded float (250000017.18) because
# IPC is itself printed rounded. Reading the counter directly avoids inventing
# precision that is not there.
STAT_INSTS = f"{CORE0}.commitStats0.numInsts"

STAT_L3_HITS = f"{L3}.overallHits::total"
STAT_L3_MISSES = f"{L3}.overallMisses::total"
STAT_L3_ACCESSES = f"{L3}.overallAccesses::total"
STAT_L3_MISS_RATE = f"{L3}.overallMissRate::total"

# Write-traffic proxies. Relevant to any endurance argument, because a
# non-volatile LLC wears out on writes rather than reads.
STAT_L3_WRITEBACKS = f"{L3}.writebacks::total"
STAT_L3_REPLACEMENTS = f"{L3}.replacements"

STAT_COMPRESSIONS = f"{COMPRESSOR}.compressions"
STAT_FAILED_COMPRESSIONS = f"{COMPRESSOR}.failedCompressions"
STAT_DECOMPRESSIONS = f"{COMPRESSOR}.decompressions"
STAT_COMPRESSION_SIZE_BITS = f"{COMPRESSOR}.compressionSizeBits"
STAT_AVG_COMPRESSION_SIZE_BITS = f"{COMPRESSOR}.avgCompressionSizeBits"
STAT_SAMPLING_END_INSTS = f"{COMPRESSOR}.samplingEndInsts"

# Custom statistics added by the HyComp work. The gem5 description strings cite
# MICRO-48 Section 5.3 for the per-set compression ratio.
STAT_COMPRESSION_RATIO = f"{TAGS}.avgPerSetCompressionRatio"
STAT_DATABITS_RATIO = f"{TAGS}.avgPerSetDataBitsRatio"
STAT_RESIDENT_BLOCKS = f"{TAGS}.residentBlocks"
STAT_OCCUPIED_SETS = f"{TAGS}.occupiedSets"
STAT_RESIDENT_UNCOMPRESSED_BITS = f"{TAGS}.residentUncompressedBits"
STAT_RESIDENT_COMPRESSED_BITS = f"{TAGS}.residentCompressedBits"

# Brute-force reference: present only when a run was launched with
# --brute-force-reference, i.e. the HyComp scheme. It records how often the
# predictor chose the same compressor an exhaustive search would have.
STAT_BF_ACCURACY = f"{COMPRESSOR}.bruteForceAccuracyPercent"
STAT_BF_TOTAL_DECISIONS = f"{COMPRESSOR}.bruteForceTotalDecisions"
STAT_BF_CORRECT = f"{COMPRESSOR}.bruteForceCorrectDecisions"
STAT_BF_INCORRECT = f"{COMPRESSOR}.bruteForceIncorrectDecisions"
STAT_BF_AVG_SIZE_BITS = f"{COMPRESSOR}.bruteForceAvgSizeBits"

SELECTION_METHODS = ("ZCA", "SC2", "BDI", "FP-H", "NONE")

ROI_LABEL = "REFERENCE / ROI STATS"

# --------------------------------------------------------------------------
# Schemes
# --------------------------------------------------------------------------

# Directory-name token -> display name. Ordered so that tables and charts read
# from no-compression through to the adaptive scheme.
SCHEMES: dict[str, str] = {
    "none": "Baseline",
    "zca": "ZCA",
    "bdi": "BDI",
    "sc2": "SC2",
    "fph": "FP-H",
    "cpack_z": "C-PACK+Z",
    "brute_f": "Brute-F",
    "hycomp": "HyComp",
}

SCHEME_ORDER = list(SCHEMES.values())

BASELINE_SCHEME = "Baseline"

# Directory names look like: SCHEME_4core_505.mcf_r_cpack_z
# The scheme token is matched last and anchored, because benchmark names
# themselves contain underscores (505.mcf_r) and would otherwise be split.
_RUN_DIR_RE = re.compile(
    r"^SCHEME_(?P<cores>\d+)core_(?P<benchmark>.+?)_(?P<scheme>"
    + "|".join(sorted(SCHEMES, key=len, reverse=True))
    + r")$"
)


class RunNameError(ValueError):
    """Raised when a run directory name cannot be interpreted."""


@dataclass(frozen=True)
class RunKey:
    """Identity of a single simulated configuration."""

    num_cores: int
    benchmark: str
    scheme: str

    @property
    def cell(self) -> tuple[int, str]:
        """The (cores, benchmark) group that schemes are compared within."""
        return (self.num_cores, self.benchmark)


def parse_run_name(name: str) -> RunKey:
    """Interpret a run directory name such as ``SCHEME_4core_505.mcf_r_cpack_z``."""
    match = _RUN_DIR_RE.match(name)
    if not match:
        raise RunNameError(f"unrecognised run directory name: {name!r}")
    return RunKey(
        num_cores=int(match.group("cores")),
        benchmark=match.group("benchmark"),
        scheme=SCHEMES[match.group("scheme")],
    )


# --------------------------------------------------------------------------
# Run record
# --------------------------------------------------------------------------


@dataclass
class RunRecord:
    """One simulated configuration and everything measured about it.

    Optional fields are ``None`` when the statistic was absent, never 0.0 --
    a missing measurement and a measured zero are different claims.
    """

    num_cores: int
    benchmark: str
    scheme: str

    # Provenance
    run_dir: str = ""

    # Measurement window
    roi_insts: float | None = None
    roi_cycles: float | None = None
    sampling_end_insts: float | None = None
    roi_dump_present: bool = False
    roi_dump_complete: bool = False

    # Performance
    ipc: float | None = None

    # Cache behaviour
    l3_hits: float | None = None
    l3_misses: float | None = None
    l3_accesses: float | None = None
    l3_miss_rate: float | None = None
    l3_mpki: float | None = None
    l3_writebacks: float | None = None
    l3_replacements: float | None = None

    # Compression
    compressions: float | None = None
    failed_compressions: float | None = None
    decompressions: float | None = None
    avg_compression_size_bits: float | None = None
    compression_ratio_per_set: float | None = None
    databits_ratio: float | None = None
    resident_blocks: float | None = None
    occupied_sets: float | None = None
    resident_uncompressed_bits: float | None = None
    resident_compressed_bits: float | None = None

    # Brute-force reference (HyComp runs only)
    brute_force_accuracy_pct: float | None = None
    brute_force_total_decisions: float | None = None
    brute_force_avg_size_bits: float | None = None

    # Which sub-compressor the adaptive scheme picked
    selections: dict[str, float] = field(default_factory=dict)

    # Validation, filled in by validate.py
    valid: bool = False
    validity_flags: list[str] = field(default_factory=list)

    @property
    def key(self) -> RunKey:
        return RunKey(self.num_cores, self.benchmark, self.scheme)

    @property
    def compression_success_rate(self) -> float | None:
        """Fraction of compression attempts that produced a smaller block."""
        if not self.compressions:
            return None
        failed = self.failed_compressions or 0.0
        return (self.compressions - failed) / self.compressions

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("selections")
        for method in SELECTION_METHODS:
            data[f"sel_{method.replace('-', '')}"] = self.selections.get(method)
        data["validity_flags"] = ";".join(self.validity_flags)
        data["compression_success_rate"] = self.compression_success_rate
        return data


CSV_COLUMNS = [
    "num_cores",
    "benchmark",
    "scheme",
    "valid",
    "validity_flags",
    "ipc",
    "roi_insts",
    "roi_cycles",
    "l3_mpki",
    "l3_miss_rate",
    "l3_hits",
    "l3_misses",
    "l3_accesses",
    "l3_writebacks",
    "l3_replacements",
    "compression_ratio_per_set",
    "databits_ratio",
    "avg_compression_size_bits",
    "compressions",
    "failed_compressions",
    "compression_success_rate",
    "decompressions",
    "resident_blocks",
    "occupied_sets",
    "resident_uncompressed_bits",
    "resident_compressed_bits",
    "brute_force_accuracy_pct",
    "brute_force_total_decisions",
    "brute_force_avg_size_bits",
    *[f"sel_{m.replace('-', '')}" for m in SELECTION_METHODS],
    "sampling_end_insts",
    "roi_dump_present",
    "roi_dump_complete",
    "run_dir",
]
