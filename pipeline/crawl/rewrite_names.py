#!/usr/bin/env python3
"""Apply MARLOW functional/minimal naming to curated home products.
Deterministic de-brand of titles: strip symbols, resale/seconds/sale suffixes,
collapse whitespace, normalize case. Keeps the functional material+form descriptor.
Outputs data/catalog_marlow.json with display_title + clean_description added.
Full voice rewrite of description bodies happens later (content.py)."""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

# promo/resale qualifiers stripped wherever they appear (mid-title or trailing)
PROMO = re.compile(
    r"\b(seconds?|renewed|final sale|last chance|clearance|on sale|\bsale\b|"
    r"exclusive|limited edition|pre-?order|back in stock|gwp|sold out|new arrival)\b",
    re.I)
# trailing standalone "New" qualifier (kept separate so "New York" etc. survive)
TRAIL_NEW = re.compile(r"\s*[-–—]\s*new\s*$", re.I)

def strip_suffix(t):
    t = PROMO.sub("", t)
    t = TRAIL_NEW.sub("", t)
    t = re.sub(r"\(\s*\)", "", t)            # empty parens left after stripping
    t = re.sub(r"\s*[-–—|]\s*\(", " (", t)   # "X - (color)" -> "X (color)"
    t = re.sub(r"\s*[-–—|]\s*[-–—|]\s*", " ", t)  # collapse dangling separators
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip(" -–—|")

ACRONYMS = {"spf": "SPF", "led": "LED", "uv": "UV"}

def smartcaps(w):
    lw = w.lower()
    if lw in ACRONYMS: return ACRONYMS[lw]
    if w.isupper() and len(w) <= 3: return w
    return w[:1].upper() + w[1:] if w else w

def rewrite_title(t):
    if not t: return t
    t = t.replace("®", "").replace("™", "").replace("™", "")
    t = re.sub(r"\s{2,}", " ", t).strip(" -–—|")
    t = strip_suffix(t)
    words = [w for w in re.split(r"\s+", t) if w]
    if not words:
        return t
    return " ".join(smartcaps(w) for w in words).strip()

def clean_desc(d):
    if not d: return d
    d = d.replace("®", "").replace("™", "").replace("™", "")
    return re.sub(r"\s{2,}", " ", d).strip()

def main():
    cat = json.load(open(os.path.join(DATA, "curated.json")))
    samples = []
    for p in cat:
        orig = p["title"]
        p["display_title"] = rewrite_title(orig)
        p["clean_description"] = clean_desc(p["description"])
        if len(samples) < 14 and orig != p["display_title"]:
            samples.append((p["src_brand"], orig, p["display_title"]))
    json.dump(cat, open(os.path.join(DATA, "catalog_marlow.json"), "w"), indent=1)
    print(f"rewrote {len(cat)} products -> data/catalog_marlow.json\n")
    print("sample renames (orig -> MARLOW):")
    for b, o, n in samples:
        print(f"  [{b}] {o!r} -> {n!r}")

if __name__ == "__main__":
    main()
