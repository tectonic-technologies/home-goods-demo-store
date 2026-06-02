# MARLOW PDP theme blocks (staged)

Custom PDP blocks for the MARLOW home store, adapted from the MAREN beauty build.
They are **data-driven**: each reads product metafields loaded by the pipeline and
renders nothing when the data is absent. No fabricated content.

| block | reads | needs loaded by |
|---|---|---|
| `marlow-reviews.liquid` | `reviews.rating/count/distribution/sentiment_themes/items` | load_products + set_content_metafields |
| `marlow-social-proof.liquid` | `reviews.rating/count`, `merch.units_sold_30d`, `inv.tier/on_hand` | load_products + set_content_metafields |
| `marlow-faq.liquid` | `content.faqs` | set_content_metafields |
| `marlow-aplus.liquid` | `content.aplus` (hero products) | set_content_metafields |
| `marlow-fbt.liquid` | `merch.fbt` (handles) | load_products + fbt_rekey |
| `marlow-product-groups.liquid` | `merch.product_group` metaobject, falls back to variant options | load_products + load_metaobjects |

## How to install (once the theme is connected via GitHub)
1. Copy these files into the theme's `blocks/` directory at the repo root.
2. In the theme editor, open the product template and add the blocks to the PDP.
3. Preview and adjust block settings (headings, toggles) per block schema.

These are staged here (not in `blocks/`) because the theme is not connected yet.
Move them to `blocks/` after the theme is installed + GitHub-synced.

## Notes
- `merch.product_group` is loaded by `pipeline/shopify/load_metaobjects.py`, which
  creates a `product_group` metaobject per material/color family (fields: name, axis,
  products[list.product_reference]) and sets the reference on each member product.
  The block supports both that `products[]` shape and a composite `members[]` shape,
  and falls back to the product's own variant options when no group is set.
- Styling uses theme CSS variables with sensible fallbacks, so blocks inherit the
  installed theme's palette/spacing.
