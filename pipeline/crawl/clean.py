#!/usr/bin/env python3
"""Post-curation cleanup: recategorize 'Other', drop edible/off-aesthetic + broken
products, dedupe cross-brand near-identical items. Produces data/catalog_clean.json."""
import json, os, re
from collections import Counter, defaultdict

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

# edible / consumable / off-aesthetic stragglers to drop outright
EDIBLE = re.compile(r"olive oil|\bjam\b|honey jar|honey pot|cocktail mix|drink mix|"
                    r"\bsyrup\b|coffee bean|granola|chocolate|felted soap|"
                    r"bath salt|bath soak|essential oil", re.I)

# recategorize remaining 'Other' by broader cues
RECAT = [
    ("Decor & Objects", r"tree|woodland|ornament|garland|wreath|figurine|"
                        r"sculpture|object|bookend|mirror|frame|seasonal|"
                        r"holiday|stocking|advent"),
    ("Serveware", r"serving|platter|board|trivet|pitcher|tray|colander|"
                  r"cake stand|compote|teapot"),
    ("Vases & Planters", r"vase|planter|\bpot\b|vessel|urn"),
    ("Candles & Scent", r"candle|taper|votive|diffuser|incense"),
    ("Storage & Baskets", r"basket|bin|crate|box|caddy|hamper"),
    ("Dinnerware", r"plate|bowl|mug|cup|dish|dinnerware"),
]

def recategorize(p):
    if p["category"] != "Other":
        return p["category"]
    hay = (p["display_title"] + " " + p.get("clean_description", "")).lower()
    for cat, pat in RECAT:
        if re.search(pat, hay):
            return cat
    return "Other"

def usable_price(p):
    return any((v.get("price") or "") not in ("", "0", "0.00") for v in p["variants"])

def score(p):
    s = min(len(p.get("images", [])), 8)
    s += 3 if len(p.get("clean_description", "") or "") >= 120 else 0
    s += 4 if p.get("variant_count", 0) > 1 else 0
    return s

def main():
    d = json.load(open(os.path.join(DATA, "catalog_marlow.json")))
    n0 = len(d)

    # 1. drop edible/off-aesthetic + broken products
    kept = []
    dropped = defaultdict(list)
    for p in d:
        desc = p.get("clean_description", "") or ""
        title = p["display_title"]
        if EDIBLE.search(title):
            dropped["edible"].append(title); continue
        if len(desc) < 30:
            dropped["empty_desc"].append(title); continue
        if not usable_price(p):
            dropped["no_price"].append(title); continue
        if len(p.get("images", [])) < 2:
            dropped["thin_images"].append(title); continue
        p["category"] = recategorize(p)
        kept.append(p)

    # 2. dedupe cross-brand near-identical (same normalized display_title)
    groups = defaultdict(list)
    for p in kept:
        key = re.sub(r"\b(set|small|large|medium|mini)\b", "", p["display_title"].lower()).strip()
        key = re.sub(r"\s{2,}", " ", key)
        groups[key].append(p)
    deduped, removed_dups = [], []
    for key, items in groups.items():
        if len(items) == 1:
            deduped.append(items[0]); continue
        items.sort(key=score, reverse=True)
        deduped.append(items[0])
        for x in items[1:]:
            removed_dups.append(x["display_title"])

    json.dump(deduped, open(os.path.join(DATA, "catalog_clean.json"), "w"), indent=1)

    print(f"in: {n0}  ->  clean: {len(deduped)}")
    for k, v in dropped.items():
        print(f"  dropped {k}: {len(v)}  e.g. {v[:3]}")
    print(f"  removed cross-brand dups: {len(removed_dups)}  e.g. {removed_dups[:5]}")
    cat = Counter(p["category"] for p in deduped)
    print("\nfinal categories:")
    for k, v in cat.most_common():
        print(f"  {v:3} {k}")
    print(f"  Other remaining: {cat.get('Other',0)}")
    print(f"\nvariant-axis products: {sum(1 for p in deduped if p.get('variant_count',0)>1)}")

if __name__ == "__main__":
    main()
