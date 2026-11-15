# Renamed fault-free controls vs the RQ1 base arm

Generated 2026-11-15 by `netlist_modifications/scripts/compare_renamed_controls.py`. Arm: `base (non-condensed)`.

- Renamed arm: 1296 result(s) over 8 board(s) — AcornRobotElectronics, CF-Chef, HadesFCS, Meshinger, OPNhydro-r2, PortalHardware, fan_controller, stack-chan.
- RQ1 base arm: 1296 result(s) over 8 board(s) — AcornRobotElectronics, CF-Chef, HadesFCS, Meshinger, OPNhydro-r2, PortalHardware, fan_controller, stack-chan.

Every prompt in the renamed arm is the clean board with components renumbered and nets relabelled, so its ground truth is `anomaly: false` throughout. A model that reports an anomaly there is raising a false alarm on a board that carries no fault.


## 1. Renamed controls alone

All-negative by construction, so recall, F1, MCC and balanced accuracy are undefined and left blank. Specificity is the whole result.

| Model | Flagged an anomaly | Specificity | Unanswered |
|---|---|---|---|
| `anthropic/claude-haiku-5.5` | 226/324 = 70% | 0.302 | 4 |
| `deepseek/deepseek-v4.1-flash` | 166/324 = 51% | 0.488 | 134 |
| `openai/gpt-6-luna` | 259/324 = 80% | 0.201 | 13 |
| `qwen/qwen3.8-flash` | 214/324 = 66% | 0.340 | 20 |
| `POOLED` | 865/1296 = 67% | 0.333 | 171 |

## 2. Against RQ1's own clean controls

The like-for-like question: does renaming alone provoke false alarms beyond what the untouched clean board already provokes? RQ1 carries one `Control` per board, so its column rests on very few decisions — which is precisely the gap this arm fills.

| Model | RQ1 clean control | Renamed control |
|---|---|---|
| `anthropic/claude-haiku-5.5` | 5/8 = 62% | 226/324 = 70% |
| `deepseek/deepseek-v4.1-flash` | 3/8 = 38% | 166/324 = 51% |
| `openai/gpt-6-luna` | 6/8 = 75% | 259/324 = 80% |
| `qwen/qwen3.8-flash` | 5/8 = 62% | 214/324 = 66% |
| `POOLED` | 19/32 = 59% | 865/1296 = 67% |

## 3. Combined binary classification

RQ1's faulty prompts as positives, the renamed controls as negatives — a balanced problem, where RQ1 on its own is almost entirely positives. Caveat: the positives keep their original identifiers while the negatives are renamed, so class and naming regime are not fully separated. Table 2 bounds how much that can matter.

| Model | TP | FN | FP | TN | Recall | Specificity | Precision | F1 | Bal. acc | MCC |
|---|---|---|---|---|---|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | 269 | 47 | 226 | 98 | 0.851 | 0.302 | 0.543 | 0.663 | 0.577 | 0.184 |
| `deepseek/deepseek-v4.1-flash` | 223 | 93 | 166 | 158 | 0.706 | 0.488 | 0.573 | 0.633 | 0.597 | 0.198 |
| `openai/gpt-6-luna` | 274 | 42 | 259 | 65 | 0.867 | 0.201 | 0.514 | 0.645 | 0.534 | 0.091 |
| `qwen/qwen3.8-flash` | 281 | 35 | 214 | 110 | 0.889 | 0.340 | 0.568 | 0.693 | 0.614 | 0.273 |
| `POOLED` | 1047 | 217 | 865 | 431 | 0.828 | 0.333 | 0.548 | 0.659 | 0.580 | 0.185 |

## 4. Combined, answered results only

The same, dropping results the model never returned (truncated at the token ceiling, unparseable, or an API error). The grader keeps those as "no anomaly", which credits a model for silence when it merely ran out of room, so this is the stricter reading.

| Model | TP | FN | FP | TN | Recall | Specificity | Precision | F1 | Bal. acc | MCC |
|---|---|---|---|---|---|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | 269 | 46 | 226 | 94 | 0.854 | 0.294 | 0.543 | 0.664 | 0.574 | 0.178 |
| `deepseek/deepseek-v4.1-flash` | 223 | 9 | 166 | 24 | 0.961 | 0.126 | 0.573 | 0.718 | 0.544 | 0.162 |
| `openai/gpt-6-luna` | 274 | 24 | 259 | 52 | 0.919 | 0.167 | 0.514 | 0.659 | 0.543 | 0.131 |
| `qwen/qwen3.8-flash` | 281 | 29 | 214 | 90 | 0.906 | 0.296 | 0.568 | 0.698 | 0.601 | 0.256 |
| `POOLED` | 1047 | 108 | 865 | 260 | 0.906 | 0.231 | 0.548 | 0.683 | 0.569 | 0.187 |

## 5. Renamed controls by board

Board size dominates the effect, so the pooled figures above should not be read as a single per-model property.

| Model | AcornRobotElectronics | CF-Chef | HadesFCS | Meshinger | OPNhydro-r2 | PortalHardware | fan_controller | stack-chan |
|---|---|---|---|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | 43/43 = 100% | 8/42 = 19% | 43/43 = 100% | 35/35 = 100% | 34/43 = 79% | 27/40 = 68% | 13/36 = 36% | 23/42 = 55% |
| `deepseek/deepseek-v4.1-flash` | 36/43 = 84% | 10/42 = 24% | 34/43 = 79% | 19/35 = 54% | 15/43 = 35% | 20/40 = 50% | 17/36 = 47% | 15/42 = 36% |
| `openai/gpt-6-luna` | 40/43 = 93% | 11/42 = 26% | 43/43 = 100% | 33/35 = 94% | 28/43 = 65% | 36/40 = 90% | 36/36 = 100% | 32/42 = 76% |
| `qwen/qwen3.8-flash` | 43/43 = 100% | 17/42 = 40% | 43/43 = 100% | 32/35 = 91% | 18/43 = 42% | 29/40 = 72% | 24/36 = 67% | 8/42 = 19% |
| `POOLED` | 162/172 = 94% | 46/168 = 27% | 163/172 = 95% | 119/140 = 85% | 95/172 = 55% | 112/160 = 70% | 90/144 = 62% | 78/168 = 46% |

## Reading these numbers

- Balanced accuracy of 0.500 and MCC of 0.000 are chance. A model that flags every board scores high recall and near-zero specificity, and the combined table is what separates the two.

- Unanswered results are scored as "no anomaly" in tables 1–3, matching `grade_anomaly_results.py`, which keeps them in every denominator. Where a model truncates often, compare table 3 against table 4 before quoting its specificity.

- Full per-decision rows: `outputs/Infected/Prompts/AnomalyDetection/RQ1_RenamedControls/grades.csv` and `outputs/Infected/Prompts/AnomalyDetection/RQ1_SimpleMods/grades.csv`.

