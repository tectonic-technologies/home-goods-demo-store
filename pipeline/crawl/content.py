#!/usr/bin/env python3
"""Generate the MARLOW copy/content layer (authored, store-independent):
  - polished MARLOW-voice titles + descriptions + SEO
  - FAQs per product (material / care / dimensions)
  - A+ blocks for hero products
  - room sets (Shop-the-Look) and material/color families (Product Groups)
Outputs to data/content/. Content rules: no em-dash, no hype superlatives.
Reads enriched.json + synth/product_metrics.json, so run AFTER enrich_facets.py."""
import json, os, re, random
from collections import defaultdict

random.seed(7)
DATA = os.path.dirname(os.path.abspath(__file__)) + "/../data"
OUT = os.path.join(DATA, "content"); os.makedirs(OUT, exist_ok=True)
CAT = json.load(open(os.path.join(DATA, "catalog_clean.json")))
ENR = {e["display_title"]: e for e in json.load(open(os.path.join(DATA, "enriched.json")))}
MET = {m["display_title"]: m for m in json.load(open(os.path.join(DATA, "synth/product_metrics.json"))).values()}

# --- functional noun appended only if the title lacks a product noun ---
NOUN = {"Dinnerware":"Dinner Plate","Glassware":"Tumbler","Flatware":"Flatware Set",
        "Serveware":"Serving Bowl","Bakeware":"Baker","Bedding":"Duvet Cover",
        "Pillows & Cushions":"Throw Pillow","Throws & Blankets":"Throw","Bath":"Bath Towel",
        "Table Linens":"Linen Napkin","Kitchen Linens":"Tea Towel","Rugs & Mats":"Rug",
        "Lighting":"Table Lamp","Candles & Scent":"Candle","Vases & Planters":"Vase",
        "Decor & Objects":"Object","Storage & Baskets":"Basket","Other":"Home Object"}
NOUN_WORDS = set("""plate plates bowl bowls mug mugs cup cups dish dishes dinnerware tumbler glass
glasses goblet coupe flute carafe pitcher decanter flatware fork spoon knife cutlery platter
board tray trivet baker casserole loaf duvet quilt comforter sheet sheets sham pillowcase pillow
cushion bolster pouf throw blanket towel towels robe napkin napkins tablecloth runner placemat
rug mat lamp sconce pendant lantern candle taper votive vase planter pot urn vessel mirror frame
bookend sculpture object ornament basket bin crate box hamper coaster canister crock holder
candlestick candleholder""".split())

def polish_title(t, cat):
    t = re.sub(r"\s{2,}", " ", t).strip(" -")
    words = [w for w in t.split() if w]
    if len(words) < 2 or not any(w.lower().strip(",.") in NOUN_WORDS for w in words):
        t = (t + " " + NOUN[cat]).strip()
    return " ".join(w if w.isupper() else w[:1].upper()+w[1:] for w in t.split()).strip()

# --- description rewrite in MARLOW voice ---
LEAD = {
    "Dinnerware":"Made for everyday meals and the table when it matters.",
    "Glassware":"A glass that feels right in the hand.",
    "Flatware":"Weighted, balanced, made to last.",
    "Serveware":"Made to bring to the table and pass around.",
    "Bakeware":"From oven to table, nothing fussy.",
    "Bedding":"A softer place to land.",
    "Pillows & Cushions":"A little comfort, considered.",
    "Throws & Blankets":"For the cooler end of the evening.",
    "Bath":"Plush, thirsty, made to wear in.",
    "Table Linens":"The quiet layer that pulls a table together.",
    "Kitchen Linens":"Hard-working, and good-looking with it.",
    "Rugs & Mats":"Grounding underfoot.",
    "Lighting":"Warm light, quietly made.",
    "Candles & Scent":"A clean, grounding burn.",
    "Vases & Planters":"For stems, branches, or nothing at all.",
    "Decor & Objects":"A small, considered detail.",
    "Storage & Baskets":"Order, kept handsome.",
    "Other":"A considered piece for the home.",
}
CARE_COPY = {
    "dishwasher-safe":"Dishwasher safe.","microwave-safe":"Microwave safe.",
    "oven-safe":"Oven safe.","machine-washable":"Machine washable, tumble dry low.",
    "hand-wash":"Hand wash to keep it at its best.","food-safe":"Food safe and lead free.",
}
CARE_DEFAULT = {
    "Dinnerware":"Dishwasher safe.","Glassware":"Dishwasher safe.","Flatware":"Dishwasher safe.",
    "Serveware":"Hand wash to keep it at its best.","Bakeware":"Oven safe, hand wash recommended.",
    "Bedding":"Machine washable, softer with every wash.","Pillows & Cushions":"Removable cover, machine washable.",
    "Throws & Blankets":"Machine wash cold, lay flat to dry.","Bath":"Machine washable, more absorbent over time.",
    "Table Linens":"Machine washable, press while damp.","Kitchen Linens":"Machine washable.",
}
HYPE = re.compile(r"\b(first-ever|first ever|world'?s first|revolutionary|#1|number one|"
                  r"best-ever|best ever|instantly|miracle|magic|game-?changer|luxurious|ultimate)\b", re.I)
