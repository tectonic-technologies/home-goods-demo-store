#!/usr/bin/env python3
"""Generate the synthetic data backbone for the MARLOW home store, internally consistent:
orders drive velocity, best-sellers, and FBT co-purchase; reviews scale with sales.
Outputs to data/synth/: customers.json, orders.json, product_metrics.json, reviews.json
Seeded for reproducibility. Runs BEFORE enrich_facets.py (which reads product_metrics)."""
import json, os, random, datetime as dt
from collections import defaultdict, Counter

random.seed(42)
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
SYNTH = os.path.join(DATA, "synth")
os.makedirs(SYNTH, exist_ok=True)
NOW = dt.date(2026, 6, 2)

CATALOG = json.load(open(os.path.join(DATA, "catalog_clean.json")))

# ---- product popularity priors (category demand x variant depth x noise) ----
CAT_DEMAND = {
    "Dinnerware": 1.6, "Glassware": 1.5, "Bedding": 1.5, "Bath": 1.4,
    "Table Linens": 1.3, "Throws & Blankets": 1.3, "Pillows & Cushions": 1.3,
    "Flatware": 1.2, "Candles & Scent": 1.2, "Serveware": 1.1, "Vases & Planters": 1.1,
    "Kitchen Linens": 1.0, "Decor & Objects": 1.0, "Bakeware": 0.9,
    "Storage & Baskets": 0.9, "Lighting": 0.9, "Rugs & Mats": 0.8, "Other": 0.6,
}
# basket affinities: anchor category -> commonly co-bought categories (room/use sets)
AFFINITY = {
    "Dinnerware": ["Glassware", "Flatware", "Serveware", "Table Linens"],
    "Glassware": ["Dinnerware", "Serveware", "Flatware"],
    "Flatware": ["Dinnerware", "Glassware", "Table Linens"],
    "Serveware": ["Dinnerware", "Table Linens", "Glassware", "Bakeware"],
    "Bakeware": ["Serveware", "Kitchen Linens", "Dinnerware"],
    "Table Linens": ["Dinnerware", "Flatware", "Glassware"],
    "Kitchen Linens": ["Bakeware", "Serveware", "Dinnerware"],
    "Bedding": ["Pillows & Cushions", "Throws & Blankets", "Bath"],
    "Pillows & Cushions": ["Bedding", "Throws & Blankets", "Decor & Objects"],
    "Throws & Blankets": ["Bedding", "Pillows & Cushions", "Decor & Objects"],
    "Bath": ["Bedding", "Throws & Blankets", "Storage & Baskets"],
    "Vases & Planters": ["Decor & Objects", "Candles & Scent"],
    "Candles & Scent": ["Decor & Objects", "Vases & Planters", "Lighting"],
    "Decor & Objects": ["Vases & Planters", "Candles & Scent", "Lighting", "Pillows & Cushions"],
    "Lighting": ["Decor & Objects", "Candles & Scent"],
    "Rugs & Mats": ["Decor & Objects", "Storage & Baskets"],
    "Storage & Baskets": ["Bath", "Bedding", "Decor & Objects"],
}
# gross-margin priors by category (small goods richer; rugs/lighting heavier COGS)
CAT_MARGIN = {
    "Candles & Scent": 0.70, "Decor & Objects": 0.66, "Vases & Planters": 0.64,
    "Table Linens": 0.62, "Kitchen Linens": 0.62, "Dinnerware": 0.60, "Glassware": 0.60,
    "Serveware": 0.58, "Bakeware": 0.58, "Flatware": 0.58, "Storage & Baskets": 0.58,
    "Pillows & Cushions": 0.56, "Throws & Blankets": 0.54, "Bath": 0.54,
    "Bedding": 0.52, "Lighting": 0.50, "Rugs & Mats": 0.46, "Other": 0.55,
}

def first_variant_price(p):
    for v in p["variants"]:
        try:
            return float(v.get("price") or 0)
        except ValueError:
            return 0.0
    return 0.0

for i, p in enumerate(CATALOG):
    p["_i"] = i
    p["_price"] = round(first_variant_price(p) or random.uniform(24, 180), 2)
    base = CAT_DEMAND.get(p["category"], 0.7)
    base *= 1.25 if p.get("variant_count", 0) > 1 else 1.0
    p["_pop"] = max(0.05, random.lognormvariate(0, 0.6) * base)

