#!/usr/bin/env python3
"""Attribute one Scriptorium bake's wall-clock time to where it actually went.

Reads system logs and the bake's own artifacts. Changes nothing, and does not
touch Scriptorium's source at all — this exists specifically so the app under
measurement stays unmodified.

Four buckets that sum to wall clock:

    text steps + image rendering + model loading + orchestration = wall

Model loading is physically *nested* inside the other two (a model load happens
during the request that triggered it), so it is carved out of them rather than
added on top. Both views are reported.

Where each number comes from
----------------------------
wall
    The job record's ``created_at`` -> ``updated_at``, or the driver's own
    external stamps when a run log is supplied.

text steps
    text-transform-service logs one JSON line per request to the journal with a
    ``latency_ms`` field. Sum it over the four transforms Scriptorium calls,
    inside the job's window.

image rendering
    ComfyUI logs ``Prompt executed in N seconds``. Those lines are *paired*
    one-to-one against the ``render.at`` timestamps Scriptorium writes into its
    own artifacts. Pairing rather than summing is load-bearing: ComfyUI serves
    other projects on this machine and its log cannot tell them apart.

model loading
    Neither service reports it separately, so it is differenced out.
    - Ollama: ``latency_ms`` *includes* the model load, because the service
      starts its timer before calling ``ensure_loaded``. A cold request is
      therefore a warm request plus the load. Subtract the warm median of the
      same transform.
    - SDXL: ``Prompt executed in N`` also includes the load. A render is cold if
      a ``Requested to load SDXL`` line falls inside its execution interval.
      Two classes, which behave very differently: a full reload after the
      orchestrator frees the GPU, and an incidental re-stage when ComfyUI
      evicts the model under video-memory pressure.

orchestration
    What is left: HTTP round trips, artifact writes, image derivative
    generation, the runner's sleep between phases, and retry backoff.

Usage
-----
    ./bake_timing.py --book-id pg-932
    ./bake_timing.py --book-id pg-932 --snapshot-dir runs/pg-932
    ./bake_timing.py --book-id pg-75201 --pad-seconds -900   # negative control
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION = 1

DEFAULT_DATA_ROOT = Path("/home/kb/scriptorium-data")

TTS_UNIT = "text-transform-service"
COMFY_UNIT = "comfyui"
IMAGEGEN_UNIT = "imagegen-service"

# The four transforms Scriptorium calls. Anything else in the window belongs to
# another project sharing these services, and its presence is a contamination
# warning rather than something to add up.
SCRIPTORIUM_TRANSFORMS = (
    "cast-mentions",
    "cast-canonicalize",
    "scene-update",
    "illustration-prompt",
)

# text-transform-service holds an Ollama model for this long after last use.
OLLAMA_KEEP_ALIVE_S = 300.0

# Scriptorium's runner sleeps this long between phase advances.
RUNNER_TICK_S = 5.0

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_RE_EXECUTED = re.compile(r"Prompt executed in ([\d.]+) seconds")
_RE_LOAD_SDXL = re.compile(r"Requested to load SDXL\b")
_RE_FREE = re.compile(r"Using RAM pressure cache")


# --------------------------------------------------------------------------
# journal reading
# --------------------------------------------------------------------------


def _decode_message(raw) -> str:
    """journald hands back a byte array when a line contains control codes.

    ComfyUI's progress bars emit ANSI colour and carriage returns, so its
    MESSAGE field arrives as a list of ints rather than a string.
    """
    if isinstance(raw, list):
        raw = bytes(raw).decode("utf-8", "replace")
    elif raw is None:
        raw = ""
    return _ANSI.sub("", str(raw)).replace("\r", "")


@dataclass
class JournalLine:
    at: datetime  # tz-aware UTC
    message: str


def read_journal(
    unit: str,
    start: datetime,
    end: datetime,
    snapshot_dir: Path | None = None,
) -> list[JournalLine]:
    """Journal lines for `unit` between `start` and `end`, as tz-aware UTC.

    Reads a snapshot file if one was captured, so re-analysis never depends on
    journald retention. `journalctl --since/--until` parse in *local* time, so
    the UTC bounds are converted on the way in.
    """
    if snapshot_dir is not None:
        path = snapshot_dir / f"{unit}.json"
        if not path.exists():
            raise SystemExit(f"snapshot missing: {path}")
        raw = path.read_text(errors="replace")
    else:
        cmd = [
            "journalctl",
            "-u",
            unit,
            "--since",
            start.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
            "--until",
            end.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
            "-o",
            "json",
            "--no-pager",
        ]
        raw = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        ).stdout

    lines: list[JournalLine] = []
    for row in raw.splitlines():
        row = row.strip()
        if not row:
            continue
        try:
            entry = json.loads(row)
        except json.JSONDecodeError:
            continue
        stamp = entry.get("__REALTIME_TIMESTAMP")
        if stamp is None:
            continue
        at = datetime.fromtimestamp(int(stamp) / 1e6, timezone.utc)
        if not (start <= at <= end):
            continue
        lines.append(JournalLine(at=at, message=_decode_message(entry.get("MESSAGE"))))
    lines.sort(key=lambda x: x.at)
    return lines


# --------------------------------------------------------------------------
# text steps
# --------------------------------------------------------------------------


@dataclass
class TextCall:
    at: datetime  # when the response was logged
    transform: str | None
    status: int
    latency_s: float | None

    @property
    def started(self) -> datetime:
        return self.at - timedelta(seconds=self.latency_s or 0.0)


def parse_text_calls(lines: list[JournalLine]) -> list[TextCall]:
    """The service's structured request log. Non-JSON lines are uvicorn noise.

    A failed request logs a status and an error code but *no* latency, because
    the service only attaches its timing metadata on the success path. Those
    seconds are real but unmeasurable, so they are counted and reported rather
    than silently folded into the residual.
    """
    calls: list[TextCall] = []
    for line in lines:
        msg = line.message.strip()
        if not msg.startswith("{"):
            continue
        try:
            rec = json.loads(msg)
        except json.JSONDecodeError:
            continue
        if "request_id" not in rec:
            continue
        latency_ms = rec.get("latency_ms")
        at = rec.get("ts")
        calls.append(
            TextCall(
                at=datetime.fromisoformat(at).astimezone(timezone.utc)
                if at
                else line.at,
                transform=rec.get("transform"),
                status=int(rec.get("status", 0)),
                latency_s=(latency_ms / 1000.0) if latency_ms is not None else None,
            )
        )
    calls.sort(key=lambda c: c.at)
    return calls


def ollama_load_seconds(calls: list[TextCall]) -> tuple[float, int]:
    """How much of the text time was actually loading the model.

    A request is cold if the orchestrator evicted the model beforehand, or if
    enough idle time passed for Ollama to drop it. The load is not reported
    anywhere, so it is estimated as the cold request's excess over the warm
    median for the same transform. That assumes generation cost is stable within
    a transform, which holds here because the prompts are structurally alike.
    """
    ok = [c for c in calls if c.status == 200 and c.latency_s is not None]
    warm_median: dict[str, float] = {}
    for name in SCRIPTORIUM_TRANSFORMS:
        vals = [c.latency_s for c in ok if c.transform == name]
        if len(vals) >= 3:
            # Drop the top decile before taking the median so a cold outlier
            # cannot drag the baseline it is being compared against.
            vals = sorted(vals)[: max(1, int(len(vals) * 0.9))]
            warm_median[name] = statistics.median(vals)

    total = 0.0
    cold_count = 0
    unloaded_since_last = True  # nothing is resident before the first call
    prev_end: datetime | None = None

    for call in calls:
        if call.transform is None:
            # An unload request. The service logs it on the same middleware
            # path, with a null transform — a free marker.
            unloaded_since_last = True
            continue
        if call.status != 200 or call.latency_s is None:
            continue
        idle_cold = (
            prev_end is not None
            and (call.started - prev_end).total_seconds() > OLLAMA_KEEP_ALIVE_S
        )
        if unloaded_since_last or idle_cold:
            baseline = warm_median.get(call.transform)
            if baseline is not None:
                total += max(0.0, call.latency_s - baseline)
                cold_count += 1
        unloaded_since_last = False
        prev_end = call.at

    return total, cold_count


# --------------------------------------------------------------------------
# image rendering
# --------------------------------------------------------------------------


@dataclass
class Render:
    end: datetime
    duration_s: float
    cold: bool = False
    after_free: bool = False
    claimed_by: str | None = None


def parse_renders(lines: list[JournalLine]) -> tuple[list[Render], list[datetime]]:
    """ComfyUI's completed prompts, plus the moments the GPU was freed.

    `Prompt executed in N seconds` includes any model load that happened inside
    it. A `Requested to load SDXL` line landing in that interval marks the
    render as cold. `Using RAM pressure cache` is what ComfyUI prints when the
    orchestrator calls its /free endpoint, which distinguishes a deliberate
    phase-boundary reload from an incidental one.
    """
    loads: list[datetime] = []
    frees: list[datetime] = []
    renders: list[Render] = []

    for line in lines:
        if _RE_LOAD_SDXL.search(line.message):
            loads.append(line.at)
            continue
        if _RE_FREE.search(line.message):
            frees.append(line.at)
            continue
        m = _RE_EXECUTED.search(line.message)
        if m:
            duration = float(m.group(1))
            renders.append(Render(end=line.at, duration_s=duration))

    # A load lands *inside* the render that paid for it, but a free happens in
    # the gap *before* the next render starts — so the two need different tests.
    renders.sort(key=lambda r: r.end)
    prev_end: datetime | None = None
    for render in renders:
        start = render.end - timedelta(seconds=render.duration_s)
        render.cold = any(start <= t <= render.end for t in loads)
        floor = prev_end if prev_end is not None else datetime.min.replace(
            tzinfo=timezone.utc
        )
        render.after_free = any(floor < t < start for t in frees)
        prev_end = render.end

    return renders, frees


def union_seconds(intervals: list[tuple[datetime, datetime]]) -> float:
    """Seconds during which at least one interval was open.

    Overlapping renders are counted once, because a wall clock only runs once.
    Disjoint intervals sum exactly, so a serial bake is unaffected.
    """
    total = 0.0
    end: datetime | None = None
    for start, stop in sorted(intervals):
        if end is None or start > end:
            total += (stop - start).total_seconds()
            end = stop
        elif stop > end:
            total += (stop - end).total_seconds()
            end = stop
    return round(total, 2)


def pair_renders(renders: list[Render], render_ats: list[tuple[str, datetime]]) -> None:
    """Claim one ComfyUI prompt per plate Scriptorium recorded rendering.

    ComfyUI does not log a prompt id and does not know which client sent a job,
    so attribution runs the other way: each plate's own `render.at` timestamp
    claims the most recent unclaimed prompt that finished at or before it.
    Anything left unclaimed belongs to something else on this machine.
    """
    for plate_id, at in sorted(render_ats, key=lambda x: x[1]):
        best: Render | None = None
        for render in renders:
            if render.claimed_by is not None or render.end > at:
                continue
            if best is None or render.end > best.end:
                best = render
        if best is not None:
            best.claimed_by = plate_id


def sdxl_load_seconds(matched: list[Render]) -> tuple[float, dict]:
    """Split the image model's load cost into its two very different classes."""
    warm = [r.duration_s for r in matched if not r.cold]
    warm_median = statistics.median(warm) if warm else 0.0

    full_cold = [r for r in matched if r.cold and r.after_free]
    restage = [r for r in matched if r.cold and not r.after_free]

    def penalty(group: list[Render]) -> float:
        if not group:
            return 0.0
        return max(0.0, statistics.median(r.duration_s for r in group) - warm_median)

    full_pen = penalty(full_cold)
    restage_pen = penalty(restage)
    total = len(full_cold) * full_pen + len(restage) * restage_pen

    detail = {
        "warm_render_median_s": round(warm_median, 3),
        "warm_render_count": len(warm),
        "full_cold_after_free": {
            "n": len(full_cold),
            "penalty_s": round(full_pen, 3),
            "total_s": round(len(full_cold) * full_pen, 2),
        },
        "intra_phase_restage": {
            "n": len(restage),
            "penalty_s": round(restage_pen, 3),
            "total_s": round(len(restage) * restage_pen, 2),
        },
    }
    return total, detail


