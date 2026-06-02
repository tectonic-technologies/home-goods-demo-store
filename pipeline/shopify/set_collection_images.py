#!/usr/bin/env python3
"""Set a representative image on each smart collection (playbook 10: collection cards
show placeholder graphics until each collection has its own image). Uses the featured
image of a best-selling product in the collection. Idempotent (skips ones with an image)."""
import time
from client import Shopify

Q = """
query($c:String){ collections(first:100, after:$c){ pageInfo{hasNextPage endCursor}
  nodes{ id handle image{ id }
    products(first:1, sortKey:BEST_SELLING){ nodes{ featuredImage{ url } } } } } }"""
M = """
mutation($input: CollectionInput!){ collectionUpdate(input:$input){
  collection{ id } userErrors{ field message } } }"""

def main():
    s = Shopify()
    cols, cursor = [], None
    while True:
        d = s.gql(Q, {"c": cursor})["collections"]
        cols.extend(d["nodes"])
        if not d["pageInfo"]["hasNextPage"]: break
        cursor = d["pageInfo"]["endCursor"]

    done, skip, noimg = 0, 0, 0
    for c in cols:
        if c.get("image"):
            skip += 1; continue
        prods = c["products"]["nodes"]
        url = prods[0]["featuredImage"]["url"] if prods and prods[0].get("featuredImage") else None
        if not url:
            noimg += 1; continue
        res = s.gql(M, {"input": {"id": c["id"], "image": {"src": url}}})["collectionUpdate"]
        if res.get("userErrors"):
            print(f"  ERR {c['handle']}: {res['userErrors'][:1]}")
        else:
            done += 1
            if done % 10 == 0: print(f"  set images: {done}")
        time.sleep(0.3)
    print(f"\ncollection images set={done} skipped(existing)={skip} no_product_image={noimg} of {len(cols)}")

if __name__ == "__main__":
    main()
