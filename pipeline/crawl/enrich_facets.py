#!/usr/bin/env python3
"""Derive home-goods facets (material, room, color, style, care, dimensions),
Shopify taxonomy path, and select ~6 images. Also emit collection definitions.
Outputs data/enriched.json + data/collections.json. Reads synth/product_metrics.json,
so run AFTER synth.py. Facet inference is keyword-based off title+description+tags+variants."""
import json, os, re
from collections import Counter

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
CAT = json.load(open(os.path.join(DATA, "catalog_clean.json")))
METRICS = json.load(open(os.path.join(DATA, "synth", "product_metrics.json")))

# ---- facet vocabularies (first match = primary; all matches kept as lists) ----
MATERIAL = [
    ("stoneware", r"stoneware"),
    ("porcelain", r"porcelain|bone china|fine china"),
    ("ceramic", r"ceramic|earthenware|terracotta|terra cotta|stoneware clay|\bclay\b|pottery|enamel"),
    ("glass", r"\bglass\b|crystal|borosilicate"),
    ("linen", r"\blinen\b|\bflax\b"),
    ("cotton", r"cotton|percale|sateen|\bjersey\b|muslin|waffle|terry|matelasse|gauze|chambray|canvas"),
    ("wool", r"\bwool\b|merino|cashmere|alpaca|mohair|shearling|sheepskin|felt"),
    ("wood", r"\bwood\b|\boak\b|walnut|\bteak\b|acacia|\bmaple\b|mango wood|\bbamboo\b|\bash wood"),
    ("brass", r"\bbrass\b|\bbronze\b|\bcopper\b"),
    ("metal", r"stainless|\bsteel\b|\biron\b|aluminum|aluminium|pewter|\bzinc\b|\bmetal\b"),
    ("marble", r"\bmarble\b|travertine|soapstone|\bslate\b|\bstone\b"),
    ("rattan", r"rattan|wicker|\bcane\b|seagrass|\bjute\b|\bsisal\b|abaca|water hyacinth|\bwillow\b"),
    ("leather", r"leather|suede"),
    ("concrete", r"concrete|cement"),
]
ROOM_BY_CAT = {
    "Dinnerware": "dining", "Glassware": "dining", "Flatware": "dining",
    "Serveware": "dining", "Table Linens": "dining",
    "Bakeware": "kitchen", "Kitchen Linens": "kitchen",
    "Bedding": "bedroom", "Pillows & Cushions": "bedroom", "Throws & Blankets": "living",
    "Bath": "bath", "Rugs & Mats": "living", "Lighting": "living",
    "Candles & Scent": "living", "Vases & Planters": "living",
    "Decor & Objects": "living", "Storage & Baskets": "entryway", "Other": "living",
}
COLOR = [("white", r"\bwhite\b|\bivory\b|\bcream\b|\bbone\b|\bchalk\b|alabaster"),
         ("natural", r"\bnatural\b|oatmeal|\bflax\b|\bsand\b|\bbeige\b|\btaupe\b|\blinen\b|\bwheat\b|\bstraw\b|undyed"),
         ("grey", r"\bgrey\b|\bgray\b|\bash\b|\bsmoke\b|\bpewter\b|\bsilver\b|\bstone\b|\bfog\b"),
         ("black", r"\bblack\b|\bcharcoal\b|\bonyx\b|\bink\b|\bnoir\b"),
         ("blue", r"\bblue\b|\bnavy\b|indigo|\bdenim\b|\bteal\b|\bslate blue\b|cornflower"),
         ("green", r"\bgreen\b|\bsage\b|\bolive\b|\bmoss\b|\bfern\b|forest|eucalyptus|\bjade\b"),
         ("terracotta", r"terracotta|terra cotta|\brust\b|\bclay\b|\bbrick\b|\bsienna\b|\bochre\b|\bamber\b"),
         ("pink", r"\bpink\b|\bblush\b|\brose\b|\bmauve\b|\bdusty rose\b"),
         ("brown", r"\bbrown\b|\bcocoa\b|\bchocolate\b|\bespresso\b|\bcaramel\b|\bcognac\b|\bhoney\b|\bcamel\b"),
         ("gold", r"\bgold\b|\bbrass\b|\bbronze\b"),
         ("multi", r"\bmulti\b|stripe|\bplaid\b|\bcheck\b|\bfloral\b|\bpattern\b|colorblock")]
