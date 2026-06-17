#!/usr/bin/env python3
"""Bind each color variant to its own image so the PDP gallery swaps when a shopper
picks a color. The exact color->image mapping comes from the raw crawl data
(variant.featured_image.src per color); we join raw->Shopify on the semantic image
filename 'stem' (Shopify re-hashes the trailing UUID on upload but keeps the stem).

For a color whose featured image wasn't among the (capped) uploaded media, we upload
that one image from the source URL, wait for it to finish processing, then bind.

Pass --analyze to only print coverage without writing. Idempotent: re-binding the
same media is a no-op."""
import json, glob, re, sys, time
from client import Shopify

RAW = glob.glob(__file__.rsplit("/pipeline/", 1)[0] + "/pipeline/crawl/raw/*.json")
CATALOG = __file__.rsplit("/pipeline/", 1)[0] + "/pipeline/data/catalog_clean.json"

def stem(u):
    n = u.split("/")[-1].split("?")[0]
    n = re.sub(r"_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?=\.)", "", n)
    n = re.sub(r"\.[a-zA-Z0-9]+$", "", n)
    return n.lower()

def cnorm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def color_in_stem(cn, color_name, st):
    """True if the color (full or last word, >=3 chars) appears in the filename stem."""
    ns = re.sub(r"[^a-z0-9]", "", st)
    toks = {cn}
    parts = (color_name or "").lower().split()
    if parts:
        toks.add(re.sub(r"[^a-z0-9]", "", parts[-1]))
    return any(t and len(t) >= 3 and t in ns for t in toks)

def build_catalog_index():
    """-> list of (image_stems:set, [(stem, url), ...]) per source product, for filename
    color-token matching when raw lacks a per-variant featured_image."""
    try:
        d = json.load(open(CATALOG))
    except Exception:
        return []
    out = []
    for p in d:
        imgs = [(stem(u), u) for u in (p.get("images") or [])]
        if imgs:
            out.append(({s for s, _ in imgs}, imgs))
    return out

def build_raw_index():
    """-> list of (image_stems:set, {color_norm: (featured_stem, src_url)}, handle)"""
    idx = []
    for f in RAW:
        if f.endswith("_crawl.log"):
            continue
        try:
            d = json.load(open(f))
        except Exception:
            continue
        prods = d if isinstance(d, list) else d.get("products", [])
        for p in prods:
            opts = p.get("options", [])
            cidx = None
            for i, o in enumerate(opts):
                nm = o.get("name") if isinstance(o, dict) else o
                if str(nm).lower() == "color":
                    cidx = i + 1
                    break
            if cidx is None:
                continue
            c2s = {}
            for v in p.get("variants", []):
                fi = v.get("featured_image")
                src = fi.get("src") if isinstance(fi, dict) else fi
                col = v.get(f"option{cidx}")
                if not src or not col:
                    continue
                c2s.setdefault(cnorm(col), (stem(src), src))
            istems = {stem(im["src"]) for im in p.get("images", []) if im.get("src")}
            if c2s:
                idx.append((istems, c2s, p.get("handle")))
    return idx

def best_raw(media_stems, idx):
    # These products were often split across several source listings (one per color
    # group), so merge the color->image map of EVERY raw listing whose images overlap
    # this product, highest-overlap first (first write wins on conflict).
    overlapping = []
    for istems, c2s, h in idx:
        ov = len(media_stems & istems)
        if ov > 0:
            overlapping.append((ov, c2s))
    overlapping.sort(key=lambda x: -x[0])
    merged = {}
    for _ov, c2s in overlapping:
        for cn, val in c2s.items():
            merged.setdefault(cn, val)
    return merged

APPEND = """mutation($pid:ID!,$vm:[ProductVariantAppendMediaInput!]!){
  productVariantAppendMedia(productId:$pid, variantMedia:$vm){ userErrors{ field message } } }"""
CREATE = """mutation($pid:ID!,$media:[CreateMediaInput!]!){
  productCreateMedia(productId:$pid, media:$media){
    media{ ... on MediaImage{ id image{url} } } mediaUserErrors{ field message } } }"""

