#!/usr/bin/env python3
"""Create product_group metaobjects (material/color families) and attach them to
member products via the merch.product_group metafield (metaobject_reference).
Reads data/content/product_groups.json. Run AFTER load_products.py (needs product GIDs).
Idempotent: skips the definition if it exists and skips families already created.

The payload-building helpers (build_entry_fields, resolve_member_gids) are pure so
they can be unit-tested offline without a store (see pipeline/qc.py / __main__ guard)."""
import json, os, time
from client import Shopify

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
def load(p): return json.load(open(os.path.join(D, p)))
CAT = load("catalog_clean.json")
DESC = load("content/descriptions.json")
PG = load("content/product_groups.json")

DEF_TYPE = "product_group"

QDEF = "query{ metaobjectDefinitions(first:50){ nodes{ id type } } }"
CREATE_DEF = """
mutation($d: MetaobjectDefinitionCreateInput!){
  metaobjectDefinitionCreate(definition:$d){
    metaobjectDefinition{ id type } userErrors{ field message } } }"""
CREATE_OBJ = """
mutation($m: MetaobjectCreateInput!){
  metaobjectCreate(metaobject:$m){
    metaobject{ id handle } userErrors{ field message } } }"""
SET_MF = """
mutation($mfs:[MetafieldsSetInput!]!){ metafieldsSet(metafields:$mfs){ userErrors{message} } }"""
Q_EXISTING = """
query($t:String!,$c:String){ metaobjects(type:$t, first:100, after:$c){
  pageInfo{hasNextPage endCursor} nodes{ id field(key:"name"){ value } } } }"""

# ---- pure helpers (offline-testable) ----
def content_title(src_handle):
    return (DESC.get(src_handle) or {}).get("title")

def resolve_member_gids(members, title_to_gid):
    """Map product_group members (by src_handle -> content title -> store GID)."""
    gids = []
    for m in members:
        t = content_title(m["product"])
        gid = title_to_gid.get(t)
        if gid and gid not in gids:
            gids.append(gid)
    return gids

def build_entry_fields(name, axis, gids):
    """Fields payload for metaobjectCreate. products is list.product_reference
    so its value is a JSON-encoded array of product GIDs."""
    return [
        {"key": "name", "value": name},
        {"key": "axis", "value": axis},
        {"key": "products", "value": json.dumps(gids)},
    ]

CREATE_MF_DEF = """
mutation($d: MetafieldDefinitionInput!){
  metafieldDefinitionCreate(definition:$d){
    createdDefinition{ id } userErrors{ field message code } } }"""
Q_MF_DEFS = """
query{ metafieldDefinitions(first:100, ownerType:PRODUCT, namespace:"merch"){
  nodes{ key } } }"""

def ensure_definition(s):
    """Ensure the product_group metaobject definition; return its GID."""
    nodes = s.gql(QDEF)["metaobjectDefinitions"]["nodes"]
    for n in nodes:
        if n["type"] == DEF_TYPE:
            print(f"  metaobject definition '{DEF_TYPE}' already exists"); return n["id"]
    d = {
        "name": "Product Group", "type": DEF_TYPE,
        "fieldDefinitions": [
            {"name": "Name", "key": "name", "type": "single_line_text_field"},
            {"name": "Axis", "key": "axis", "type": "single_line_text_field"},
            {"name": "Products", "key": "products", "type": "list.product_reference"},
        ],
    }
    res = s.gql(CREATE_DEF, {"d": d})["metaobjectDefinitionCreate"]
    if res.get("userErrors"):
        raise SystemExit(f"metaobject definition create failed: {res['userErrors']}")
    print(f"  created metaobject definition '{DEF_TYPE}'")
    return res["metaobjectDefinition"]["id"]

def ensure_pg_metafield_def(s, mo_def_gid):
    """A metaobject_reference metafield needs a PRODUCT metafield definition
    (merch.product_group) constrained to the product_group metaobject definition,
    or metafieldsSet rejects the value."""
    existing = {n["key"] for n in s.gql(Q_MF_DEFS)["metafieldDefinitions"]["nodes"]}
    if "product_group" in existing:
        print("  metafield definition merch.product_group already exists"); return
    d = {
        "name": "Product Group", "namespace": "merch", "key": "product_group",
        "ownerType": "PRODUCT", "type": "metaobject_reference",
        "validations": [{"name": "metaobject_definition_id", "value": mo_def_gid}],
    }
    res = s.gql(CREATE_MF_DEF, {"d": d})["metafieldDefinitionCreate"]
    if res.get("userErrors"):
        raise SystemExit(f"merch.product_group metafield def create failed: {res['userErrors']}")
    print("  created metafield definition merch.product_group")

def main():
    s = Shopify()
    mo_def_gid = ensure_definition(s)
    ensure_pg_metafield_def(s, mo_def_gid)

    # store product GID map, keyed by (content) title — same approach as fbt_rekey.py
    title_to_gid, cursor = {}, None
    while True:
        d = s.gql('query($c:String){products(first:100,after:$c){pageInfo{hasNextPage endCursor} nodes{id title}}}', {"c": cursor})["products"]
        for nd in d["nodes"]: title_to_gid[nd["title"]] = nd["id"]
        if not d["pageInfo"]["hasNextPage"]: break
        cursor = d["pageInfo"]["endCursor"]

    # existing metaobjects (idempotency on re-run): name-field value -> gid, so we reuse
    # (displayName is auto-generated "Product Group #XXXX", so we must match the name field)
    existing, cursor = {}, None
    while True:
        d = s.gql(Q_EXISTING, {"t": DEF_TYPE, "c": cursor})["metaobjects"]
        for n in d["nodes"]:
            nm = (n.get("field") or {}).get("value")
            if nm: existing[nm] = n["id"]
        if not d["pageInfo"]["hasNextPage"]: break
        cursor = d["pageInfo"]["endCursor"]

    made, set_refs = 0, 0
    for g in PG:
        gids = resolve_member_gids(g["members"], title_to_gid)
        if len(gids) < 2:
            print(f"  skip (only {len(gids)} members resolved): {g['name']}"); continue
        mo_gid = existing.get(g["name"])
        if mo_gid:
            print(f"  reuse metaobject: {g['name']}")
        else:
            fields = build_entry_fields(g["name"], g.get("axis", "material/color"), gids)
            res = s.gql(CREATE_OBJ, {"m": {"type": DEF_TYPE, "fields": fields}})["metaobjectCreate"]
            if res.get("userErrors"):
                print(f"  ERR {g['name']}: {res['userErrors'][:2]}"); continue
            mo_gid = res["metaobject"]["id"]; made += 1
        # attach (or re-attach) to every member product — idempotent
        batch = [{"ownerId": gid, "namespace": "merch", "key": "product_group",
                  "type": "metaobject_reference", "value": mo_gid} for gid in gids]
        r = s.gql(SET_MF, {"mfs": batch})["metafieldsSet"]
        if r.get("userErrors"): print(f"    ref errs: {r['userErrors'][:2]}")
        else: set_refs += len(batch)
        time.sleep(0.4)
    print(f"\nproduct_group metaobjects created={made}; merch.product_group refs set={set_refs}")

if __name__ == "__main__":
    main()