# --------------------------------------------------------------------------
# artifacts
# --------------------------------------------------------------------------


@dataclass
class Artifacts:
    render_ats: list[tuple[str, datetime]] = field(default_factory=list)
    reattempted: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    plates_selected: int | None = None
    # Per-plate durations the RENDERER reported about itself, from
    # `render.params_echo` (ADR-0038). Present only for backends that report them
    # -- the Runpod worker does; the local imagegen-service does not.
    self_reported: dict[str, dict] = field(default_factory=dict)


def read_artifacts(work: Path) -> Artifacts:
    out = Artifacts()
    prompts = work / "prompts"
    if prompts.is_dir():
        for path in sorted(prompts.glob("*.json")):
            try:
                doc = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            render = doc.get("render") or {}
            at = render.get("at")
            if at:
                out.render_ats.append(
                    (path.stem, datetime.fromisoformat(at).astimezone(timezone.utc))
                )
            if (render.get("attempts") or 1) > 1:
                out.reattempted += 1
            echo = render.get("params_echo") or {}
            if echo.get("render_s") is not None:
                out.self_reported[path.stem] = {
                    "render_s": echo.get("render_s"),
                    "model_load_s": echo.get("model_load_s"),
                    "total_s": echo.get("total_s"),
                    "gpu": echo.get("gpu"),
                }

    for label, rel in (
        ("cast-mentions", "mentions"),
        ("scene-update", "ledgers"),
        ("cast-canonicalize", "cast/canon"),
    ):
        d = work / rel
        out.counts[label] = len(list(d.glob("*.json"))) if d.is_dir() else 0

    selection = work / "selection.json"
    if selection.is_file():
        try:
            doc = json.loads(selection.read_text())
            plates = doc.get("plates") or doc.get("choices") or []
            out.plates_selected = len(plates)
        except (json.JSONDecodeError, OSError):
            pass
    return out


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------


