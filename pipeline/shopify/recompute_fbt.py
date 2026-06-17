#!/usr/bin/env python3
"""Recompute 'Pairs well with' (merch.fbt) with a content-based logic instead of the
synthetic co-occurrence (which produced nonsense like glasses->wallet).

A good companion for product A is something you'd actually style/use alongside it:
  + same ROOM (things that live in the same space pair well)        strong
  + shares STYLE (cohesive aesthetic)                                medium
  + COMPLEMENTARY category (different cat = a pairing, not a dupe)   medium
  + shares MATERIAL                                                  small
  + coherent PRICE (within ~0.3x-3x)                                 medium
  - different room                                                   penalty

The top 3 are chosen with category diversity (prefer 3 distinct categories) so the
set reads as a styled grouping rather than three near-identical items.
Writes a 3-handle list to merch.fbt. Idempotent."""
import json, time
from client import Shopify

SET = """mutation($mf:[MetafieldsSetInput!]!){
  metafieldsSet(metafields:$mf){ userErrors{ field message } } }"""

def cat_of(p):
    for t in p["tags"]:
        if t.startswith("cat:"):
            return t
    return p["productType"] or "?"

def fetch_all(s):
    out, cur = [], None
    while True:
        d = s.gql("""query($c:String){products(first:100,after:$c){pageInfo{hasNextPage endCursor}
          nodes{id handle productType tags status
            price: priceRangeV2{minVariantPrice{amount}}
            mf: metafields(first:12, namespace:"spec"){nodes{key value}}}}}""", {"c": cur})["products"]
        for p in d["nodes"]:
            if p["status"] != "ACTIVE":
                continue
            spec = {m["key"]: m["value"] for m in p["mf"]["nodes"]}
            try:
                mats = set(json.loads(spec.get("materials", "[]")))
            except Exception:
                mats = set()
            out.append({
                "id": p["id"],
                "handle": p["handle"],
                "cat": cat_of(p),
                "room": spec.get("room", ""),
                "style": spec.get("style", ""),
                "materials": mats or ({spec["material"]} if spec.get("material") else set()),
                "price": float(p["price"]["minVariantPrice"]["amount"] or 0),
                "best": "best-seller" in p["tags"],
            })
        if not d["pageInfo"]["hasNextPage"]:
            break
        cur = d["pageInfo"]["endCursor"]
    return out

def score(a, c):
    s = 0.0
    if a["room"] and c["room"]:
        s += 4 if a["room"] == c["room"] else -2
    if a["style"] and c["style"] and a["style"] == c["style"]:
        s += 2
    if a["materials"] & c["materials"]:
        s += 1
    if a["cat"] and c["cat"]:
        s += 1.5 if a["cat"] != c["cat"] else 0.5
    if a["price"] > 0 and c["price"] > 0:
        r = c["price"] / a["price"]
        if 0.3 <= r <= 3.0:
            s += 1.5
        elif 0.15 <= r <= 6.0:
            s += 0.5
        else:
            s -= 1.0
    if c["best"]:
        s += 0.5
    return s

def pick_top3(a, prods):
    scored = sorted(
        ((score(a, c), c) for c in prods if c["handle"] != a["handle"]),
        key=lambda x: (-x[0], -int(x[1]["best"])),
    )
    picked, used_cat = [], set()
    # pass 1: best per distinct category (diversity)
    for sc, c in scored:
        if len(picked) >= 3:
            break
        if c["cat"] in used_cat:
            continue
        picked.append(c["handle"])
        used_cat.add(c["cat"])
    # pass 2: fill remaining with next best regardless of category
    if len(picked) < 3:
        for sc, c in scored:
            if len(picked) >= 3:
                break
            if c["handle"] not in picked:
                picked.append(c["handle"])
    return picked[:3]

def main():
    s = Shopify()
    prods = fetch_all(s)
    print(f"active products: {len(prods)}")
    byh = {p["handle"]: p for p in prods}

    batch, written = [], 0
    for a in prods:
        top3 = pick_top3(a, prods)
        batch.append({"ownerId": a["id"], "namespace": "merch", "key": "fbt",
                      "type": "json", "value": json.dumps(top3)})
        if len(batch) >= 25:
            written += flush(s, batch)
            batch = []
    if batch:
        written += flush(s, batch)
    print(f"fbt rewritten on {written} products")

def flush(s, batch):
    r = s.gql(SET, {"mf": batch})["metafieldsSet"]
    if r.get("userErrors"):
        print("  errs:", r["userErrors"][:2])
    time.sleep(0.3)
    return len(batch)

if __name__ == "__main__":
    main()
