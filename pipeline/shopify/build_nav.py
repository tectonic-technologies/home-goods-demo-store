#!/usr/bin/env python3
"""Build the main + footer navigation via menuUpdate (playbook 6b/10):
Shop -> 5 top categories -> subcategories, plus Best Sellers / New flat items.
Resolves collection GIDs by handle. Idempotent (menuUpdate replaces items)."""
from client import Shopify

# top slug -> (title, [sub category handles in order])
NAV = [
    ("top-tabletop", "Tabletop", ["cat-dinnerware","cat-glassware","cat-flatware","cat-serveware","cat-bakeware"]),
    ("top-bed-bath", "Bed & Bath", ["cat-bedding","cat-pillows-cushions","cat-throws-blankets","cat-bath"]),
    ("top-linens", "Linens", ["cat-table-linens","cat-kitchen-linens"]),
    ("top-decor-lighting", "Decor & Lighting", ["cat-vases-planters","cat-candles-scent","cat-decor-objects","cat-lighting","cat-rugs-mats"]),
    ("top-storage", "Storage", ["cat-storage-baskets"]),
]
FLAT = [("best-sellers", "Best Sellers"), ("new", "New Arrivals")]

Q_COLS = "query($c:String){ collections(first:100,after:$c){ pageInfo{hasNextPage endCursor} nodes{ id handle title } } }"
Q_MENUS = "query{ menus(first:20){ nodes{ id handle title } } }"
M = """
mutation($id:ID!,$title:String!,$items:[MenuItemUpdateInput!]!){
  menuUpdate(id:$id, title:$title, items:$items){
    menu{ id handle items{ title items{ title items{ title } } } }
    userErrors{ field message } } }"""

def main():
    s = Shopify()
    by_handle, cursor = {}, None
    while True:
        d = s.gql(Q_COLS, {"c": cursor})["collections"]
        for n in d["nodes"]: by_handle[n["handle"]] = (n["id"], n["title"])
        if not d["pageInfo"]["hasNextPage"]: break
        cursor = d["pageInfo"]["endCursor"]

    def col_item(handle, title=None):
        gid, t = by_handle[handle]
        return {"title": title or t, "type": "COLLECTION", "resourceId": gid, "items": []}

    # Shop -> tops -> subs
    shop_children = []
    for top_handle, top_title, subs in NAV:
        if top_handle not in by_handle:
            print(f"  missing {top_handle}"); continue
        sub_items = [col_item(h) for h in subs if h in by_handle]
        gid, _ = by_handle[top_handle]
        shop_children.append({"title": top_title, "type": "COLLECTION", "resourceId": gid, "items": sub_items})
    items = [{"title": "Shop", "type": "HTTP", "url": "/collections/all", "items": shop_children}]
    for handle, title in FLAT:
        if handle in by_handle: items.append(col_item(handle, title))

    menus = {m["handle"]: m["id"] for m in s.gql(Q_MENUS)["menus"]["nodes"]}
    mid = menus.get("main-menu")
    if not mid:
        raise SystemExit(f"main-menu not found; menus = {list(menus)}")
    res = s.gql(M, {"id": mid, "title": "Main menu", "items": items})["menuUpdate"]
    if res.get("userErrors"):
        raise SystemExit(f"menuUpdate errors: {res['userErrors']}")
    menu = res["menu"]
    print("main-menu updated. Top level:")
    for it in menu["items"]:
        print(f"  - {it['title']}" + (f"  ({len(it['items'])} children)" if it["items"] else ""))
        for c in it["items"]:
            print(f"      > {c['title']}" + (f" ({len(c['items'])})" if c["items"] else ""))

if __name__ == "__main__":
    main()
