#!/usr/bin/env python3
"""Create smart (rule-based) collections so they auto-populate from product
type/tags loaded by load_products.py. Run after products are loaded."""
import json, os, time
from client import Shopify

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
DEFS = json.load(open(os.path.join(D, "collections.json")))

MUT = """
mutation($input: CollectionInput!) {
  collectionCreate(input: $input) {
    collection { id handle title }
    userErrors { field message }
  }
}"""

def rule(col):
    r = col["rule"]; field = r.get("field")
    # map our definitions to Shopify collection rule columns.
    # products are tagged (load_products.py) with: category, material, room, style,
    # price_band, and best-seller/new/clearance.
    if col["handle"].startswith("cat-") or field == "category":
        return {"column": "TYPE", "relation": "EQUALS", "condition": col["title"]}
    if field == "best_seller":
        return {"column": "TAG", "relation": "EQUALS", "condition": "best-seller"}
    if field == "is_new":
        return {"column": "TAG", "relation": "EQUALS", "condition": "new"}
    if field == "is_clearance":
        return {"column": "TAG", "relation": "EQUALS", "condition": "clearance"}
    if field in ("room", "material", "style", "price_band"):
        return {"column": "TAG", "relation": "EQUALS", "condition": r.get("value")}
    if field == "editorial":
        # manual/curated collection; no rule
        return None
    return None

def main():
    s = Shopify()
    made, skipped = 0, 0
    for col in DEFS:
        rl = rule(col)
        if rl is None:
            skipped += 1; continue
        inp = {
            "title": col["title"], "handle": col["handle"],
            "ruleSet": {"appliedDisjunctively": False, "rules": [rl]},
        }
        res = s.gql(MUT, {"input": inp})["collectionCreate"]
        if res.get("userErrors"):
            print(f"  ERR {col['handle']}: {res['userErrors'][:1]}")
        else:
            made += 1
            print(f"  + {res['collection']['title']} ({res['collection']['handle']})")
        time.sleep(0.4)
    print(f"\ncollections created={made} skipped(metafield/manual)={skipped}")

if __name__ == "__main__":
    main()
