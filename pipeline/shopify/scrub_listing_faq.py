#!/usr/bin/env python3
"""Drop the synthetic 'How do I choose a listing?' FAQ that was keyed to the now-deleted
`listing` variant option. 'listing' is e-commerce jargon that shouldn't face customers.
Removes any FAQ item whose question or answer mentions 'listing'; rewrites content.faqs.
Idempotent."""
import json, time
from client import Shopify

SET = """mutation($mf:[MetafieldsSetInput!]!){
  metafieldsSet(metafields:$mf){ userErrors{ field message } } }"""

def main():
    s = Shopify()
    fixed = cursor = 0
    cursor = None
    scanned = 0
    while True:
        d = s.gql("query($c:String){products(first:100,after:$c){pageInfo{hasNextPage endCursor} "
                  "nodes{id handle metafield(namespace:\"content\",key:\"faqs\"){value}}}}",
                  {"c": cursor})["products"]
        batch = []
        for p in d["nodes"]:
            scanned += 1
            mf = p.get("metafield")
            if not mf:
                continue
            try:
                faqs = json.loads(mf["value"])
            except Exception:
                continue
            kept = [f for f in faqs
                    if "listing" not in (f.get("question", "") + " " + f.get("answer", "")).lower()]
            if len(kept) != len(faqs):
                batch.append({"ownerId": p["id"], "namespace": "content", "key": "faqs",
                              "type": "json", "value": json.dumps(kept)})
        if batch:
            r = s.gql(SET, {"mf": batch})["metafieldsSet"]
            if r.get("userErrors"):
                print("  errs:", r["userErrors"][:2])
            fixed += len(batch)
            time.sleep(0.3)
        if not d["pageInfo"]["hasNextPage"]:
            break
        cursor = d["pageInfo"]["endCursor"]
    print(f"scanned {scanned}; FAQs scrubbed on {fixed} products")

if __name__ == "__main__":
    main()
