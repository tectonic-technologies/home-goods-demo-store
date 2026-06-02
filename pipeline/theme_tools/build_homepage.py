#!/usr/bin/env python3
"""Rebuild the MARLOW homepage with real depth (vaaree-style): a Shop by Category
tile grid + several product carousels by collection + an editorial brand break.

product-list sections work reliably with a `collection` handle (unlike collection_list,
which Shopify strips from raw JSON). Category tiles are rendered by a custom-liquid block
using native Liquid (collections[handle] + the collection images already set), which also
bypasses the stripping. Edits local index.json AND pushes via Asset API."""
import json, os, sys, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shopify"))
from client import Shopify

THEME_ID = 153320390812
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
PATH = os.path.join(ROOT, "templates", "index.json")

# Shop-by-category tiles (handle, label) — sub-categories that photograph well
CAT_TILES = [
    ("cat-dinnerware", "Dinnerware"), ("cat-glassware", "Glassware"),
    ("cat-bedding", "Bedding"), ("cat-bath", "Bath"),
    ("cat-vases-planters", "Vases & Planters"), ("cat-candles-scent", "Candles"),
]
# product carousels: (section key, heading, collection handle)
ROWS = [
    ("mp_bestsellers", "Best Sellers", "best-sellers"),
    ("mp_tabletop", "The Tabletop", "top-tabletop"),
    ("mp_bedbath", "Bed & Bath", "top-bed-bath"),
    ("mp_new", "New Arrivals", "new"),
]

def heading_block(title):
    return {"type": "text", "settings": {
        "text": f"<h3><em>{title}</em></h3>", "width": "fit-content", "max_width": "normal",
        "alignment": "left", "type_preset": "h4", "font": "var(--font-primary--family)",
        "font_size": "", "line_height": "normal", "letter_spacing": "normal", "case": "none",
        "wrap": "pretty", "color": "", "background": False, "background_color": "#00000026",
        "corner_radius": 0, "padding-block-start": 0, "padding-block-end": 0,
        "padding-inline-start": 0, "padding-inline-end": 0}, "blocks": {}}

def category_section():
    handles = ",".join(h for h, _ in CAT_TILES)
    css = (
        "{%- assign hs = '" + handles + "' | split: ',' -%}"
        "<div class=\"marlow-cats\"><h3 class=\"marlow-cats__title\"><em>Shop by Category</em></h3>"
        "<div class=\"marlow-cats__grid\">"
        "{%- for h in hs -%}{%- assign c = collections[h] -%}{%- if c.id -%}"
        "<a class=\"marlow-cat\" href=\"{{ c.url }}\">"
        "<div class=\"marlow-cat__img\" style=\"background-image:url('{{ c.image | image_url: width: 700 }}')\"></div>"
        "<span class=\"marlow-cat__label\">{{ c.title }}</span></a>"
        "{%- endif -%}{%- endfor -%}</div></div>"
        "<style>"
        ".marlow-cats{max-width:1200px;margin:0 auto;padding:36px 20px;}"
        ".marlow-cats__title{text-align:center;font-weight:500;margin:0 0 24px;font-size:1.6rem;}"
        ".marlow-cats__grid{display:grid;grid-template-columns:repeat(6,1fr);gap:16px;}"
        ".marlow-cat{text-decoration:none;color:inherit;display:block;}"
        ".marlow-cat__img{aspect-ratio:1/1.15;background-size:cover;background-position:center;"
        "border-radius:4px;background-color:#f1efec;transition:opacity .2s;}"
        ".marlow-cat:hover .marlow-cat__img{opacity:.85;}"
        ".marlow-cat__label{display:block;margin-top:10px;text-align:center;font-size:.92rem;letter-spacing:.01em;}"
        "@media(max-width:749px){.marlow-cats__grid{grid-template-columns:repeat(2,1fr);}}"
        "</style>"
    )
    return {"type": "section", "name": "Shop by Category",
            "blocks": {"cats": {"type": "custom-liquid", "settings": {"custom_liquid": css}, "blocks": {}}},
            "block_order": ["cats"],
            "settings": {"content_direction": "column", "vertical_on_mobile": True,
                         "horizontal_alignment": "center", "vertical_alignment": "center",
                         "gap": 0, "section_width": "full-width", "color_scheme": "",
                         "padding-block-start": 12, "padding-block-end": 12}}

def main():
    raw = open(PATH).read()
    header = raw[:raw.index("{")]
    d = json.loads(raw[raw.index("{"):])

    hero_key = next(k for k, v in d["sections"].items() if v.get("type") == "hero")
    quote_key = next((k for k, v in d["sections"].items()
                      if v.get("type") == "section" and "quote" in (v.get("name", "").lower())), None)
    pl_template = next(v for v in d["sections"].values() if v.get("type") == "product-list")

    sections = {hero_key: d["sections"][hero_key]}
    if quote_key:
        sections[quote_key] = d["sections"][quote_key]
    sections["shop_by_category"] = category_section()

    for key, title, handle in ROWS:
        s = copy.deepcopy(pl_template)
        s["name"] = title
        s["settings"]["collection"] = handle
        s["settings"]["max_products"] = 8
        s["blocks"]["static-header"]["blocks"] = {"heading": heading_block(title)}
        s["blocks"]["static-header"]["block_order"] = ["heading"]
        sections[key] = s

    order = [hero_key, "shop_by_category", "mp_bestsellers", "mp_tabletop"]
    if quote_key:
        order.append(quote_key)
    order += ["mp_bedbath", "mp_new"]

    d["sections"] = sections
    d["order"] = order
    open(PATH, "w").write(header + json.dumps(d, indent=2))

    s = Shopify()
    r = s.rest("PUT", f"themes/{THEME_ID}/assets.json",
               {"asset": {"key": "templates/index.json", "value": open(PATH).read()}})
    print("pushed index.json:", "asset" in r and not r.get("errors"))
    print("homepage order:", order)

if __name__ == "__main__":
    main()