STYLE = [("rustic", r"rustic|farmhouse|\baged\b|\bhandmade\b|hand-?thrown|hand-?made|artisan|\bcrafted\b"),
         ("coastal", r"coastal|\bseaside\b|nautical|\bbeach\b"),
         ("scandi", r"scandi|nordic|\bminimal\b|\bsimple\b|\bclean lines\b"),
         ("traditional", r"traditional|\bclassic\b|\bheritage\b|\bvintage\b|antique"),
         ("organic", r"organic|\bnatural\b|\bearthy\b|\borganic shape\b|\bwabi\b"),
         ("modern", r"modern|\bcontemporary\b|sculptural|\bgeometric\b")]
CARE = [("dishwasher-safe", r"dishwasher.?safe|dishwasher safe"),
        ("microwave-safe", r"microwave.?safe|microwave safe"),
        ("oven-safe", r"oven.?safe|oven to table|oven safe"),
        ("machine-washable", r"machine.?wash|machine washable|tumble dry"),
        ("hand-wash", r"hand.?wash|hand wash only|spot clean"),
        ("food-safe", r"food.?safe|food safe|lead-?free")]

DIM = re.compile(r"(\d+(?:\.\d+)?)\s*[\"”']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*[\"”']?"
                 r"(?:\s*[xX×]\s*(\d+(?:\.\d+)?)\s*[\"”']?)?")

def all_matches(rules, hay):
    return [label for label, pat in rules if re.search(pat, hay)]

def first(rules, hay, default=None):
    for label, pat in rules:
        if re.search(pat, hay): return label
    return default

def price_band(price):
    if price < 40: return "entry"
    if price < 100: return "core"
    if price < 250: return "premium"
    return "luxe"

# Shopify standard taxonomy paths (GIDs resolved at load via taxonomy query)
TAX = {
    "Dinnerware": "Home & Garden > Kitchen & Dining > Tableware > Dinnerware",
    "Glassware": "Home & Garden > Kitchen & Dining > Tableware > Drinkware",
    "Flatware": "Home & Garden > Kitchen & Dining > Tableware > Flatware",
    "Serveware": "Home & Garden > Kitchen & Dining > Tableware > Serveware",
    "Bakeware": "Home & Garden > Kitchen & Dining > Cookware & Bakeware > Bakeware",
    "Bedding": "Home & Garden > Linens & Bedding > Bedding",
    "Pillows & Cushions": "Home & Garden > Decor > Throw Pillows",
    "Throws & Blankets": "Home & Garden > Linens & Bedding > Bedding > Blankets",
    "Bath": "Home & Garden > Linens & Bedding > Towels > Bath Towels",
    "Table Linens": "Home & Garden > Linens & Bedding > Table Linens",
    "Kitchen Linens": "Home & Garden > Linens & Bedding > Kitchen Linens",
    "Rugs & Mats": "Home & Garden > Decor > Rugs",
    "Lighting": "Home & Garden > Lighting > Lamps",
    "Candles & Scent": "Home & Garden > Decor > Home Fragrance > Candles",
    "Vases & Planters": "Home & Garden > Decor > Vases",
    "Decor & Objects": "Home & Garden > Decor",
    "Storage & Baskets": "Home & Garden > Household Supplies > Storage & Organization > Baskets, Bins & Containers",
    "Other": "Home & Garden > Decor",
}

