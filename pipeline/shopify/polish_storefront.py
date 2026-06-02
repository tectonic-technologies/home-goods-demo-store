#!/usr/bin/env python3
"""Storefront polish (playbook 6b/10) applied to the connected MARLOW theme via the
Asset API for instant effect (GitHub sync lags). Edits local theme files AND pushes
them to the theme so the preview updates immediately. Idempotent.

Fixes: header/footer logo -> MARLOW, announcement copy, hero lifestyle background +
tagline (covers the stock placeholder), and removes the stock placeholder sections
(media-with-content t-shirt on home + PDP, empty product-hotspots) that read as fake."""
import json, os, re
from client import Shopify

THEME_ID = 153320390812
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")

HERO_IMG = "https://cdn.shopify.com/s/files/1/0750/8878/9660/files/noe_duvet_softwhite_c_sp22_3946_x_1d8cbc30-a8fd-41cd-83e1-b19867cbbd9f.jpg?v=1780410978"
HERO_CSS = (
    "<style>"
    ".hero .hero__media-grid{background-image:url('" + HERO_IMG + "') !important;"
    "background-size:cover !important;background-position:center !important;}"
    ".hero svg.hero__media{opacity:0 !important;}"
    ".hero .overlay--gradient{opacity:.35 !important;}"
    "</style>"
)
ANNOUNCE = "Complimentary shipping over $150 · A more thoughtful home"

# homepage collection-list sections, in document order, get these real collections
TOPS = ["gid://shopify/Collection/328507687068", "gid://shopify/Collection/328507719836",
        "gid://shopify/Collection/328507752604", "gid://shopify/Collection/328507785372",
        "gid://shopify/Collection/328507818140"]
ACCESSORIES = ["gid://shopify/Collection/328501231772", "gid://shopify/Collection/328501690524",
               "gid://shopify/Collection/328501264540", "gid://shopify/Collection/328501428380",
               "gid://shopify/Collection/328501592220"]

def read(path):
    return open(os.path.join(ROOT, path)).read()

def split_header(raw):
    i = raw.index("{")
    return raw[:i], raw[i:]

def patch_logo(raw):
    return raw.replace("text_fallback: shop.name", "text_fallback: 'MARLOW'")

def patch_announcement(raw):
    h, body = split_header(raw) if raw.lstrip().startswith("/*") else ("", raw)
    d = json.loads(body)
    for sec in d.get("sections", {}).values():
        for blk in sec.get("blocks", {}).values():
            if blk.get("type") == "_announcement" and "text" in blk.get("settings", {}):
                blk["settings"]["text"] = ANNOUNCE
    return h + json.dumps(d, indent=2)

def patch_index(raw):
    h, body = split_header(raw)
    d = json.loads(body)
    hero = next((s for s in d["sections"].values() if s.get("type") == "hero"), None)
    if hero:
        for b in hero["blocks"].values():
            if b.get("type") == "text":
                b["settings"]["text"] = "<h2><em>A more thoughtful home</em></h2>"
                break
        hero["blocks"]["marlow_hero_bg"] = {"type": "custom-liquid",
                                            "settings": {"custom_liquid": HERO_CSS}, "blocks": {}}
        if "marlow_hero_bg" not in hero["block_order"]:
            hero["block_order"].append("marlow_hero_bg")
    # remove stock placeholder sections (t-shirt bestseller, empty hotspots + its heading)
    for k in list(d["sections"]):
        s = d["sections"][k]
        if s.get("type") in ("media-with-content", "product-hotspots") or s.get("name") == "Hotspots heading":
            d["sections"].pop(k, None)
            if k in d["order"]:
                d["order"].remove(k)
    # assign real collections to the collection-list sections (in order) so they
    # stop showing placeholder "COLLECTION TITLE" t-shirt cards
    cl_order = [k for k in d["order"] if d["sections"].get(k, {}).get("type") == "collection-list"]
    picks = [TOPS, ACCESSORIES]
    for i, k in enumerate(cl_order[:2]):
        d["sections"][k]["settings"]["collection_list"] = picks[i]
        d["sections"][k]["settings"]["max_collections"] = 5
    return h + json.dumps(d, indent=2)

def patch_brand(raw):
    # replace shop.name only where it's not followed by a property access (.size etc.),
    # so "{{ shop.name.size ... }}" stays valid Liquid.
    return re.sub(r"shop\.name(?!\.)", "'MARLOW'", raw)

def patch_product(raw):
    h, body = split_header(raw)
    d = json.loads(body)
    for k in list(d["sections"]):
        if d["sections"][k].get("type") == "media-with-content":
            d["sections"].pop(k, None)
            if k in d["order"]:
                d["order"].remove(k)
    return h + json.dumps(d, indent=2)

EDITS = [
    ("blocks/_header-logo.liquid", patch_logo),
    ("blocks/logo.liquid", patch_brand),
    ("blocks/footer-copyright.liquid", patch_brand),
    ("sections/header-group.json", patch_announcement),
    ("templates/index.json", patch_index),
    ("templates/product.json", patch_product),
]

def main():
    s = Shopify()
    for path, fn in EDITS:
        new = fn(read(path))
        open(os.path.join(ROOT, path), "w").write(new)        # local
        r = s.rest("PUT", f"themes/{THEME_ID}/assets.json",
                   {"asset": {"key": path, "value": new}})      # live (instant)
        ok = "asset" in r and not r.get("errors")
        print(f"  {'OK ' if ok else 'ERR'} {path}" + ("" if ok else f"  {str(r)[:200]}"))
    print("\nstorefront polish pushed to theme", THEME_ID)

if __name__ == "__main__":
    main()
