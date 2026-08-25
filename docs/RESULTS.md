# Results

Every number below is **Simulated**: measured from a gem5 run, over a
250 million instruction region of interest, on the validated subset of
the dataset. Excluded runs are listed in `VALIDITY.md` and appear
nowhere in these tables.

Generated: 2026-08-25 06:15 UTC

**Reading the columns**

- **IPC** — instructions per cycle. Higher is faster.
- **MPKI** — last-level-cache misses per thousand instructions. Lower is better.
- **Comp. ratio** — effective cache capacity divided by physical capacity,
  averaged over occupied sets. 1.0 means compression bought nothing.
  The design caps this at 4.0 because a set holds at most 4 tags.
- **Δ IPC** — change against the uncompressed Baseline in the same group.

## 502.gcc_r — 2 cores

| Scheme | IPC | MPKI | Comp. ratio | Avg comp. bits | Δ IPC |
|---|---|---|---|---|---|
| Baseline | 2.3746 | 0.37 | — | — | +0.00% |
| ZCA | 2.3739 | 0.37 | 1.144 | 390.7 | -0.03% |
| BDI | 2.3716 | 0.37 | 1.252 | 372.1 | -0.12% |
| SC2 | 2.3814 | 0.37 | 1.449 | 240.0 | +0.29% |
| FP-H | 2.3761 | 0.37 | 1.265 | 263.3 | +0.06% |
| C-PACK+Z | 2.3717 | 0.37 | 1.474 | 230.2 | -0.12% |
| Brute-F | 2.3697 | 0.37 | 1.468 | 249.7 | -0.21% |
| HyComp | 2.3959 | 0.37 | 1.268 | 250.7 | +0.90% |

## 519.lbm_r — 2 cores

| Scheme | IPC | MPKI | Comp. ratio | Avg comp. bits | Δ IPC |
|---|---|---|---|---|---|
| Baseline | 0.2396 | 61.60 | — | — | +0.00% |
| ZCA | 0.2392 | 62.46 | 1.000 | 511.8 | -0.18% |
| BDI | 0.2392 | 62.45 | 1.000 | 470.4 | -0.17% |
| SC2 | 0.2393 | 61.94 | 1.027 | 406.9 | -0.16% |
| FP-H | 0.2394 | 56.82 | 1.972 | 165.8 | -0.09% |
| C-PACK+Z | 0.2397 | 58.93 | 1.476 | 294.5 | +0.00% |
| Brute-F | 0.2394 | 56.88 | 1.955 | 201.7 | -0.08% |
| HyComp | 0.2394 | 57.50 | 1.827 | 183.6 | -0.10% |

## 538.imagick_r — 2 cores

| Scheme | IPC | MPKI | Comp. ratio | Avg comp. bits | Δ IPC |
|---|---|---|---|---|---|
| Baseline | 1.3642 | 11.56 | — | — | +0.00% |
| ZCA | 1.3561 | 11.62 | 1.000 | 501.8 | -0.59% |
| BDI | 1.3577 | 11.60 | 1.034 | 492.4 | -0.47% |
| SC2 | 1.3594 | 11.48 | 1.127 | 343.1 | -0.35% |
| FP-H | 1.3704 | 10.93 | 1.375 | 285.3 | +0.46% |
| C-PACK+Z | 1.3688 | 11.04 | 1.383 | 382.8 | +0.34% |
| Brute-F | 1.3767 | 10.91 | 1.454 | 324.9 | +0.92% |
| HyComp | 1.3698 | 10.97 | 1.395 | 302.1 | +0.41% |

## 502.gcc_r — 4 cores

| Scheme | IPC | MPKI | Comp. ratio | Avg comp. bits | Δ IPC |
|---|---|---|---|---|---|
| Baseline | 2.3701 | 0.94 | — | — | +0.00% |
| ZCA | 2.3788 | 0.95 | 1.071 | 430.2 | +0.37% |
| BDI | 2.3472 | 0.93 | 1.152 | 405.2 | -0.97% |
| SC2 | 2.3602 | 0.92 | 1.380 | 287.1 | -0.42% |
| FP-H | 2.3548 | 0.92 | 1.184 | 252.5 | -0.64% |
| C-PACK+Z | 2.3466 | 0.90 | 1.445 | 324.7 | -0.99% |
| Brute-F | 2.3462 | 0.90 | 1.413 | 312.8 | -1.01% |
| HyComp | 2.3571 | 0.91 | 1.189 | 241.6 | -0.55% |

## 505.mcf_r — 4 cores

| Scheme | IPC | MPKI | Comp. ratio | Avg comp. bits | Δ IPC |
|---|---|---|---|---|---|
| Baseline | 0.3821 | 10.16 | — | — | +0.00% |
| ZCA | 0.3857 | 9.53 | 1.240 | 275.0 | +0.93% |
| BDI | 0.3824 | 10.09 | 1.255 | 266.0 | +0.07% |
| SC2 | 0.3858 | 9.35 | 1.336 | 211.3 | +0.96% |
| FP-H | 0.3857 | 9.21 | 1.109 | 215.0 | +0.92% |
| C-PACK+Z | 0.3864 | 9.35 | 1.933 | 163.6 | +1.12% |
| Brute-F | 0.3860 | 9.38 | 1.203 | 200.7 | +1.00% |
| HyComp | 0.3858 | 9.43 | 1.155 | 187.4 | +0.97% |