by_cat = defaultdict(list)
for p in CATALOG:
    by_cat[p["category"]].append(p)
pop_weights = [p["_pop"] for p in CATALOG]

def pick_product(weights=None):
    return random.choices(CATALOG, weights=weights or pop_weights, k=1)[0]

# ---- customers ----
FIRST = ("Ava Mia Zoe Ivy Lena Nora Ruby Eva Aria Maya Cleo Iris Faye Tess Remy Juno "
         "Wren Esme Greta Noor Priya Anaya Leah Sana Dina Hana Lola Romy Edie Nell "
         "Liam Noah Ezra Cole Reid Theo Milo Owen Jude Hugo Asa Eli Beau Wes Roman "
         "Dev Arjun Omar Sage Quinn Rory Elliot Hadley June Margot").split()
LAST = ("Reed Park Cole Hayes Vance Stone Quinn Rhodes Frost Lake Marsh Wells Brook Vale "
        "Pierce Ash Finch Knox Sloane Day Fox Bram Hale Crane Mercer Booth Lowell Tate "
        "Ramsey Okafor Nair Sato Cho Romano Vega Bauer Ellis Hart Maddox").split()
CITIES = [("New York","NY","US"),("Los Angeles","CA","US"),("Austin","TX","US"),("Chicago","IL","US"),
          ("Seattle","WA","US"),("Miami","FL","US"),("Denver","CO","US"),("Portland","OR","US"),
          ("Boston","MA","US"),("Brooklyn","NY","US"),("Minneapolis","MN","US"),("Nashville","TN","US"),
          ("Atlanta","GA","US"),("San Francisco","CA","US"),("Charleston","SC","US")]

def make_customers(n=600):
    custs = []
    for k in range(n):
        fn, ln = random.choice(FIRST), random.choice(LAST)
        city, prov, cc = random.choice(CITIES)
        created = NOW - dt.timedelta(days=random.randint(1, 540))
        seg = random.choices(["new", "returning", "vip"], weights=[5, 4, 1])[0]
        custs.append({
            "ref": f"C{k+1:04d}",
            "first_name": fn, "last_name": ln,
            "email": f"{fn.lower()}.{ln.lower()}{random.randint(1,899)}@example.com",
            "city": city, "province": prov, "country_code": cc,
            "created_at": created.isoformat(),
            "tags": [seg, "demo"],
            "_seg": seg,
        })
    return custs

def make_orders(custs, n=2400):
    orders = []
    def order_date():
        d = int(min(269, abs(random.gauss(0, 110))))
        return NOW - dt.timedelta(days=d)
    for k in range(n):
        c = random.choices(custs, weights=[3 if x["_seg"]=="vip" else 2 if x["_seg"]=="returning" else 1 for x in custs])[0]
        anchor = pick_product()
        items = [anchor]
        # home baskets run a touch larger than beauty (room sets)
        for _ in range(random.choices([0,1,2,3,4], weights=[2,4,3,2,1])[0]):
            aff = AFFINITY.get(anchor["category"], [])
            if aff and random.random() < 0.72:
                pool = [p for p in by_cat[random.choice(aff)]]
                if pool:
                    items.append(random.choices(pool, weights=[p["_pop"] for p in pool])[0])
                    continue
            items.append(pick_product())
        seen, line = set(), []
        for p in items:
            if p["_i"] in seen: continue
            seen.add(p["_i"])
            qty = random.choices([1,2,3,4], weights=[68,18,9,5])[0]  # tabletop bought in multiples
            line.append({"product_i": p["_i"], "title": p["display_title"], "qty": qty, "price": p["_price"]})
        subtotal = round(sum(l["qty"]*l["price"] for l in line), 2)
        orders.append({
            "ref": f"O{k+1:05d}", "customer_ref": c["ref"],
            "created_at": order_date().isoformat(),
            "line_items": line, "subtotal": subtotal,
            "financial_status": "paid",
            "fulfillment_status": random.choices(["fulfilled","unfulfilled"], weights=[8,2])[0],
        })
    return orders