def fmt(seconds: float) -> str:
    seconds = max(0.0, seconds)
    m, s = divmod(int(round(seconds)), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"


def build_report(result: dict) -> str:
    b = result["buckets"]
    wall = result["wall_s"]
    rows = [
        ("Text steps", b["text_steps_s"]),
        ("Image rendering", b["image_rendering_s"]),
        ("Model loading", b["model_loading_s"]),
        ("Orchestration", b["orchestration_s"]),
    ]
    rows.sort(key=lambda r: -r[1])

    out = [
        f"## Bake timing — {result['book_id']}",
        "",
        f"Wall clock {fmt(wall)} · gate wait {fmt(result['gates']['total_s'])} "
        f"· machine time {fmt(result['machine_time_s'])}",
        "",
        "| Bucket | Time | Share |",
        "|---|---:|---:|",
    ]
    for label, value in rows:
        share = (value / wall * 100) if wall else 0.0
        out.append(f"| {label} | {fmt(value)} | {share:.1f}% |")
    out.append(f"| **Total** | **{fmt(wall)}** | **100%** |")

    md = result["model_loading_detail"]
    out += [
        "",
        f"Model loading: image model {md['sdxl_s']:.1f}s, "
        f"text model {md['ollama_s']:.1f}s ({md['ollama_cold_requests']} cold requests).",
        "",
    ]
    # A remote renderer reports its own load time and has no local journal, so the
    # two local-ComfyUI breakdowns below simply do not exist for it. Absent is the
    # correct answer here, not zero, and not a traceback.
    fc = md["sdxl"].get("full_cold_after_free")
    rs = md["sdxl"].get("intra_phase_restage")
    if fc:
        out.append(
            f"- Deliberate reload after the orchestrator freed the GPU: "
            f"{fc['n']} × {fc['penalty_s']:.2f}s = {fc['total_s']:.1f}s"
        )
    if rs:
        out.append(
            f"- Incidental re-stage under video-memory pressure: "
            f"{rs['n']} × {rs['penalty_s']:.2f}s = {rs['total_s']:.1f}s"
        )
    out += [
        f"- Warm render median: {md['sdxl']['warm_render_median_s']:.2f}s "
        f"(n={md['sdxl']['warm_render_count']})",
        "",
        "Integrity: "
        + " · ".join(
            [
                f"{result['image_detail']['renders_matched']}/"
                f"{result['image_detail']['renders_in_window']} renders attributed",
                f"{result['text_detail']['calls_counted']} text calls",
                f"residual {b['orchestration_s'] / wall * 100:.1f}%"
                if wall
                else "residual n/a",
                "counts match artifacts"
                if result["integrity"]["counts_match_artifacts"]
                else "**COUNT MISMATCH**",
            ]
        ),
    ]
    if result["integrity"]["warnings"]:
        out.append("")
        for w in result["integrity"]["warnings"]:
            out.append(f"> ⚠️ {w}")
    return "\n".join(out)


# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book-id", required=True)
    ap.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    ap.add_argument(
        "--pad-seconds",
        type=float,
        default=120.0,
        help="widen the journal window either side; a negative value widens it "
        "far enough to pull in foreign traffic, which is the negative control",
    )
    ap.add_argument("--snapshot-dir", type=Path, default=None)
    ap.add_argument("--run-log", type=Path, default=None, help="driver's run log")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()

    job_path = args.data_root / "jobs" / f"{args.book_id}.json"
    if not job_path.is_file():
        raise SystemExit(f"no job record at {job_path}")
    job = json.loads(job_path.read_text())

    window_source = "job_record"
    start = datetime.fromisoformat(job["created_at"]).astimezone(timezone.utc)
    end = datetime.fromisoformat(job["updated_at"]).astimezone(timezone.utc)
    gates = {"cast_s": 0.0, "approve_s": 0.0, "total_s": 0.0, "source": "absent"}
    transition_times: list[datetime] = []

    if args.run_log and args.run_log.is_file():
        run = json.loads(args.run_log.read_text())
        start = datetime.fromisoformat(run["t_start"]).astimezone(timezone.utc)
        end = datetime.fromisoformat(run["t_end"]).astimezone(timezone.utc)
        window_source = "driver"
        gates = {**run.get("gates", gates), "source": "driver"}
        transition_times = [
            datetime.fromisoformat(t["at"]).astimezone(timezone.utc)
            for t in run.get("transitions", [])
            if t.get("at")
        ]

    pad = timedelta(seconds=abs(args.pad_seconds))
    # A negative pad is the deliberate contamination control: widen far enough
    # to swallow neighbouring work and confirm the integrity checks fail loudly.
    q_start, q_end = start - pad, end + pad
    if args.pad_seconds < 0:
        start, end = q_start, q_end

    wall = (end - start).total_seconds()

    tts_lines = read_journal(TTS_UNIT, q_start, q_end, args.snapshot_dir)
    comfy_lines = read_journal(COMFY_UNIT, q_start, q_end, args.snapshot_dir)

    all_calls = [c for c in parse_text_calls(tts_lines) if start <= c.at <= end]
    mine = [c for c in all_calls if c.transform in SCRIPTORIUM_TRANSFORMS]
    unloads = [c for c in all_calls if c.transform is None]
    foreign = sorted(
        {
            c.transform
            for c in all_calls
            if c.transform is not None and c.transform not in SCRIPTORIUM_TRANSFORMS
        }
    )
    non_200 = [c for c in mine if c.status != 200]

    text_gross = sum(c.latency_s for c in mine if c.latency_s is not None)
    ollama_s, ollama_cold = ollama_load_seconds(
        sorted(mine + unloads, key=lambda c: c.at)
    )

    artifacts = read_artifacts(args.data_root / "work" / args.book_id)
    renders, frees = parse_renders(comfy_lines)
    renders = [r for r in renders if start <= r.end <= end]
    pair_renders(renders, artifacts.render_ats)
    matched = [r for r in renders if r.claimed_by is not None]

    # Where the renderer reported its own per-plate duration, use it (ADR-0038).
    #
    # `pair_renders` attributes a local ComfyUI log line to a plate by "the most
    # recent unclaimed prompt finishing at or before this plate's render.at". That
    # is only sound while renders are SERIAL. Under a parallel fan-out it
    # mis-attributes, and nothing catches it: the counts still match, so the
    # integrity check stays green while every duration is wrong.
    #
    # It also cannot see a remote render at all -- the work happened on someone
    # else's GPU and never touched this journal -- so on a Runpod bake the local
    # journal is silent and pairing yields nothing rather than something wrong.
    #
    # A number the renderer reports about itself needs no attribution, so it is
    # preferred wherever it exists. `image_wall_s` is the wall-clock span the
    # render phase occupied, which is NOT the sum under concurrency; the sum is
    # kept separately as the work done.
    self_reported = artifacts.self_reported
    remote_render_sum = sum(
        v["render_s"] for v in self_reported.values() if v.get("render_s") is not None
    )
    remote_cards = sorted({v["gpu"] for v in self_reported.values() if v.get("gpu")})

    # Under a fan-out the sum of render durations is NOT the wall clock they
    # occupied, so a bucket built from the sum does not partition the run -- it
    # double-counts every overlap and pushes the difference into the residual,
    # which is what made the first parallel bake report a residual of -70.27s.
    #
    # The union of the render intervals is the honest wall-clock figure: time
    # when at least one render was in flight, counted once however many were.
    # For a serial run the intervals are disjoint and the union equals the sum
    # exactly, so this leaves every previously published serial number untouched.
    render_intervals = [
        (at - timedelta(seconds=v["total_s"] or v["render_s"]), at)
        for pid, at in artifacts.render_ats
        if (v := self_reported.get(pid)) and (v.get("total_s") or v.get("render_s"))
    ]
    render_union_s = union_seconds(render_intervals)

    if self_reported:
        # The renderer is the authority on its own time.
        durations = [
            v["render_s"] for v in self_reported.values()
            if v.get("render_s") is not None
        ]
        image_gross = round(render_union_s if render_intervals else remote_render_sum, 2)
        sdxl_s = round(sum(
            v["model_load_s"] for v in self_reported.values()
            if v.get("model_load_s") is not None
        ), 2)
        sdxl_detail = {
            "source": "renderer-reported (params_echo)",
            # A true median. `sorted(...)[n//2]` is the upper-middle value on an
            # even sample, which is how Cycle 3 published 4.406 for a median of
            # 4.2175; the same defect was fixed in render_bench.py and lived on
            # here.
            "warm_render_median_s": (
                round(statistics.median(durations), 4) if durations else None
            ),
            "warm_render_count": len(self_reported),
            "cards": remote_cards,
        }
    else:
        image_gross = sum(r.duration_s for r in matched)
        sdxl_s, sdxl_detail = sdxl_load_seconds(matched)

    model_loading = ollama_s + sdxl_s
    orchestration = wall - text_gross - image_gross

    pair_gaps = sorted(
        (
            at - r.end
            for r in matched
            for pid, at in artifacts.render_ats
            if pid == r.claimed_by
        ),
        key=lambda d: d.total_seconds(),
    )
    gap_values = [g.total_seconds() for g in pair_gaps]

    # How much of the residual was the orchestrator simply waiting. Measured, not
    # assumed: a stretch between two state changes with no model call and no
    # render in it is time the pipeline spent idle between phases. The runner
    # sleeps RUNNER_TICK_S between advances, so on a short book this is a large
    # and entirely fixed cost.
    idle_between_phases = 0.0
    idle_gaps = 0
    if len(transition_times) >= 2:
        # Renders count as busy however they were measured. Omitting the
        # renderer-reported ones made every remote render look like idle time:
        # the first Runpod bake charged ~70s of real rendering to
        # "idle between phases" and drove `unexplained_s` negative.
        busy = (
            [c.started for c in mine if c.latency_s is not None]
            + [r.end - timedelta(seconds=r.duration_s) for r in matched]
            + [start for start, _ in render_intervals]
        )
        for t1, t2 in zip(transition_times, transition_times[1:]):
            if any(t1 <= b <= t2 for b in busy):
                continue
            idle_between_phases += (t2 - t1).total_seconds()
            idle_gaps += 1

    counts_match = all(
        len([c for c in mine if c.transform == name]) == artifacts.counts.get(name, -1)
        for name in ("cast-mentions", "scene-update", "cast-canonicalize")
    )

    warnings: list[str] = []
    if orchestration < 0:
        warnings.append(
            f"Residual is NEGATIVE ({orchestration:.1f}s). The window contains work "
            f"from something other than this bake. Do not trust these numbers."
        )
    if foreign:
        warnings.append(
            f"Foreign transforms in window: {', '.join(foreign)}. "
            f"Another project was using the text service during this run."
        )
    if not counts_match:
        warnings.append(
            "Text call counts do not match artifact file counts — the window is "
            "wrong or another bake overlapped."
        )
    if len(renders) - len(matched) > 3:
        warnings.append(
            f"{len(renders) - len(matched)} ComfyUI renders in the window belong to "
            f"nothing in this bake."
        )
    if non_200:
        bound = len(non_200) * (
            statistics.median([c.latency_s for c in mine if c.latency_s]) or 0
        )
        warnings.append(
            f"{len(non_200)} failed text requests carry no latency; they inflate the "
            f"residual by up to ~{bound:.0f}s."
        )
    if artifacts.reattempted:
        warnings.append(
            f"{artifacts.reattempted} plates were rendered more than once; only the "
            f"last attempt is timestamped, so earlier attempts land in the residual."
        )

    result = {
        "schema_version": SCHEMA_VERSION,
        "book_id": args.book_id,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "source": window_source,
        },
        "wall_s": round(wall, 2),
        "gates": gates,
        "machine_time_s": round(wall - gates["total_s"], 2),
        "buckets": {
            "text_steps_s": round(text_gross - ollama_s, 2),
            "image_rendering_s": round(image_gross - sdxl_s, 2),
            "model_loading_s": round(model_loading, 2),
            "orchestration_s": round(orchestration, 2),
        },
        "gross": {
            "text_including_model_load_s": round(text_gross, 2),
            "image_including_model_load_s": round(image_gross, 2),
        },
        "model_loading_detail": {
            "ollama_s": round(ollama_s, 2),
            "ollama_cold_requests": ollama_cold,
            "sdxl_s": round(sdxl_s, 2),
            "sdxl": sdxl_detail,
            "gpu_free_events": len(frees),
            "text_model_unload_events": len(unloads),
        },
        "text_detail": {
            "calls_counted": len(mine),
            "by_transform": {
                name: {
                    "n": len([c for c in mine if c.transform == name]),
                    "sum_s": round(
                        sum(
                            c.latency_s
                            for c in mine
                            if c.transform == name and c.latency_s
                        ),
                        2,
                    ),
                    "median_s": round(
                        statistics.median(
                            [
                                c.latency_s
                                for c in mine
                                if c.transform == name and c.latency_s
                            ]
                        ),
                        3,
                    )
                    if any(c.transform == name and c.latency_s for c in mine)
                    else None,
                }
                for name in SCRIPTORIUM_TRANSFORMS
            },
            "non_200_requests": len(non_200),
            "artifact_counts": artifacts.counts,
        },
        "image_detail": {
            "renders_in_window": len(renders),
            "renders_matched": len(matched),
            "renders_unattributed": len(renders) - len(matched),
            "plates_with_render_timestamp": len(artifacts.render_ats),
            "plates_selected": artifacts.plates_selected,
            "plates_reattempted": artifacts.reattempted,
            "pair_gap_p50_s": round(statistics.median(gap_values), 3)
            if gap_values
            else None,
            "pair_gap_max_s": round(max(gap_values), 3) if gap_values else None,
            "derivative_time_s": round(sum(g for g in gap_values if g >= 0), 2),
            # ADR-0038. Present only when the backend reported its own timings.
            # `sum_s` is work done; under a fan-out it deliberately exceeds the
            # wall-clock the render phase occupied, and that gap IS the parallelism.
            "renderer_reported": {
                # The work done and the time it took are different numbers the
                # moment renders overlap, and the ratio is the only honest way to
                # state how wide the fan-out actually ran -- as opposed to how
                # wide it was configured to run.
                "work_sum_s": round(remote_render_sum, 2),
                "elapsed_union_s": render_union_s,
                "overlap_factor": (
                    round(remote_render_sum / render_union_s, 3)
                    if render_union_s else None
                ),
                "plates": len(self_reported),
                "sum_s": round(remote_render_sum, 2),
                "cards": remote_cards,
                "per_plate": {
                    k: v["render_s"] for k, v in sorted(self_reported.items())
                },
            } if self_reported else None,
        },
        "orchestration_detail": {
            "derivatives_s": round(sum(g for g in gap_values if g >= 0), 2),
            "idle_between_phases_s": round(idle_between_phases, 2)
            if transition_times
            else None,
            "idle_gaps": idle_gaps if transition_times else None,
            "runner_tick_s": RUNNER_TICK_S,
            "unexplained_s": round(
                orchestration
                - sum(g for g in gap_values if g >= 0)
                - idle_between_phases,
                2,
            ),
        },
        "integrity": {
            "counts_match_artifacts": counts_match,
            "residual_non_negative": orchestration >= 0,
            "foreign_transforms_in_window": foreign,
            "warnings": warnings,
        },
    }

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n")
    if args.markdown:
        print(build_report(result))
    else:
        json.dump(result, sys.stdout, indent=2)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
