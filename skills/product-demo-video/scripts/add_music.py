#!/usr/bin/env python3
"""Trim a music track to the demo length and mix it into the rendered video.

  add_music.py --track music_src/track.mp3 --offset 6.6 --duration 67 \
      --page-out page/music.m4a --video-in output/demo-silent.mp4 --video-out output/demo.mp4

--offset is where in the track the demo starts. Pick it so the track's first big change
(the beat coming in) lands on the first chapter: offset = buildSecond - firstChapterStart.
Fades in and out, loudness-normalises to background level, writes the page's music file and
(optionally) muxes it into the video without re-encoding the picture. Needs ffmpeg.
"""
import argparse, os, subprocess


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--offset", type=float, default=0)
    ap.add_argument("--duration", type=float, required=True)
    ap.add_argument("--fade-in", type=float, default=1.2)
    ap.add_argument("--fade-out", type=float, default=3)
    ap.add_argument("--lufs", type=float, default=-20)
    ap.add_argument("--page-out", required=True)
    ap.add_argument("--video-in")
    ap.add_argument("--video-out")
    a = ap.parse_args()

    af = (f"afade=t=in:d={a.fade_in},afade=t=out:st={a.duration - a.fade_out}:d={a.fade_out},"
          f"loudnorm=I={a.lufs}:TP=-2:LRA=11")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a.offset), "-t", str(a.duration), "-i", a.track,
                    "-af", af, "-ar", "48000", "-c:a", "aac", "-b:a", "192k", a.page_out], check=True)
    print("music ->", a.page_out)
    if a.video_in and a.video_out:
        tmp = a.video_out + ".tmp.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.video_in, "-i", a.page_out, "-map", "0:v", "-map", "1:a",
                        "-c", "copy", "-shortest", "-movflags", "+faststart", tmp], check=True)
        os.replace(tmp, a.video_out)
        print("video with music ->", a.video_out)


if __name__ == "__main__":
    main()