## 519.lbm_r — 4 cores

| Scheme | IPC | MPKI | Comp. ratio | Avg comp. bits | Δ IPC |
|---|---|---|---|---|---|
| Baseline | 0.2605 | 49.80 | — | — | +0.00% |
| ZCA | 0.2615 | 49.26 | 1.060 | 278.3 | +0.36% |
| BDI | 0.2591 | 50.32 | 1.297 | 283.8 | -0.56% |
| SC2 | 0.2551 | 50.88 | 1.095 | 223.7 | -2.09% |
| FP-H | 0.2522 | 51.54 | 1.391 | 229.2 | -3.22% |
| C-PACK+Z | 0.2750 | 43.21 | 1.621 | 153.3 | +5.54% |
| Brute-F | 0.2671 | 46.42 | 1.130 | 224.8 | +2.54% |
| HyComp | 0.2628 | 48.21 | 1.101 | 201.6 | +0.88% |

## 538.imagick_r — 4 cores

| Scheme | IPC | MPKI | Comp. ratio | Avg comp. bits | Δ IPC |
|---|---|---|---|---|---|
| Baseline | 1.2955 | 22.34 | — | — | +0.00% |
| ZCA | 1.3095 | 22.21 | 1.355 | 307.3 | +1.09% |
| BDI | 1.3036 | 22.25 | 1.071 | 314.7 | +0.63% |
| SC2 | 1.3038 | 21.96 | 1.402 | 240.6 | +0.65% |
| FP-H | 1.3088 | 21.67 | 1.206 | 244.7 | +1.03% |
| C-PACK+Z | 1.3148 | 21.85 | 1.512 | 176.7 | +1.49% |
| Brute-F | 1.3053 | 21.86 | 1.088 | 257.9 | +0.76% |
| HyComp | 1.3046 | 22.05 | 1.309 | 222.6 | +0.71% |

## 502.gcc_r — 8 cores

| Scheme | IPC | MPKI | Comp. ratio | Avg comp. bits | Δ IPC |
|---|---|---|---|---|---|
| Baseline | 2.3968 | 10.63 | — | — | +0.00% |
| ZCA | 2.3817 | 10.99 | 1.467 | 171.9 | -0.63% |
| BDI | 2.3760 | 11.00 | 1.361 | 191.9 | -0.87% |
| SC2 | 2.3973 | 11.12 | 1.516 | 160.0 | +0.02% |
| FP-H | 2.3695 | 10.95 | 1.457 | 175.7 | -1.14% |
| C-PACK+Z | 2.3840 | 11.17 | 1.872 | 74.9 | -0.53% |
| Brute-F | 2.3834 | 11.14 | 1.527 | 126.7 | -0.56% |
| HyComp | 2.3820 | 11.04 | 1.454 | 142.5 | -0.62% |

## 505.mcf_r — 8 cores

| Scheme | IPC | MPKI | Comp. ratio | Avg comp. bits | Δ IPC |
|---|---|---|---|---|---|
| Baseline | 0.3321 | 11.04 | — | — | +0.00% |
| ZCA | 0.3244 | 11.14 | 1.345 | 428.6 | -2.32% |
| BDI | 0.3253 | 11.00 | 1.400 | 407.9 | -2.05% |
| SC2 | 0.3305 | 10.74 | 1.409 | 295.9 | -0.48% |
| FP-H | 0.3311 | 9.86 | 1.612 | 226.8 | -0.31% |
| C-PACK+Z | 0.3300 | 10.69 | 1.509 | 348.6 | -0.64% |
| Brute-F | 0.3368 | 9.67 | 1.726 | 231.7 | +1.40% |
| HyComp | 0.3308 | 9.93 | 1.616 | 216.3 | -0.42% |

## HyComp predictor accuracy

How often the adaptive scheme chose the same compressor that an
exhaustive search of all candidates would have chosen. Measured only
on runs launched with a brute-force reference.

| Cores | Benchmark | Accuracy | Decisions |
|---|---|---|---|
| 2 | 502.gcc_r | 45.78% | 93,048 |
| 2 | 519.lbm_r | 83.81% | 21,533,171 |
| 2 | 538.imagick_r | 66.39% | 3,549,739 |
| 4 | 502.gcc_r | 72.62% | 434,545 |
| 4 | 505.mcf_r | 68.55% | 4,797,323 |
| 4 | 519.lbm_r | 70.06% | 23,348,264 |
| 4 | 538.imagick_r | 68.88% | 9,666,023 |
| 8 | 502.gcc_r | 71.02% | 6,155,381 |
| 8 | 505.mcf_r | 78.40% | 4,213,416 |

