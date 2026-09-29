# CacheLab

A Python analysis harness for a gem5 last-level-cache compression study. It takes finished gem5 runs, copies them out of the simulator's workspace read-only, parses their `stats.txt`, decides which runs are scientifically usable, and writes the results and the reasons for every exclusion.

> **Scope, stated plainly.** This repository is the *analysis pipeline and its published results*. It does **not** contain gem5, the gem5 configuration scripts, the cache-compression implementations, or the raw simulator output. The simulations were run in a separate research tree, and CacheLab only consumes what that tree produced. There is **no STT-RAM implementation and no STT-RAM result** here; see [What was simulated](#what-was-simulated).

## Overview

A gem5 job that exits 0 has not necessarily measured anything meaningful. In this project's sweep, 82 jobs finished without crashing, but 10 of them could not be used in any comparison. CacheLab exists to make that distinction explicit instead of letting weak rows flow into a chart.

It does three things:

1. **Exports** finished runs from the gem5 research tree into its own workspace, treating the source as strictly read-only.
2. **Ingests and validates** each run against explicit rules, keeping invalid runs with their flags instead of deleting them.
3. **Reports** the results tables and a validity report generated from the validated data.

## Key Features

- **Read-only export with provenance.** Source files are only ever opened for reading; the exporter refuses to run if its output directory is inside the source tree; every copied file is recorded in a manifest with its SHA-256, size and modification time. Runs still being written by a live simulation are detected and skipped rather than half-copied.
- **`stats.txt` parser** for gem5 output, reading the dump labelled `REFERENCE / ROI STATS`.
- **Eight explicit validity flags**, each with a written explanation: `ROI_DUMP_MISSING`, `ROI_DUMP_INCOMPLETE`, `NO_IPC`, `ROI_BELOW_TARGET`, `ROI_EQUALS_SAMPLING`, `CELL_WINDOW_MISMATCH`, `CELL_MISSING_BASELINE`, `COMPRESSION_RATIO_IMPLAUSIBLE`.
- **Nothing is deleted.** Excluded runs keep their flags and appear in a published report, on the principle that "we ran it and threw it out, here is why" is a stronger claim than a dataset that is quietly smaller than the job count.
- **Standard library only** at runtime. `pytest` is needed only to run the tests.

## Architecture

```
gem5 research tree            (separate project, read-only, NOT in this repo)
        │
        │  cachelab export      one-way copy + SHA-256 manifest
        ▼
data/raw_export/              (gitignored, ~234 MB, NOT published)
        │
        │  cachelab build       ingest → validate
        ▼
data/dataset.csv              82 runs, every run, with validity flags
data/dataset_valid.csv        72 runs that passed validation
docs/RESULTS.md               results tables, valid runs only
docs/VALIDITY.md              what was excluded, and why
```

Nothing downstream of the exporter reads the source tree. If the source disappeared, `build` would still produce identical output from the export.

## What was simulated

Every number in this repository is **Simulated**: produced by gem5, a model of a machine, not measured on silicon.

| Item | Value |
|---|---|
| Last-level cache | **SRAM** L3, 4 MiB, 16-way, 20-cycle (from the gem5 configuration files) |
| Compression schemes compared | 8: Baseline (none), ZCA, BDI, SC2, FP-H, C-PACK+Z, Brute-F, HyComp |
| Benchmarks | 4 SPEC CPU2017: `502.gcc_r`, `505.mcf_r`, `519.lbm_r`, `538.imagick_r` |
| Core counts in the dataset | 2, 4, 8 |
| Region of interest | 250,000,000 instructions |
| Runs ingested | 82, exactly one run per (cores, benchmark, scheme) cell |
| Valid / excluded | **72 (87.8%) / 10** |

**On STT-RAM.** The simulator configuration states that the L3 is SRAM and that there is deliberately no STT-RAM option. The study varies the *compression scheme on an SRAM last-level cache*. It is not STT-RAM research, and this repository makes no STT-RAM claim.

## Technical Details

- **Why validity is its own stage.** The sweep ledger counts jobs that did not crash. `validate.py` decides whether a run measured what the experiment intended, using rules derived from inspecting the real dataset rather than invented in advance.
- **A defect the validator caught.** In the 2-core `505.mcf_r` group every scheme reports exactly 20,000,000 instructions, the size of the *sampling* window, instead of the intended 250,000,000-instruction ROI. During sampling compression is deliberately not applied, so those rows' compression ratios (1.0001 for ZCA, 1.0004 for BDI) are artefacts of the wrong measurement window. `ROI_EQUALS_SAMPLING` flags this, and all eight runs in that group are excluded.
- **Compression ratio bounds.** The design allows at most 4 tags per set, so a per-set ratio above 4.0 or below 1.0 is physically implausible and is flagged.
- **Comparisons are within a group only.** Speedups are computed against the uncompressed baseline in the same (cores, benchmark) group, and only where that group has a valid baseline.

## Results / Evaluation

All values below are **Simulated**, over the validated subset. Full tables for every group are in [docs/RESULTS.md](docs/RESULTS.md); exclusions and reasons are in [docs/VALIDITY.md](docs/VALIDITY.md).

**Excluded runs (10 of 82)**

| Reason | Runs |
|---|---|
| `CELL_MISSING_BASELINE` | 10 |
| `ROI_BELOW_TARGET` | 8 |
| `ROI_EQUALS_SAMPLING` | 1 |

These overlap: the eight 2-core `505.mcf_r` runs and two 8-core `519.lbm_r` runs (`fph`, `sc2`) are excluded. The 8-core `519.lbm_r` group had no baseline when the data was exported because that part of the sweep was still running.

**Examples from the tables** (Δ IPC against the uncompressed baseline in the same group)

| Group | Scheme | Δ IPC | Compression ratio |
|---|---|---|---|
| 4 cores, `519.lbm_r` | C-PACK+Z | +5.54% | 1.621 |
| 4 cores, `519.lbm_r` | FP-H | −3.22% | 1.391 |
| 4 cores, `505.mcf_r` | C-PACK+Z | +1.12% | 1.933 |
| 2 cores, `502.gcc_r` | HyComp | +0.90% | 1.268 |

**HyComp predictor accuracy** (how often the adaptive scheme picked the compressor an exhaustive search would have picked; measured only on runs launched with the brute-force reference): 45.78% (2 cores, `502.gcc_r`) to 83.81% (2 cores, `519.lbm_r`) across 9 measured groups.

**How to read these numbers.** The dataset holds one simulated run per cell, so there are no repeated runs and no confidence intervals. Most IPC differences are within a few percent, and no scheme wins in every group. The tables report what was simulated; they do not establish that any scheme is better in general.

## Testing

```bash
python -m pytest -q
```

**57 tests pass** (verified 2026-09-29 in the project's virtual environment), covering the read-only exporter, the `stats.txt` parser and the validation rules.

| File | Covers |
|---|---|
| `tests/test_export.py` | refuses to export into or onto the source tree; source tree is byte-identical and gains no files after an export; provenance manifest; incremental re-export; unfinished runs skipped, then picked up once complete |
| `tests/test_statsfile.py` | single and multiple dumps, numeric formats, NaN handling, unterminated (incomplete) dumps, empty files |
| `tests/test_validate.py` | each validity flag, cell-level baseline and window checks, cells failing independently, ROI target inference |

## Reproduction

What works from a fresh clone:

```bash
git clone git@github.com:nishantchourasia/cachelab.git
cd cachelab
python3 -m venv .venv && . .venv/bin/activate
pip install pytest
python -m pytest -q              # 57 tests
```

The published results are the committed `data/dataset*.csv` and `docs/*.md`.

What does **not** work from a fresh clone: `python -m cachelab.cli build` and `status` read `data/raw_export/`, which is gitignored and not published, so the published numbers cannot be regenerated without the original gem5 output. `python -m cachelab.cli export` needs access to that gem5 research tree; point it at one with `CACHELAB_GEM5_SOURCE=/path/to/tree` or `--source`. Its built-in default is a path on the author's machine.

## Limitations

- **Not the simulator.** No gem5 sources, configs or compression implementations are in this repository, so the simulations themselves cannot be reproduced from it.
- **Results are not regenerable from the repository alone**, because the raw export (~234 MB) is not published. The committed CSVs and reports are the record.
- **One run per cell**, no confidence intervals; small differences may not be meaningful.
- **Coverage is incomplete.** 2-core `505.mcf_r` has no valid runs and 8-core `519.lbm_r` has none; the 16-core configuration is not in the dataset.
- **Simulated, not measured** on hardware. No energy, area or timing-closure results.
- **No STT-RAM.** The studied L3 is SRAM.

## Tech Stack

Python 3 (standard library only at runtime), `pytest` for tests, gem5 as the (external) simulator whose output is analysed.

## Project Structure

```
cachelab/
├── cachelab/
│   ├── cli.py         export / build / status
│   ├── export.py      read-only export with SHA-256 manifest
│   ├── statsfile.py   gem5 stats.txt parser
│   ├── ingest.py      dataset loading and CSV writing
│   ├── schema.py      run naming and record schema
│   ├── validate.py    validity flags and rules
│   └── report.py      RESULTS.md and VALIDITY.md generation
├── data/
│   ├── dataset.csv         all 82 runs with validity flags
│   └── dataset_valid.csv   the 72 valid runs
├── docs/
│   ├── RESULTS.md
│   └── VALIDITY.md
└── tests/
```

## License

No license has been selected for this repository yet, so no license file is included.
