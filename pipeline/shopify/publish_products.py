#!/usr/bin/env python3
"""Publish all products to the Online Store channel. productSet creates products
as ACTIVE but does NOT publish them to a sales channel, so they stay invisible on
the storefront until published (see playbook section 4). Idempotent: re-publishing
an already-published product is a no-op. Run after load_products.py."""
import time
from client import Shopify

PUBS = "query{ publications(first:25){ nodes{ id name } } }"
PUBLISH = """
mutation($id:ID!,$pid:ID!){
  publishablePublish(id:$id, input:[{publicationId:$pid}]){
    userErrors{ field message } } }"""

def online_store_publication_id(s):
    for n in s.gql(PUBS)["publications"]["nodes"]:
        if n["name"] == "Online Store":
            return n["id"]
    # fall back to the first publication if the channel is named differently
    nodes = s.gql(PUBS)["publications"]["nodes"]
    return nodes[0]["id"] if nodes else None

def main():
    s = Shopify()
    pid = online_store_publication_id(s)
    if not pid:
        raise SystemExit("No publications found; is the Online Store channel installed?")
    print(f"Online Store publication: {pid}")

    ok, err, cursor = 0, 0, None
    while True:
        d = s.gql('query($c:String){products(first:100,after:$c){pageInfo{hasNextPage endCursor} nodes{id title}}}', {"c": cursor})["products"]
        for n in d["nodes"]:
            res = s.gql(PUBLISH, {"id": n["id"], "pid": pid})["publishablePublish"]
            if res.get("userErrors"):
                err += 1
                if err <= 5: print(f"  ERR {n['title']}: {res['userErrors'][:1]}")
            else:
                ok += 1
                if ok % 100 == 0: print(f"  published: {ok}")
            time.sleep(0.3)
        if not d["pageInfo"]["hasNextPage"]: break
        cursor = d["pageInfo"]["endCursor"]
    print(f"\npublished to Online Store: ok={ok} err={err}")

if __name__ == "__main__":
    main()
