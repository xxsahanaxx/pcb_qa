#!/usr/bin/env python3
"""
Run the anomaly-detection prompts (built by netlist_modifications/scripts/build_anomaly_prompts.py)
through one or more models on OpenRouter, saving each response together with
the run's metadata.

One result file per (model, prompt), inside the prompt's own folder at
``<prompts-root>/<Board>/<anomaly>/results/<model>.json``, holding:

- ``response``: the model's raw text, the parsed JSON verdict (or the parse
  error), and the finish reason;
- ``usage``: prompt / completion / reasoning / cached / total tokens and the
  cost in USD, as OpenRouter reports them on the response;
- ``generation``: OpenRouter's per-generation record (provider, native token
  counts, total cost, latency, generation time, cache discount, ...), fetched
  from ``/generation`` after the call;
- ``timing``: start / end timestamps and wall-clock latency;
- ``request``: model, temperature, max tokens, reasoning settings;
- ``prompt``: paths, character count and SHA-256 of the rendered prompt, so a
  result can be tied to the exact input;
- ``raw_response``: the complete, unfiltered response dump.

``<prompts-root>/run_summary.json`` holds, per model, totals of tokens, cost and
failures over every saved result for that model, recomputed after each run so
it stays correct across resumed runs. The answer key is never read here.

Run from the repo root:
    .venv/bin/python netlist_modifications/scripts/run_anomaly_prompts.py [--models a/x,b/y]
        [--ids CF-Chef/GndShortRandom_Wire1,...] [--boards CF-Chef,...] [--limit N]
        [--jobs 4] [--max-tokens N] [--reasoning-effort low|medium|high]
        [--overwrite] [--retry-errors] [--dry-run]
"""

import argparse
import concurrent.futures
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys
import time

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

from netlist_modifications.scripts.build_anomaly_prompts import DEFAULT_OUT, render  # noqa: E402

CHARS_PER_TOKEN = 3.5  # rough, tokenizer-independent estimate for --dry-run

# Default model set for this benchmark (OpenRouter ids): fast/low-cost tier,
# closed and open weights, every one with context for the largest prompt (~151k)
DEFAULT_MODELS = [
    "openai/gpt-6-luna",
    "anthropic/claude-haiku-5.5",
    "qwen/qwen3.8-flash",
    "deepseek/deepseek-v4.1-flash",
    "z-ai/glm-5.3-flash",
    "meta-llama/llama-4-scout",
    "google/gemma-4-31b-it",
    "minimax/minimax-m3.1-flash",
]
GENERATION_RETRIES = 6  # /generation can lag the completion by a few seconds


def model_slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "__", model)


def result_path(root: str, model: str, pid: str) -> str:
    return os.path.join(root, pid, "results", f"{model_slug(model)}.json")


# --------------------------------------------------------------------------- #
# Response handling
# --------------------------------------------------------------------------- #

def parse_verdict(text: str):
    """(parsed JSON verdict, error) from the model's text; tolerates code fences
    and prose around the object."""
    if not text:
        return None, "empty response"
    body = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    try:
        return json.loads(body), None
    except json.JSONDecodeError:
        pass
    start, end = body.find("{"), body.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(body[start:end + 1]), None
        except json.JSONDecodeError as exc:
            return None, f"invalid JSON: {exc}"
    return None, "no JSON object in response"


def usage_of(raw: dict) -> dict:
    """Token counts and cost from an OpenRouter chat-completion dump."""
    u = raw.get("usage") or {}
    pdet = u.get("prompt_tokens_details") or {}
    cdet = u.get("completion_tokens_details") or {}
    return {
        "prompt_tokens": u.get("prompt_tokens"),
        "completion_tokens": u.get("completion_tokens"),
        "reasoning_tokens": cdet.get("reasoning_tokens"),
        "cached_tokens": pdet.get("cached_tokens"),
        "total_tokens": u.get("total_tokens"),
        "cost_usd": u.get("cost"),
        "cost_details": u.get("cost_details"),
    }


