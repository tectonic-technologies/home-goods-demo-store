# MARLOW — Shopify demo store (home goods)

Internal Spectrum demo store for showcasing the discovery / merchandising / search /
retention Kits on a cohesive, high-volume home-goods catalog (~1,000 SKUs). House brand:
**MARLOW** (a more thoughtful home — warm-minimalist modern home goods). Catalog is a
de-branded blend of elevated tabletop, textiles, decor, and lighting.

This is the **scale story** companion to the MAREN beauty store (the depth story).

## Repo layout

```
/ (root)            Shopify theme files live here once the store theme is connected
                    via the Shopify <> GitHub integration.
                    config/ layout/ sections/ snippets/ templates/ assets/ locales/ blocks/
pipeline/           The data build (not part of the theme; Shopify ignores it)
  crawl/            Crawl + normalize + de-brand + clean scripts
  data/             Curated catalog, schema, reports, synth + content
  brand/            MARLOW brand + voice spec
  shopify/          Admin API client + loaders (products/collections/orders/metafields)
```

## Source brands (verified Shopify public /products.json)
hawkinsnewyork.com · parachutehome.com · coyuchi.com · leifshop.com ·
pigletinbed.com · farmhousepottery.com — blended + de-branded into MARLOW, balanced
to ~1,000 cohesive SKUs.

## Pipeline run order
```
# data build (no store needed)
python3 pipeline/crawl/crawl.py        # fetch raw (gitignored)
python3 pipeline/crawl/normalize.py    # de-brand + curate + per-brand caps
python3 pipeline/crawl/rewrite_names.py
python3 pipeline/crawl/clean.py        # dedupe + recategorize -> catalog_clean.json
python3 pipeline/crawl/synth.py        # customers/orders/metrics/reviews
python3 pipeline/crawl/enrich_facets.py# facets/taxonomy/~6 images/collections
python3 pipeline/crawl/content.py      # MARLOW-voice copy, FAQs, room sets, groups

# load (needs creds in pipeline/shopify/secrets.env) — run from pipeline/shopify/
python3 verify.py
python3 load_products.py               # idempotent; re-run to fill gaps; then publish
python3 load_collections.py
python3 set_content_metafields.py
python3 load_orders.py
```

## Shopify connection
- Create a Dev Dashboard custom app on the store, mint the `shpat_` via client-credentials
  (see SHOPIFY_DEMO_STORE_BUILD_PLAYBOOK.md section 3). Put creds in
  `pipeline/shopify/secrets.env` (gitignored).
- Install a home/furniture theme, connect it to this repo's `main` branch.
- The `pipeline/` folder is plain tooling and does not interfere with the theme.
