#!/usr/bin/env python3
"""Apply visible compare-at 'sale' pricing to a spread of products across collections,
so they render with a strikethrough original price + Sale badge on the storefront.
Varies the markdown (15/20/25/30% off) for variety. Idempotent: re-running recomputes
compare-at from the live price; skips products already marked down at the same rate."""
import time
from client import Shopify

# collection handle -> how many products to put on sale
PLAN = {
    "cat-dinnerware": 6, "cat-glassware": 5, "cat-bedding": 6, "cat-bath": 5,
    "cat-throws-blankets": 5, "cat-candles-scent": 5, "cat-vases-planters": 5,
    "cat-decor-objects": 5, "cat-lighting": 4, "cat-table-linens": 5,
}
PCTS = [0.15, 0.20, 0.25, 0.30]  # cycle for variety

Q = """
query($h:String!,$n:Int!){ collectionByHandle(handle:$h){ products(first:$n, sortKey:BEST_SELLING){
  nodes{ id title variants(first:20){ nodes{ id price compareAtPrice } } } } } }"""
M = """
mutation($pid:ID!,$v:[ProductVariantsBulkInput!]!){
  productVariantsBulkUpdate(productId:$pid, variants:$v){ userErrors{field message} } }"""

def main():
    s = Shopify()
    total, i = 0, 0
    for handle, n in PLAN.items():
        c = s.gql(Q, {"h": handle, "n": n}).get("collectionByHandle")
        if not c:
            print(f"  {handle}: not found"); continue
        for p in c["products"]["nodes"]:
            pct = PCTS[i % len(PCTS)]; i += 1
            variants = []
            for v in p["variants"]["nodes"]:
                try:
                    price = float(v["price"])
                except (TypeError, ValueError):
                    continue
                if price <= 0:
                    continue
                # compare-at (the "was" price) = current price marked up so it reads as pct off
                compare = round(price / (1 - pct) + 0.005, 2)
                # skip if already on sale at ~this level
                cur = v.get("compareAtPrice")
                if cur and abs(float(cur) - compare) < 0.5:
                    continue
                variants.append({"id": v["id"], "compareAtPrice": f"{compare:.2f}"})
            if not variants:
                continue
            r = s.gql(M, {"pid": p["id"], "v": variants})["productVariantsBulkUpdate"]
            if r.get("userErrors"):
                print(f"  ERR {p['title']}: {r['userErrors'][:1]}")
            else:
                total += 1
                if total % 10 == 0: print(f"  marked down: {total}")
            time.sleep(0.25)
    print(f"\nproducts put on sale (compare-at set): {total}")

if __name__ == "__main__":
    main()
