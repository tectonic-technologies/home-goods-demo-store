#!/usr/bin/env python3
"""Normalize + de-brand + curate the raw crawl into ~1,000 cohesive home-goods products.
Output: data/curated.json (normalized) and data/curation_report.txt.
De-branding here is conservative (strip vendor + brand tokens from titles/desc);
full house-brand (MARLOW) voice rewrite is a later step (content.py)."""
import json, os, glob, re, html
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

# brand / vendor tokens stripped from titles + descriptions
BRAND_TOKENS = ["hawkins new york", "hawkins", "parachute home", "parachute",
                "coyuchi", "leif shop", "leif", "piglet in bed", "piglet",
                "farmhouse pottery", "farmhouse"]

# drop entirely: apparel/sleepwear, personal care, furniture, gift cards, off-aesthetic
JUNK = re.compile(
    r"gift card|e-gift|egift|\bsample\b|swatch|fabric by the yard|by the metre|"
    r"pajama|pyjama|sleepwear|nightgown|night dress|loungewear|\bslipper|"
    r"\bsock\b|\bsocks\b|scrunchie|hair tie|\bbag\b|tote\b|book\b|\bcard\b|"
    r"wick trimmer|candle snuffer kit|"
    # apparel (coyuchi 'Renewed' resale line, leif clothing)
    r"\bdress\b|\btee\b|t-shirt|\btshirt|jogger|cardigan|romper|jumpsuit|"
    r"legging|\bpants\b|trouser|\bshirt\b|sweater|sweatshirt|hoodie|\bgown\b|"
    r"\bskirt\b|\bshorts\b|\bbra\b|underwear|\bbrief\b|kimono|caftan|kaftan|"
    r"bath wrap|body wrap|beach wrap|cover-up|jumper|\bvest\b|\bscarf\b|"
    # personal care
    r"body serum|body wash|body lotion|body oil|hand cream|hand wash|shampoo|"
    r"conditioner|deodorant|bar soap|hand soap|facial|\bshave\b|perfume|fragrance oil|"
    # furniture
    r"bed frame|bed base|box spring|nightstand|dresser|headboard|\bsofa\b|"
    r"armchair|\bottoman\b|sideboard|\bcabinet\b|wardrobe|\bdesk\b|\bbench\b|"
    r"\bstool\b|mattress|\bcot\b|\bcrib\b|changing table|coffee table|console table|"
    r"dining table|side table|\bshelf\b|bookcase|\bchair\b",
    re.I)

# true bundles / configurators to drop (real sheet/place settings are KEPT)
SETLIKE = re.compile(r"gift set|gift bundle|build your own|build-your-own|"
                     r"create your own|mystery|bundle & save|sampler", re.I)

