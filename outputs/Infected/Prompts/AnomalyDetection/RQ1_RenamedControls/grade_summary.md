# Anomaly-detection grades

Localisation = one finding with the expected category that names the fault (for shorts/bridges any part on the affected net, or the net itself). Unanswered results (incomplete, unparsed, API error) count as wrong.

## By model

| Model | Results | Not answered | Detection | Beyond baseline | Category | **Localisation** | Top-1 | False alarms | Cost |
|---|---|---|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 79 | 0 | – | – | – | **–** | – | 71% (79) | $8.855 |
| deepseek/deepseek-v4.1-flash | 79 | 23 | – | – | – | **–** | – | 67% (79) | $5.847 |
| openai/gpt-6-luna | 79 | 0 | – | – | – | **–** | – | 96% (79) | $1.181 |
| qwen/qwen3.8-flash | 79 | 1 | – | – | – | **–** | – | 85% (79) | $3.290 |

## By scenario (localisation)

| Model | RenamedControl |
|---|---|
| anthropic/claude-haiku-5.5 | – |
| deepseek/deepseek-v4.1-flash | – |
| openai/gpt-6-luna | – |
| qwen/qwen3.8-flash | – |

## By board (localisation)

| Model | AcornRobotElectronics | fan_controller |
|---|---|---|
| anthropic/claude-haiku-5.5 | – | – |
| deepseek/deepseek-v4.1-flash | – | – |
| openai/gpt-6-luna | – | – |
| qwen/qwen3.8-flash | – | – |
