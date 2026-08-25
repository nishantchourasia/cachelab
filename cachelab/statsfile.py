"""Parser for gem5 ``stats.txt`` files.

A gem5 stats file is a sequence of *dumps*. Each dump is one snapshot of every
statistic in the simulated machine, delimited by::

    ---------- Begin Simulation Statistics ----------
    <name> <value>    # <description> (<Unit>)
    ...
    ---------- End Simulation Statistics   ----------

The HyComp experiment driver additionally writes a label line immediately
before a dump::

    === REFERENCE / ROI STATS ===

so that the sampling window and the measured region-of-interest can be told
apart after the fact. Labels are attached to the dump that follows them.

Two properties of the source data drove this design:

* **Files may be mid-write.** A 128-job sweep runs for days, and the dataset is
  parsed while jobs are still running. A dump without its terminating marker is
  therefore returned with ``complete=False`` rather than raising, so that
  partial results can be inspected without waiting for the sweep to finish.

* **Statistics are per-dump deltas, not cumulative.** gem5 resets counters
  after each dump in this configuration. This was verified against a known-good
  run: ``502.gcc_r`` reports 20,000,000 committed instructions in the sampling
  dump and exactly 250,000,000 in the ROI dump, rather than 270,000,000. Any
  analysis that treats dumps as cumulative would be wrong.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

BEGIN_MARKER = "---------- Begin Simulation Statistics ----------"
END_MARKER = "---------- End Simulation Statistics   ----------"

# Driver annotations look like "=== REFERENCE / ROI STATS ===".
_LABEL_RE = re.compile(r"^===\s*(?P<label>.+?)\s*===\s*$")

# A statistic line: name, whitespace, value, then an optional "# description".
# Values seen in practice: integers, floats, scientific notation, and "nan"
# (emitted for ratios whose denominator was zero -- e.g. the IPC of a CPU that
# was switched out and never executed).
_STAT_RE = re.compile(
    r"^(?P<name>[^\s#|]+)\s+(?P<value>-?(?:\d+\.?\d*(?:[eE][-+]?\d+)?|nan|inf))\s*(?:#.*)?$"
)


@dataclass
class Dump:
    """One snapshot of the simulator's statistics."""

    index: int
    """Position of this dump in the file, starting at 0."""

    label: str | None = None
    """Driver annotation preceding the dump, e.g. ``"REFERENCE / ROI STATS"``."""

    stats: dict[str, float] = field(default_factory=dict)
    """Statistic name to value. ``nan`` values are preserved, not dropped."""

    complete: bool = False
    """False if the terminating marker was missing (file still being written)."""

    def get(self, name: str, default: float | None = None) -> float | None:
        """Return a statistic, or ``default`` if absent or not a number.

        ``nan`` is treated as absent. gem5 emits ``nan`` for a ratio whose
        denominator was zero, which carries no information and would otherwise
        silently poison downstream arithmetic.
        """
        value = self.stats.get(name)
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        return value

    def find(self, pattern: str) -> dict[str, float]:
        """Return every statistic whose name matches a regular expression."""
        regex = re.compile(pattern)
        return {k: v for k, v in self.stats.items() if regex.search(k)}

    def __len__(self) -> int:
        return len(self.stats)


def _parse_value(raw: str) -> float:
    if raw == "nan":
        return math.nan
    if raw == "inf":
        return math.inf
    if raw == "-inf":
        return -math.inf
    return float(raw)


def iter_dumps(path: str | Path) -> Iterator[Dump]:
    """Yield each dump in a gem5 stats file, in order.

    Streams the file rather than reading it whole: a sweep produces well over a
    hundred stats files of ~1 MB each, and only a handful of statistics from
    each are ultimately needed.
    """
    path = Path(path)
    index = 0
    pending_label: str | None = None
    current: Dump | None = None

    with path.open("r", errors="replace") as handle:
        for line in handle:
            line = line.rstrip("\n")
            stripped = line.strip()

            if not stripped:
                continue

            if stripped == BEGIN_MARKER:
                current = Dump(index=index, label=pending_label)
                pending_label = None
                index += 1
                continue

            if stripped == END_MARKER:
                if current is not None:
                    current.complete = True
                    yield current
                    current = None
                continue

            if current is None:
                # Between dumps: the only thing we care about is a label, which
                # applies to the dump that comes next.
                match = _LABEL_RE.match(stripped)
                if match:
                    pending_label = match.group("label")
                continue

            match = _STAT_RE.match(stripped)
            if match:
                current.stats[match.group("name")] = _parse_value(match.group("value"))

    # A dump with no terminating marker means the simulator is still running
    # (or was killed). Surface it, flagged, rather than discarding it.
    if current is not None:
        yield current


def read_dumps(path: str | Path) -> list[Dump]:
    """Read every dump from a stats file into a list."""
    return list(iter_dumps(path))


def find_dump(dumps: list[Dump], label: str) -> Dump | None:
    """Return the last dump carrying ``label``, or None.

    The last is chosen deliberately: if a driver were ever to re-dump the same
    phase, the final write is the authoritative one.
    """
    matches = [d for d in dumps if d.label == label]
    return matches[-1] if matches else None
