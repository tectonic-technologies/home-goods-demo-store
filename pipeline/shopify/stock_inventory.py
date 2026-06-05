#!/usr/bin/env python3
"""Stock every product so none read 'sold out'. API-created variants (productSet
with tracked:false) end up in a state where the storefront /cart/add returns 422
'already sold out' (tracked-with-zero-stock). Fix: enable inventory tracking and set
a healthy available quantity at the location; inventory_policy stays CONTINUE so
nothing ever hard-blocks. Idempotent."""
import time
from client import Shopify

QTY = 100  # healthy stock; low-stock badges come from the inv.tier metafield, not real qty

PVU = """mutation($pid:ID!,$v:[ProductVariantsBulkInput!]!){
  productVariantsBulkUpdate(productId:$pid, variants:$v){ userErrors{ message } } }"""
SETQ = """mutation($in:InventorySetQuantitiesInput!){
  inventorySetQuantities(input:$in){ userErrors{ message } } }"""

def main():
    s = Shopify()
    loc = s.gql("query{locations(first:1){nodes{id}}}")["locations"]["nodes"][0]["id"]

    items, cursor, tracked_on, prod = [], None, 0, 0
    while True:
        d = s.gql("query($c:String){products(first:50,after:$c){pageInfo{hasNextPage endCursor} "
                  "nodes{id variants(first:100){nodes{id inventoryItem{id tracked}}}}}}", {"c": cursor})["products"]
        for p in d["nodes"]:
            vs = p["variants"]["nodes"]
            upd = [{"id": v["id"], "inventoryItem": {"tracked": True}}
                   for v in vs if not v["inventoryItem"]["tracked"]]
            if upd:
                r = s.gql(PVU, {"pid": p["id"], "v": upd})["productVariantsBulkUpdate"]
                if not r.get("userErrors"):
                    tracked_on += len(upd)
                time.sleep(0.18)
            for v in vs:
                items.append(v["inventoryItem"]["id"])
            prod += 1
            if prod % 200 == 0:
                print(f"  tracking enabled, products scanned: {prod}")
        if not d["pageInfo"]["hasNextPage"]:
            break
        cursor = d["pageInfo"]["endCursor"]
    print(f"products scanned: {prod}; variants: {len(items)}; tracking turned on: {tracked_on}")

    # set available quantity in batches
    set_n = 0
    for i in range(0, len(items), 200):
        chunk = items[i:i + 200]
        q = [{"inventoryItemId": iid, "locationId": loc, "quantity": QTY} for iid in chunk]
        r = s.gql(SETQ, {"in": {"name": "available", "reason": "correction",
                                 "ignoreCompareQuantity": True, "quantities": q}})["inventorySetQuantities"]
        if r.get("userErrors"):
            print("  set qty errs:", r["userErrors"][:2])
        else:
            set_n += len(chunk)
        time.sleep(0.3)
    print(f"\navailable quantity set to {QTY} on {set_n} variants")

if __name__ == "__main__":
    main()