# ---- derive product metrics from orders ----
def derive_metrics(orders):
    units_total = Counter(); units_30d = Counter(); revenue = Counter()
    cooc = defaultdict(Counter)
    for o in orders:
        odate = dt.date.fromisoformat(o["created_at"])
        recent = (NOW - odate).days <= 30
        idxs = [l["product_i"] for l in o["line_items"]]
        for l in o["line_items"]:
            units_total[l["product_i"]] += l["qty"]
            revenue[l["product_i"]] += l["qty"]*l["price"]
            if recent: units_30d[l["product_i"]] += l["qty"]
        for a in idxs:
            for b in idxs:
                if a != b: cooc[a][b] += 1
    sold_sorted = sorted(units_total.values(), reverse=True)
    best_cut = sold_sorted[max(0, int(len(sold_sorted)*0.15)-1)] if sold_sorted else 0
    metrics = {}
    for p in CATALOG:
        i = p["_i"]
        ut = units_total.get(i, 0)
        on_hand = max(0, int(random.lognormvariate(4.4, 0.7)))
        tier = "healthy"
        roll = random.random()
        if roll < 0.04: on_hand, tier = random.randint(1,6), "critical"
        elif roll < 0.14: on_hand, tier = random.randint(7,20), "low"
        cat_margin = CAT_MARGIN.get(p["category"], 0.55)
        margin = round(min(0.85, max(0.4, random.gauss(cat_margin, 0.06))), 3)
        is_clear = random.random() < 0.08
        is_new = random.random() < 0.15
        fbt = [CATALOG[b]["display_title"] for b, _ in cooc[i].most_common(4)]
        base_price = p["_price"]
        hist = []
        for m in range(4, -1, -1):
            d = (NOW - dt.timedelta(days=m*45)).isoformat()
            price = base_price
            if is_clear and m == 0: price = round(base_price*0.75, 2)
            hist.append({"date": d, "price": price})
        metrics[str(i)] = {
            "display_title": p["display_title"], "category": p["category"], "price": base_price,
            "units_sold_total": ut, "units_sold_30d": units_30d.get(i, 0),
            "revenue": round(revenue.get(i, 0), 2),
            "best_seller": ut >= best_cut and ut > 0,
            "on_hand": on_hand, "inv_tier": tier,
            "margin": margin, "is_new": is_new, "is_clearance": is_clear,
            "fbt": fbt, "live_viewers_base": max(1, int(p["_pop"]*4)),
            "price_history": hist,
        }
    return metrics

# ---- reviews ----
TITLES_POS = ["Exactly what I hoped for","Buying more","Beautiful and well made","Better in person",
              "New everyday favorite","Obsessed","Worth it","Looks lovely on the table",
              "Holds up beautifully","Gift-worthy"]
TITLES_MIX = ["Lovely, with one note","Nice but pricey","Smaller than expected","Almost perfect"]
BODY_POS = {
    "Dinnerware":["The glaze is gorgeous and they feel substantial without being heavy.","Perfect weight and the size works for everyday and dinner parties.","Survived the dishwasher and still looks new."],
    "Glassware":["Thin rim, lovely to drink from, and surprisingly sturdy.","Catches the light beautifully and feels balanced in the hand.","Great weight, no awkward seams, dishwasher held up fine."],
    "Flatware":["Nice heft, balanced, and the finish hasn't dulled.","Comfortable in the hand and looks far more expensive than it was.","Matte finish is elegant and hides water spots."],
    "Serveware":["Becomes the centerpiece every time we host.","Generous size and the glaze is even and rich.","Sturdy and beautiful, goes from oven to table."],
    "Bedding":["Soft from the first wash and only gets better.","Breathable and cool, exactly the relaxed look I wanted.","Heavy enough to feel luxe, washes beautifully."],
    "Bath":["Thirsty and plush, dries fast, no lint.","Soft, absorbent, and the color is true to the photos.","Held its softness after many washes."],
    "Table Linens":["Drapes beautifully and presses easily.","The texture and color elevate the whole table.","Washes well and the hems are clean and even."],
    "Throws & Blankets":["Cozy without being heavy, and the weave is gorgeous.","Drapes nicely over the sofa and feels substantial.","Warm, soft, and the color is exactly as shown."],
    "Pillows & Cushions":["Plump, well-filled, and the cover feels lovely.","Holds its shape and the fabric is beautiful.","Perfect accent, the color is rich and true."],
    "Candles & Scent":["Clean burn, even pool, and the scent is subtle not cloying.","Burns evenly for hours and the vessel is reusable.","Warm, grounding scent that fills the room gently."],
    "Vases & Planters":["Heavier and more beautiful than expected, holds a big arrangement.","The matte finish is stunning, looks great even empty.","Perfect proportions and a lovely organic shape."],
    "Lighting":["Warm, soft light and a beautifully made base.","Looks designer, the shade casts a lovely glow.","Solid, weighty base and the finish is gorgeous."],
    "Decor & Objects":["Beautifully made, the detail is lovely up close.","Exactly the quiet, sculptural piece I wanted.","Great quality and the finish feels premium."],
}
GENERIC_POS = ["Quality feels premium and the packaging was lovely.","Natural materials, well made, and it actually lasts.","Became part of our home immediately."]
BODY_MIX = ["Love it, just wish it came in more colors.","Works well but I expected a bit more for the price.","Beautiful, runs a little smaller than I pictured.","Lovely piece, shipping took a while."]
LIKES = ["quality","craftsmanship","material","weight","color accuracy","packaging","softness","durability","finish","value"]
DISLIKES = ["price","sizing","shipping time","color accuracy","packaging"]

