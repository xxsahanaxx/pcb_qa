# Anomaly-detection grades

Localisation = one finding with the expected category that names the fault (for shorts/bridges any part on the affected net, or the net itself). Unanswered results (incomplete, unparsed, API error) count as wrong.

## By model

| Model | Results | Not answered | Detection | Beyond baseline | Category | **Localisation** | Top-1 | False alarms | Cost |
|---|---|---|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 324 | 4 | – | – | – | **–** | – | 70% (324) | $23.186 |
| deepseek/deepseek-v4.1-flash | 324 | 134 | – | – | – | **–** | – | 51% (324) | $19.410 |
| openai/gpt-6-luna | 324 | 13 | – | – | – | **–** | – | 80% (324) | $3.466 |
| qwen/qwen3.8-flash | 324 | 20 | – | – | – | **–** | – | 66% (324) | $12.123 |

## By scenario (localisation)

| Model | RenamedControl |
|---|---|
| anthropic/claude-haiku-5.5 | – |
| deepseek/deepseek-v4.1-flash | – |
| openai/gpt-6-luna | – |
| qwen/qwen3.8-flash | – |

## By board (localisation)

| Model | AcornRobotElectronics | CF-Chef | HadesFCS | Meshinger | OPNhydro-r2 | PortalHardware | fan_controller | stack-chan |
|---|---|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | – | – | – | – | – | – | – | – |
| deepseek/deepseek-v4.1-flash | – | – | – | – | – | – | – | – |
| openai/gpt-6-luna | – | – | – | – | – | – | – | – |
| qwen/qwen3.8-flash | – | – | – | – | – | – | – | – |