def fetch_generation(base_url: str, api_key: str, gen_id: str) -> dict:
    """OpenRouter's stored record for one generation, or {"error": ...}."""
    url = f"{base_url.rstrip('/')}/generation"
    last = None
    for attempt in range(GENERATION_RETRIES):
        try:
            r = requests.get(url, params={"id": gen_id},
                             headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
            if r.status_code == 200:
                return r.json().get("data", r.json())
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        except requests.RequestException as exc:
            last = repr(exc)
        time.sleep(1.5 * (attempt + 1))
    return {"error": last}


# --------------------------------------------------------------------------- #
# One call
# --------------------------------------------------------------------------- #

def run_one(client, base_url: str, api_key: str, model: str, row: dict, args) -> dict:
    prompt = render(row["prompt"])
    request = {"model": model, "temperature": args.temperature,
               "max_tokens": args.max_tokens, "reasoning_effort": args.reasoning_effort}
    extra_body = {"usage": {"include": True}}
    if args.reasoning_effort:
        extra_body["reasoning"] = {"effort": args.reasoning_effort}

    record = {
        "id": row["id"], "model": model, "request": request,
        "prompt": {"prompt": row["prompt"], "netlist": row["netlist"],
                   "spice_circuit": row["spice_circuit"], "chars": len(prompt),
                   "sha256": hashlib.sha256(prompt.encode()).hexdigest()},
    }
    started = dt.datetime.now(dt.timezone.utc)
    t0 = time.monotonic()
    try:
        kwargs = {"model": model, "temperature": args.temperature,
                  "messages": [{"role": "user", "content": prompt}], "extra_body": extra_body}
        if args.max_tokens:
            kwargs["max_tokens"] = args.max_tokens
        resp = client.chat.completions.create(**kwargs)
    except Exception as exc:  # noqa: BLE001 -- saved, so the run carries on
        record.update({"error": repr(exc), "timing": {
            "started_at": started.isoformat(),
            "ended_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "latency_s": round(time.monotonic() - t0, 3)}})
        return record
    latency = time.monotonic() - t0
    raw = resp.model_dump()

    choice = (raw.get("choices") or [{}])[0]
    text = (choice.get("message") or {}).get("content") or ""
    verdict, parse_error = parse_verdict(text)
    record.update({
        "response": {"text": text, "parsed": verdict, "parse_error": parse_error,
                     "finish_reason": choice.get("finish_reason"),
                     "reasoning": (choice.get("message") or {}).get("reasoning")},
        "usage": usage_of(raw),
        "timing": {"started_at": started.isoformat(),
                   "ended_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "latency_s": round(latency, 3)},
        "provider": raw.get("provider"),
        "generation": fetch_generation(base_url, api_key, raw["id"]) if raw.get("id") else None,
        "raw_response": raw,
    })
    return record


# --------------------------------------------------------------------------- #
# Summaries
# --------------------------------------------------------------------------- #

def summarise(root: str, model: str) -> dict:
    """Totals over every saved result for `model` under `root` (so resumes stay correct)."""
    tot = {"results": 0, "errors": 0, "parse_errors": 0, "prompt_tokens": 0,
           "completion_tokens": 0, "reasoning_tokens": 0, "cached_tokens": 0,
           "total_tokens": 0, "cost_usd": 0.0, "latency_s": 0.0}
    for path in sorted(glob.glob(os.path.join(root, "*", "*", "results",
                                              f"{model_slug(model)}.json"))):
        with open(path) as f:
            rec = json.load(f)
        tot["results"] += 1
        if rec.get("error"):
            tot["errors"] += 1
            continue
        if rec.get("response", {}).get("parse_error"):
            tot["parse_errors"] += 1
        u = rec.get("usage") or {}
        gen = rec.get("generation") or {}
        for k in ("prompt_tokens", "completion_tokens", "reasoning_tokens",
                  "cached_tokens", "total_tokens"):
            tot[k] += u.get(k) or 0
        # prefer the usage cost; fall back to the generation record's
        tot["cost_usd"] += u.get("cost_usd") or gen.get("total_cost") or 0.0
        tot["latency_s"] += (rec.get("timing") or {}).get("latency_s") or 0.0
    tot["cost_usd"] = round(tot["cost_usd"], 6)
    tot["latency_s"] = round(tot["latency_s"], 1)
    tot["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    return tot


def model_pricing(base_url: str, model: str):
    """(USD per prompt token, per completion token) from OpenRouter's public
    model list, or None."""
    try:
        r = requests.get(f"{base_url.rstrip('/')}/models", timeout=30)
        for m in r.json().get("data", []):
            if m.get("id") == model:
                p = m.get("pricing") or {}
                return float(p.get("prompt", 0)), float(p.get("completion", 0))
    except (requests.RequestException, ValueError):
        pass
    return None


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--models", default=",".join(DEFAULT_MODELS),
                   help="Comma list of OpenRouter model ids (default: the 8 in DEFAULT_MODELS)")
    p.add_argument("--root", default=DEFAULT_OUT, help=f"Prompts root (default: {DEFAULT_OUT})")
    p.add_argument("--ids", help="Comma list of prompt ids, <Board>/<Scenario>_<Variant> or <Board>/Control (default: all)")
    p.add_argument("--boards", help="Comma list of boards to keep")
    p.add_argument("--limit", type=int, help="Run at most N prompts per model")
    p.add_argument("--jobs", type=int, default=4, help="Parallel requests (default: 4)")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max-tokens", type=int, help="Completion token cap (default: model's)")
    p.add_argument("--timeout", type=float, default=1800,
                   help="Seconds to wait for one response (default: 1800). Long reasoners "
                        "can exceed the client's 600 s default, which abandons the answer")
    p.add_argument("--max-retries", type=int, default=0,
                   help="Automatic retries per call (default: 0). A retry after a timeout "
                        "re-runs, and may re-bill, the whole generation; prefer --retry-errors")
    p.add_argument("--reasoning-effort", choices=["low", "medium", "high"],
                   help="Ask reasoning models for this effort (OpenRouter `reasoning`)")
    p.add_argument("--overwrite", action="store_true", help="Re-run prompts that have results")
    p.add_argument("--retry-errors", action="store_true",
                   help="Re-run prompts whose saved result is an API error")
    p.add_argument("--dry-run", action="store_true",
                   help="Estimate tokens (and cost, from OpenRouter pricing) without calling")
    args = p.parse_args(argv)

    os.chdir(REPO_ROOT)
    with open(os.path.join(args.root, "prompts.jsonl")) as f:
        rows = [json.loads(line) for line in f]
    if args.ids:
        want = set(args.ids.split(","))
        rows = [r for r in rows if r["id"] in want]
    if args.boards:
        want = set(args.boards.split(","))
        rows = [r for r in rows if r["id"].split("/", 1)[0] in want]
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    from pcb_qa.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL

    for model in models:
        todo = []
        for row in rows:
            out = result_path(args.root, model, row["id"])
            if os.path.exists(out) and not args.overwrite:
                if not args.retry_errors:
                    continue
                with open(out) as f:
                    if not json.load(f).get("error"):
                        continue
            todo.append(row)
        if args.limit:
            todo = todo[: args.limit]

        if args.dry_run:
            est = sum(len(render(r["prompt"])) for r in todo) / CHARS_PER_TOKEN
            line = f"{model}: {len(todo)} prompt(s), ~{est / 1e6:.2f}M input tokens"
            price = model_pricing(OPENROUTER_BASE_URL, model)
            if price:
                line += f", ~${est * price[0]:.2f} input cost (output and reasoning extra)"
            print(line)
            continue

        if not OPENROUTER_API_KEY:
            print("error: OPENROUTER_API_KEY is not set", file=sys.stderr)
            return 2
        from pcb_qa.config import get_openai_client
        client = get_openai_client().with_options(timeout=args.timeout,
                                                  max_retries=args.max_retries)

        print(f"{model}: {len(todo)} prompt(s) to run", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
            futs = {ex.submit(run_one, client, OPENROUTER_BASE_URL, OPENROUTER_API_KEY,
                              model, row, args): row for row in todo}
            for i, fut in enumerate(concurrent.futures.as_completed(futs), 1):
                rec = fut.result()
                out = result_path(args.root, model, rec["id"])
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with open(out, "w") as f:
                    json.dump(rec, f, indent=2)
                u = rec.get("usage") or {}
                status = ("ERROR " + rec["error"][:80]) if rec.get("error") else (
                    f"in={u.get('prompt_tokens')} out={u.get('completion_tokens')} "
                    f"cost=${u.get('cost_usd')}"
                    + (" PARSE-ERROR" if rec["response"]["parse_error"] else ""))
                print(f"[{i}/{len(todo)}] {rec['id']}: {status}", flush=True)

        summary_path = os.path.join(args.root, "run_summary.json")
        summaries = {}
        if os.path.exists(summary_path):
            with open(summary_path) as f:
                summaries = json.load(f)
        summary = summaries[model] = summarise(args.root, model)
        with open(summary_path, "w") as f:
            json.dump(summaries, f, indent=2)
        print(f"{model}: {summary['results']} result(s), {summary['errors']} error(s), "
              f"{summary['total_tokens']:,} tokens, ${summary['cost_usd']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