def select_images(imgs, cap=6):
    if len(imgs) <= cap: return imgs
    out = [imgs[0]]
    rest = imgs[1:]
    step = max(1, len(rest)//(cap-1))
    out += rest[::step][:cap-1]
    return out[:cap]

def option_values_text(p):
    vals = []
    for o in p.get("options", []):
        for v in (o.get("values") or []):
            if isinstance(v, str): vals.append(v)
    return " ".join(vals)

def main():
    enriched = []
    for p in CAT:
        opttext = option_values_text(p)
        hay = (p["display_title"] + " " + p.get("clean_description","") + " " +
               " ".join(p.get("tags", [])) + " " + opttext).lower()
        m = next((mm for mm in METRICS.values() if mm["display_title"] == p["display_title"]), {})
        price = m.get("price", 0) or 0
        materials = all_matches(MATERIAL, hay)
        if not materials:  # safe category-definitional fallback
            fb = {"Glassware":"glass","Flatware":"metal","Bakeware":"ceramic"}.get(p["category"])
            if fb: materials = [fb]
        colors = all_matches(COLOR, hay)
        dim_m = DIM.search(p.get("clean_description","") or "")
        dimensions = None
        if dim_m:
            dims = [g for g in dim_m.groups() if g]
            dimensions = " x ".join(dims) + " in"
        enriched.append({
            "src_handle": p["src_handle"],
            "display_title": p["display_title"],
            "category": p["category"],
            "taxonomy_path": TAX.get(p["category"], TAX["Other"]),
            "facets": {
                "material": materials[0] if materials else None,
                "materials": materials,
                "room": ROOM_BY_CAT.get(p["category"], "living"),
                "color": colors,
                "style": first(STYLE, hay, "modern"),
                "care": all_matches(CARE, hay),
                "price_band": price_band(price),
                "has_variants": p.get("variant_count", 0) > 1,
                "variant_count": p.get("variant_count", 0),
                "primary_option": p.get("primary_option"),
            },
            "dimensions": dimensions,
            "images": select_images(p.get("images", [])),
        })
    json.dump(enriched, open(os.path.join(DATA,"enriched.json"),"w"), indent=1)

    # ---- collection definitions ----
    cats = sorted({p["category"] for p in CAT})
    collections = []
    for c in cats:
        collections.append({"handle": "cat-"+re.sub(r"[^a-z0-9]+","-",c.lower()).strip("-"),
                            "title": c, "type": "smart", "rule": {"field":"category","value":c}})
    for room in ["dining","kitchen","bedroom","bath","living","entryway"]:
        collections.append({"handle":"room-"+room,"title":"The "+room.title()+" Room" if room not in ("dining","bath","kitchen") else {"dining":"The Dining Room","bath":"The Bath","kitchen":"The Kitchen"}[room],
                            "type":"smart","rule":{"field":"room","value":room}})
    # top materials as collections
    mat_counts = Counter(e["facets"]["material"] for e in enriched if e["facets"]["material"])
    for mat,_ in mat_counts.most_common(8):
        collections.append({"handle":"material-"+mat,"title":mat.title(),
                            "type":"smart","rule":{"field":"material","value":mat}})
    collections += [
        {"handle":"best-sellers","title":"Best Sellers","type":"manual","rule":{"field":"best_seller"}},
        {"handle":"new","title":"New Arrivals","type":"manual","rule":{"field":"is_new"}},
        {"handle":"last-chance","title":"Last Chance","type":"manual","rule":{"field":"is_clearance"}},
        {"handle":"the-edit","title":"The Edit","type":"manual","rule":{"field":"editorial"}},
        {"handle":"the-tabletop","title":"The Tabletop","type":"smart","rule":{"field":"room","value":"dining"}},
    ]
    json.dump(collections, open(os.path.join(DATA,"collections.json"),"w"), indent=1)

    # report
    img_total = sum(len(e["images"]) for e in enriched)
    mat = Counter(e["facets"]["material"] for e in enriched)
    room = Counter(e["facets"]["room"] for e in enriched)
    print(f"enriched {len(enriched)} products")
    print(f"images after ~6 cap: {img_total} (avg {img_total/len(enriched):.1f}/product)")
    print(f"material coverage: {dict(mat.most_common())}")
    print(f"room coverage: {dict(room)}")
    print(f"with color facet: {sum(1 for e in enriched if e['facets']['color'])}")
    print(f"with care facet: {sum(1 for e in enriched if e['facets']['care'])}")
    print(f"with dimensions: {sum(1 for e in enriched if e['dimensions'])}")
    print(f"collections defined: {len(collections)}")

if __name__ == "__main__":
    main()
