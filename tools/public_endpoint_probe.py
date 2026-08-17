#!/usr/bin/env python3
"""Ask a Runpod hosted text model to do a real Scriptorium job, and count the parses.

The question this answers
-------------------------
Scriptorium's text steps are 41.7% of a bake (FINDINGS.md, `pg-41` baseline) and
they are the largest bucket. Moving them to a Runpod **public endpoint** -- a
model Runpod operates, billed per token, nothing to deploy -- is either a URL
swap or a rewrite, and the deciding factor is not price or quality. It is
whether the endpoint returns JSON that the existing pipeline can parse.

Home does not rely on the prompt for that. `text-transform-service`'s Ollama
client passes each transform's full JSON Schema to Ollama's ``format`` field
(`src/tts/llm.py`), which is grammar-constrained decoding: the model *cannot*
emit anything that violates the schema. No Runpod public-endpoint page documents
``response_format``, JSON mode, or guided decoding. So the risk is not "is the
model good enough" -- it is "does anything constrain the output at all".

Why it imports the real transform instead of copying it
-------------------------------------------------------
A hand-copied prompt would answer a question about a hand-copied prompt. This
imports `build_cast_mentions()`, `render_messages()` and `COMMON_FRAMING`
directly from the running text-transform-service source, so the bytes sent are
the bytes production sends, and the sampling parameters come off the same
`Transform` object.

`cast-mentions` is the transform under test because it is the highest-volume one
(20 of the 55 calls in the `pg-41` baseline) and has the strictest schema:
`additionalProperties: false`, four required fields per mention, nested arrays,
and item caps.

What counts as a clean parse
----------------------------
Not "looks like JSON". Each response goes through the pipeline's own
`_attempt_reason()`, the same function the service uses, which returns a reason
string on failure. That distinguishes three outcomes the summary keeps apart,
because they are different findings:

  invalid JSON     the text is not JSON at all
  schema: ...      it parsed but violates the output schema
  validator        it parsed and validated but broke a transform rule

Credentials never appear anywhere: see `tools/runpod_http.py`.

    ./public_endpoint_probe.py --no-call                  # dry run, free
    ./public_endpoint_probe.py --calls 10                 # the measurement
    ./public_endpoint_probe.py --calls 10 --response-format
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import runpod_http as R  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
TTS_ROOT = Path("/home/kb/Desktop/projects/text-transform-service")
PAGES = Path.home() / "scriptorium-data" / "work" / "pg-41" / "pages"
OUT_DIR = REPO / "runs" / "public-endpoint"

# The endpoint slug and the model id are TWO DIFFERENT THINGS, and Runpod's
# reference page lists them in one column as though they were one. `kimi-k2.6`
# is a model you name in the request body; the endpoint that serves it is
# `moonshot-kimi`. Passing the model id as a slug returns 404.
#
# Cycle 2 recorded seven text endpoints from the docs. Live, as of this cycle:
#   moonshot-kimi   200  -> kimi-k2.6, kimi-k2.7-code, kimi-k3
#   qwen3-32b-awq   200  -> Qwen/Qwen3-32B-AWQ  (owned_by vllm)
#   cogito-671b-v2-1-fp8-dynamic, qwen3-32b, granite-4   all 404
DEFAULT_SLUG = "moonshot-kimi"
DEFAULT_MODEL = "kimi-k2.6"
BASE = "https://api.runpod.ai/v2/{slug}/openai/v1/chat/completions"


def load_tts():
    """Import the real transform machinery from text-transform-service.

    Its venv is used when present because `tts.pipeline` imports httpx, which is
    not needed here but is imported at module scope.
    """
    src = TTS_ROOT / "src"
    if not src.is_dir():
        raise SystemExit(f"text-transform-service not found at {TTS_ROOT}")
    sys.path.insert(0, str(src))

    venv_sp = sorted((TTS_ROOT / ".venv" / "lib").glob("python3.*/site-packages"))
    if venv_sp:
        sys.path.append(str(venv_sp[-1]))

    try:
        from tts.pipeline import COMMON_FRAMING, _attempt_reason, render_messages
        from tts.transforms.cast_mentions import build_cast_mentions
    except ImportError as exc:
        raise SystemExit(
            f"could not import the real transform ({exc}). "
            f"Run with {TTS_ROOT}/.venv/bin/python."
        ) from None
    return build_cast_mentions(), render_messages, _attempt_reason, COMMON_FRAMING


def balance() -> float:
    """clientBalance to full precision. runpodctl reads its own credential file."""
    out = subprocess.run(["runpodctl", "user"], capture_output=True, text=True).stdout
    return json.loads(out)["clientBalance"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slug", default=DEFAULT_SLUG,
                    help="the ENDPOINT slug in the URL (not the model id)")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help="the model id sent in the request body")
    ap.add_argument("--price-in", type=float, default=0.95,
                    help="$ per 1M input tokens, for the full-run extrapolation")
    ap.add_argument("--price-out", type=float, default=4.00,
                    help="$ per 1M output tokens; equal to --price-in for a "
                         "blended rate")
    ap.add_argument("--calls", type=int, default=10)
    ap.add_argument("--omit-sampling", action="store_true",
                    help="send neither temperature nor top_p. Required for "
                         "moonshot-kimi, which returns an opaque HTTP 500 when "
                         "either is present -- see FINDINGS.md")
    ap.add_argument("--no-call", action="store_true",
                    help="render and print the prompt; send nothing, spend nothing")
    ap.add_argument("--response-format", action="store_true",
                    help="also send response_format:{type:json_schema} -- undocumented "
                         "for public endpoints; the point is to find out")
    ap.add_argument("--tag", default=None, help="label for the saved run directory")
    args = ap.parse_args()

    transform, render_messages, attempt_reason, framing = load_tts()

    pages = sorted(PAGES.glob("*.json"))[: args.calls]
    if len(pages) < args.calls:
        raise SystemExit(f"only {len(pages)} pages under {PAGES}")

    print(f"transform   {transform.name} v{transform.version}")
    print(f"home model  {transform.model}  (temp {transform.temperature}, "
          f"top_p {transform.top_p}, num_predict {transform.num_predict})")
    print(f"endpoint    {args.slug}  serving model id {args.model}")
    print(f"price       ${args.price_in}/1M in, ${args.price_out}/1M out")
    print(f"pages       {len(pages)}: {pages[0].stem}..{pages[-1].stem}")
    print(f"schema      enforced at home via Ollama `format`; "
          f"response_format {'SENT' if args.response_format else 'not sent'}")
    print()

    if args.no_call:
        msgs = render_messages(transform.template, json.loads(pages[0].read_text())["text"], {})
        print("--- system ---");  print(msgs[0]["content"])
        print("--- user (truncated) ---"); print(msgs[1]["content"][:1200], "...")
        print("\n--- output schema ---")
        print(json.dumps(transform.output_schema)[:600], "...")
        print("\nno call made, nothing spent")
        return 0

    url = BASE.format(slug=args.slug)
    tag = args.tag or ("respfmt" if args.response_format else "plain")
    run_dir = OUT_DIR / f"{args.slug}-{args.model.replace('/', '_')}-{tag}"
    run_dir.mkdir(parents=True, exist_ok=True)

    b_before = balance()
    print(f"clientBalance before  ${b_before:.10f}\n")

    results = []
    for path in pages:
        page = json.loads(path.read_text())
        msgs = render_messages(transform.template, page["text"], {})

        body = {
            "model": args.model,
            "messages": msgs,
            "max_tokens": transform.num_predict,
        }
        if not args.omit_sampling:
            # Match home's sampling so the comparison is about the endpoint,
            # not about decoding settings. Not always possible: see
            # --omit-sampling.
            body["temperature"] = transform.temperature
            body["top_p"] = transform.top_p
        if args.response_format:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "cast_mentions",
                    "strict": True,
                    "schema": transform.output_schema,
                },
            }

        resp = R.post(url, body, timeout=300)
        rec: dict = {"page": path.stem, "status": resp.status, "seconds": resp.seconds}

        raw = None
        if resp.status == 200:
            try:
                payload = resp.json
                choice = payload["choices"][0]
                raw = choice["message"]["content"]
                rec["finish_reason"] = choice.get("finish_reason")
                rec["usage"] = payload.get("usage")
                rec["reported_cost"] = payload.get("cost")
                # Reasoning models spend the output budget thinking before they
                # emit any content. On a fixed num_predict that can truncate the
                # JSON, which looks like a parse failure but is a budget
                # failure -- a different finding, so it is counted separately.
                reasoning = choice["message"].get("reasoning_content") or ""
                rec["reasoning_chars"] = len(reasoning)
            except (KeyError, IndexError, ValueError, TypeError) as exc:
                rec["envelope_error"] = f"{type(exc).__name__}: {exc}"
        else:
            rec["body"] = resp.body[:500]

        if raw is not None:
            output, reason, warnings = attempt_reason(transform, raw, {})
            rec["clean"] = reason is None
            rec["reason"] = reason
            rec["warnings"] = warnings
            rec["mentions"] = len(output.get("mentions", [])) if output else None
            rec["raw_chars"] = len(raw)
            (run_dir / f"{path.stem}.raw.txt").write_text(R.redact(raw))
        else:
            rec["clean"] = False
            rec["reason"] = rec.get("envelope_error") or f"HTTP {resp.status}"

        results.append(rec)
        flag = "ok  " if rec["clean"] else "FAIL"
        print(f"{flag} {path.stem}  {resp.status}  {resp.seconds:6.2f}s  "
              f"{('%d mentions' % rec['mentions']) if rec.get('mentions') is not None else ''}"
              f"{('  ' + str(rec['reason'])[:90]) if rec['reason'] else ''}")

    # Cost accounting, and a correction worth stating in the code.
    #
    # This originally read the balance, waited for it to stop moving, and
    # reported the delta as the cost. That is WRONG: Runpod's balance lags
    # charges by several minutes -- longer than any settle loop worth waiting
    # through -- so an early read reports a fraction of the real spend and a
    # "stable" reading is not a settled one. It produced a confident claim that
    # this account was billed 3.26x under list price. It is not.
    #
    # The endpoint's own `cost` field is exact: it equals total_tokens x the
    # published rate, verified on both models. So that is the number used, and
    # the balance is reported alongside only as a lagging cross-check.
    reported_total = sum(r.get("reported_cost") or 0 for r in results)
    time.sleep(45)
    b_after = balance()

    clean = sum(1 for r in results if r["clean"])
    lat = sorted(r["seconds"] for r in results)
    median = lat[len(lat) // 2] if lat else 0.0
    in_tok = sum((r.get("usage") or {}).get("prompt_tokens", 0) or 0 for r in results)
    out_tok = sum((r.get("usage") or {}).get("completion_tokens", 0) or 0 for r in results)

    # Extrapolate one whole pg-41 bake. The measured baseline is 55 text calls:
    # 20 cast-mentions, 20 scene-update, 9 illustration-prompt, 6
    # cast-canonicalize (FINDINGS.md, Cycle 2). Scaling cast-mentions' measured
    # tokens to all 55 is an OVER-estimate: cast-mentions carries the largest
    # num_predict (700) of the four, so the other three return less.
    PG41_TEXT_CALLS = 55
    per_in = in_tok / len(results) if results else 0
    per_out = out_tok / len(results) if results else 0
    full_in = per_in * PG41_TEXT_CALLS
    full_out = per_out * PG41_TEXT_CALLS
    full_cost = full_in * args.price_in / 1e6 + full_out * args.price_out / 1e6

    summary = {
        "endpoint_slug": args.slug,
        "model": args.model,
        "price_per_1m_in": args.price_in,
        "price_per_1m_out": args.price_out,
        "response_format_sent": args.response_format,
        "transform": f"{transform.name} v{transform.version}",
        "calls": len(results),
        "clean_parses": clean,
        "latency_median_s": round(median, 3),
        "latency_min_s": round(lat[0], 3) if lat else None,
        "latency_max_s": round(lat[-1], 3) if lat else None,
        "prompt_tokens": in_tok,
        "completion_tokens": out_tok,
        "cost_usd_reported": round(reported_total, 6),
        "balance_before": b_before,
        "balance_after_45s": b_after,
        "balance_delta_45s": round(b_before - b_after, 10),
        "balance_note": "the balance lags charges by minutes; cost_usd_reported "
                        "is the authoritative figure",
        "pg41_extrapolation": {
            "text_calls": PG41_TEXT_CALLS,
            "basis": "cast-mentions measured here, scaled to all 55 calls; an "
                     "over-estimate because cast-mentions has the largest "
                     "num_predict of the four transforms",
            "input_tokens": round(full_in),
            "output_tokens": round(full_out),
            "cost_usd": round(full_cost, 6),
        },
        "results": results,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\nclean parses          {clean}/{len(results)}")
    print(f"latency median        {median:.3f}s  (min {lat[0]:.3f}, max {lat[-1]:.3f})")
    print(f"tokens                {in_tok} in, {out_tok} out")
    print(f"cost (endpoint-reported, authoritative)  ${reported_total:.6f}")
    print(f"clientBalance +45s    ${b_after:.10f}  "
          f"(delta ${b_before - b_after:.10f}, LAGGING -- not the cost)")
    print(f"\none full pg-41 bake, extrapolated ({PG41_TEXT_CALLS} text calls):")
    print(f"  {round(full_in)} in + {round(full_out)} out tokens  ->  ${full_cost:.4f}")
    print("  over-estimate: cast-mentions has the largest num_predict of the four")
    print(f"\nsaved {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
