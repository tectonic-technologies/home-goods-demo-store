#!/usr/bin/env python3
"""Create PRODUCT metafield definitions for the facets already loaded on products.
The metafields were set without definitions (works for rendering), but definitions
with storefront access are needed to expose them as native storefront FILTERS
(the home 'discovery/faceted-filter' story) and to show them cleanly in admin.
Idempotent: skips definitions that already exist. Types MUST match the loaded values."""
import time
from client import Shopify

# (namespace, key, type, display name) — types must match what load_products.py set
DEFS = [
    ("spec", "material",      "single_line_text_field",       "Material"),
    ("spec", "materials",     "list.single_line_text_field",  "Materials"),
    ("spec", "room",          "single_line_text_field",       "Room"),
    ("spec", "color",         "list.single_line_text_field",  "Color"),
    ("spec", "style",         "single_line_text_field",       "Style"),
    ("spec", "price_band",    "single_line_text_field",       "Price band"),
    ("spec", "care",          "list.single_line_text_field",  "Care"),
    ("spec", "dimensions",    "single_line_text_field",       "Dimensions"),
    ("spec", "variant_count", "number_integer",               "Variant count"),
    ("reviews", "rating",     "number_decimal",               "Rating"),
    ("reviews", "count",      "number_integer",               "Review count"),
    ("merch", "best_seller",  "boolean",                      "Best seller"),
    ("merch", "is_new",       "boolean",                      "New arrival"),
    ("merch", "is_clearance", "boolean",                      "Clearance"),
]

Q = 'query($ns:String!){ metafieldDefinitions(first:100, ownerType:PRODUCT, namespace:$ns){ nodes{ key } } }'
M = """
mutation($d: MetafieldDefinitionInput!){
  metafieldDefinitionCreate(definition:$d){
    createdDefinition{ id } userErrors{ field message code } } }"""

def existing_keys(s, ns):
    return {n["key"] for n in s.gql(Q, {"ns": ns})["metafieldDefinitions"]["nodes"]}

def main():
    s = Shopify()
    seen, made, skip = {}, 0, 0
    for ns, key, typ, name in DEFS:
        if ns not in seen:
            seen[ns] = existing_keys(s, ns)
        if key in seen[ns]:
            print(f"  skip (exists): {ns}.{key}"); skip += 1; continue
        d = {"name": name, "namespace": ns, "key": key, "ownerType": "PRODUCT",
             "type": typ, "access": {"storefront": "PUBLIC_READ"}}
        res = s.gql(M, {"d": d})["metafieldDefinitionCreate"]
        errs = res.get("userErrors") or []
        if errs:
            print(f"  ERR {ns}.{key}: {errs[:1]}")
        else:
            print(f"  + {ns}.{key} ({typ})"); made += 1
        time.sleep(0.3)
    print(f"\nmetafield definitions created={made} skipped={skip}")
    print("Note: to surface as storefront filters, enable them in the Shopify")
    print("Search & Discovery app (Filters) — that part is admin-only, not API.")

if __name__ == "__main__":
    main()
