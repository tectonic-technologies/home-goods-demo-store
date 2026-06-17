#!/usr/bin/env python3
"""Remove the junk `listing` variant option (UUID values) that came in from the
source 'combined listing' data. Affected products end up with options like
[color, size, listing] where `listing` is a list of UUIDs rendered as raw buttons
on the PDP. Delete that option with POSITION strategy so Shopify collapses the
variants down to clean color x size (keeping the lowest-position variant per combo).
Idempotent: skips products that no longer have a `listing` option."""
import time
from client import Shopify

DELETE = """mutation($pid:ID!,$opts:[ID!]!){
  productOptionsDelete(productId:$pid, options:$opts, strategy: POSITION){
    deletedOptionsIds
    userErrors{ field message code }
  } }"""

def main():
    s = Shopify()
    targets, cursor = [], None
    while True:
        d = s.gql("query($c:String){products(first:100,after:$c){pageInfo{hasNextPage endCursor} "
                  "nodes{id handle options{id name}}}}", {"c": cursor})["products"]
        for p in d["nodes"]:
            opt = next((o for o in p["options"] if o["name"].lower() == "listing"), None)
            if opt:
                targets.append((p["id"], p["handle"], opt["id"]))
        if not d["pageInfo"]["hasNextPage"]:
            break
        cursor = d["pageInfo"]["endCursor"]

    print(f"products with a `listing` option: {len(targets)}")
    ok = errs = 0
    for pid, handle, oid in targets:
        r = s.gql(DELETE, {"pid": pid, "opts": [oid]})["productOptionsDelete"]
        ue = r.get("userErrors") or []
        if ue:
            errs += 1
            print(f"  ERR {handle}: {ue[:1]}")
        else:
            ok += 1
            if ok % 10 == 0:
                print(f"  cleaned {ok}/{len(targets)}")
        time.sleep(0.25)
    print(f"\ndone: {ok} cleaned, {errs} errors")

if __name__ == "__main__":
    main()
