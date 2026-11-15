# Anomaly-detection grades

Localisation = one finding with the expected category that names the fault (for shorts/bridges any part on the affected net, or the net itself). Unanswered results (incomplete, unparsed, API error) count as wrong.

## By model

| Model | Results | Not answered | Detection | Beyond baseline | Category | **Localisation** | Top-1 | False alarms | Cost |
|---|---|---|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 324 | 1 | 85% | 81% | 52% | **49%** | 45% | 62% (8) | $19.610 |
| deepseek/deepseek-v4.1-flash | 324 | 89 | 71% | 67% | 39% | **38%** | 32% | 38% (8) | $16.836 |
| openai/gpt-6-luna | 324 | 18 | 87% | 69% | 36% | **34%** | 31% | 75% (8) | $3.333 |
| qwen/qwen3.8-flash | 324 | 6 | 89% | 79% | 45% | **44%** | 41% | 62% (8) | $8.329 |

## By scenario (localisation)

| Model | BridgeRandom | CapacitorMagnitudeDownRandom | CapacitorMagnitudeUpRandom | CapacitorToResistorRandom | CapacitorToleranceDownRandom | CapacitorToleranceUpRandom | GndShortRandom | PolarityFlipRandom | ResistorMagnitudeDownRandom | ResistorMagnitudeUpRandom | ResistorToCapacitorRandom | ResistorToleranceDownRandom | ResistorToleranceUpRandom | VccShortRandom |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 15/24 | 20/23 | 21/23 | 1/23 | 1/23 | 3/23 | 18/24 | 9/14 | 22/23 | 23/23 | 14/23 | 0/23 | 6/23 | 3/24 |
| deepseek/deepseek-v4.1-flash | 15/24 | 16/23 | 16/23 | 0/23 | 0/23 | 0/23 | 17/24 | 5/14 | 15/23 | 17/23 | 11/23 | 0/23 | 1/23 | 6/24 |
| openai/gpt-6-luna | 15/24 | 13/23 | 12/23 | 1/23 | 0/23 | 0/23 | 15/24 | 4/14 | 15/23 | 15/23 | 7/23 | 0/23 | 1/23 | 10/24 |
| qwen/qwen3.8-flash | 20/24 | 16/23 | 15/23 | 4/23 | 0/23 | 0/23 | 15/24 | 6/14 | 19/23 | 19/23 | 12/23 | 0/23 | 2/23 | 11/24 |

## By board (localisation)

| Model | AcornRobotElectronics | CF-Chef | HadesFCS | Meshinger | OPNhydro-r2 | PortalHardware | fan_controller | stack-chan |
|---|---|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 19/42 | 23/41 | 16/42 | 14/34 | 25/42 | 24/39 | 16/35 | 19/41 |
| deepseek/deepseek-v4.1-flash | 12/42 | 18/41 | 8/42 | 13/34 | 15/42 | 19/39 | 13/35 | 21/41 |
| openai/gpt-6-luna | 9/42 | 20/41 | 2/42 | 14/34 | 11/42 | 23/39 | 8/35 | 21/41 |
| qwen/qwen3.8-flash | 11/42 | 22/41 | 6/42 | 13/34 | 24/42 | 23/39 | 14/35 | 26/41 |