# category inference from product_type + title + tags (first match wins; order matters)
CATMAP = [
    ("Flatware", r"flatware|cutlery|silverware|\bfork\b|\bspoon\b|steak knife|"
                 r"utensil set|serving spoon|serving fork|\bcutler"),
    ("Glassware", r"\bglass\b|glasses\b|tumbler|stemware|wine glass|goblet|coupe|"
                  r"champagne|\bflute\b|decanter|carafe|drinkware|highball|lowball|"
                  r"old fashioned|cocktail glass|juice glass|water glass|stemless"),
    ("Bakeware", r"\bbaker\b|loaf pan|pie dish|pie plate|casserole|batter bowl|"
                 r"mixing bowl|measuring cup|canister|\bcrock\b|cookie jar|bread bin|"
                 r"bread box|utensil crock"),
    ("Serveware", r"serving bowl|serving platter|\bplatter\b|cheese board|"
                  r"cutting board|cheese knife|\btrivet\b|serving tray|\btray\b|"
                  r"colander|butter dish|salt cellar|pepper mill|salt and pepper|"
                  r"gravy boat|cake stand|cake plate|berry bowl|compote|pitcher|"
                  r"creamer|sugar bowl|teapot|tea pot|salad bowl|chip and dip"),
    ("Dinnerware", r"dinnerware|dinner plate|salad plate|dessert plate|side plate|"
                   r"\bcharger\b|\bplate\b|\bplates\b|\bbowl\b|\bbowls\b|\bmug\b|"
                   r"\bmugs\b|cup and saucer|teacup|tea cup|coffee cup|espresso cup|"
                   r"cereal bowl|pasta bowl|soup bowl|ramekin|place setting|"
                   r"\bdish\b|\bdishes\b|tumbler cup|coffee mug"),
    ("Table Linens", r"napkin|tablecloth|table cloth|table runner|placemat|place mat|"
                     r"table linen|cocktail napkin|dinner napkin"),
    ("Kitchen Linens", r"tea towel|dish towel|dishtowel|kitchen towel|\bapron\b|"
                       r"oven mitt|pot holder|potholder|dish cloth"),
    ("Bedding", r"duvet|comforter|\bquilt\b|coverlet|sheet set|fitted sheet|"
                r"flat sheet|\bsheets?\b|pillowcase|pillow case|pillow sham|"
                r"\bsham\b|bed skirt|bedding|bed set|matelasse|bedspread|bedspread"),
    ("Pillows & Cushions", r"pillow cover|throw pillow|decorative pillow|\bcushion\b|"
                           r"bolster|\bpillow\b|\bpouf\b|floor cushion|sham insert|"
                           r"pillow insert"),
    ("Throws & Blankets", r"throw blanket|\bthrow\b|\bblanket\b|afghan|\bquilt throw"),
    ("Bath", r"bath towel|hand towel|washcloth|wash cloth|bath sheet|bath mat|"
             r"\btowel\b|\btowels\b|\brobe\b|bathrobe|shower curtain|bath rug|"
             r"\bwaffle\b|bath mit|hooded towel"),
    ("Rugs & Mats", r"\brug\b|\brugs\b|doormat|door mat|floor mat|\bmat\b"),
    ("Lighting", r"\blamp\b|table lamp|floor lamp|\bsconce\b|pendant|lampshade|"
                 r"lamp shade|light fixture|chandelier|\bbulb\b|\bnightlight\b"),
    ("Candles & Scent", r"\bcandle\b|candles\b|\btaper\b|tapers\b|votive|"
                        r"candleholder|candle holder|candlestick|candelabra|"
                        r"\bincense\b|\bdiffuser\b|room spray|pillar candle"),
    ("Vases & Planters", r"\bvase\b|vases\b|planter|\bpot\b|bud vase|\burn\b|"
                         r"\bvessel\b|jardiniere|cachepot|flower frog"),
    ("Decor & Objects", r"\bmirror\b|picture frame|\bframe\b|bookend|sculpture|"
                        r"\bobject\b|ornament|\bgarland\b|\bwreath\b|wall hook|"
                        r"wall art|\bprint\b|figurine|catchall|catch-all|"
                        r"\bbox\b|matchbox|match strike|paperweight|coaster"),
    ("Storage & Baskets", r"\bbasket\b|baskets\b|storage bin|\bbin\b|hamper|"
                          r"storage box|organizer|\bcaddy\b|\bcrate\b|magazine"),
]

def strip_brands(text, extra=None):
    if not text: return text
    toks = BRAND_TOKENS + ([extra] if extra else [])
    for t in toks:
        if t and len(t) >= 3:
            text = re.sub(r"\b" + re.escape(t) + r"\b", "", text, flags=re.I)
    return re.sub(r"\s{2,}", " ", text).strip(" -–—|")

def clean_html(s):
    if not s: return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s{2,}", " ", s).strip()

def categorize(p):
    # primary signal: product_type + title (clean). Tags are noisy
    # (e.g. "not-pillowcase", "gwp-robe-sale") so only consult them as a fallback.
    primary = (p.get("product_type", "") + " " + p.get("title", "")).lower()
    for cat, pat in CATMAP:
        if re.search(pat, primary): return cat
    tags = " ".join(p.get("tags", []) if isinstance(p.get("tags"), list) else [])
    hay = (primary + " " + tags).lower()
    for cat, pat in CATMAP:
        if re.search(pat, hay): return cat
    return "Other"

# variant axis: largest option (Color, Size, Material, Set...) drives the variant story
def variant_axis(p):
    best_name, best_vals = None, []
    for o in p.get("options", []):
        vals = o.get("values", []) or []
        nm = (o.get("name") or "").strip()
        if nm.lower() in ("title",) and vals == ["Default Title"]:
            continue
        if len(vals) > len(best_vals):
            best_name, best_vals = nm, vals
    return best_name, len(best_vals)

def norm_tags(p):
    tags = p.get("tags", [])
    if isinstance(tags, str): tags = [t.strip() for t in tags.split(",")]
    clean = []
    for t in tags:
        tl = strip_brands(str(t).lower()).strip()
        if not tl or len(tl) > 28 or re.search(r"http|\.com|=|:|\d{4,}", tl):
            continue
        clean.append(tl)
    return sorted(set(clean))[:20]