CAMEL = re.compile(r"\b[A-Z][a-z]+[A-Z][a-z]+\w*\b")

def tidy(s):
    s = HYPE.sub("", s)
    s = s.replace("—", ", ").replace(" — ", ", ").replace("–", ", ")
    s = re.sub(r"\s+,", ",", s); s = re.sub(r",\s*,", ",", s); s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" ,")

# source sentences to skip: brand/marketing voice or fragments broken by de-branding
PROMO_SENT = re.compile(r"\b(we'?ve|we are|we're|our team|partnered|partner with|"
                        r"introducing|meet the|collaborat|proudly|founded|brand|"
                        r"shop the|click here|sign up|newsletter|story behind|free shipping)\b", re.I)
BROKEN = re.compile(r"\bwith to\b|\bto\s*\.|\bwith\s*\.|\bfor\s*\.|\band\s*\.|^\W|  ", re.I)

def clean_source_sentence(s):
    if not s: return ""
    if PROMO_SENT.search(s) or BROKEN.search(s): return ""
    if not re.match(r"^[A-Z]", s): return ""   # likely a mid-clause fragment
    return s

def rewrite_desc(p, enr):
    cat = p["category"]; f = (enr or {}).get("facets", {})
    src = (p.get("clean_description") or "").strip()
    firstsent = clean_source_sentence(tidy(re.split(r"(?<=[.!])\s", src)[0])) if src else ""
    bits = [LEAD.get(cat, "A considered piece for the home.")]
    if firstsent and 30 < len(firstsent) < 220: bits.append(firstsent.rstrip("."))
    mats = f.get("materials") or ([f["material"]] if f.get("material") else [])
    if mats: bits.append(", ".join(m.capitalize() for m in mats[:2]) + " construction")
    care = f.get("care") or []
    care_line = CARE_COPY.get(care[0]) if care else CARE_DEFAULT.get(cat)
    txt = ". ".join(b.strip().rstrip(".") for b in bits if b) + "."
    if care_line: txt += " " + care_line
    return txt.replace(" — ", ", ").replace("—", ", ")

# --- FAQs ---
def faqs(p, enr):
    cat = p["category"]; f = (enr or {}).get("facets", {})
    mats = f.get("materials") or ([f["material"]] if f.get("material") else [])
    care = f.get("care") or []
    care_ans = CARE_COPY.get(care[0]) if care else CARE_DEFAULT.get(cat, "Wipe clean or spot clean as needed.")
    out = [
        {"category":"materials","question":f"What is the {p['display_title']} made of?",
         "answer":(f"Made from {', '.join(mats[:2])}." if mats else "Made from natural, considered materials.")},
        {"category":"care","question":"How do I care for it?",
         "answer":care_ans},
        {"category":"general","question":"Is it made for everyday use?",
         "answer":"Yes. It is built to be used and to wear in beautifully over time."},
    ]
    if (enr or {}).get("dimensions"):
        out.append({"category":"dimensions","question":"What are the dimensions?",
                    "answer":f"Approximately {enr['dimensions']}. See the product details for the full spec."})
    # Skip junk option names (e.g. source 'listing' axis with UUID values) — never
    # surface internal axis names in a customer FAQ.
    opt = (f.get("primary_option") or "").strip()
    if p.get("variant_count",0) > 1 and opt and opt.lower() not in ("listing", "title", "default title"):
        out.append({"category":"sizing","question":f"How do I choose a {opt.lower()}?",
                    "answer":f"Browse the {opt.lower()} options above. Each is made to the same standard, so choose what suits your space."})
    return out

