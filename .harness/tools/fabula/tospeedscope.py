"""Convert a stepdemo trace into one speedscope file with four measures per run.

Usage: python3 -I tospeedscope.py TRACE.json OUT.speedscope.json

Every run becomes four evented profiles with the same frames and the same
open/close order, differing only in weight:

    "<call> · stappen"  every step weighs 1          (unit none)
    "<call> · υ"        a step weighs its ``u``      (unit none; instructions)
    "<call> · μ"        a step weighs its ``m``      (unit none; memory accesses)
    "<call> · t"        a step weighs te - ts in ns  (nanoseconds)

The patched speedscope groups profiles by the name before the last " · " and
cycles through a group on a click on the time ruler; a unitless measure named
by one symbol (υ, μ) follows each ruler value, a word (stappen) leaves it bare.

The trace leaves fields out: a missing ``m`` is 0; a missing ``te`` is the
``ts`` of the next step of the run, and for the last step the ``t1`` of the
outermost frame, or else the median step duration. A ``te`` past the next
step's ``ts`` (the tracer stamps it at the frame's later return, measured on
57 of 1052 steps) is cut back to that ``ts``: the steps run one at a time, so
a step's time cannot overlap the next, and the run's ``t`` stays within its
wall-clock span.

A frame is open over its steps and its callees' steps: walking the steps, the
open stack is made equal to the step's frame and its ancestors, closing what
is not on that chain and opening what is missing. A frame that is left and
entered again (a generator resumed after a yield) is opened again, so the
flamechart shows it twice; such reopenings are counted and printed.
"""

import json
import statistics
import sys

MEASURES = ("stappen", "υ", "μ", "t")


def durations(run):
    """Each step's te - ts in ns, with the gaps filled as the docstring says."""
    steps = run["steps"]
    ends = [s.get("te") for s in steps]
    for i in range(len(steps) - 1):
        nxt = steps[i + 1]["ts"]
        ends[i] = nxt if ends[i] is None else min(ends[i], nxt)
    if ends[-1] is None:
        by_id = {f["id"]: f for f in run["frames"]}
        root = by_id[steps[-1]["f"]]
        while root["parent"] is not None:
            root = by_id[root["parent"]]
        if root.get("t1") is not None:
            ends[-1] = root["t1"]
        else:
            known = [e - s["ts"] for e, s in zip(ends[:-1], steps)]
            ends[-1] = steps[-1]["ts"] + round(statistics.median(known))
    out = [e - s["ts"] for e, s in zip(ends, steps)]
    assert all(d >= 0 for d in out), f"{run['call']}: a step ends before it starts"
    assert sum(out) <= ends[-1] - steps[0]["ts"], f"{run['call']}: steps overlap"
    return out


def convert(runs):
    frames, frame_index = [], {}
    profiles, reopened = [], 0
    for run in runs:
        by_id = {f["id"]: f for f in run["frames"]}
        codes = run.get("codes") or []

        def shared(fid):
            fr = by_id[fid]
            key = (fr["func"], fr.get("file"))
            if key not in frame_index:
                frame_index[key] = len(frames)
                entry = {"name": fr["func"]}
                if fr.get("file"):
                    entry["file"] = fr["file"]
                code = fr.get("code")
                if code is not None and code < len(codes) and "first" in codes[code]:
                    entry["line"] = codes[code]["first"]
                frames.append(entry)
            return frame_index[key]

        def chain(fid):
            out = []
            while fid is not None:
                out.append(fid)
                fid = by_id[fid]["parent"]
            return out[::-1]

        steps = run["steps"]
        weights = {
            "stappen": [1] * len(steps),
            "υ": [s["u"] for s in steps],
            "μ": [s.get("m", 0) for s in steps],
            "t": durations(run),
        }
        # one event list per measure; the order of events is shared
        events = {m: [] for m in MEASURES}
        at = dict.fromkeys(MEASURES, 0)
        stack, seen = [], set()
        for i, step in enumerate(steps):
            want = chain(step["f"])
            keep = 0
            while keep < len(stack) and keep < len(want) and stack[keep] == want[keep]:
                keep += 1
            for fid in reversed(stack[keep:]):
                for m in MEASURES:
                    events[m].append({"type": "C", "frame": shared(fid), "at": at[m]})
            for fid in want[keep:]:
                reopened += fid in seen
                seen.add(fid)
                for m in MEASURES:
                    events[m].append({"type": "O", "frame": shared(fid), "at": at[m]})
            stack = want
            for m in MEASURES:
                at[m] += weights[m][i]
        for fid in reversed(stack):
            for m in MEASURES:
                events[m].append({"type": "C", "frame": shared(fid), "at": at[m]})

        for m in MEASURES:
            total = sum(weights[m])
            assert at[m] == total, f"{run['call']} · {m}: {at[m]} != {total}"
            if m == "t":
                assert total == sum(durations(run))
            elif m == "υ":
                assert total == sum(s["u"] for s in steps)
            elif m == "μ":
                assert total == sum(s.get("m", 0) for s in steps)
            else:
                assert total == len(steps)
            profiles.append({
                "type": "evented",
                "name": f"{run['call']} · {m}",
                "unit": "nanoseconds" if m == "t" else "none",
                "startValue": 0,
                "endValue": total,
                "events": events[m],
            })
    names = [p["name"] for p in profiles]
    assert len(names) == len(set(names)), "two runs share a call: names collide"
    return {
        "$schema": "https://www.speedscope.app/file-format-schema.json",
        "shared": {"frames": frames},
        "profiles": profiles,
        "name": "stepdemo",
        "activeProfileIndex": 0,
        "exporter": "tospeedscope.py",
    }, reopened


def main():
    src, dst = sys.argv[1:3]
    with open(src, encoding="utf-8") as f:
        runs = json.load(f)
    out, reopened = convert(runs)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"{len(runs)} runs, {len(out['profiles'])} profiles, "
          f"{len(out['shared']['frames'])} frames, {reopened} reopened frames -> {dst}")


if __name__ == "__main__":
    main()
