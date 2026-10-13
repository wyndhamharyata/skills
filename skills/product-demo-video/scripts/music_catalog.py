#!/usr/bin/env python3
"""Search the two free music catalogues a script can download from, with direct MP3 links.

  music_catalog.py --text techno                       # both sources, title/genre/description match
  music_catalog.py --source incompetech --feel Bright --bpm 100-130 --text synth
  music_catalog.py --source mixkit                     # every Mixkit track a script can see (about 50)

Mixkit: no credit needed (Mixkit Stock Music Free License). Only its corporate and technology tag pages
are readable without a browser, and they list no BPM.
Incompetech (Kevin MacLeod): about 1,400 pieces with BPM, feel and a description, CC BY 4.0, so the
video description must credit it. The credit line is printed with the results.
Pixabay blocks scripts (HTTP 403); don't try it.
"""
import argparse, json, re, urllib.parse, urllib.request

AGENT = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
INCOMPETECH = "https://incompetech.com/music/royalty-free/"


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def mixkit():
    found = {}
    for tag in ("corporate", "technology"):
        html = fetch(f"https://mixkit.co/free-stock-music/tag/{tag}/")
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            try:
                stack = [json.loads(block)]
            except ValueError:
                continue
            while stack:
                x = stack.pop()
                if isinstance(x, list):
                    stack.extend(x)
                elif isinstance(x, dict):
                    if x.get("@type") == "MusicRecording" and x.get("url"):
                        by = x.get("byArtist")
                        minutes, seconds = re.match(r"PT(?:(\d+)M)?(?:(\d+)S)?", x.get("duration") or "PT0S").groups()
                        found[x["url"]] = {"source": "mixkit", "title": x.get("name", ""), "by": by.get("name") if isinstance(by, dict) else by or "",
                                           "bpm": None, "seconds": int(minutes or 0) * 60 + int(seconds or 0),
                                           "mood": x.get("genre") or "", "about": "", "url": x["url"]}
                    stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
    return list(found.values())


def incompetech():
    rows = []
    for p in json.loads(fetch(INCOMPETECH + "pieces.json")):
        h, m, s = (int(x) for x in (p.get("length") or "0:0:0").split(":"))
        rows.append({"source": "incompetech", "title": p["title"], "by": "Kevin MacLeod",
                     "bpm": int(p["bpm"]) if (p.get("bpm") or "").isdigit() else None, "seconds": h * 3600 + m * 60 + s,
                     "mood": p.get("feel") or "", "about": " ".join(str(p.get(k) or "") for k in ("description", "instruments")),
                     "url": INCOMPETECH + "mp3-royaltyfree/" + urllib.parse.quote(p["filename"])})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["mixkit", "incompetech", "all"], default="all")
    ap.add_argument("--text", help="word to find in the title, genre, feel or description")
    ap.add_argument("--feel", help="Incompetech feel, e.g. Bright, Calming, Driving, Grooving, Uplifting")
    ap.add_argument("--bpm", help="range such as 100-130 (Incompetech only)")
    ap.add_argument("--max-minutes", type=float, default=6)
    ap.add_argument("--limit", type=int, default=25)
    a = ap.parse_args()

    rows = (mixkit() if a.source in ("mixkit", "all") else []) + (incompetech() if a.source in ("incompetech", "all") else [])
    low, high = (int(x) for x in a.bpm.split("-")) if a.bpm else (0, 999)
    hits = [r for r in rows
            if r["seconds"] <= a.max_minutes * 60
            and (not a.text or a.text.lower() in " ".join((r["title"], r["mood"], r["about"])).lower())
            and (not a.feel or a.feel.lower() in r["mood"].lower())
            and (not a.bpm or (r["bpm"] and low <= r["bpm"] <= high))]
    print(f"{len(hits)} of {len(rows)} tracks match")
    for r in hits[: a.limit]:
        bpm = str(r["bpm"] or "")
        print(f"{r['source']:11} {r['title'][:32]:32} {r['by'][:20]:20} {bpm:>4} {r['seconds'] // 60}:{r['seconds'] % 60:02d}  {r['mood'][:34]:34} {r['url']}")
    if any(r["source"] == "incompetech" for r in hits[: a.limit]):
        print('\nIncompetech credit for the video description:\n"<Title>" Kevin MacLeod (incompetech.com)\n'
              "Licensed under Creative Commons: By Attribution 4.0 License\nhttp://creativecommons.org/licenses/by/4.0/")


if __name__ == "__main__":
    main()
