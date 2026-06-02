#!/usr/bin/env python3
"""Idempotent fix for two room-collection titles that came out with a double 'Room'.
Safe to re-run: only updates when the title actually differs."""
from client import Shopify

FIXES = {"room-bedroom": "The Bedroom", "room-entryway": "The Entryway"}
Q = 'query($h:String!){ collectionByHandle(handle:$h){ id title } }'
M = 'mutation($i:CollectionInput!){ collectionUpdate(input:$i){ userErrors{message} } }'

def main():
    s = Shopify()
    for handle, want in FIXES.items():
        c = s.gql(Q, {"h": handle}).get("collectionByHandle")
        if not c:
            print(f"  {handle}: not found"); continue
        if c["title"] == want:
            print(f"  {handle}: already '{want}'"); continue
        r = s.gql(M, {"i": {"id": c["id"], "title": want}})["collectionUpdate"]
        print(f"  {handle}: '{c['title']}' -> '{want}'" + (f"  ERR {r['userErrors']}" if r.get("userErrors") else ""))

if __name__ == "__main__":
    main()