def make_reviews(metrics):
    out = {}
    for i_str, m in metrics.items():
        ut = m["units_sold_total"]
        cnt = min(80, max(3, int(ut*0.6) + random.randint(2, 8)))
        revs = []
        dist = Counter()
        cat = m["category"]
        for _ in range(cnt):
            r = random.choices([5,4,3,2], weights=[64,25,8,3])[0]
            dist[r] += 1
            pos = r >= 4
            title = random.choice(TITLES_POS if pos else TITLES_MIX)
            body = random.choice(BODY_POS.get(cat, GENERIC_POS)) if pos else random.choice(BODY_MIX)
            d = NOW - dt.timedelta(days=random.randint(1, 300))
            revs.append({
                "rating": r, "title": title, "body": body,
                "author": f"{random.choice(FIRST)} {random.choice(LAST)[0]}.",
                "verified": random.random() < 0.85,
                "sentiment": "positive" if r>=4 else ("neutral" if r==3 else "negative"),
                "date": d.isoformat(),
            })
        total = sum(dist.values())
        avg = round(sum(k*v for k,v in dist.items())/total, 2) if total else 0
        out[i_str] = {
            "display_title": m["display_title"],
            "rating": avg, "count": total,
            "distribution": {str(k): dist.get(k,0) for k in (5,4,3,2,1)},
            "sentiment_themes": {
                "top_likes": random.sample(LIKES, 3),
                "top_dislikes": random.sample(DISLIKES, 2),
                "quotes": [r["body"] for r in revs if r["rating"]==5][:2],
            },
            "reviews": revs,
        }
    return out

def main():
    custs = make_customers(600)
    orders = make_orders(custs, 2400)
    metrics = derive_metrics(orders)
    reviews = make_reviews(metrics)
    json.dump(custs, open(os.path.join(SYNTH,"customers.json"),"w"), indent=1)
    json.dump(orders, open(os.path.join(SYNTH,"orders.json"),"w"), indent=1)
    json.dump(metrics, open(os.path.join(SYNTH,"product_metrics.json"),"w"), indent=1)
    json.dump(reviews, open(os.path.join(SYNTH,"reviews.json"),"w"), indent=1)

    tot_units = sum(m["units_sold_total"] for m in metrics.values())
    tot_rev = sum(m["revenue"] for m in metrics.values())
    tot_reviews = sum(r["count"] for r in reviews.values())
    best = sum(1 for m in metrics.values() if m["best_seller"])
    low = sum(1 for m in metrics.values() if m["inv_tier"] in ("low","critical"))
    print(f"customers: {len(custs)}")
    print(f"orders:    {len(orders)}  (units sold: {tot_units}, gross: ${tot_rev:,.0f})")
    print(f"reviews:   {tot_reviews}  (avg/product: {tot_reviews/len(reviews):.1f})")
    print(f"best-sellers flagged: {best}  | low/critical stock: {low}")
    print(f"products with FBT pairs: {sum(1 for m in metrics.values() if m['fbt'])}")
    avg_rating = sum(r['rating']*r['count'] for r in reviews.values())/max(1,tot_reviews)
    print(f"catalog avg rating: {avg_rating:.2f}")

if __name__ == "__main__":
    main()
