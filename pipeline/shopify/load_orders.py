#!/usr/bin/env python3
"""Load synthetic customers + orders. Idempotent-ish: skips if customers exist.
Orders backdated via processed_at; line items mapped to real store variants.
Run after products are loaded."""
import json, os, sys, time
from client import Shopify

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
def load(p): return json.load(open(os.path.join(D, p)))
CAT = load("catalog_clean.json")
DESC = load("content/descriptions.json")
CUST = load("synth/customers.json")
ORD = load("synth/orders.json")

def main():
    s = Shopify()
    # Resumable: optional start index into the synth order list (skip already-loaded).
    resume = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    # variant map: content title -> numeric variant id
    vmap, cursor = {}, None
    while True:
        d = s.gql('query($c:String){products(first:100,after:$c){pageInfo{hasNextPage endCursor} nodes{title variants(first:1){nodes{legacyResourceId}}}}}', {"c": cursor})["products"]
        for n in d["nodes"]:
            vs = n["variants"]["nodes"]
            if vs: vmap[n["title"]] = vs[0]["legacyResourceId"]
        if not d["pageInfo"]["hasNextPage"]: break
        cursor = d["pageInfo"]["endCursor"]
    idx_variant = {}
    for i, p in enumerate(CAT):
        title = DESC.get(p["src_handle"], {}).get("title") or p["display_title"]
        if title in vmap: idx_variant[i] = vmap[title]
    print(f"variant map: {len(idx_variant)}/{len(CAT)} products")

    # customers: reuse any that already exist (by email), create the rest. Idempotent.
    email_to_id, cursor = {}, None
    while True:
        d = s.gql('query($c:String){customers(first:250,after:$c){pageInfo{hasNextPage endCursor} nodes{legacyResourceId email}}}', {"c": cursor})["customers"]
        for n in d["nodes"]:
            if n.get("email"): email_to_id[n["email"].lower()] = n["legacyResourceId"]
        if not d["pageInfo"]["hasNextPage"]: break
        cursor = d["pageInfo"]["endCursor"]
    cid, created = {}, 0
    for c in CUST:
        eid = email_to_id.get(c["email"].lower())
        if eid:
            cid[c["ref"]] = eid; continue
        body = {"customer": {"first_name": c["first_name"], "last_name": c["last_name"],
                "email": c["email"], "tags": ",".join(c["tags"]),
                "addresses": [{"city": c["city"], "province": c["province"], "country_code": c["country_code"]}]}}
        try:
            r = s.rest("POST", "customers.json", body)
            cid[c["ref"]] = r["customer"]["id"]; created += 1
        except SystemExit:
            pass
        time.sleep(0.4)
    print(f"customers: reused {len(cid)-created}, created {created} (total {len(cid)})")

    # orders (resume from index); tag each with its synth ref for clean future resumes
    ok = 0
    for o in ORD[resume:]:
        items = [{"variant_id": idx_variant[li["product_i"]], "quantity": li["qty"]}
                 for li in o["line_items"] if li["product_i"] in idx_variant]
        if not items: continue
        body = {"order": {
            "line_items": items,
            "financial_status": "paid",
            "processed_at": o["created_at"] + "T12:00:00Z",
            "tags": f"{o['ref']},demo",
            "send_receipt": False, "send_fulfillment_receipt": False,
            "inventory_behaviour": "bypass",
        }}
        if o["customer_ref"] in cid:
            body["order"]["customer"] = {"id": cid[o["customer_ref"]]}
        try:
            s.rest("POST", "orders.json", body); ok += 1
        except SystemExit:
            pass
        if ok % 100 == 0: print(f"  orders: {ok} (from index {resume})")
        time.sleep(0.4)
    print(f"\norders created this run: {ok}")

if __name__ == "__main__":
    main()
