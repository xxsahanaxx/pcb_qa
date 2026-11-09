# Anomaly-detection grades

Localisation = one finding with the expected category that names the fault (for shorts/bridges any part on the affected net, or the net itself). Unanswered results (incomplete, unparsed, API error) count as wrong.

## By model

| Model | Results | Not answered | Detection | Beyond baseline | Category | **Localisation** | Top-1 | False alarms | Cost |
|---|---|---|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 36 | 0 | 71% | 60% | 46% | **46%** | 46% | 100% (1) | $0.168 |
| deepseek/deepseek-v4.1-flash | 36 | 12 | 63% | 40% | 40% | **37%** | 31% | 100% (1) | $1.671 |
| openai/gpt-6-luna | 38 | 0 | 100% | 31% | 28% | **25%** | 22% | 50% (2) | $0.126 |
| qwen/qwen3.8-flash | 36 | 0 | 94% | 94% | 40% | **40%** | 40% | 0% (1) | $0.533 |

## By scenario (localisation)

| Model | BridgeRandom | CapacitorMagnitudeDownRandom | CapacitorMagnitudeUpRandom | CapacitorToResistorRandom | CapacitorToleranceDownRandom | CapacitorToleranceUpRandom | GndShortRandom | PolarityFlipRandom | ResistorMagnitudeDownRandom | ResistorMagnitudeUpRandom | ResistorToCapacitorRandom | ResistorToleranceDownRandom | ResistorToleranceUpRandom | VccShortRandom |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 2/3 | 2/2 | 2/2 | 0/2 | 0/2 | 0/2 | 2/3 | 1/1 | 3/3 | 3/3 | 1/3 | 0/3 | 0/3 | 0/3 |
| deepseek/deepseek-v4.1-flash | 3/3 | 2/2 | 0/2 | 0/2 | 0/2 | 0/2 | 3/3 | 1/1 | 2/3 | 1/3 | 1/3 | 0/3 | 0/3 | 0/3 |
| openai/gpt-6-luna | 1/3 | 1/2 | 0/2 | 0/2 | 0/2 | 0/2 | 3/4 | 0/1 | 1/3 | 1/3 | 1/3 | 0/3 | 0/3 | 1/3 |
| qwen/qwen3.8-flash | 2/3 | 1/2 | 0/2 | 0/2 | 0/2 | 0/2 | 1/3 | 1/1 | 3/3 | 2/3 | 2/3 | 0/3 | 0/3 | 2/3 |

## By board (localisation)

| Model | CF-Chef | fan_controller |
|---|---|---|
| anthropic/claude-haiku-5.5 | – | 16/35 |
| deepseek/deepseek-v4.1-flash | – | 13/35 |
| openai/gpt-6-luna | 1/1 | 8/35 |
| qwen/qwen3.8-flash | – | 14/35 |
