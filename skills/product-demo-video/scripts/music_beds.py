#!/usr/bin/env python3
"""Measure candidate music tracks and write one ready-to-play bed per track, for the user to choose by ear.

  music_beds.py --duration 36 --intro-end 4.6 --out music_choices music_src/a.mp3 music_src/b.mp3
  music_beds.py --duration 36 --intro-end 4.6 --out music_choices music_src/a.mp3@12.5   # force an offset
  music_beds.py --measure-only music_src/*.mp3                                           # table only

For each track it finds the biggest lift (the 4 s after a moment against the 4 s before it) that still leaves
room for the whole demo, sets the offset so that lift lands on chapter 1 (--intro-end, from render.mjs
--timeline), and writes <out>/<track>.m4a at the demo length with the same fades and loudness as add_music.py.
A lift under 3 dB means the track is flat; the bed then starts at the track's beginning.
It also prints a rough pulse: the beat period found by autocorrelation and how regular it is (0–1).
You can't hear the beds, so hand the folder to the user and mux only the one they pick:
  add_music.py --track <track> --offset <offset> --duration … --page-out page/music.m4a --video-in … --video-out …
Needs ffmpeg.
"""
import argparse, math, os, subprocess, sys
from array import array

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from add_music import write_bed

RATE, FRAME = 8000, 80          # 8 kHz mono, 10 ms frames
WINDOW = 25                     # 0.25 s per loudness reading


def decode(path):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    samples = array("h")
    samples.frombytes(pcm[: len(pcm) // 2 * 2])
    frames = []
    for i in range(0, len(samples) - FRAME, FRAME):
        chunk = samples[i:i + FRAME]
        frames.append(math.sqrt(sum(x * x for x in chunk) / FRAME))
    return frames


def db(x):
    return 20 * math.log10(max(x, 1e-3) / 32768)


def lift_second(frames, intro_end, duration):
    levels = [db(sum(frames[i:i + WINDOW]) / WINDOW) for i in range(0, len(frames) - WINDOW, WINDOW)]
    span = 16                                            # 4 s of 0.25 s readings
    latest = (len(frames) / 100 - duration + intro_end) * 4
    body_db = sorted(levels)[int(len(levels) * .7)] - 2  # a lift has to rise into the track's loud body
    best, best_rise = None, 0.0
    for k in range(span, len(levels) - span):
        if k / 4 < intro_end or k > latest:
            continue
        after = sum(levels[k:k + span]) / span
        rise = after - sum(levels[k - span:k]) / span
        if rise > best_rise and after >= body_db:
            best, best_rise = k / 4, rise
    return best, best_rise


def pulse(frames, start, duration):
    part = frames[int(start * 100): int((start + duration) * 100)]
    onset = [max(0.0, part[i] - part[i - 1]) for i in range(1, len(part))]
    mean = sum(onset) / max(1, len(onset))
    onset = [x - mean for x in onset]
    energy = sum(x * x for x in onset) or 1.0
    best_lag, best = 0, 0.0
    for lag in range(25, 101):                           # 0.25–1.0 s between beats
        score = sum(onset[i] * onset[i + lag] for i in range(len(onset) - lag)) / energy
        if score > best:
            best_lag, best = lag, score
    bpm = 60 / (best_lag / 100) if best_lag else 0
    while bpm > 140:                                     # report the tempo you'd tap: fold eighth notes and
        bpm /= 2                                         # half time into 70-140; still only a rough guide
    while 0 < bpm < 70:
        bpm *= 2
    return bpm, best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tracks", nargs="+", help="audio files; add @seconds to force an offset")
    ap.add_argument("--duration", type=float, default=45, help="page duration from render.mjs --timeline")
    ap.add_argument("--intro-end", type=float, default=5.4, help="chapter 1 start from render.mjs --timeline")
    ap.add_argument("--out", help="folder for the beds")
    ap.add_argument("--measure-only", action="store_true")
    ap.add_argument("--lufs", type=float, default=-20)
    a = ap.parse_args()
    if not a.measure_only and not a.out:
        raise SystemExit("--out is required unless --measure-only")
    if a.out:
        os.makedirs(a.out, exist_ok=True)

    print(f"{'track':28} {'length':>7} {'lift at':>8} {'lift dB':>8} {'offset':>7} {'bpm':>5} {'pulse':>6}  bed")
    for arg in a.tracks:
        path, _, forced = arg.partition("@")
        frames = decode(path)
        length = len(frames) / 100
        lift, rise = lift_second(frames, a.intro_end, a.duration)
        if lift is None or rise < 3:
            lift = None
        offset = float(forced) if forced else (lift - a.intro_end if lift is not None else 0.0)
        bpm, regularity = pulse(frames, offset, a.duration)
        name = os.path.splitext(os.path.basename(path))[0]
        bed = ""
        if length < offset + a.duration:
            bed = "too short"
        elif not a.measure_only:
            bed = os.path.join(a.out, name + ".m4a")
            write_bed(path, offset, a.duration, bed, lufs=a.lufs)
        lift_text = f"{lift:.2f}" if lift is not None else "none"
        print(f"{name[:28]:28} {length:7.1f} {lift_text:>8} {rise:8.1f} {offset:7.2f} {bpm:5.0f} {regularity:6.2f}  {bed}")


if __name__ == "__main__":
    main()
