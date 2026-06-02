#!/usr/bin/env python3
"""Safely wire the MARLOW PDP module blocks into templates/product.json.
Parses the auto-generated JSON (stripping its /* ... */ header), inserts a
full-width 'section' hosting the marlow-* theme blocks after the main product
section, and writes valid JSON back (header preserved). Idempotent.

Edits the theme file programmatically so the output is always valid JSON
(a malformed product.json would break every product page)."""
import json, os, re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
PATH = os.path.join(ROOT, "templates", "product.json")

MODULES_KEY = "marlow_modules"
BLOCKS = [
    ("mpg",  "marlow-product-groups", {"show_heading": True, "heading": "Options", "fallback_to_variants": True}),
    ("maplus","marlow-aplus",         {"heading": "The detail"}),
    ("mrev", "marlow-reviews",        {"heading": "Reviews", "show_distribution": True, "show_themes": True, "max_reviews": 6}),
    ("mfaq", "marlow-faq",            {"heading": "Questions", "open_first": False, "show_categories": False}),
    ("mfbt", "marlow-fbt",            {"heading": "Pairs well with", "show_bulk_add": True}),
]

def split_header(raw):
    i = raw.index("{")
    return raw[:i], raw[i:]

def main():
    raw = open(PATH).read()
    header, body = split_header(raw)
    d = json.loads(body)

    blocks = {bid: {"type": btype, "settings": settings, "blocks": {}}
              for bid, btype, settings in BLOCKS}
    section = {
        "type": "section",
        "blocks": blocks,
        "block_order": [bid for bid, _, _ in BLOCKS],
        "name": "MARLOW · PDP modules",
        "settings": {
            "content_direction": "column", "vertical_on_mobile": True,
            "horizontal_alignment": "flex-start", "vertical_alignment": "flex-start",
            "gap": 40, "section_width": "page-width", "color_scheme": "",
            "padding-block-start": 24, "padding-block-end": 48,
        },
    }
    d["sections"][MODULES_KEY] = section
    if MODULES_KEY in d["order"]:
        d["order"].remove(MODULES_KEY)
    # place right after the main product section
    insert_at = d["order"].index("main") + 1 if "main" in d["order"] else len(d["order"])
    d["order"].insert(insert_at, MODULES_KEY)

    open(PATH, "w").write(header + json.dumps(d, indent=2))
    print(f"wired {len(BLOCKS)} MARLOW blocks into product.json; order = {d['order']}")

if __name__ == "__main__":
    main()