# --- A+ blocks for heroes ---
def aplus(p, enr, met):
    f = (enr or {}).get("facets", {})
    mats = f.get("materials") or ([f["material"]] if f.get("material") else [])
    blocks = [{"type":"story","heading":"A more thoughtful home",
               "body":"Fewer, better pieces in natural materials. Made to be lived with, not looked at."}]
    if mats:
        blocks.append({"type":"material","heading":"Made from " + ", ".join(m.capitalize() for m in mats[:2]),
                       "body":"Honest materials, chosen for how they feel and how they last."})
    blocks.append({"type":"hero","heading":p["display_title"], "body": rewrite_desc(p, enr)})
    return blocks

def main():
    descs, fqs, ap = {}, {}, {}
    for p in CAT:
        enr = ENR.get(p["display_title"])
        title = polish_title(p["display_title"], p["category"])
        d = rewrite_desc(p, enr)
        descs[p["src_handle"]] = {
            "title": title, "description": d,
            "seo_title": f"{title} | MARLOW",
            "seo_description": (d[:150]).rstrip(". ") + ".",
        }
        fqs[p["src_handle"]] = faqs(p, enr)
    heroes = sorted(CAT, key=lambda p: MET.get(p["display_title"],{}).get("units_sold_total",0), reverse=True)[:40]
    for p in heroes:
        ap[p["src_handle"]] = aplus(p, ENR.get(p["display_title"]), MET.get(p["display_title"]))

    # room sets (Shop the Look)
    by_cat = defaultdict(list)
    for p in CAT: by_cat[p["category"]].append(p)
    def pick(cat):
        return random.choice(by_cat[cat])["src_handle"] if by_cat.get(cat) else None
    set_defs = [
        ("The Set Table","Layered for a slow dinner at home.",
         [("Table Linens","Start with the linen"),("Dinnerware","Lay the plates"),
          ("Glassware","Pour something"),("Flatware","Set each place")]),
        ("The Made Bed","Built up in considered layers.",
         [("Bedding","Start with the duvet"),("Pillows & Cushions","Layer the pillows"),
          ("Throws & Blankets","Fold a throw at the foot")]),
        ("The Considered Kitchen","Pieces that earn their counter space.",
         [("Bakeware","Bake it"),("Serveware","Serve it"),("Kitchen Linens","Wipe down")]),
        ("The Quiet Corner","A calm, lived-in vignette.",
         [("Lighting","Warm the corner"),("Vases & Planters","Add a few stems"),
          ("Candles & Scent","Light a candle"),("Decor & Objects","One small object")]),
        ("The Soft Bath","Spa-quiet, every day.",
         [("Bath","Stack the towels"),("Storage & Baskets","Keep it tidy")]),
    ]
    routines = []
    for name, ed, steps in set_defs:
        members = [{"product": pick(c), "note": n} for c, n in steps if pick(c)]
        routines.append({"title": name, "editorial": ed, "steps": members})

    # product groups (material/color families within a category)
    groups = []
    for cat in ["Dinnerware","Glassware","Bedding","Bath","Vases & Planters","Table Linens"]:
        items = [p for p in by_cat.get(cat, []) if p.get("variant_count",0) > 1][:4] or by_cat.get(cat, [])[:4]
        if len(items) >= 2:
            groups.append({"name": f"The {cat} Family", "axis": "material/color",
                           "members": [{"product": p["src_handle"],
                                        "label": polish_title(p["display_title"], cat)} for p in items]})

    json.dump(descs, open(f"{OUT}/descriptions.json","w"), indent=1)
    json.dump(fqs, open(f"{OUT}/faqs.json","w"), indent=1)
    json.dump(ap, open(f"{OUT}/aplus.json","w"), indent=1)
    json.dump(routines, open(f"{OUT}/routines.json","w"), indent=1)
    json.dump(groups, open(f"{OUT}/product_groups.json","w"), indent=1)

    print(f"descriptions: {len(descs)} (MARLOW voice)")
    print(f"FAQs: {sum(len(v) for v in fqs.values())} across {len(fqs)} products")
    print(f"A+ blocks: {sum(len(v) for v in ap.values())} across {len(ap)} hero products")
    print(f"room sets: {len(routines)} | product groups: {len(groups)}")
    print("\nsample title/desc:")
    for h in list(descs)[:4]:
        print(f"  {descs[h]['title']!r}\n    {descs[h]['description']}")

if __name__ == "__main__":
    main()
