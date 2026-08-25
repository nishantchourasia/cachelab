# Data Validity Report

Which simulated runs CacheLab considers usable, and exactly why each
excluded run was excluded.

This report exists because a gem5 job that exits 0 has not necessarily
measured anything meaningful. The sweep ledger counts jobs that did not
crash. Validity is a separate question, decided by the rules in
`cachelab/validate.py` and re-checked every time the dataset is rebuilt.

Generated: 2026-08-25 06:15 UTC

## Summary

| Measure | Value |
|---|---|
| Runs ingested | 82 |
| Valid | 72 (87.8%) |
| Excluded | 10 |
| Target ROI length | 250,000,000 instructions |

All measurements are **Simulated** — produced by gem5, a model of a
machine, not by silicon.

## Why runs were excluded

| Reason | Runs | What it means |
|---|---|---|
| `CELL_MISSING_BASELINE` | 10 | This group has no valid uncompressed baseline, so no speedup or improvement can be computed for it. |
| `ROI_BELOW_TARGET` | 8 | The ROI committed fewer instructions than the experiment targets. A shorter window covers a different part of the program, so the result is not comparable with full-length runs. |
| `ROI_EQUALS_SAMPLING` | 1 | The ROI instruction count exactly equals the sampling-window size, indicating the ROI dump captured the sampling phase instead. During sampling, compression is deliberately not applied, so any compression ratio from this run is an artefact. |

## Groups excluded entirely

A (cores, benchmark) group with no usable runs cannot contribute to
any scheme comparison.

| Cores | Benchmark | Reasons |
|---|---|---|
| 2 | 505.mcf_r | `CELL_MISSING_BASELINE`, `ROI_BELOW_TARGET`, `ROI_EQUALS_SAMPLING` |
| 8 | 519.lbm_r | `CELL_MISSING_BASELINE` |

## Excluded runs

| Run | Flags |
|---|---|
| `SCHEME_2core_505.mcf_r_bdi` | `ROI_BELOW_TARGET`, `CELL_MISSING_BASELINE` |
| `SCHEME_2core_505.mcf_r_brute_f` | `ROI_BELOW_TARGET`, `CELL_MISSING_BASELINE` |
| `SCHEME_2core_505.mcf_r_cpack_z` | `ROI_BELOW_TARGET`, `CELL_MISSING_BASELINE` |
| `SCHEME_2core_505.mcf_r_fph` | `ROI_BELOW_TARGET`, `CELL_MISSING_BASELINE` |
| `SCHEME_2core_505.mcf_r_hycomp` | `ROI_EQUALS_SAMPLING`, `ROI_BELOW_TARGET`, `CELL_MISSING_BASELINE` |
| `SCHEME_2core_505.mcf_r_none` | `ROI_BELOW_TARGET`, `CELL_MISSING_BASELINE` |
| `SCHEME_2core_505.mcf_r_sc2` | `ROI_BELOW_TARGET`, `CELL_MISSING_BASELINE` |
| `SCHEME_2core_505.mcf_r_zca` | `ROI_BELOW_TARGET`, `CELL_MISSING_BASELINE` |
| `SCHEME_8core_519.lbm_r_fph` | `CELL_MISSING_BASELINE` |
| `SCHEME_8core_519.lbm_r_sc2` | `CELL_MISSING_BASELINE` |

## Coverage of valid data

| Cores | Benchmark | Valid schemes | Of |
|---|---|---|---|
| 2 | 502.gcc_r | 8 | 8 |
| 2 | 505.mcf_r | 0 | 8 |
| 2 | 519.lbm_r | 8 | 8 |
| 2 | 538.imagick_r | 8 | 8 |
| 4 | 502.gcc_r | 8 | 8 |
| 4 | 505.mcf_r | 8 | 8 |
| 4 | 519.lbm_r | 8 | 8 |
| 4 | 538.imagick_r | 8 | 8 |
| 8 | 502.gcc_r | 8 | 8 |
| 8 | 505.mcf_r | 8 | 8 |
| 8 | 519.lbm_r | 0 | 2 |

