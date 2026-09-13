# Andrice Levels v4 — Complete project guide

**GitHub equation-formatting revision: 13 September 2026.**

**Historical RTH excursions, extreme-time statistics, projected price zones, and estimation uncertainty.**

Documentation prepared **11 September 2026** for Christian Andrice's [Andrice_levels-v4 repository](https://github.com/andricechristian/Andrice_levels-v4).

This is a companion to the existing short README. It explains the project from its original idea through the current converter and calculator, then records the earlier calibration research and the features still outside this repository.

**Source snapshot:** commit [`7eeb97f7024be248f0c0d90387d2925ed92b4fbb`](https://github.com/andricechristian/Andrice_levels-v4/tree/7eeb97f7024be248f0c0d90387d2925ed92b4fbb). The repository inspected contains `README.md`, `01_build_rth_sessions_v2.py`, and `02_calculate_rth_levels_v4.py`. Filenames in commands below match that snapshot. Older downloads used different suffixes.

> Andrice Levels asks: **How far has price historically moved above and below its RTH open, when have the session extremes occurred, and what price areas do those distributions imply when applied to a new session's open and known volatility?**
>
> A projected area is a statistical reference. A narrow uncertainty band estimates the precision of a statistic; it does not guarantee that tomorrow's high or low will form there. A historical containment rate is not a trading win rate.

## Contents

1. [The original idea and project scope](#1-the-original-idea-and-project-scope)
2. [Workflow and implementation status](#2-workflow-and-implementation-status)
3. [RTH, timestamps, and data quality](#3-rth-timestamps-and-data-quality)
4. [Every column in the session CSV](#4-every-column-in-the-session-csv)
5. [Points, percentages, and ATR formulas](#5-points-percentages-and-atr-formulas)
6. [Means and the original seven-session exercise](#6-means-and-the-original-seven-session-exercise)
7. [Standard uncertainty and bootstrap confidence intervals](#7-standard-uncertainty-and-bootstrap-confidence-intervals)
8. [Percentiles and excursion zones](#8-percentiles-and-excursion-zones)
9. [Projecting statistics into current prices](#9-projecting-statistics-into-current-prices)
10. [Outer envelopes and containment](#10-outer-envelopes-and-containment)
11. [HOD and LOD timing statistics](#11-hod-and-lod-timing-statistics)
12. [Which extreme happened first](#12-which-extreme-happened-first)
13. [Full history, recent windows, and regime change](#13-full-history-recent-windows-and-regime-change)
14. [How to run both commands](#14-how-to-run-both-commands)
15. [Reading every kind of console output](#15-reading-every-kind-of-console-output)
16. [CSV and JSON output dictionary](#16-csv-and-json-output-dictionary)
17. [Walk-forward calibration and backtest metrics](#17-walk-forward-calibration-and-backtest-metrics)
18. [Earlier research results and their limits](#18-earlier-research-results-and-their-limits)
19. [Project evolution and updates](#19-project-evolution-and-updates)
20. [Maintenance, troubleshooting, and validation](#20-maintenance-troubleshooting-and-validation)
21. [Extensions discussed and remaining research](#21-extensions-discussed-and-remaining-research)
22. [Formula reference and source map](#22-formula-reference-and-source-map)

## 1. The original idea and project scope

The initial project reduced each completed regular trading session to its open, high, and low. With session index $`D`$, the original notation was:


```math
S(D)=\bigl(O_{RTH}(D),H_{RTH}(D),L_{RTH}(D)\bigr).
```


The historical data range was written as $`DATA\_RNG=[1,n]`$. Here $`D`$ is the position of a session in the dataset. It is not the day of the month, and it does not imply that every intervening calendar date has a row. The later addition of `Date` gives each observation an unambiguous real date.

Two distances were defined separately:


```math
PUV(D)=H_{RTH}(D)-O_{RTH}(D),
```


```math
PDV(D)=O_{RTH}(D)-L_{RTH}(D).
```


**PUV** means *price up value*: the largest upward excursion from the session open. **PDV** means *price down value*: the magnitude of the largest downward excursion from that open. Both are nonnegative distances. PDV is not a negative return.

The first objective was to average these distances across historical sessions and project them above and below a new day's open. The project then grew to include normalization, uncertainty, percentile zones, timing, recent-history comparisons, and historical calibration.

### Relationship to the original inspiration

The supplied description of the Extreme Map indicator combined open-relative historical extremes with historical volume concentration. Andrice Levels adopted the general question of open-relative extremes, then developed its own simpler statistical framework.

**The current Andrice Levels code does not calculate a volume-at-price map, confluence with volume concentration, or volume-weighted excursion statistics.** `RTH_Volume` is retained as a session field and for data-quality checks; each eligible session receives equal weight in the means and quantiles. There is also no fixed five-point zone width: zone width comes from the selected statistics.

### Questions the current model can answer

- What were the average upside and downside excursions in a chosen historical sample?
- What distances correspond to the median, 75th, 90th, or 95th historical excursion percentiles?
- What are those distances in points, percentage terms, and prior-ATR units?
- At what recorded times did the final RTH high and low most often occur?
- How precisely were those means, quantiles, window frequencies, and order ratios estimated?
- How do recent 60- and 252-session distributions differ from the full available history?

The earlier separate backtest asks whether forecasts built before each test session contained its realized range or captured its final extremes.

### Questions it does not answer by itself

A level does not establish an entry, reversal, stop loss, profit target, position size, expected trading profit, or prop-evaluation pass rate. Those require separate trading rules and execution assumptions. The project's HOD and LOD are the **final extremes of a completed RTH session**, not a continuously updating declaration that the current intraday high or low is already final.

## 2. Workflow and implementation status

| Stage | Input | Work performed | Output / status |
| --- | --- | --- | --- |
| Command 1 | Raw 1m, 5m, or 15m OHLCV | Interpret timestamps, isolate RTH, reject incomplete sessions, extract OHLC/timing, calculate excursions and ATR | Implemented in `01_build_rth_sessions_v2.py` |
| Command 2 | Completed-session CSV | Calculate historical statistics, bootstrap uncertainty, timing and history comparisons; project using a supplied open | Implemented in `02_calculate_rth_levels_v4.py` |
| Historical calibration | Long completed-session history | Refit from earlier sessions for each test day and measure forecast outcomes | Earlier `03_backtest_rth_levels.py` research package; **not in the inspected GitHub snapshot** |
| Chart display | Date-specific projected levels | Display lines/zones with their definitions | Discussed; no TradingView integration in these two commands |
| Trading strategy | Levels plus explicit entry/exit rules and intraday prices | Simulate orders, costs, drawdowns, and possibly prop rules | Separate research task |

The current scripts are standalone. The calculator embeds its helpers and does not need `rth_stats.py` beside it. Older research scripts, including the earlier separate backtester, did depend on that helper.

## 3. RTH, timestamps, and data quality

### 3.1 The session being measured

The converter is configured for **09:30–16:00 America/New_York**, the 390-minute US equity regular session used in this ES research. This is an explicit research window, not the complete futures exchange trading day. Applying the same code to another asset keeps this window unless the implementation is changed deliberately.

Use **Eastern Time / America/New_York**, rather than calling every date “EST.” New York changes between standard and daylight time. A genuinely fixed `UTC-05:00` export is not the same clock as New York throughout the year.

For example, 08:30 in a fixed UTC−5 export corresponds to 09:30 New York during daylight time, but to 08:30 New York during standard time. A permanent +1-hour shift would therefore misclassify winter sessions. The source timezone is an input because timestamps alone cannot reliably establish it.

### 3.2 Start labels versus end labels

The raw file's bar-label convention must be specified independently of the chart's import display convention.

| Interval | Start-labeled RTH bars | End-labeled RTH bars | Required count |
| --- | --- | --- | ---: |
| 1 minute | 09:30 through 15:59 | 09:31 through 16:00 | 390 |
| 5 minutes | 09:30 through 15:55 | 09:35 through 16:00 | 78 |
| 15 minutes | 09:30 through 15:45 | 09:45 through 16:00 | 26 |

For a start-labeled bar, the converter adds the selected interval to obtain its end. All exported `HOD_Time` and `LOD_Time` values use **Eastern end-of-bar labels**. Thus a one-minute bar starting at 09:30 is represented by 09:31 in the extreme-time output. This agrees with the project's clarified raw-CSV/chart-label distinction.

An extreme attributed to 10:15 on a 15-minute end-labeled series occurred somewhere in the bar spanning 10:00–10:15. Its exact time and the internal order of high and low cannot be reconstructed from OHLC.

### 3.3 Supported input formats and intervals

Required input columns:

```csv
Date,Time,Open,High,Low,Close,Volume
```

The converter accepts compact dates such as `20250106` and ISO dates such as `2025-01-06`. Slash dates require a date-order choice or `--date-format`. Time formats include `HHMM`, `HHMMSS`, `HH:MM`, and `HH:MM:SS`. Retain leading zeros in compact exports; colon-separated times remove ambiguity.

Only **1, 5, and 15 minutes** are supported. Two-minute or ten-minute data are not supported merely because they are below the maximum. The requested rejection message is:

```text
Please upload 1-minute, 5-minute or 15-minute OHLCV. Timeframes higher than 15 minutes are not supported.
```

Automatic detection examines the most frequent positive timestamp spacing in a preview of up to 50,000 rows, preferring observations near RTH. A repeated missing-bar pattern can resemble a coarser export, so the interactive flow asks the user to confirm the actual interval. A single 30-minute gap in otherwise one-minute data is a completeness problem, not proof of 30-minute candles.

### 3.4 What qualifies as a complete session

The converter requires the exact expected RTH grid. It excludes a source date for missing RTH bars, duplicate RTH timestamps, out-of-order RTH bars, misaligned bars, boundary-straddling bars, invalid RTH OHLCV, or no positive total RTH volume. Valid OHLC obey:


```math
0<L\leq\min(O,C)\leq\max(O,C)\leq H.
```


Negative or nonfinite volume is invalid. Individual zero-volume bars may remain if valid and the session's total volume is positive. Their existence is not a guarantee of reliable data. Premarket and postmarket extremes do not enter RTH statistics.

Early-closing sessions do not meet the 390-minute definition and are excluded. There is no exchange-holiday calendar lookup. The audit can record a date present only overnight as having no RTH overlap; it cannot identify a date missing entirely from the source as a data outage versus a legitimate closure.

Rows must arrive in chronological date order after timestamp interpretation. The converter does not silently repair duplicate or disordered data. Correct the raw source and reconvert if a session is invalid.

## 4. Every column in the session CSV

The output always uses these **25 columns in this order**:

```csv
Session,Date,O_RTH,H_RTH,L_RTH,C_RTH,HOD_Time,LOD_Time,Extreme_First,PUV_Points,PDV_Points,PUV_Percent,PDV_Percent,RTH_Range_Points,Calendar_Days_Since_Previous_Complete,ATR_Sequence_Reset,Previous_Complete_RTH_Close,TR_RTH,ATR14_Previous,ATR14_End,PUV_ATR,PDV_ATR,RTH_Volume,Bar_Count,Duplicate_Bars
```

| Column | Meaning and unit | Interpretation / special case |
| --- | --- | --- |
| `Session` | Sequential accepted-session identifier, starting at 1 | Rejected dates do not receive a row. Use `Date`, not this number, when merging histories. |
| `Date` | RTH session date, `YYYY-MM-DD` | Forecast eligibility is based on this date. |
| `O_RTH` | Open of the first RTH bar, price points | Anchor for both excursion directions. |
| `H_RTH` | Highest high across RTH bars, price points | Final RTH high, not a close-based maximum. |
| `L_RTH` | Lowest low across RTH bars, price points | Final RTH low. |
| `C_RTH` | Close of the final RTH bar, price points | Also used in the next complete session's TR calculation unless a reset occurs. |
| `HOD_Time` | End label of the first bar attaining the final RTH high | Eastern clock time; precision equals the source bar interval. |
| `LOD_Time` | End label of the first bar attaining the final RTH low | Repeated lows use their first occurrence. |
| `Extreme_First` | `HOD_FIRST`, `LOD_FIRST`, or `SAME_BAR` | `SAME_BAR` means the order cannot be inferred within that bar. |
| `PUV_Points` | $`H-O`$ | Nonnegative upward distance. |
| `PDV_Points` | $`O-L`$ | Nonnegative downward distance. |
| `PUV_Percent` | $`100(H-O)/O`$ | `0.50` means 0.50%, not 50%. |
| `PDV_Percent` | $`100(O-L)/O`$ | Downward percentage magnitude. |
| `RTH_Range_Points` | $`H-L=PUV+PDV`$ | Full session range, distinct from true range. |
| `Calendar_Days_Since_Previous_Complete` | Calendar-date difference from the previous accepted session | Blank on the first row; Friday to Monday is 3. |
| `ATR_Sequence_Reset` | 1 when a gap of at least 7 calendar days resets ATR state; otherwise 0 | First row starts a sequence but is flagged 0 because there is no preceding gap. |
| `Previous_Complete_RTH_Close` | Prior accepted RTH close used in TR | Blank initially and on a reset row. |
| `TR_RTH` | RTH true range in points | Includes distance from the previous complete RTH close when available. |
| `ATR14_Previous` | Wilder ATR known before this session | Denominator for historical ATR-normalized excursions; blank during warm-up. |
| `ATR14_End` | Wilder ATR after incorporating this session's TR | Available after completion, not at this session's open. |
| `PUV_ATR` | $`(H-O)/ATR14\_Previous`$ | Dimensionless ATR multiple; blank when prior ATR is unavailable or not positive. |
| `PDV_ATR` | $`(O-L)/ATR14\_Previous`$ | Same convention for the downside. |
| `RTH_Volume` | Sum of source volume over RTH bars | In the source's volume units; no bid/ask split or volume-at-price calculation. |
| `Bar_Count` | Actual accepted RTH bars: 390, 78, or 26 | Coarse bars are never expanded into fabricated minutes. |
| `Duplicate_Bars` | Duplicate RTH timestamps in an accepted session | Always 0 in newly converted accepted rows; duplicates instead appear in exclusions. |

The original manually maintained eight-column form remains useful for supplying raw session observations:

```csv
Date,O_RTH,H_RTH,L_RTH,C_RTH,HOD_Time,LOD_Time,RTH_Volume
```

However, **it is not the full direct input contract of Command 2**. The calculator requires the ATR columns too, even if they are blank during legitimate warm-up. Manual OHLC alone also cannot prove complete intraday coverage or exact extreme times.

## 5. Points, percentages, and ATR formulas

### 5.1 Points normalization

For session $`i`$:


```math
u_{i}=H_{i}-O_{i},\qquad d_{i}=O_{i}-L_{i}.
```


Points are easy to translate to a chart. Their limitation is comparability across large changes in price and volatility. A 40-point ES excursion does not represent the same relative move at an opening price of 2,000 as at 8,000.

### 5.2 Percentage normalization


```math
u_{i}^{\%}=100\frac{H_{i}-O_{i}}{O_{i}},\qquad d_{i}^{\%}=100\frac{O_{i}-L_{i}}{O_{i}}.
```


Normalize **each session by its own open first**, then calculate its sample mean or percentile. The average of these ratios is generally not the ratio of the average excursion to the average open.

Percentage normalization adjusts for price scale. It does not fully adjust for volatility regimes, news shocks, or structural change. A quiet and a volatile period can occur at the same price level.

### 5.3 True range and Wilder RTH ATR14

Let $`C_{i-1}^{complete}`$ be the previous eligible completed RTH close in the same ATR sequence:


```math
TR_{i}=\max\left(H_{i}-L_{i},\;|H_{i}-C_{i-1}^{complete}|,\;|L_{i}-C_{i-1}^{complete}|\right).
```


Without a previous close, the first TR is $`H_{i}-L_{i}`$. The initial ending ATR is seeded after 14 accepted sessions:


```math
ATR^{end}_{14}=\frac{1}{14}\sum_{i=1}^{14}TR_{i}.
```


Subsequent values use Wilder smoothing:


```math
ATR^{end}_{i}=\frac{13ATR^{end}_{i-1}+TR_{i}}{14},\qquad ATR^{previous}_{i}=ATR^{end}_{i-1}.
```


A gap of **at least seven calendar days between accepted sessions** clears the previous close, seed, and ATR. Warm-up restarts. This is a preserved project convention, not a universal definition of ATR. Normal weekends do not reset it; prolonged missing data can.

The first ending ATR is available on complete session 14. The first historical excursion with a usable prior ATR is on session 15. At least two valid observations are needed for a distribution's sample SD and standard error, so the calculator ordinarily needs session 16 before it can describe an ATR-normalized historical sample, assuming no resets and positive ATR.

This is **RTH ATR**, not the ATR of full overnight futures daily bars, and not ATR14 of one-minute candles. Substituting either changes the units and meaning of the normalization.

### 5.4 ATR normalization


```math
u_{i}^{ATR}=\frac{H_{i}-O_{i}}{ATR^{previous}_{i}},\qquad d_{i}^{ATR}=\frac{O_{i}-L_{i}}{ATR^{previous}_{i}}.
```


An excursion of `0.60 ATR` means 60% of the prior RTH ATR. It is a size multiple, not a 60% probability. For example, a 40-point excursion with prior ATR 80 is 0.50 ATR.

The prior ATR is essential: today's ending ATR contains today's high and low. Using it to create an at-open forecast would introduce information unavailable at that open.

ATR normalization allows a historical dimensionless excursion distribution to scale with a current known volatility measure. It can improve comparability, but it cannot guarantee stable normalized tails. ATR is smoothed and can lag abrupt changes.

## 6. Means and the original seven-session exercise

For any one side and normalization, denote its $`n`$ valid observations by $`x_{1},\ldots,x_{n}`$:


```math
\bar{x}=\frac{1}{n}\sum_{i=1}^{n}x_{i}.
```


Thus `AVG_PUV` and `AVG_PDV` are independent sample means, calculated separately in points, percentages, and ATR units. The number of eligible ATR observations can be smaller than the total number of session rows.

The original learning example was:

| Session | Open | High | Low | PUV points | PDV points |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 7700 | 7750 | 7664 | 50 | 36 |
| 2 | 7750 | 7813 | 7666 | 63 | 84 |
| 3 | 7777 | 7817 | 7717 | 40 | 60 |
| 4 | 7800 | 7833 | 7780 | 33 | 20 |
| 5 | 7785 | 7820 | 7772 | 35 | 13 |
| 6 | 7725 | 7754 | 7695 | 29 | 30 |
| 7 | 7790 | 7838 | 7732 | 48 | 58 |


```math
AVG\_PUV=298/7=42.571429\text{ points},\quad AVG\_PDV=301/7=43.000000\text{ points}.
```


| Statistic | PUV points | PDV points | PUV percentage | PDV percentage |
| --- | ---: | ---: | ---: | ---: |
| Mean | 42.571429 | 43.000000 | 0.548690% | 0.554172% |
| Sample SD | 11.844227 | 25.304809 | 0.153462 percentage points | 0.325994 percentage points |
| IID standard uncertainty of mean | 4.476697 | 9.564319 | 0.058003 percentage points | 0.123214 percentage points |

For an illustrative new open of **7,800**, the points mean levels are **7,842.571429** and **7,757.000000**. They are the projected average extreme prices under this sample's points model.

The original exercise has no close, timing, or prior ATR series. It cannot legitimately produce ATR-normalized or timing statistics. These values are an arithmetic teaching example, not measured live levels or evidence of trading performance.

## 7. Standard uncertainty and bootstrap confidence intervals

### 7.1 Sample dispersion versus precision of a mean

The sample standard deviation is:


```math
s=\sqrt{\frac{\sum_{i=1}^{n}(x_{i}-\bar{x})^{2}}{n-1}}.
```


It measures the spread of the observed sessions. The **standard uncertainty of the mean under independent, identically distributed observations** is:


```math
u_{IID}(\bar{x})=SE_{IID}=\frac{s}{\sqrt{n}}.
```


This is the project's precise interpretation of the originally requested “incertitude-type” around an average. The code names it `Mean_SE_IID` in nested statistics and `SE_IID` on a flattened mean row.

Under this model, quadrupling $`n`$ roughly halves the standard error if dispersion remains similar. It does not make the next session's excursion four times less variable. A mean estimated to within a few points can coexist with highly variable daily extremes.

The project is estimating sampling uncertainty from historical observations. It does not model separate instrument-measurement tolerances, timestamp errors, or data-vendor inaccuracies inside that standard error.

### 7.2 One standard error is not a 95% confidence interval

The displayed `MeanSE` zone uses **one IID standard error**. It is neither a 95% interval nor a prediction interval. For comparison, a conventional mean confidence interval under suitable independent normal-sample assumptions is $`\bar{x}\pm t_{0.975,n-1}s/\sqrt n`$. This t-based formula is explanatory; the current exported `CI95_*` fields use bootstrap percentiles instead. See [NIST's mean confidence-interval definition](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm).

### 7.3 Circular block bootstrap

Daily market observations can be dependent. The calculator therefore also estimates uncertainty by resampling **blocks of consecutive eligible sessions**.

The implementation draws starting positions, takes fixed-length blocks with end-to-start wraparound, concatenates enough blocks, and truncates each resample to the original number of rows. Each resample recalculates the statistic. This preserves some local dependence while breaking longer relationships. The concept is described in the [official time-series bootstrap documentation](https://arch.readthedocs.io/en/latest/bootstrap/timeseries-bootstraps.html); this project implements its own NumPy resampling and does not require the `arch` package.

For bootstrap estimates $`\hat\theta_{1}^{\ast},\ldots,\hat\theta_{B}^{\ast}`$:


```math
SE_{Block}(\hat\theta)=\sqrt{\frac{\sum_{b=1}^{B}(\hat\theta_{b}^{\ast}-\bar\theta^{\ast})^{2}}{B-1}}.
```


`CI95_Low` and `CI95_High` are the 2.5th and 97.5th percentiles of the finite bootstrap estimates. They are approximate percentile-bootstrap confidence limits for the estimator. They may be asymmetric and need not equal the estimate plus/minus 1.96 times its bootstrap SE.

Defaults are **1,000 repetitions**, requested **5-session blocks**, and base seed **731**. The calculator offsets the seed for successive cohorts. To avoid a full-sample block generating artificial zero uncertainty on tiny histories:


```math
b_{effective}=\min\left(b_{requested},\max(1,\lfloor n/3\rfloor)\right).
```


For five sessions, the default becomes one-session resampling. This is a pipeline test, not an adequate dependence model for trading research. The block length is a sensitivity choice; it is not statistically optimized by this code. Blocks refer to consecutive eligible rows, which may be separated by excluded calendar dates.

`SE_Block` need not be greater than `SE_IID`. Their difference is informative, but neither captures unknown future regime changes or all data-quality errors. More bootstrap repetitions reduce resampling noise; they do not create more market observations.

### 7.4 Which estimates receive uncertainty

The calculator bootstraps means, P10/P25/P50/P75/P90/P95, the two `MeanSE` endpoints, IQR width, P10–P90 width, timing statistics, timing-window frequencies, and the extreme-order share and ratio. Each projected price boundary receives the uncertainty of its underlying estimator, converted to points.

It recomputes the `MeanSE` endpoints inside every resample, including that resample's IID SE. The uncertainty of an endpoint is therefore not simply copied from the original mean's SE.

Zero bootstrap uncertainty can occur when resamples repeatedly yield the same discrete quantile. It means stability within those resamples, not perfect knowledge of the market. `Valid_Replicates` records how many finite estimates entered an uncertainty calculation; undefined ratios are omitted and counted separately.

## 8. Percentiles and excursion zones

### 8.1 Meaning of a percentile

For one excursion distribution, $`Q_{q}`$ denotes its sample quantile at fraction $`q`$. `P75` and `Q75` refer to the same percentile threshold, but the code uses `P75` in descriptive statistics and `Q75` as an envelope name.

The current NumPy calculation uses linear interpolation. With sorted values $`x_{(1)},\ldots,x_{(n)}`$, define $`h=(n-1)q`$, $`j=\lfloor h\rfloor`$, and $`g=h-j`$. Using zero-based sorted indices, $`Q_{q}=(1-g)x_{j}+gx_{j+1}`$, with the endpoint handled directly. This explains fractional results even when input prices are tick-aligned.

P75 is a historical threshold below which roughly 75% of the distribution lies; finite samples and ties need not yield exactly 75% observed counts. It does **not** mean price will bounce at that threshold with 75% probability.

### 8.2 Three zone definitions

| Zone | Distance interval | Center used in price export | What it describes |
| --- | --- | --- | --- |
| `MeanSE` | $`[\max(0,\bar{x}-SE_{IID}),\bar{x}+SE_{IID}]`$ | Mean | Precision-oriented region around the estimated average excursion. |
| `P25_P75` | $`[Q_{0.25},Q_{0.75}]`$ | Median, $`Q_{0.50}`$ | Middle approximately 50% of the historical excursion distribution. |
| `P10_P90` | $`[Q_{0.10},Q_{0.90}]`$ | Median, $`Q_{0.50}`$ | Middle approximately 80% of the historical excursion distribution. |

The center of a percentile zone is the median, **not necessarily the arithmetic midpoint of its edges**. The zero clamp on the lower `MeanSE` distance prevents a negative excursion distance. Upper timing endpoints are not separately clamped to the session close by the generic statistics function.

Widths are:


```math
IQR=Q_{0.75}-Q_{0.25},\qquad P10P90\_Width=Q_{0.90}-Q_{0.10}.
```


These widths describe dispersion, and their own bootstrap SEs describe uncertainty in that estimated dispersion.

### 8.3 Why the zones matter

A narrow `MeanSE` zone can become narrower as a sample grows even if tomorrow's possible extremes remain widely spread. The percentile zones address where historical individual extremes have occurred. Their future usefulness still needs calibration on later data.

Do not combine a percentile boundary with its SE by default and continue calling the result the same percentile. Adding uncertainty changes the forecast rule and requires its own evaluation.

## 9. Projecting statistics into current prices

Let $`O_{\ast}`$ be the actual open of the session being forecast. Let $`A_{\ast}`$ be the known prior RTH ATR. Define a positive scale:


```math
k=\begin{cases}1&\text{points model},\\O_{\ast}/100&\text{percentage model},\\A_{\ast}&\text{ATR model}.\end{cases}
```


For any chosen historical upside statistic $`x_{u}`$ and downside statistic $`x_{d}`$:


```math
Upper=O_{\ast}+kx_{u},\qquad Lower=O_{\ast}-kx_{d}.
```


The model uses independent upside and downside distributions. Levels need not be symmetric around the open, and the three normalizations are alternative views, not three independent pieces of evidence.

### 9.1 Correct ordering of downside zone bounds

If a distance zone is $`[a,b]`$, with $`a\le b`$:


```math
HOD\ zone=[O_{\ast}+ka,O_{\ast}+kb],
```


```math
LOD\ zone=[O_{\ast}-kb,O_{\ast}-ka].
```


Larger downside distance creates the **lower price**. This reversal is why a projected LOD zone's `Low` boundary uses the higher PDV percentile.

### 9.2 Worked price examples

Assume an illustrative open of 6,000, an upside points P25/P75 of 20/60, and downside points P25/P75 of 15/50:

- HOD `P25_P75` = **6,020–6,060**.
- LOD `P25_P75` = **5,950–5,985**.

The final HOD could finish below 6,020 or above 6,060; both miss this HOD zone. A high above 6,060 still reaches its near edge, so a “zone reached” statistic can succeed while an “extreme in zone” statistic fails.

For a percentage mean upside distance of 0.60%, the projected level is $`6000+6000(0.60/100)=6036`$. For an ATR mean upside distance of 0.50 and prior ATR 80, it is $`6000+80(0.50)=6040`$. These examples are intentionally different historical models, not a requirement that all models agree.

### 9.3 Price uncertainty and its assumptions

For a fixed supplied open and scale:


```math
SE_{price}=k\,SE_{statistic}.
```


For example, 0.03 percentage points of estimator SE at an open of 6,000 corresponds to 1.8 price points. An ATR-normalized SE of 0.04 at prior ATR 80 corresponds to 3.2 price points.

The current calculation treats $`O_{\ast}`$ and $`A_{\ast}`$ as supplied constants. It does not propagate uncertainty in the opening price or ATR model itself. If a downside confidence interval is transformed manually, reverse its endpoints: $`[a,b]`$ in distances becomes $`[O_{\ast}-kb,O_{\ast}-ka]`$ in prices.

Statistical calculations retain floating-point precision. Console prices display two decimals, but the code does not round forecasts to exchange ticks. A future order-execution implementation must specify its tick-rounding rule and evaluate its consequences.

## 10. Outer envelopes and containment

An **extreme zone** describes a region where one final high or low might occur. An **outer envelope** supplies a lower and upper boundary for the entire RTH price range.

| Envelope | Upside/downside distance statistic | Meaning |
| --- | --- | --- |
| `Mean` | Separate means | The two projected average extremes. No nominal coverage probability. |
| `MeanPlusSE` | Separate $`\bar{x}+SE_{IID}`$ distances | Uses the outward edges of the two `MeanSE` zones; the lower price is open minus the larger downside distance. |
| `Q50` | Separate P50 values | Median excursion thresholds on both sides. |
| `Q75` | Separate P75 values | 75th-percentile excursion thresholds on both sides. |
| `Q90` | Separate P90 values | 90th-percentile excursion thresholds on both sides. |
| `Q95` | Separate P95 values | 95th-percentile excursion thresholds on both sides. |

For percentile $`q`$:


```math
U_{q}=O_{\ast}+kQ_{q}^{up},\qquad L_{q}=O_{\ast}-kQ_{q}^{down}.
```


Envelope width is $`U_{q}-L_{q}=k(Q_{q}^{up}+Q_{q}^{down})`$. It is the **total width**, not the distance on each side of the open. A 160-point envelope can have an upside distance of 90 and a downside distance of 70.

### Joint probability is not a marginal percentile

RTH containment is the joint event:


```math
H_{RTH}\le U_{q}\quad\text{and}\quad L_{RTH}\ge L_{q}.
```


Even if both marginal bounds were perfectly calibrated at probability $`q`$ for the same future population, joint containment need not equal $`q`$. Its general bounds would be:


```math
\max(0,2q-1)\le P(\text{both contained})\le q.
```


Thus calibrated Q90 marginals imply a theoretical joint range of 80%–90%; calibrated Q95 marginals imply 90%–95%. Independence would give $`q^{2}`$, but **the code does not assume independence**. Historical finite-sample estimates and future regime drift mean these theoretical calibration assumptions themselves require testing.

An unusually small upside excursion can remain below the Q90 upper boundary yet fall below the P10 edge of the HOD `P10_P90` zone. Consequently, “both extremes in their P10–P90 zones” and “entire session contained by the Q90 envelope” are different metrics.

## 11. HOD and LOD timing statistics

### 11.1 Numerical representation

Clock labels are converted to minutes after 09:30:


```math
t=60\,hour+minute+second/60-570.
```


Examples: 09:30 becomes 0, 10:00 becomes 30, 12:00 becomes 150, and 16:00 becomes 390. Because these observations lie within one daytime session, ordinary linear statistics are appropriate; no averaging across midnight is involved.

The calculator uses the labels supplied in the session CSV. It does not retrospectively shift old manual labels. Newly converted labels are consistently bar-end labels; mixing those with older unverified conventions can bias timing comparisons.

### 11.2 Mean, median, and ranges

For each of HOD and LOD, the calculator provides:

- Mean time, with $`s_{t}/\sqrt n`$ IID uncertainty and bootstrap mean uncertainty, in minutes.
- Median time, with its own bootstrap uncertainty.
- P25–P75 and P10–P90 time intervals, with endpoint and width uncertainties.
- Additional P10/P25/P50/P75/P90/P95 timing estimates in detailed exports.

An average time such as 12:00 can result from many extremes near 09:30 and 15:30, with relatively few near noon. It is a center of the distribution, not automatically its most likely time. Median time means half the recorded extremes are on either side approximately; it also need not be the most frequent minute.

A calculated time such as 11:25:30 is arithmetic interpolation. It does not imply the original data contain second-level event timing. Timing SEs and widths are **durations in minutes**, not times of day.

### 11.3 Thirty-minute windows

There are 13 bins: 09:30–10:00, 10:00–10:30, through 15:30–16:00. Every bin is left-inclusive and right-exclusive except the final bin, which includes 16:00. A recorded label of exactly 10:00 belongs to **10:00–10:30**, even though its one-minute source bar may span 09:59–10:00. These are bins of recorded labels.

For window $`j`$:


```math
\hat p_{j}=\frac{\text{valid extreme labels in window }j}{\text{all valid labels for that side}},\qquad SE_{IID}(\hat p_{j})=\sqrt{\frac{\hat p_{j}(1-\hat p_{j})}{n}}.
```


Every window has a count, share, IID share SE, block SE, bootstrap confidence interval, and modal status. **All tied modes are retained.** A categorical modal window does not have a meaningful standard uncertainty of “± minutes”; its frequency uncertainty and stability are reported instead.

`Bootstrap_Mode_Inclusion_Rate` is the fraction of resamples in which the window is among the most frequent windows, including ties. It is not the probability that tomorrow's extreme occurs there. Inclusion rates can sum above 100% because several windows may tie in one resample.

### 11.4 Missing times

Invalid or outside-RTH times are marked unavailable for timing statistics. A session's valid OHLC can still participate in price statistics. `Invalid_HOD_Times` and `Invalid_LOD_Times` record the issue. A inconsistent provided `Extreme_First` value can instead trigger the loader's derived-data mismatch error. Check the audit and the actual `N` for each statistic.

## 12. Which extreme happened first

The order is determined from the first recorded occurrence of the **final** session high and low:

- `LOD_FIRST` if $`t_{LOD}<t_{HOD}`$.
- `HOD_FIRST` if $`t_{HOD}<t_{LOD}`$.
- `SAME_BAR` when both first occurrences have the same bar label.
- Missing timing pairs cannot establish order.

Let $`N_{L}`$ and $`N_{H}`$ be the known LOD-first and HOD-first counts:


```math
Ratio_{LOD/HOD}=\frac{N_{L}}{N_{H}},\qquad Share_{LOD-first}=\frac{N_{L}}{N_{L}+N_{H}}.
```


For 60 LOD-first and 40 HOD-first sessions, the ratio is **1.5**, while the LOD-first share is **60%**. A ratio of 1 means equal counts; a ratio of 1.135 is not a probability of 113.5%.

Same-bar and missing pairs are excluded from the known-order denominator and displayed separately. A zero HOD-first denominator makes the ratio undefined, represented by `null`/`None`. Bootstrap draws with that denominator are excluded from the ratio's uncertainty and counted in `Undefined_Ratio_Replicates`. The share can be easier to interpret when a ratio is unstable.

This is a retrospective sequence statistic. It does not establish that an early intraday low is already the final LOD, or that a long trade should be entered there.

## 13. Full history, recent windows, and regime change

| Cohort | Definition after date filtering | Benefit | Limitation |
| --- | --- | --- | --- |
| `All` | All eligible historical rows strictly before the forecast date | More observations and often more precise estimates | Older regimes can dominate; small SE does not remove bias for today's regime. |
| `Last60` | Latest up to 60 eligible rows | Faster response to recent behavior | Greater sampling uncertainty and noisier tail quantiles. |
| `Last252` | Latest up to 252 eligible rows | Intermediate balance | Still lags abrupt changes; 252 rows need not be exactly one calendar year. |
| `LastN` | Optional custom cohort added with `--lookback N` | User-defined research window | Not automatically selected as the console display window. |

`All` is a fixed descriptive sample for one calculation. Recomputed each day with new data, it becomes an **expanding-window estimator**. Each rolling cohort drops old observations as new ones arrive.

Rows on or after `--forecast-date` are excluded. `--start` and `--end` restrict the historical estimation dates before the windows are taken. With only five eligible sessions, all default cohorts use those five sessions and explicitly report the shortfall. They are not three independent five-session experiments.

ATR sample counts can be lower because of warm-up and resets. The program first selects cohort rows, then excludes unavailable ATR values within each distribution. It does not extend the cohort backward to obtain exactly 60 valid ATR observations.

### What adaptation does and does not solve

The project discussed concerns that downside PDV behavior can drift and that a static long-history mean may understate recent downside excursions. That is a hypothesis to assess with time-separated marginal calibration, not a universal established result of this repository. A previously quoted 35% exceedance versus a 25% target is not a fresh v4 result verified here.

Rolling windows change the estimated shape and scale of the historical distribution. ATR normalization changes its units and rescales it using known recent volatility. Both can help, but neither proves stationarity. An IV/GJR-GARCH blend was discussed as another adaptive approach; it is **not implemented** in these commands.

Comparing `All`, `Last60`, and `Last252` is descriptive. The samples overlap, so subtracting their means and treating the standard errors as independent is not a valid automatic significance test. Any formal drift test needs a defined method and attention to dependence and repeated comparisons.

## 14. How to run both commands

### 14.1 Local installation

Use Python 3.10 or later. The converter needs pandas and NumPy; the standalone calculator needs NumPy. Install timezone data where the operating system does not provide the required IANA database:

```bash
python -m pip install pandas numpy tzdata
```

Save the scripts under their actual repository filenames. An old README or embedded docstring may omit their `_v2` or `_v4` suffixes; the filename passed to Python must match the file on disk.

### 14.2 Command 1 — convert raw bars

For a raw file with Eastern start labels:

```bash
python 01_build_rth_sessions_v2.py raw_ohlcv.csv --source-timezone America/New_York --timestamp-label start --timeframe 1 --output sessions.csv --no-download
```

Use `--timestamp-label end` for actual raw end labels. Use `--timeframe 5`, `15`, or `auto` as appropriate. `--source-timezone UTC-05:00` is for a genuinely fixed offset, not a shorthand for all Eastern dates.

| Converter argument | Default | Purpose |
| --- | --- | --- |
| Positional `input_csv` | Omitted | Path to raw CSV; omitting it opens Colab upload or asks for a local path. |
| `--output` | Source stem plus `_RTH_SESSIONS.csv` | Accepted session output path. Raw input cannot be overwritten. |
| `--timeframe` | `auto` | Source interval: auto, 1, 5, or 15. |
| `--source-timezone` | `America/New_York` | Source clock before conversion to Eastern. |
| `--timestamp-label` | `start` | Whether source labels mark start or end of each bar. |
| `--date-format` | ISO/compact recognition | Explicit format, e.g. `%m/%d/%Y` or `%d/%m/%Y`. |
| `--chunksize` | `200000` | Number of source rows per read chunk; does not change the statistical formulas. |
| `--no-download` | Off | Suppress the automatic download helper. |

With an omitted file argument, the interactive flow previews source labels and asks for timezone, label convention, and interval confirmation. Slash dates trigger a date-order prompt. With a supplied file path, specify the settings yourself; do not assume an interactive confirmation will occur.

Command 1 creates the accepted CSV, an `_EXCLUDED.csv` audit, and a `_METADATA.json` settings record. If no sessions qualify, the accepted CSV contains a header but no session rows. The exclusion report explains why.

### 14.3 Command 2 — descriptive statistics only

Before the forecast day's opening price is known:

```bash
python 02_calculate_rth_levels_v4.py sessions.csv --forecast-date 2026-09-11 --stats-only --display-window Last252 --output-dir levels_2026_09_11_stats
```

This produces statistics and timing reports without price projections. The example date is explicit for reproducibility; replace it with the intended forecast date when using new data.

### 14.4 Command 2 — project levels from a known open

```bash
python 02_calculate_rth_levels_v4.py sessions.csv --forecast-date 2026-09-11 --open 6000 --display-window Last252 --output-dir levels_2026_09_11
```

**6,000 is an example, not an asserted market opening price.** Enter the actual RTH open for the date and instrument being forecast. If `--open` is omitted, the script asks for it after calculating the statistics.

The default current scale for ATR projections is the **last available pre-forecast row's `ATR14_End`**, taken from the full input before the optional estimation-date filters. This avoids using an ATR made stale merely by selecting an older research cohort. It is distinct from each historical observation's own `ATR14_Previous` used during normalization.

`--current-atr` overrides that current projection scale. It does not rewrite historical ATR-normalized observations. Use an independently verified **prior RTH ATR on the same definition and price scale**, with no forecast-session outcome included.

The calculator does not verify that the forecast day immediately follows the latest row, nor does it automatically reset this projection scale merely because the requested forecast date is far in the future. Inspect the last available date. A seven-day reset is applied when converting accepted historical rows, not by inventing intervening future rows.

### 14.5 Calculator arguments

| Argument | Default | Meaning |
| --- | --- | --- |
| Positional `session_csv` | Omitted | Completed-session CSV; opens upload/path prompt when omitted. |
| `--open` | Prompt unless stats-only | Known RTH opening price used as projection anchor. |
| `--current-atr` | Latest available pre-forecast ending ATR | Optional current prior-ATR scale override; must be positive and finite. |
| `--forecast-date` | Runtime system date | Only rows strictly earlier than this date can train the calculation. Set explicitly for reproducibility. |
| `--start` | None | Inclusive lower date filter on historical estimation rows. |
| `--end` | None | Inclusive upper date filter on historical estimation rows; never overrides the strict forecast-date exclusion. |
| `--lookback` | None | Add `LastN` to exported cohorts; at least 2. The default cohorts still run. |
| `--display-window` | `All` | Console cohort: `All`, `Last60`, or `Last252`; custom `LastN` is exported but not an accepted display choice. |
| `--bootstrap` | `1000` | Resampling repetitions; at least 100. |
| `--block-length` | `5` | Requested consecutive eligible sessions per bootstrap block; positive integer. |
| `--seed` | `731` | Base random seed; cohort offsets are applied. |
| `--stats-only` | Off | Calculate distributions/timing without current price projections. |
| `--output-dir` | Session-file stem plus `_ANALYSIS` | Output directory. Prefer a different directory for each dated run. |
| `--summary-output` | `statistical_summary.csv` in output directory | Optional alternate path for the flattened statistics. |
| `--levels-output` | `projected_zones.csv` in output directory | Optional alternate path for zones; envelopes still use their regular output filename. |
| `--timing-output` | `timing_summary.json` in output directory | Optional alternate path for timing JSON. |

### 14.6 Google Colab

There are two supported approaches: paste the **entire** standalone script into a cell, or upload the script and execute it with `%run`. Each script opens its CSV upload prompt when no input CSV path is supplied.

For uploaded scripts:

```python
# First upload the script files using Colab's Files panel.
%run 01_build_rth_sessions_v2.py
```

Then run the calculator on the converted file already in the Colab runtime:

```python
%run 02_calculate_rth_levels_v4.py sessions.csv --forecast-date 2026-09-11 --display-window Last252 --output-dir my_levels
```

Replace `sessions.csv` with the actual filename printed by Command 1. Alternatively, omit the path to select it using the calculator's upload dialog. Uploading a Python file alone does not execute it.

Command 1 attempts to download the converted CSV automatically. Command 2 **saves its files but does not automatically download every output**. Download selected calculator files explicitly:

```python
from google.colab import files
files.download('my_levels/projected_zones.csv')
files.download('my_levels/projected_envelopes.csv')
files.download('my_levels/analysis.json')
```

Both scripts strip Colab/Jupyter's injected `-f` kernel argument. The separate delivered converter notebook embeds the converter too, but that notebook was not present in the inspected GitHub snapshot.

## 15. Reading every kind of console output

The console is intentionally shorter than the CSV/JSON exports. It prints one selected history cohort while calculating all default cohorts.

| Printed item | How to read it |
| --- | --- |
| `Read ... source bars...` | Converter progress through the raw file, including non-RTH rows. It is not an accepted-session count. |
| `Converted ... complete sessions; excluded ... source dates` | Number of accepted RTH rows versus source dates rejected by the grid/quality checks. |
| `Timeframe ... expected ... bars/session` | Selected interval and its full-session count: 390, 78, or 26. |
| `ATR14 warm-up...` | Not enough uninterrupted accepted history for a prior ATR. Blank ATR values are intentional. |
| `Converted CSV`, `Exclusions`, `Settings/audit` | Locations of the three converter outputs. |
| `Calculating All / Last60 / Last252: n sessions` | Cohort row count before metric-specific missing values are excluded. |
| `Only n of the requested ... sessions are available` | Recent window is shorter than requested; results are not based on 60/252 observations merely because of its name. |
| `Small sample: bootstrap block reduced...` | Effective block length shortened by the tiny-sample safeguard. |
| `HISTORICAL TIMING` | Statistics of final extreme bar labels in the selected historical cohort. |
| `LOD/HOD average` | Mean clock time; IID and block uncertainties are standard errors of that mean in minutes. |
| `LOD/HOD median ... +/- ... min` | Median clock time and its block SE; the ± value is not a future time window. |
| `LOD/HOD P25–P75 ... endpoint SEs` | Central timing interval and separate uncertainty of each estimated boundary. |
| `LOD/HOD modal window ... % of sessions` | Most frequent recorded half-hour bin, its observed share, and share uncertainty in percentage points. All tied modes print. |
| `LOD-first/HOD-first ... block SE` | Count ratio and standard uncertainty of that ratio; dimensionless, not a percentage. |
| `POINTS LEVELS` | Statistics fitted to raw point excursions and translated to current price levels. |
| `PERCENTAGE LEVELS` | Statistics fitted to per-session open-relative percentages, then translated to **price**, not printed as percentage bounds. |
| `ATR LEVELS` | Statistics fitted to per-session prior-ATR multiples, then translated to **price** using current prior ATR. |
| `HOD MeanSE`, `HOD P25_P75`, `HOD P10_P90` | Three candidate areas for the final high, with numerically ordered price bounds. |
| `LOD MeanSE`, `LOD P25_P75`, `LOD P10_P90` | Three candidate areas for the final low; larger downward excursions produce lower prices. |
| `boundary block SE: a, b points` | Standard uncertainties of the displayed low and high price boundaries, respectively. They do not widen the zone automatically. |
| `Q90 / Q95 envelope` | Outer lower/upper price limits using the two separate marginal quantiles. Not a printed joint probability. |
| `Unavailable...` | Insufficient valid sample or current scaling input, most commonly ATR warm-up. No fabricated replacement is inserted. |
| `Files saved in...` | Analysis directory. Detailed estimates and all cohorts are there. |

For example, this **invented explanatory line**:

```text
HOD P25_P75: 6020.00–6060.00 | boundary block SE: 2.00, 4.00 points
```

means the fitted central HOD excursion zone projects to 6,020–6,060. The lower-bound estimator has a 2-point block SE and the upper-bound estimator a 4-point block SE. It does not mean a trade has a 50% win rate, nor that the boundaries are guaranteed within those errors.

The console does not print separate rows for every mean center, quantile, and envelope. **Mean centers are available in the zone export's `Center` field; Mean/Q50/Q75 envelopes and detailed P10–P95 estimates are exported even when omitted from the console.**

## 16. CSV and JSON output dictionary

### 16.1 Converter audit files

`*_EXCLUDED.csv` contains:

| Field | Meaning |
| --- | --- |
| `Date` | Rejected interpreted session date. |
| `Reasons` | One or more failed rules, separated by semicolons. |
| `Expected_Bars` | 390, 78, or 26 for the selected interval. |
| `Observed_Bars` | Number of source bars overlapping RTH, including invalid/duplicate records. |
| `Duplicate_Bars` | Extra occurrences of duplicate RTH minute labels. |
| `Missing_Bars` | Expected labels absent from the observed set. |
| `First_Missing_Labels` | Up to ten missing end labels to help diagnose the source. |

`*_METADATA.json` contains the input name and SHA-256 fingerprint, raw row count, first/last raw and converted labels, source timezone, date format and label convention, chosen timeframe and selection method, RTH definition, required counts, timing precision, complete/excluded counts, first/last accepted dates, ATR definition, number of rows with prior ATR, and methodological notes. The fingerprint identifies the exact file bytes; it does not certify that those bytes are economically correct.

### 16.2 `statistical_summary.csv`

One row represents one **cohort × model × side × metric** combination.

| Field | Meaning |
| --- | --- |
| `Cohort` | `All`, `Last60`, `Last252`, or optional `LastN`. |
| `Model` | `Points`, `Percentage`, `ATR`, or `Time`. |
| `Side` | `HOD` for upside/high timing or `LOD` for downside/low timing. |
| `Metric` | `Mean`, `P10`, `P25`, `P50`, `P75`, `P90`, `P95`, `MeanSE_Low`, `MeanSE_High`, `IQR_Width`, or `P10P90_Width`. |
| `N` | Finite observations actually used for this distribution. |
| `Value` | Estimated metric in its listed unit. |
| `Unit` | `points`, `percentage_points`, `ATR`, or `minutes_after_09:30`. |
| `Clock_Time` | Human-readable time for non-width timing estimates; blank for other models or durations. |
| `SE_IID` | $`s/\sqrt n`$ only on the `Mean` row; blank on other metrics, not zero. |
| `SE_Block` | Standard deviation of the metric's bootstrap estimates, in the same unit as `Value`. |
| `CI95_Low`, `CI95_High` | Approximate 95% bootstrap confidence limits for that metric. |
| `Valid_Replicates` | Finite bootstrap estimates used. |

For `Time` width metrics, the `Unit` label is inherited as `minutes_after_09:30`, but the number is a **duration in minutes**, not a clock offset to display as a time. The nested JSON also contains `Sample_SD` and `Mean_SE_IID`; sample SD is not a separate flattened metric row.

### 16.3 `timing_windows.csv`

Each row identifies `Cohort`, `Side`, and `Window`, with:

- `Count`: number of valid labels in that window.
- `Share`: count divided by all valid timing observations for that side, expressed as a fraction.
- `Share_SE_IID`: independent-binomial reference standard error of that fraction.
- `SE_Block`, `CI95_Low`, `CI95_High`, `Valid_Replicates`: bootstrap uncertainty of the window share.
- `Is_Mode`: whether the window ties for largest observed count.
- `Bootstrap_Mode_Inclusion_Rate`: fraction of resamples in which it is a mode, including ties.

Convert fractional probabilities and their standard errors by multiplying by 100. `Share=0.293` is 29.3%; `SE_Block=0.0074` is **0.74 percentage points**, not 0.0074%.

### 16.4 `timing_summary.json`

For each cohort and side, `Timing_Minutes_After_Open` holds `N`, `Sample_SD`, `Mean_SE_IID`, `Estimates`, `Uncertainty`, and `Clock_Estimates`. `Thirty_Minute_Windows` holds the window records, and `Modal_Windows` lists all observed modes.

`Order` contains:

| Field | Meaning |
| --- | --- |
| `LOD_First`, `HOD_First` | Counts with known strict ordering. |
| `Same_Bar` | Valid pairs with equal labels. |
| `Missing_Pair` | Sessions where at least one timing value is unavailable. |
| `Known_Order_N` | `LOD_First + HOD_First`. |
| `LOD_First_Share` | `LOD_First / Known_Order_N`. |
| `Share_SE_IID` | Binomial reference SE of that share. |
| `Share_Uncertainty` | Block SE, confidence limits, and replicate count for the share. |
| `LOD_to_HOD_Ratio` | `LOD_First / HOD_First`, when defined. |
| `Ratio_Uncertainty` | Block SE, confidence limits, and valid replicate count for the ratio. |
| `Undefined_Ratio_Replicates` | Resamples with no HOD-first observations. |

### 16.5 `projected_zones.csv`

One row represents **cohort × normalization × side × zone**. With all three default cohorts, all three models available, two sides, and three zones, there are **54 rows**.

| Field | Meaning |
| --- | --- |
| `Cohort`, `Model`, `Side`, `Zone` | Configuration identifying the forecast. |
| `N` | Historical observations for that side/model. |
| `RTH_Open` | Current price anchor supplied by the user. |
| `Previous_ATR` | Current prior ATR used for projection scaling; also recorded on other model rows as context. |
| `Center` | Projected mean for `MeanSE`; projected median for percentile zones. |
| `Low`, `High` | Numerically ordered zone prices. |
| `Center_SE_Block_Points` | Estimator uncertainty of the projected mean or median center. |
| `Low_SE_Block_Points`, `High_SE_Block_Points` | Separate estimator uncertainties of the respective price edges. |
| `Mean_SE_IID_Points` | Scaled IID SE of the underlying mean, recorded on every zone row; it is not the percentile boundary SE. |

The zone export does not include projected 95% confidence limits. Underlying native-unit bootstrap confidence limits are in the detailed statistics and can be transformed using the side-aware formulas in Section 9.

### 16.6 `projected_envelopes.csv`

One row represents **cohort × model × envelope**. Three cohorts × three models × six envelopes gives **54 rows** when all are available. If ATR is unavailable, there are ordinarily 36 default envelope rows and 36 default zone rows.

| Field | Meaning |
| --- | --- |
| `Cohort`, `Model`, `Envelope` | Forecast configuration. |
| `RTH_Open`, `Previous_ATR` | Current anchor and known prior ATR context. |
| `Lower`, `Upper` | Outer lower/upper price bounds. |
| `Width_Points` | `Upper - Lower`. |
| `Lower_SE_Block_Points`, `Upper_SE_Block_Points` | Estimator uncertainty of each outer bound. |

No column here is a measured future containment probability. Those rates require the separate walk-forward evaluation.

### 16.7 `analysis.json`

This is the complete combined record. It includes `Forecast_Date`, `Input_Audit`, all `Cohorts`, methodology text, and timing-window conventions. With projection enabled it also includes `RTH_Open`, `Previous_ATR`, `Projected_Zones`, `Projected_Envelopes`, and `Outer_Envelopes`.

`Outer_Envelopes` is the nested forecast for the **selected display cohort**, not a replacement for the all-cohort projected tables. Each available model contains `N_HOD`, `N_LOD`, `Scale`, `Envelopes`, and `Zones`. Nested envelopes include `Upper`, `Lower`, `Up_Distance`, `Down_Distance`, and `Q`; `Q` is null for non-quantile envelopes.

Each cohort records row count, first/last estimation dates, bootstrap repetitions, effective and requested block lengths, timing, and excursion descriptions.

### 16.8 Input audit interpretation

`Input_Audit` records the source filename and `SHA256`, `Rows`, `First_Date`, `Last_Date`, `Annual_Counts`, `Missing_Bar_Count_Dates`, `Bar_Timeframes_Minutes`, invalid timing counts, derived-value mismatch counts, ATR mismatch counts, `Input_Was_Sorted`, and notes.

The loader recalculates excursions from OHLC and checks populated derived columns, positive recorded ATR values, duplicate dates, OHLC consistency, permitted bar counts, duplicate-bar flags, and applicable ATR continuity/recurrence. It sorts session dates for analysis after rejecting duplicates.

**Passing the loader is not a complete re-audit of raw bars.** It inherits completeness from the CSV; blank bar counts are allowed and flagged. It does not independently rebuild every ATR seed/reset or reconstruct missing price bars. `Input_Audit.Rows` describes the original loaded file, while each cohort's dates/counts describe the actual filtered training sample.

## 17. Walk-forward calibration and backtest metrics

This section documents the **earlier separate research backtester**, whose code and report were inspected for this guide. It is not a third command currently present in the GitHub snapshot.

### 17.1 A forecast must precede its outcome

For each test date $`t`$:

1. Select eligible sessions dated strictly before $`t`$.
2. Fit each distribution using the expanding, last-60, or last-252 history.
3. Use that day's known opening price and its recorded `ATR14_Previous` to project levels.
4. Freeze those forecasts for evaluation.
5. Compare them with the completed day's high, low, close, and extreme labels.

Computing one set of levels from the full 2026 history and checking it against 2025 outcomes would leak future observations. `--forecast-date` makes a **single** calculator run historical-date safe; it does not automatically turn that run into a multi-day backtest.

The earlier backtester required 252 prior rows for `All`, exactly 60 for `Last60`, and exactly 252 for `Last252`. Its `--start` was the test-period start, unlike the calculator's historical estimation filter of the same name. Preserve the long training history in the input when evaluating from 2025 onward.

### 17.2 Exact envelope events

Let $`U,L`$ be the frozen outer bounds and $`H_{t},L_{t},C_{t}`$ the realized high, low, and close. The implementation uses a numerical tolerance of $`10^{-9}`$ points for comparisons; it is not a tradable tick buffer.

| Metric | Event / definition |
| --- | --- |
| `Contained_RTH` | $`H_{t}\le U`$ and $`L_{t}\ge L`$. The entire observed RTH range remained inside. |
| `HOD_Within_Upper` | $`H_{t}\le U`$. Upper marginal respect. |
| `LOD_Within_Lower` | $`L_{t}\ge L`$. Lower marginal respect. |
| `Close_Inside` | $`L\le C_{t}\le U`$, even if earlier prices breached. |
| `Upper_Reached` | $`H_{t}\ge U`$. Threshold reached or exceeded, not proof of a fill. |
| `Lower_Reached` | $`L_{t}\le L`$. Same interpretation for downside. |
| `Upper_Breached` | $`H_{t}>U`$. |
| `Lower_Breached` | $`L_{t}<L`$. |
| `Both_Breached` | Both strict breaches occurred during the session, with no ordering implied. |
| `Only_Upper_Breached` | Upper breach and no lower breach. |
| `Only_Lower_Breached` | Lower breach and no upper breach. |
| `Breach_Then_Close_Inside` | At least one breach occurred and final close was inside; an **unconditional fraction of all evaluated sessions**. |

At exact equality a boundary can be both reached and respected. “Reached” is therefore not the complement of “respected.” The mutually exclusive partition is: contained, only upper breached, only lower breached, both breached.

Session OHLC supports threshold comparisons but cannot establish exact touch time, gap execution, first rejection, or stop/target sequencing. “Breach then close inside” is not the conditional probability of a successful rejection trade.

### 17.3 Extreme-zone events

| Metric | Definition |
| --- | --- |
| `HOD_In_Zone` | Final high lies between the HOD zone's two edges. |
| `LOD_In_Zone` | Final low lies between the LOD zone's two edges. |
| `Both_Extremes_In_Zones` | Both previous conditions hold. |
| `HOD_Zone_Reached` | Final high reaches or exceeds the HOD zone's near edge. Passing through and ending above the far edge still counts. |
| `LOD_Zone_Reached` | Final low reaches or falls below the LOD zone's near edge. |
| `Joint_Outer_Containment` | High stays below the HOD zone's far edge and low above the LOD zone's far edge; inner edges are ignored. |

For a P10–P90 zone pair, `Joint_Outer_Containment` matches its corresponding Q90 envelope event, while `Both_Extremes_In_Zones` also imposes the inner percentile constraints.

### 17.4 Width, overshoot, and quantile loss

Wider envelopes tend to increase containment mechanically. Report width with every rate:


```math
Width=U-L,\qquad Width_{ATR}=\frac{U-L}{A_{t}}.
```


Overshoots are:


```math
Overshoot_{up}=\max(H_{t}-U,0),\qquad Overshoot_{down}=\max(L-L_{t},0).
```


`Overshoot_ATR` is their sum divided by prior ATR. `P95_Overshoot_Points` is the 95th percentile of their summed point distance across **all evaluated sessions, including zero overshoots**. It is not the 95th percentile conditional on breaches.

For a forecast quantile $`q`$, pinball loss is:


```math
\rho_{q}(e)=\max(qe,(q-1)e).
```


The backtester uses upside error $`e_{u}=H_{t}-U`$ and downside distance error $`e_{d}=L-L_{t}`$:


```math
Pinball\_Loss\_ATR=\frac{\rho_{q}(e_{u})+\rho_{q}(e_{d})}{A_{t}}.
```


Lower loss is better when comparing **the same quantile and evaluation sample**. It balances forecast magnitude and exceedances. Non-quantile Mean/MeanPlusSE envelopes have no quantile-loss value.

`Historical_Joint_Containment` is the fitted envelope's empirical joint coverage in that day's training data. `Mean_Historical_Joint_Containment` averages those training rates over test days. Neither is the observed test-period containment rate; that is the `Contained_RTH` summary's `Rate`.

### 17.5 Timing forecast metrics

| Metric | Meaning |
| --- | --- |
| `MeanSE_Hit` | Actual extreme label falls inside the training mean ± one IID SE interval, with the lower clamp. |
| `P25_P75_Hit`, `P10_P90_Hit` | Actual label falls inside the corresponding predicted historical timing interval. |
| `Modal_Window_Hit` | Actual label falls in any predicted modal half-hour bin. |
| `Mean_Absolute_Error_Minutes` | Average absolute error of the **mean-time forecast**. |
| `Median_Absolute_Error_Minutes` | Average absolute error of the **median-time forecast**; despite the name, it is not the median of absolute errors. |
| `Mean_Bias_Minutes` | Average actual minus mean-predicted time; positive means actual extremes happened later. |
| `Mean_RMSE_Minutes` | Square root of average squared mean-time forecast errors. |
| `Mean_Modal_Width_Minutes` | Average total width of predicted modal bins; tied modes expand this width. |

Daily timing records retain actual and predicted offsets, quantiles, errors, hit flags, predicted mode bins, and training mode share. Timing statistics identify final extremes retrospectively; they are not intraday alerts confirming an extreme in real time.

### 17.6 Probability uncertainty

For binary outcomes $`I_{t}`$ across $`N`$ eligible forecasts:


```math
\hat p=\frac{\sum I_{t}}{N},\qquad SE_{IID}=\sqrt{\frac{\hat p(1-\hat p)}{N}}.
```


The summaries retain `N`, `Hits`, `Rate`, `SE_IID`, `SE_Block`, bootstrap `CI95_Low/High`, and `Valid_Replicates`. They also provide `Wilson95_Low/High`, an independent-binomial interval reference. With $`z=1.95996398454`$:


```math
Wilson95=\frac{\hat p+z^{2}/(2N)\ \pm\ z\sqrt{\hat p(1-\hat p)/N+z^{2}/(4N^{2})}}{1+z^{2}/N}.
```


Wilson limits remain bounded and can be informative when all observed outcomes are identical and the empirical bootstrap gives a degenerate interval. They do not adjust for serial dependence. See [NIST's proportion confidence-interval guidance](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).

The backtest bootstrap resamples chronological **forecast outcomes with the fitted forecasts held fixed**. It does not rerun the entire training/selection pipeline inside each resample. The earlier package also evaluated 20-session blocks as an uncertainty sensitivity. Confidence intervals do not erase model-selection bias or guarantee calibration after a regime change.

### 17.7 Backtest files and filtering

The earlier package produced `daily_envelopes.csv`, `daily_extreme_zones.csv`, `daily_timing.csv`, `envelope_summary.csv`, `extreme_zone_summary.csv`, `timing_backtest_summary.csv`, `containment_block20_sensitivity.csv`, optional `skipped_forecasts.csv`, and `backtest_metadata.json`.

Daily records identify the test `Date`, `Cohort`, `Train_First`, `Train_Last`, `Train_Sessions`, `RTH_Open`, `ATR_Known_Before_Open`, and `Bar_Count_Verified`, followed by model-specific predictions and outcomes. Every fitted training end must precede its test date.

Summary rows must be filtered by **configuration, `Period`, and `Metric` together**. `Period=All` covers the actual available evaluation period; year rows split it; `VerifiedBarCounts` is a separate metadata sensitivity. The earlier implementation defines verified counts as exactly **390 bars**, so it does not automatically classify newly supported 5m/15m rows as verified. Updating that separate backtester would require an explicit compatibility review.

The word “verified” in this sensitivity means a recorded bar-count field matched, not that the entire raw feed was independently verified. Removing incomplete-metadata evaluation rows does not automatically remove them from later training histories.

## 18. Earlier research results and their limits

**These are archived reported results, not a new backtest executed while writing this README.** They come from `RTH_Level_Backtest_Report.md`, prepared 11 September 2026, and its earlier session-level research package. That report and its daily result tables are not included in the GitHub snapshot inspected here.

The reported input was `ES_RTH_Sessions_Updated_2026-09-10.csv`, containing **3,499 sessions**, 7 June 2010–10 September 2026. Its SHA-256 was:

```text
c7164de5b189a2363412d54767615bc1f9965ed66757e13fca5b12692536361a
```

Although the requested evaluation ran from 1 January 2025 through 11 September 2026, available completed evaluation rows were **2 January 2025–10 September 2026: 420 sessions**, comprising 247 in 2025 and 173 in 2026. The full-history ATR descriptive sample was 3,290 usable observations because of warm-up/reset exclusions.

The short repository README mentions 3,699 rows. The earlier report records 3,499 for its specific input. **Do not assume those are the same dataset.** Read the current file's audit and hash; no 3,699-row session CSV was present in the inspected repository to reconcile that statement.

### 18.1 Reported containment comparison

| History | Model | MeanPlusSE containment | Q90 containment | Mean Q90 width | Q95 containment | Mean Q95 width |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| All | Points | 4.3% | 43.1% | 86.2 points | 66.4% | 119.7 points |
| All | Percentage | 21.4% | 71.9% | 131.1 points | 85.7% | 176.1 points |
| All | ATR | 29.3% | 83.6% | 156.7 points | 91.2% | 197.9 points |
| Last60 | Points | 35.5% | 75.2% | 144.0 points | 85.7% | 181.2 points |
| Last60 | Percentage | 36.7% | 76.9% | 147.6 points | 85.2% | 185.9 points |
| Last60 | ATR | 35.7% | 79.0% | 150.7 points | 85.7% | 191.0 points |
| Last252 | Points | 28.8% | 75.2% | 136.8 points | 87.1% | 178.9 points |
| Last252 | Percentage | 35.0% | 79.3% | 146.1 points | 87.6% | 191.5 points |
| Last252 | ATR | 32.4% | 79.8% | 152.2 points | 89.8% | 192.4 points |

All widths above are average **total** lower-to-upper widths. Full-history ATR Q90 contained 351/420 sessions; Q95 contained 383/420. The reported approximate block 95% intervals were 78.8%–87.9% and 87.6%–94.5%, respectively, with standard uncertainties about 2.3 and 1.7 percentage points. Twenty-session blocks gave 78.6%–88.6% and 87.1%–94.8%.

These results favor ATR normalization for containment in this particular comparison, but increasing width naturally helps containment. The report also found slightly lower Q90 normalized pinball loss for rolling-252 ATR than full-history ATR, 0.18241 versus 0.18331. That small exploratory difference did not establish a universal best model.

### 18.2 Extreme zones were a different test

| Full-history ATR zone | HOD in its zone | LOD in its zone | Both in their own zones |
| --- | ---: | ---: | ---: |
| MeanSE | 1.4% | 3.1% | 0.0% |
| P25_P75 | 50.0% | 49.0% | 26.2% |
| P10_P90 | 84.0% | 79.8% | 68.1% |

The low MeanSE hit rates illustrate the conceptual problem with treating uncertainty of an average as the variability of an individual future session. The 68.1% joint P10–P90 zone hit rate is different from Q90 envelope containment of 83.6% because the zones also impose near-edge constraints.

### 18.3 Reported timing and order examples

| Full-history descriptive statistic | Earlier reported value |
| --- | --- |
| Mean LOD time | 12:02:58; IID SE 2.41 minutes; block SE 2.34 minutes |
| Mean HOD time | 12:35:12; IID SE 2.56 minutes; block SE 2.48 minutes |
| Median LOD / HOD time | 11:11:00 / 12:11:00 |
| LOD timing P25–P75 | 09:49:00–14:21:00 |
| HOD timing P25–P75 | 10:01:00–15:20:00 |
| Modal LOD / HOD window | 09:30–10:00 for both; shares 29.3% / 24.2% |
| LOD-first / HOD-first counts | 1,860 / 1,639 |
| LOD-first share and ratio | 53.2%; ratio 1.135 with block SE 0.036 |

In that report's last 60 sessions the LOD/HOD counts were 30/30, with ratio 1.000. The descriptive timing shift was substantial, but overlapping samples and uncertainty prevent treating it as an automatic formal drift test.

The walk-forward mean-time forecasts had mean absolute errors of 124.7 minutes for LOD and 135.3 minutes for HOD. Mean ± SE timing intervals caught no LODs and only two HODs in the 420 tests. A precisely estimated average time can be a poor point forecast of an individual day's extreme.

### 18.4 Conditions on those results

The earlier report explicitly noted unresolved raw-data conversion concerns, sparse early history, mixed manual/time-label conventions, and seven manually entered September evaluation rows without bar-count evidence. Its verified-count sensitivity retained 413 evaluation sessions. The subsequent converter update established explicit conventions and passed targeted tests, but **it did not reconvert and revalidate all 16 years or rerun those 420 forecasts in this documentation task**.

The data were continuous and back-adjusted. Under a within-session additive adjustment $`P'=P+c`$, point excursions can remain unchanged while open-relative percentages change because the denominator becomes $`O+c`$. Adjustments can also affect cross-session TR around rolls. Chronological date filtering does not establish that the data vintage itself was available at the historical forecast time.

The comparison involved 54 envelope configurations and previously discussed evaluation years. Walk-forward fitting helps prevent direct future-row leakage, but those years are not an untouched model-selection holdout. Reported rates do not demonstrate profitability, rejection probability, live execution quality, or prop-pass probability.

## 19. Project evolution and updates

This is a concept-and-implementation history reconstructed from the project discussion, current code, and earlier saved research. It is not a claim that every step has a separate dated Git commit.

| Phase | Addition or correction | Why it matters / current status |
| --- | --- | --- |
| Original concept | One row per RTH session, open/high/low, independent PUV and PDV | Establishes the two excursion distributions. |
| Original exercise | Seven-session CSV and arithmetic means | Demonstrates the core calculation transparently. |
| Date identification | Real `Date` alongside sequential session number | Supports updates, sorting, chronology, and historical forecasts. |
| Richer session records | RTH close, HOD/LOD times, volume | Enables TR/ATR, timing, order, and later validation. |
| Mean uncertainty | Sample SD and $`s/\sqrt n`$ | Adds precision measures without confusing them with future variation. |
| Normalization | Per-session percentage and prior-ATR excursions | Separates price-scale and volatility-scale comparisons. |
| ATR provenance | Wilder RTH definition, previous versus ending ATR, gap reset and warm-up | Avoids using today's realized volatility in its own at-open forecast. |
| Manual updates | September sessions supplied as OHLC/timing/volume rows; incomplete September 7 skipped | Preserves complete-session intent; manual fields alone do not verify bar coverage. |
| Timing statistics | Average HOD/LOD times and their uncertainty | Answers the original timing question with explicit units. |
| Extreme order | Counts, LOD-first share, and LOD/HOD ratio | Separates ratio from probability and excludes unknown order. |
| Distribution detail | Median, P25–P75, P10–P90, all half-hour frequencies | Avoids describing a broad/bimodal timing distribution only by its mean. |
| Recent comparisons | All, Last60, Last252, optional custom lookback | Makes historical drift visible, with unequal sample precision. |
| Bootstrap uncertainty | Means, quantiles, boundaries, widths, shares, ratios | Provides a second uncertainty estimate preserving short blocks of dependence. |
| Outer envelopes | Mean, MeanPlusSE, Q50/Q75/Q90/Q95 | Separates whole-range containment from final-extreme zone formation. |
| Separate research backtest | Daily earlier-history forecasts from 2025, event rates, width, overshoot, timing errors, uncertainty and sensitivity | Previously delivered research; absent from current GitHub snapshot. |
| Colab argument fix | Ignore injected `-f` kernel parameters | Prevents notebook launcher arguments breaking the CLI parser. |
| Missing-helper fix | Bundle calculator helpers into one standalone file | Removes the recurring `No module named 'rth_stats'` error for current Command 2. |
| Converter rewrite | Explicit timezone and raw start/end labels, exact RTH grid, rejection audit, metadata | Makes conversion assumptions reproducible. |
| Multi-timeframe support | 1m, 5m, 15m; reject unsupported intervals | Retains real coarse-bar counts and honest timing precision. |
| Short-sample compatibility | Permit 390/78/26 counts, continue points/percentage output without ATR, shorten tiny bootstrap blocks | Allows the five-session pipeline test without inventing ATR or artificial zero mean SE. |
| Usability and scale | Upload/download flow, chunked conversion, embedded converter notebook delivered separately | Simplifies Colab use and reduces raw-data processing memory. |
| Current documentation | Full companion README tied to a source commit | Explains what every output means and which features are outside the repository. |

The Noise Area, VWAP trend, prop evaluation, and GC stop/breakeven strategy discussions are separate trading projects. Their checkpoint rules, risk ratios, commissions, and trade statistics are not implicit Andrice Levels formulas.

## 20. Maintenance, troubleshooting, and validation

### 20.1 Adding new data correctly

The current converter converts a raw OHLCV file; it **does not merge or append an existing completed-session CSV**. For a clean full-history regeneration, supply the complete updated raw history. A future incremental updater must preserve prior close, ATR state, dates, and the definitions used in the old history.

When manually supplied sessions are introduced, do not invent `Bar_Count`, replace absent times with guesses, or use an unrelated ATR. Recompute downstream ATR fields if an earlier OHLC row changes. Fix obvious date-entry mistakes before conversion; for example, a nine-digit date is not a valid `YYYYMMDD` date.

Always identify the data's asset, contract/continuous-adjustment convention, source timezone, bar-label convention, and interval. Combining histories with different conventions can produce plausible but inconsistent levels. Session volume must represent the intended total source volume, not an unrecognized uptick-only or trade-count field.

### 20.2 Common issues

| Symptom | Meaning / action |
| --- | --- |
| `No module named 'rth_stats'` from Command 2 | An older helper-dependent script is being run. Use the full current `02_calculate_rth_levels_v4.py`, not an old cell containing the old import. |
| Unrecognized `-f` argument | Older CLI code is receiving notebook kernel arguments. The inspected versions filter these. |
| No complete sessions | Open the exclusions report and check timezone, start/end convention, selected interval, and raw coverage. |
| Many missing labels near the opening/closing boundary | Suspect a one-bar label mismatch or timezone mismatch before changing prices. |
| Input uses 30-minute or unsupported intervals | Export genuine 1m/5m/15m data. Changing a setting does not reconstruct missing intrabar information. |
| Blank ATR values in a five-session test | Expected warm-up; no 14-session ending ATR or prior normalization can yet exist. |
| ATR fields rejected as nonpositive | Recorded finite ATR must be positive for this calculator. A completely flat synthetic history can generate zero ATR and is unsuitable for ATR normalization. |
| Need at least two historical sessions | Forecast-date filtering or a short input left fewer than two eligible rows. |
| Duplicate date or inconsistent derived-data error | Correct the data rather than bypassing validation. |
| Very small or zero bootstrap SE | Could reflect discrete values or resample degeneracy; inspect sample size, quantile ties, and valid replicates. It is not proof of certainty. |
| Same statistics under all default cohorts | The available history may be shorter than both recent windows; inspect their actual sample counts. |
| Files appear unchanged or unexpected | Use a new dated output directory. Old projection files can remain after a later `--stats-only` run in the same folder. |
| No automatic calculator download | Command 2 saves files; use `files.download(...)` or the Colab Files panel. |
| Forecast based on stale data | Check the latest input date and prior ATR. The calculator does not fetch missing sessions. |

### 20.3 Tests completed before this guide

The delivered converter package passed eleven targeted automated tests covering exact output columns, synthetic OHLC/volume reconciliation, chunk boundaries, 1m/5m/15m equivalence, start/end equivalence, 30m rejection, missing stretches, duplicates/invalid data, timezone conversion across seasons, slash-date parsing, ATR recurrence/reset, and short-sample calculator compatibility. Its notebook code also ran with a simulated Colab upload/download interface; browser permissions were not exercised.

The five synthetic sessions covered **3–7 February 2025**. Their 2,700 one-minute input bars included premarket/postmarket data; each accepted RTH had 390 bars. Aggregated 5m/15m inputs retained identical session OHLC and volume while producing coarser extreme labels. The uploaded 6–10 January example yielded four complete sessions under Eastern/start assumptions; January 9 had only one overlapping RTH bar and was excluded.

The inspected GitHub converter and calculator were byte-identical to those tested standalone files. This does not imply a new full-history performance run. A one-year synthetic stress dataset and a full 16-year reconversion remained later steps. Keep synthetic data out of real calibration histories.

### 20.4 Reproducibility record

Retain the source file and fingerprint, repository commit, Python/dependency versions, timestamp settings, accepted/excluded date counts, forecast date, supplied open and prior ATR, history filters, bootstrap settings, and output files. All projections for one session should use the same frozen settings when compared with that session's later outcome.

## 21. Extensions discussed and remaining research

### 21.1 TradingView display

The desired next step is to display date-specific calculated levels directly on a chart. **Neither current Python command contains a TradingView API connection or a Pine indicator.** Providing an opening price currently calculates and exports levels; it does not plot them on TradingView despite the short README's informal wording.

A future integration needs an explicit delivery method supported by the target chart platform, a session-date identifier, asset and timezone mapping, chosen cohort/model, separate HOD/LOD zones and outer envelopes, stale-data behavior, and display rounding. Feasible API or Pine transport choices must be verified when that integration is built.

A useful display would distinguish:

- The RTH open anchor.
- HOD and LOD percentile zones with their model and cohort.
- Q90/Q95 outer boundaries.
- A small label or panel for estimator uncertainty, sample size, and timing statistics.

Showing every combination simultaneously can obscure price. A user-selected model/cohort is a presentation choice; it should not silently change the underlying historical calculation.

### 21.2 Further calibration work

Useful future metrics include conditional containment after one side is breached, breach magnitude conditional on a breach, coverage by volatility regime, side-specific calibration drift, and a held-out interval score comparing coverage with width. These should be specified before examining the new evaluation period.

Conditional intraday probabilities require conditioning variables known at the decision time. For example, “given that the upper level was reached by 10:30” cannot be tested from daily OHLC alone. Reconstruct the intraday path using appropriate bar data and acknowledge within-bar ambiguity.

Adaptive estimators such as rolling or exponentially weighted distributions, or a separately validated volatility forecast including IV/GJR-GARCH, were discussed. Their exact fitting rules, data availability, and evaluation would be new implementations. No blend weights, GARCH parameters, or superiority claims are encoded in this repository.

### 21.3 From statistical levels to a trading strategy

Before calculating trading metrics, define which event triggers an entry, whether it is a breakout or a rejection, the execution price, stop, target, time exit, allowed sessions, position size, commissions, slippage, and rules when both stop and target fall within one bar. A high containment probability can coexist with an unprofitable strategy.

Likewise, a prop-evaluation simulator needs the actual drawdown mechanism, consistency rule, profit target, costs, evaluation horizon, and chronological equity path. These are separate from the distribution-of-extremes model. The current project has no trade P&L, win rate, risk/reward optimization, or funded-account pass-rate output.

## 22. Formula reference and source map

### 22.1 Compact formula reference

| Quantity | Formula |
| --- | --- |
| PUV / PDV points | $`H-O`$ / $`O-L`$ |
| PUV / PDV percentage | $`100(H-O)/O`$ / $`100(O-L)/O`$ |
| PUV / PDV ATR | $`(H-O)/A_{previous}`$ / $`(O-L)/A_{previous}`$ |
| RTH range | $`H-L=PUV+PDV`$ |
| True range with prior close | $`\max(H-L,\lvert H-C_{previous}\rvert,\lvert L-C_{previous}\rvert)`$ |
| ATR14 seed | Mean of first 14 TRs in the accepted sequence |
| Wilder continuation | $`(13A_{previous}+TR)/14`$ |
| Sample mean | $`\sum x_{i}/n`$ |
| Sample SD | $`\sqrt{\sum(x_{i}-\bar{x})^{2}/(n-1)}`$ |
| Mean IID standard uncertainty | $`s/\sqrt n`$ |
| Block standard uncertainty | Sample SD of finite resampled estimator values |
| Bootstrap CI95 | 2.5th and 97.5th percentiles of finite resampled estimates |
| MeanSE distance bounds | $`\max(0,\bar{x}-s/\sqrt n)`$ and $`\bar{x}+s/\sqrt n`$ |
| Central distance zones | $`[Q_{.25},Q_{.75}]`$ and $`[Q_{.10},Q_{.90}]`$ |
| Upside / downside price | $`O_{\ast}+kx`$ / $`O_{\ast}-kx`$ |
| Projected boundary SE | $`kSE_{x}`$, conditional on the supplied scale |
| Timing offset | $`60h+m+s/60-570`$ minutes |
| LOD-first share | $`N_{L}/(N_{L}+N_{H})`$ |
| LOD/HOD order ratio | $`N_{L}/N_{H}`$ when $`N_{H}>0`$ |
| Event rate | $`Hits/N`$ |
| Independent event-rate SE | $`\sqrt{\hat p(1-\hat p)/N}`$ |
| Entire RTH contained | $`H_{t}\le U`$ and $`L_{t}\ge L`$ |
| Total overshoot | $`\max(H_{t}-U,0)+\max(L-L_{t},0)`$ |

### 22.2 Implementation source map

Current implementation claims were checked against these immutable source files:

- [Converter v2 at the reviewed commit](https://github.com/andricechristian/Andrice_levels-v4/blob/7eeb97f7024be248f0c0d90387d2925ed92b4fbb/01_build_rth_sessions_v2.py): `timestamps`, `detect_timeframe`, `summarize_day`, `add_atr`, `convert_file`, `download_output`, and `main`.
- [Calculator v4 at the reviewed commit](https://github.com/andricechristian/Andrice_levels-v4/blob/7eeb97f7024be248f0c0d90387d2925ed92b4fbb/02_calculate_rth_levels_v4.py): `load_sessions`, `describe`, `block_indices`, `uncertainty`, `timing_report`, `cohort_report`, `forecast`, `project_rows`, `project_envelopes`, and `main`.
- [Original short README at the reviewed commit](https://github.com/andricechristian/Andrice_levels-v4/blob/7eeb97f7024be248f0c0d90387d2925ed92b4fbb/README.md): original usage notes, supplemented and clarified here.

The history and archived numerical snapshot additionally use the earlier saved `RTH_Level_Backtest_Report.md`, `03_backtest_rth_levels.py`, and RTH Levels Research v3 README, read during preparation. These are not implied to be present in this GitHub snapshot. The current filenames, standalone behavior, multi-timeframe support, and converter conventions supersede contradictory operational instructions in those older documents.

The statistical interpretation references are linked beside the relevant explanations in Sections 7 and 17. The source of the project's precise formulas and output names is the inspected implementation; the original seven-session values were recalculated for this guide.

### 22.3 How to add this guide to the existing README

Place this file at the repository root, alongside the short `README.md`, and add:

```markdown
For the complete project explanation, formulas, output dictionary, examples,
updates, and backtest interpretation, see
[the complete Andrice Levels guide](README_ANDRICE_LEVELS_DETAILED.md).
```

When code changes, update this guide's source commit, argument tables, formula definitions, output dictionaries, and test status together. New results should carry their own data fingerprint and actual evaluation dates rather than replace a dated research snapshot without explanation.
