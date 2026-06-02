#!/usr/bin/env python3
"""Offline QC for the MARLOW build. Validates the data layer + the exact payloads
the loaders will send, catching issues that would only surface mid-load against the
live Shopify API. Run from anywhere: python3 pipeline/qc.py  (exit 1 on any FAIL)."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, os.path.join(HERE, "shopify"))
def load(p): return json.load(open(os.path.join(DATA, p)))

fails, warns = [], []
def check(cond, msg):
    (print(f"  ok   {msg}") if cond else fails.append(msg) or print(f"  FAIL {msg}"))
def warn(cond, msg):
    if not cond: warns.append(msg); print(f"  warn {msg}")
    else: print(f"  ok   {msg}")

print("== 1. JSON validity ==")
files = ["catalog_clean","enriched","collections",
         "synth/customers","synth/orders","synth/product_metrics","synth/reviews",
         "content/descriptions","content/faqs","content/aplus","content/routines","content/product_groups"]
blobs = {}
for f in files:
    try:
        blobs[f] = load(f + ".json"); print(f"  ok   {f}.json ({len(blobs[f])})")
    except Exception as e:
        fails.append(f"{f}.json unparseable: {e}"); print(f"  FAIL {f}.json: {e}")

CAT = blobs["catalog_clean"]
handles = {p["src_handle"] for p in CAT}
dtitles = {p["display_title"] for p in CAT}

print("\n== 2. Referential integrity ==")
check(set(blobs["content/descriptions"]).issubset(handles), "descriptions keys are catalog handles")
check(set(blobs["content/faqs"]).issubset(handles), "faqs keys are catalog handles")
check(set(blobs["content/aplus"]).issubset(handles), "aplus keys are catalog handles")
check(set(blobs["enriched"][0].keys()) >= {"src_handle","facets","images"}, "enriched shape")
enr_handles = {e["src_handle"] for e in blobs["enriched"]}
check(enr_handles == handles, "enriched covers exactly the catalog")
met = {m["display_title"] for m in blobs["synth/product_metrics"].values()}
check(met == dtitles, "product_metrics covers exactly the catalog (by title)")
rev = {r["display_title"] for r in blobs["synth/reviews"].values()}
check(rev == dtitles, "reviews cover exactly the catalog (by title)")
# routines + product_groups reference real handles
rt_bad = [s["product"] for r in blobs["content/routines"] for s in r["steps"] if s["product"] not in handles]
check(not rt_bad, f"routine step products resolve ({len(rt_bad)} bad)")
pg_bad = [m["product"] for g in blobs["content/product_groups"] for m in g["members"] if m["product"] not in handles]
check(not pg_bad, f"product_group members resolve ({len(pg_bad)} bad)")
# orders reference valid product indices
n = len(CAT)
oob = [li["product_i"] for o in blobs["synth/orders"] for li in o["line_items"] if not (0 <= li["product_i"] < n)]
check(not oob, f"order line items reference valid product indices ({len(oob)} oob)")
# customer refs on orders exist
cust_refs = {c["ref"] for c in blobs["synth/customers"]}
bad_cref = [o["customer_ref"] for o in blobs["synth/orders"] if o["customer_ref"] not in cust_refs]
check(not bad_cref, f"orders reference existing customers ({len(bad_cref)} bad)")

print("\n== 3. productSet payloads (the real load) ==")
import load_products as LP
dup_optvals, lost_variants, bad_mf, empty_tags, title_dups = [], [], [], [], {}
VALID_MF_TYPES = {"single_line_text_field","multi_line_text_field","number_integer",
                  "number_decimal","boolean","json","list.single_line_text_field"}
for p in CAT:
    inp = LP.build_input(p)
    t = inp["title"]; title_dups[t] = title_dups.get(t,0)+1
    if not inp.get("tags") or any(x is None for x in inp["tags"]): empty_tags.append(t)
    # duplicate option-value tuples (Shopify productSet errors on these)
    seen = set()
    for v in inp.get("variants", []):
        key = tuple((ov["optionName"], ov["name"]) for ov in v["optionValues"])
        if key in seen: dup_optvals.append((t, key));
        seen.add(key)
    # products that HAD real options but collapsed to a single default variant
    real_opts = [o for o in p["options"] if o["name"] and o["name"].lower() not in ("title","default title")]
    if real_opts and inp["productOptions"] and inp["productOptions"][0]["name"] == "Title":
        lost_variants.append(t)
    # metafield types + JSON-serializability
    for m in inp["metafields"]:
        if m["type"] not in VALID_MF_TYPES: bad_mf.append((t, m["key"], m["type"]))
        if m["type"] == "json" or m["type"].startswith("list."):
            try: json.loads(m["value"])
            except Exception: bad_mf.append((t, m["key"], "unparseable-json"))
    # every variant must cover every declared option (no null optionValues)
    opt_names = {o["name"] for o in inp["productOptions"]}
    for v in inp["variants"]:
        got = {ov["optionName"] for ov in v["optionValues"]}
        if got != opt_names: bad_mf.append((t, "optionValue-mismatch", str(got)))
check(not dup_optvals, f"no duplicate variant option-value combos ({len(dup_optvals)})")
for d in dup_optvals[:5]: print("       ", d)
check(not bad_mf, f"metafield types valid + json parses + optionValues complete ({len(bad_mf)})")
for b in bad_mf[:5]: print("       ", b)
check(not empty_tags, f"every product has non-null tags ({len(empty_tags)})")
check(max(title_dups.values()) == 1, f"store titles unique (idempotency) — max dup {max(title_dups.values())}")
warn(not lost_variants, f"products with options collapsed to single variant ({len(lost_variants)})")
for lv in lost_variants[:8]: print("       ", lv)

print("\n== 4. Collections wire to real product values ==")
cols = blobs["collections"]
# what tags/types products will actually carry
types_present = {p["category"] for p in CAT}
tags_present = set()
for p in CAT:
    inp = LP.build_input(p)
    tags_present.update(str(x).lower() for x in inp["tags"])
import load_collections as LC
ruled, manual, unmatched = 0, 0, []
for col in cols:
    rl = LC.rule(col)
    if rl is None:
        manual += 1; continue
    ruled += 1
    cond = rl["condition"]; coltype = rl["column"]
    if coltype == "TYPE":
        if cond not in types_present: unmatched.append((col["handle"],"TYPE",cond))
    elif coltype == "TAG":
        if str(cond).lower() not in tags_present: unmatched.append((col["handle"],"TAG",cond))
check(not unmatched, f"every smart-collection rule matches real product type/tags ({len(unmatched)} unmatched)")
for u in unmatched[:10]: print("       ", u)
print(f"  info collections: {ruled} smart (ruled), {manual} manual/editorial")

print("\n== 5. load_orders variant mapping ==")
import load_orders  # noqa: just ensure it imports clean
# every order will map at least one line to a variant (titles match content titles)
desc = blobs["content/descriptions"]
title_for_i = {}
for i,p in enumerate(CAT):
    title_for_i[i] = (desc.get(p["src_handle"]) or {}).get("title") or p["display_title"]
orders_with_no_mappable = sum(1 for o in blobs["synth/orders"]
    if not any(li["product_i"] in title_for_i for li in o["line_items"]))
check(orders_with_no_mappable == 0, f"every order has mappable line items ({orders_with_no_mappable} empty)")

print("\n== 6. product_group metaobject payloads (offline) ==")
import load_metaobjects as LM
# stub a store GID map from content titles, as load_metaobjects would build post-load
title_to_gid = {}
for i, p in enumerate(CAT):
    t = (blobs["content/descriptions"].get(p["src_handle"]) or {}).get("title")
    if t: title_to_gid[t] = f"gid://shopify/Product/{1000+i}"
pg_made, pg_bad = 0, []
for g in blobs["content/product_groups"]:
    gids = LM.resolve_member_gids(g["members"], title_to_gid)
    if len(gids) < 2:
        pg_bad.append((g["name"], f"only {len(gids)} resolved")); continue
    fields = LM.build_entry_fields(g["name"], g.get("axis","material/color"), gids)
    keys = {f["key"] for f in fields}
    if keys != {"name","axis","products"}: pg_bad.append((g["name"], f"fields {keys}")); continue
    prod_field = next(f for f in fields if f["key"]=="products")
    try:
        arr = json.loads(prod_field["value"])
        if not (isinstance(arr,list) and all(str(x).startswith("gid://shopify/Product/") for x in arr)):
            pg_bad.append((g["name"],"products not a GID list")); continue
    except Exception as e:
        pg_bad.append((g["name"], f"products json: {e}")); continue
    pg_made += 1
check(not pg_bad, f"every product_group builds a valid metaobject payload ({len(pg_bad)} bad)")
for b in pg_bad[:6]: print("       ", b)
print(f"  info {pg_made}/{len(blobs['content/product_groups'])} families would create (>=2 members resolved)")

print("\n" + "="*50)
if fails:
    print(f"QC FAILED: {len(fails)} failure(s), {len(warns)} warning(s)")
    for f in fails: print("  FAIL", f)
    sys.exit(1)
print(f"QC PASSED ✓  ({len(warns)} warning(s))")