def load_all():
    out = []
    for f in glob.glob(os.path.join(HERE, "raw", "*.json")):
        slug = os.path.basename(f)[:-5]
        if slug.startswith("_"):  # skip logs
            continue
        for p in json.load(open(f)):
            p["_brand"] = slug; out.append(p)
    return out

def score(p):
    s = min(len(p.get("images", [])), 8)
    s += 3 if len(clean_html(p.get("body_html"))) >= 120 else 0
    _, vc = variant_axis(p)
    if vc > 1: s += 4            # color/size/material variants = demo gold
    return s

def main():
    allp = load_all()
    if not allp:
        raise SystemExit("No raw crawl data found. Run crawl.py first.")
    cands = []
    for p in allp:
        hay = p.get("title", "") + " " + p.get("product_type", "")
        if JUNK.search(hay): continue
        if SETLIKE.search(p.get("title", "")): continue
        if not p.get("images"): continue
        cands.append(p)

    # curate per category for a balanced, cohesive assortment
    by_cat = {}
    for p in cands: by_cat.setdefault(categorize(p), []).append(p)
    TARGET = 1130  # over-curate; clean.py drops ~120 (dedup + broken) to net ~1,000
    # category caps keep variety (no single category dominates)
    caps = {"Other": 25, "Decor & Objects": 130, "Dinnerware": 140, "Bedding": 130,
            "Bath": 110, "Glassware": 110}
    # per-source-brand caps for a balanced blend (sum ~1100 so fill reaches TARGET)
    brand_caps = {"hawkins": 270, "leif": 260, "coyuchi": 220,
                  "parachute": 200, "farmhouse": 170, "piglet": 130}
    brand_used = Counter()
    curated = []
    for cat, items in by_cat.items():
        items.sort(key=score, reverse=True)
    order = sorted(by_cat, key=lambda c: -len(by_cat[c]))
    idx = {c: 0 for c in by_cat}
    cat_added = Counter()
    progressed = True
    while len(curated) < TARGET and progressed:
        progressed = False
        for c in order:
            if len(curated) >= TARGET: break
            if cat_added[c] >= caps.get(c, 9999): continue
            while idx[c] < len(by_cat[c]):
                p = by_cat[c][idx[c]]; idx[c] += 1
                b = p["_brand"]
                if brand_used[b] < brand_caps.get(b, 9999):
                    curated.append(p); brand_used[b] += 1; cat_added[c] += 1
                    progressed = True
                    break

    # normalize curated
    norm = []
    for p in curated:
        vendor = (p.get("vendor") or "").strip()
        opts = [{"name": o.get("name"), "values": o.get("values", [])} for o in p.get("options", [])]
        variants = [{
            "sku": v.get("sku"), "title": strip_brands(v.get("title"), vendor),
            "price": v.get("price"), "option_values": [v.get("option1"), v.get("option2"), v.get("option3")],
            "available": v.get("available"),
        } for v in p.get("variants", [])]
        axis_name, axis_n = variant_axis(p)
        norm.append({
            "src_brand": p["_brand"],
            "src_handle": p.get("handle"),
            "src_type": p.get("product_type", ""),
            "title": strip_brands(p.get("title"), vendor),
            "category": categorize(p),
            "description": strip_brands(clean_html(p.get("body_html")), vendor),
            "options": opts,
            "variants": variants,
            "images": [img.get("src") for img in p.get("images", [])],
            "tags": norm_tags(p),
            "primary_option": axis_name,
            "variant_count": axis_n,
        })

    os.makedirs(DATA, exist_ok=True)
    json.dump(norm, open(os.path.join(DATA, "curated.json"), "w"), indent=1)

    # report
    catc = Counter(p["category"] for p in norm)
    srcc = Counter(p["src_brand"] for p in norm)
    varied = sum(1 for p in norm if p["variant_count"] > 1)
    rep = ["CURATED CATALOG REPORT", f"count: {len(norm)}", "",
           "by category:"] + [f"  {v:3} {k}" for k, v in catc.most_common()] + \
          ["", "by source brand:"] + [f"  {v:3} {k}" for k, v in srcc.most_common()] + \
          ["", f"products with variant axis (>1): {varied}",
           f"total variants: {sum(len(p['variants']) for p in norm)}",
           f"total images: {sum(len(p['images']) for p in norm)}"]
    open(os.path.join(DATA, "curation_report.txt"), "w").write("\n".join(rep))
    print("\n".join(rep))

if __name__ == "__main__":
    main()
