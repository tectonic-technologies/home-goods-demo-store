# MARLOW data-layer schema (home goods)

Built once to serve all 8 Kits. `source` column: **crawl** (have it), **synth** (we generate),
**authored** (LLM/house-brand). Mirrors the MAREN beauty schema; facets are re-keyed for home.

## Product metafields

| namespace.key | type | module / kit | source |
|---|---|---|---|
| `spec.material` | enum (stoneware/porcelain/ceramic/glass/linen/cotton/wool/wood/brass/metal/marble/rattan/leather/concrete) | Discovery facets, Similar | crawl+authored |
| `spec.materials` | list.single_line | Discovery multi-facet, A+ | crawl+authored |
| `spec.room` | enum (dining/kitchen/bedroom/bath/living/entryway) | Discovery facets, room collections | authored |
| `spec.color` | list.single_line (white/natural/grey/black/blue/green/terracotta/pink/brown/gold/multi) | Discovery facets, Product Groups | crawl+authored |
| `spec.style` | enum (modern/rustic/coastal/scandi/traditional/organic) | Discovery facets | authored |
| `spec.care` | list.single_line (dishwasher-safe/microwave-safe/oven-safe/machine-washable/hand-wash/food-safe) | FAQs, A+, facets | crawl+authored |
| `spec.dimensions` | single_line | PDP spec, A+ comparison | crawl |
| `spec.price_band` | enum (entry/core/premium/luxe) | Discovery facets, Similar (price) | authored |
| `spec.has_variants` | boolean | Product Groups, facets | crawl |
| `spec.variant_count` | integer | Product Groups | crawl |
| `spec.primary_option` | single_line (Color/Size/Material/Set) | Product Groups axis | crawl |
| `spec.attributes` | json (spec table) | Marketplace Sync, A+ comparison | crawl+synth |
| `seo.title` / `seo.description` | single_line / multi_line | Brand Enrichment, Organic | authored |
| `seo.tags` | list.single_line | Organic, feed | authored |
| `reviews.rating` | number_decimal | Reviews, badges | synth |
| `reviews.count` | integer | Reviews, FOMO | synth |
| `reviews.distribution` | json (5→1 star counts) | Reviews | synth |
| `reviews.sentiment_themes` | json (top_likes[], top_dislikes[], quotes[]) | Reviews (theme extraction) | synth |
| `merch.margin` | number_decimal | Similar (Margin mode) | synth |
| `merch.is_new` | boolean | Similar (New Arrivals), badges | synth |
| `merch.is_clearance` | boolean | Similar (Last Chance), badges | synth |
| `merch.best_seller` | boolean | Best Sellers, badges | synth |
| `merch.units_sold_30d` | integer | FOMO velocity | synth |
| `merch.live_viewers_base` | integer | FOMO live count | synth |
| `merch.fbt` | json ({strategy, product_gids[]}) | Frequently Bought Together | synth |
| `merch.price_history` | json ([{date, price}]) | Watchlist price-drop | synth |
| `inv.on_hand` | integer | FOMO low-stock, reorder | synth |
| `inv.tier` | enum (healthy/low/critical) | FOMO multi-tier | synth |
| `feed.google_category` | single_line | Paid feed | authored |
| `feed.gtin` | single_line | Paid feed | synth |
| `content.faqs` | list.metaobject_reference → faq | FAQs | authored/synth |
| `content.aplus` | list.metaobject_reference → aplus_block | A+ Content | authored |
| `content.reviews` | list.metaobject_reference → review | Reviews | synth |
| `content.looks` | list.metaobject_reference → look | Shop the Look / Room Set | authored |
| `merch.product_group` | metaobject_reference → product_group | Product Groups (material/color family) | crawl+authored |

## Metaobjects

| type | key fields | module |
|---|---|---|
| `media_asset` | image(file), tag(lifestyle/detail/styled), color_match, sort | Gallery (per-variant, filterable) |
| `faq` | question, answer, category(materials/care/dimensions/sizing/general) | FAQs |
| `review` | author, rating, title, body, media, sentiment, verified, date, variant | Reviews |
| `aplus_block` | type(hero/material/story/comparison), heading, body, image, table_json | A+ Content |
| `look` (room_set) | title, hero_product, steps([{product, note}]), image, editorial | Shop the Look / Room Set |
| `bundle` | type(room/quantity/builder), products[], discount_pct, copy, segment | Room Sets / Volume Bundles |
| `product_group` | name, axis(material/color/size), members([{product, swatch, label}]) | Product Groups |
| `fomo_rule` | metric(stock/velocity/viewers), tiers([{min,max,message,urgency}]), segment | FOMO |
| `synonym` | term, synonyms[] | Discovery/Search |
| `loyalty_tier` | name, threshold, perks[] | Retention |

## Collections (Discovery / Merchandising / Collection-gen)
- Category (rule: product.category, 18 cats) · Room (dining/kitchen/bedroom/bath/living/entryway) ·
  Material (top 8) · The Tabletop
- Merch sets: Best Sellers, New Arrivals, Last Chance, The Edit (editorial)
- Each carries `collection.sort_default` + `collection.merch_rules` (json) for the merchandising kit.

## Store-level (later kits)
- `llms.txt`, structured-data (Product/Review/FAQ schema auto from above), blog/editorial pages (Organic)
- Synthetic customers + orders (Retention, FBT co-purchase basis, CRO analytics), gift cards
- Discounts (auto-apply room sets, volume) (Monetisation)

## Catalog snapshot (current build)
- ~995 de-branded products across 18 categories, ~800 with a variant axis (color/size/material)
- 600 customers, 2,400 backdated orders, ~10k reviews (rating scales with units sold)
- FBT co-purchase derived from order baskets (room/use affinities)

## Out of scope
- Virtual Try-On (Mod 16): apparel/footwear only — N/A for home goods.