def main():
    analyze = "--analyze" in sys.argv
    s = Shopify()
    idx = build_raw_index()
    cat = build_catalog_index()
    print(f"raw color->image maps: {len(idx)}; catalog products: {len(cat)}")

    total = s.gql("query{productsCount{count}}")["productsCount"]["count"]

    cursor = None
    stats = {"scanned": 0, "multi": 0, "joined": 0, "fully": 0, "partial": 0, "none": 0,
             "skipped": 0, "uploads": 0, "bound_variants": 0, "products_bound": 0}

    def progress():
        n, t = stats["scanned"], total or 1
        filled = int(28 * n / t)
        bar = "#" * filled + "-" * (28 - filled)
        print(f"[{bar}] {n}/{t}  multi={stats['multi']} bound={stats['products_bound']}p/"
              f"{stats['bound_variants']}v skip={stats['skipped']} up={stats['uploads']}", flush=True)

    while True:
        d = s.gql("""query($c:String){products(first:50,after:$c){pageInfo{hasNextPage endCursor}
          nodes{id handle
            options{name optionValues{name}}
            media(first:50){nodes{... on MediaImage{id image{url}}}}
            variants(first:100){nodes{id image{id} selectedOptions{name value}}}}}}""", {"c": cursor})["products"]
        for p in d["nodes"]:
            stats["scanned"] += 1
            colors = [o for o in p["options"] if o["name"].lower() == "color"]
            if not colors or len(colors[0]["optionValues"]) < 2:
                continue
            stats["multi"] += 1
            # resumable: skip products whose color variants already all have an image
            cvars = [v for v in p["variants"]["nodes"]
                     if any(o["name"].lower() == "color" for o in v["selectedOptions"])]
            if cvars and all(v.get("image") for v in cvars):
                stats["skipped"] += 1
                continue
            media = [(m["id"], stem(m["image"]["url"])) for m in p["media"]["nodes"] if m.get("image")]
            stem2id = {st: mid for mid, st in media}
            mstems = set(stem2id)
            raw = best_raw(mstems, idx) or {}
            # catalog source images for this product (filename color-token fallback)
            cat_imgs = []
            best_ov = 0
            for cstems, imgs in cat:
                ov = len(mstems & cstems)
                if ov > best_ov:
                    best_ov, cat_imgs = ov, imgs
            if not raw and not cat_imgs:
                stats["none"] += 1
                continue
            stats["joined"] += 1

            colvals = colors[0]["optionValues"]
            color_media = {}     # color value -> media_id (existing)
            need_upload = {}     # color value -> (src url, stem)
            for cv in colvals:
                cn = cnorm(cv["name"])
                name = cv["name"]
                # (a) raw per-variant featured image, already uploaded
                if cn in raw and raw[cn][0] in stem2id:
                    color_media[name] = stem2id[raw[cn][0]]
                    continue
                # (b) filename color token in an already-uploaded media
                hit = next((st for st in stem2id if color_in_stem(cn, name, st)), None)
                if hit:
                    color_media[name] = stem2id[hit]
                    continue
                # (c) raw featured image that wasn't uploaded -> upload it
                if cn in raw:
                    need_upload[name] = (raw[cn][1], raw[cn][0])
                    continue
                # (d) filename color token in a source image -> upload it
                srchit = next(((st, u) for st, u in cat_imgs if color_in_stem(cn, name, st)), None)
                if srchit:
                    need_upload[name] = (srchit[1], srchit[0])

            covered = len(color_media) + len(need_upload)
            if covered == len(colvals):
                stats["fully"] += 1
            elif covered > 0:
                stats["partial"] += 1
            else:
                stats["none"] += 1

            if analyze:
                continue

            # upload missing color images, then resolve to media ids.
            # productCreateMedia returns media in input order; the image URL is not
            # populated until processing finishes, so match by ORDER, not by stem.
            if need_upload:
                items = list(need_upload.items())  # [(color, (src, stem)), ...]
                cre = [{"originalSource": src, "mediaContentType": "IMAGE"}
                       for (_c, (src, _st)) in items]
                r = s.gql(CREATE, {"pid": p["id"], "media": cre})["productCreateMedia"]
                newm = r.get("media") or []
                ue = r.get("mediaUserErrors") or []
                if ue:
                    print(f"  upload err {p['handle']}: {ue[:1]}")
                for (color, _v), m in zip(items, newm):
                    if m and m.get("id"):
                        color_media[color] = m["id"]
                        stats["uploads"] += 1
                time.sleep(0.3)  # brief; freshly-uploaded media that isn't ready yet
                                 # is bound on the next (resumable) sweep instead

            # build variant -> media binding. productVariantAppendMedia is atomic and
            # rejects the whole batch if ANY variant already has media, so only include
            # variants that are not yet bound.
            vm = []
            for v in p["variants"]["nodes"]:
                if v.get("image"):
                    continue
                cv = next((o["value"] for o in v["selectedOptions"] if o["name"].lower() == "color"), None)
                mid = color_media.get(cv)
                if mid:
                    vm.append({"variantId": v["id"], "mediaIds": [mid]})
            if vm:
                # one quick attempt + one short retry; media still processing is left
                # for the next sweep (the image is uploaded, so it binds then).
                for attempt in range(2):
                    r = s.gql(APPEND, {"pid": p["id"], "vm": vm})["productVariantAppendMedia"]
                    ue = r.get("userErrors") or []
                    if not ue:
                        stats["bound_variants"] += len(vm)
                        stats["products_bound"] += 1
                        break
                    if attempt == 0 and any("process" in e.get("message", "").lower() or "ready" in e.get("message", "").lower() for e in ue):
                        time.sleep(0.8)
                        continue
                    print(f"  ERR {p['handle']}: {ue[:1]}")
                    break
                time.sleep(0.1)
        progress()
        if not d["pageInfo"]["hasNextPage"]:
            break
        cursor = d["pageInfo"]["endCursor"]

    print("DONE", json.dumps(stats))

if __name__ == "__main__":
    main()
