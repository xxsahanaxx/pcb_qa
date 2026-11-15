# Anomaly-detection grades

Localisation = one finding with the expected category that names the fault (for shorts/bridges any part on the affected net, or the net itself). Unanswered results (incomplete, unparsed, API error) count as wrong.

## By model

| Model | Results | Not answered | Detection | Beyond baseline | Category | **Localisation** | Top-1 | False alarms | Cost |
|---|---|---|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 79 | 0 | 87% | 79% | 44% | **40%** | 39% | 50% (2) | $0.968 |
| deepseek/deepseek-v4.1-flash | 79 | 27 | 66% | 64% | 32% | **29%** | 23% | 50% (2) | $4.713 |
| openai/gpt-6-luna | 79 | 0 | 99% | 71% | 30% | **26%** | 18% | 100% (2) | $0.411 |
| qwen/qwen3.8-flash | 79 | 0 | 95% | 84% | 42% | **36%** | 32% | 100% (2) | $2.169 |

## By scenario (localisation)

| Model | BridgeRandom | CapacitorMagnitudeDownRandom | CapacitorMagnitudeUpRandom | CapacitorToResistorRandom | CapacitorToleranceDownRandom | CapacitorToleranceUpRandom | GndShortRandom | PolarityFlipRandom | ResistorMagnitudeDownRandom | ResistorMagnitudeUpRandom | ResistorToCapacitorRandom | ResistorToleranceDownRandom | ResistorToleranceUpRandom | VccShortRandom |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 5/6 | 4/5 | 2/5 | 1/5 | 0/5 | 1/5 | 3/6 | 2/4 | 5/6 | 6/6 | 2/6 | 0/6 | 0/6 | 0/6 |
| deepseek/deepseek-v4.1-flash | 5/6 | 3/5 | 1/5 | 0/5 | 0/5 | 0/5 | 4/6 | 0/4 | 3/6 | 3/6 | 2/6 | 0/6 | 0/6 | 1/6 |
| openai/gpt-6-luna | 4/6 | 3/5 | 0/5 | 0/5 | 0/5 | 0/5 | 4/6 | 1/4 | 4/6 | 4/6 | 0/6 | 0/6 | 0/6 | 0/6 |
| qwen/qwen3.8-flash | 5/6 | 2/5 | 1/5 | 0/5 | 0/5 | 0/5 | 3/6 | 2/4 | 6/6 | 6/6 | 1/6 | 0/6 | 0/6 | 2/6 |

## By board (localisation)

| Model | AcornRobotElectronics | fan_controller |
|---|---|---|
| anthropic/claude-haiku-5.5 | 16/42 | 15/35 |
| deepseek/deepseek-v4.1-flash | 10/42 | 12/35 |
| openai/gpt-6-luna | 10/42 | 10/35 |
| qwen/qwen3.8-flash | 15/42 | 13/35 |
