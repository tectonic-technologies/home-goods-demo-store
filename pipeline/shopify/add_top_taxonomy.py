#!/usr/bin/env python3
"""2-level taxonomy (playbook 9): tag every product with cat:<top> and create
top-level smart collections, so navigation can be Shop -> top -> sub. The 18
loaded categories are the 'sub' level (productType); these 5 are the 'top' level.
Idempotent: tagsAdd is a no-op for existing tags; existing collections are skipped."""
import time
from client import Shopify

TOP_OF = {
    "Dinnerware":"tabletop","Glassware":"tabletop","Flatware":"tabletop",
    "Serveware":"tabletop","Bakeware":"tabletop",
    "Bedding":"bed-bath","Pillows & Cushions":"bed-bath","Throws & Blankets":"bed-bath","Bath":"bed-bath",
    "Table Linens":"linens","Kitchen Linens":"linens",
    "Vases & Planters":"decor-lighting","Candles & Scent":"decor-lighting",
    "Decor & Objects":"decor-lighting","Lighting":"decor-lighting","Rugs & Mats":"decor-lighting",
    "Storage & Baskets":"storage","Other":"decor-lighting",
}
TOP_TITLE = {"tabletop":"Tabletop","bed-bath":"Bed & Bath","linens":"Linens",
             "decor-lighting":"Decor & Lighting","storage":"Storage"}

TAGSADD = 'mutation($id:ID!,$t:[String!]!){ tagsAdd(id:$id, tags:$t){ userErrors{message} } }'
COL_CREATE = """
mutation($input: CollectionInput!){ collectionCreate(input:$input){
  collection{ id handle } userErrors{ field message } } }"""
PUBS = "query{ publications(first:25){ nodes{ id name } } }"
PUBLISH = 'mutation($id:ID!,$pid:ID!){ publishablePublish(id:$id, input:[{publicationId:$pid}]){ userErrors{message} } }'
Q_COLS = "query($c:String){ collections(first:100,after:$c){ pageInfo{hasNextPage endCursor} nodes{ handle } } }"

def online_store_pub(s):
    for n in s.gql(PUBS)["publications"]["nodes"]:
        if n["name"] == "Online Store": return n["id"]
    return s.gql(PUBS)["publications"]["nodes"][0]["id"]

def main():
    s = Shopify()

    # 1. tag every product with cat:<top> (derived from productType = sub category)
    tagged, cursor, miss = 0, None, 0
    while True:
        d = s.gql('query($c:String){products(first:100,after:$c){pageInfo{hasNextPage endCursor} nodes{id productType}}}', {"c": cursor})["products"]
        for n in d["nodes"]:
            top = TOP_OF.get(n["productType"])
            if not top: miss += 1; continue
            r = s.gql(TAGSADD, {"id": n["id"], "t": [f"cat:{top}"]})["tagsAdd"]
            if not r.get("userErrors"): tagged += 1
            if tagged % 200 == 0: print(f"  tagged: {tagged}")
            time.sleep(0.12)
        if not d["pageInfo"]["hasNextPage"]: break
        cursor = d["pageInfo"]["endCursor"]
    print(f"tagged cat:<top> on {tagged} products (unmapped types: {miss})")

    # 2. create top-level smart collections (TAG = cat:<slug>)
    existing, cursor = set(), None
    while True:
        d = s.gql(Q_COLS, {"c": cursor})["collections"]
        existing.update(n["handle"] for n in d["nodes"])
        if not d["pageInfo"]["hasNextPage"]: break
        cursor = d["pageInfo"]["endCursor"]
    pid = online_store_pub(s)
    made = 0
    for slug, title in TOP_TITLE.items():
        handle = f"top-{slug}"
        if handle in existing:
            print(f"  collection exists: {handle}"); continue
        inp = {"title": title, "handle": handle,
               "ruleSet": {"appliedDisjunctively": False,
                           "rules": [{"column": "TAG", "relation": "EQUALS", "condition": f"cat:{slug}"}]}}
        res = s.gql(COL_CREATE, {"input": inp})["collectionCreate"]
        if res.get("userErrors"): print(f"  ERR {handle}: {res['userErrors'][:1]}"); continue
        cid = res["collection"]["id"]; made += 1
        s.gql(PUBLISH, {"id": cid, "pid": pid})
        print(f"  + {title} ({handle}) published")
        time.sleep(0.3)
    print(f"\ntop collections created={made}")

if __name__ == "__main__":
    main()
