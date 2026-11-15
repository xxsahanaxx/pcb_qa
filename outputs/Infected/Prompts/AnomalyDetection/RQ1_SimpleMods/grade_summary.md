# Anomaly-detection grades

Localisation = one finding with the expected category that names the fault (for shorts/bridges any part on the affected net, or the net itself). Unanswered results (incomplete, unparsed, API error) count as wrong.

## By model

| Model | Results | Not answered | Detection | Beyond baseline | Category | **Localisation** | Top-1 | False alarms | Cost |
|---|---|---|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 79 | 0 | 87% | 82% | 48% | **46%** | 39% | 100% (2) | $8.450 |
| deepseek/deepseek-v4.1-flash | 79 | 22 | 71% | 61% | 36% | **32%** | 23% | 50% (2) | $4.710 |
| openai/gpt-6-luna | 81 | 0 | 99% | 59% | 28% | **23%** | 19% | 67% (3) | $1.190 |
| qwen/qwen3.8-flash | 79 | 1 | 96% | 91% | 35% | **32%** | 27% | 50% (2) | $2.388 |

## By scenario (localisation)

| Model | BridgeRandom | CapacitorMagnitudeDownRandom | CapacitorMagnitudeUpRandom | CapacitorToResistorRandom | CapacitorToleranceDownRandom | CapacitorToleranceUpRandom | GndShortRandom | PolarityFlipRandom | ResistorMagnitudeDownRandom | ResistorMagnitudeUpRandom | ResistorToCapacitorRandom | ResistorToleranceDownRandom | ResistorToleranceUpRandom | VccShortRandom |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 4/6 | 5/5 | 4/5 | 0/5 | 0/5 | 1/5 | 4/6 | 2/4 | 6/6 | 6/6 | 1/6 | 0/6 | 1/6 | 1/6 |
| deepseek/deepseek-v4.1-flash | 5/6 | 4/5 | 1/5 | 0/5 | 0/5 | 0/5 | 6/6 | 1/4 | 3/6 | 4/6 | 1/6 | 0/6 | 0/6 | 0/6 |
| openai/gpt-6-luna | 2/6 | 3/5 | 0/5 | 0/5 | 0/5 | 0/5 | 5/7 | 0/4 | 3/6 | 3/6 | 1/6 | 0/6 | 0/6 | 1/6 |
| qwen/qwen3.8-flash | 4/6 | 3/5 | 1/5 | 0/5 | 0/5 | 0/5 | 2/6 | 1/4 | 5/6 | 4/6 | 2/6 | 0/6 | 0/6 | 3/6 |

## By board (localisation)

| Model | AcornRobotElectronics | CF-Chef | fan_controller |
|---|---|---|---|
| anthropic/claude-haiku-5.5 | 19/42 | – | 16/35 |
| deepseek/deepseek-v4.1-flash | 12/42 | – | 13/35 |
| openai/gpt-6-luna | 9/42 | 1/1 | 8/35 |
| qwen/qwen3.8-flash | 11/42 | – | 14/35 |
