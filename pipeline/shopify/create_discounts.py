#!/usr/bin/env python3
"""Create a variety of discounts on the MARLOW store:
  1. Automatic % off a collection (Decor & Lighting 20% off)
  2. Code % off a collection (MARLOW15 = 15% off Tabletop)
  3. Code fixed amount off order (HOME50 = 50 off orders over 300)
  4. Free shipping code (FREESHIP, over 200)
  5. Automatic Buy X Get Y (Glassware: buy 2 get 1 free)
  6. Visible compare-at 'sale' markdowns on a spread of products across collections
Idempotent-ish: discount creates may duplicate on re-run; compare-at is safe to re-run."""
import time
from client import Shopify

START = "2026-06-01T00:00:00Z"
COMBINE = {"orderDiscounts": True, "productDiscounts": True, "shippingDiscounts": True}

def gid_for(s, handle):
    d = s.gql('query($h:String!){ collectionByHandle(handle:$h){ id } }', {"h": handle})
    return (d.get("collectionByHandle") or {}).get("id")

def main():
    s = Shopify()
    tabletop = gid_for(s, "top-tabletop")
    decor = gid_for(s, "top-decor-lighting")
    glassware = gid_for(s, "cat-glassware")
    made = []

    # 1. Automatic % off a collection
    m = """mutation($d:DiscountAutomaticBasicInput!){ discountAutomaticBasicCreate(automaticBasicDiscount:$d){
      automaticDiscountNode{id} userErrors{field message} } }"""
    r = s.gql(m, {"d": {
        "title": "Decor & Lighting Event – 20% Off", "startsAt": START,
        "combinesWith": COMBINE,
        "customerGets": {"value": {"percentage": 0.20},
                         "items": {"collections": {"add": [decor]}}}}})["discountAutomaticBasicCreate"]
    made.append(("auto 20% off Decor & Lighting", r.get("userErrors")))

    # 2. Code % off a collection
    m = """mutation($d:DiscountCodeBasicInput!){ discountCodeBasicCreate(basicCodeDiscount:$d){
      codeDiscountNode{id} userErrors{field message} } }"""
    r = s.gql(m, {"d": {
        "title": "MARLOW15", "code": "MARLOW15", "startsAt": START,
        "customerSelection": {"all": True}, "combinesWith": COMBINE,
        "appliesOncePerCustomer": False,
        "customerGets": {"value": {"percentage": 0.15},
                         "items": {"collections": {"add": [tabletop]}}}}})["discountCodeBasicCreate"]
    made.append(("code MARLOW15 15% off Tabletop", r.get("userErrors")))

    # 3. Code fixed amount off order with minimum subtotal
    r = s.gql(m, {"d": {
        "title": "HOME50", "code": "HOME50", "startsAt": START,
        "customerSelection": {"all": True}, "combinesWith": COMBINE,
        "appliesOncePerCustomer": True,
        "minimumRequirement": {"subtotal": {"greaterThanOrEqualToSubtotal": "300.0"}},
        "customerGets": {"value": {"discountAmount": {"amount": "50.0", "appliesOnEachItem": False}},
                         "items": {"all": True}}}})["discountCodeBasicCreate"]
    made.append(("code HOME50 (50 off 300+)", r.get("userErrors")))

    # 4. Free shipping code
    m = """mutation($d:DiscountCodeFreeShippingInput!){ discountCodeFreeShippingCreate(freeShippingCodeDiscount:$d){
      codeDiscountNode{id} userErrors{field message} } }"""
    r = s.gql(m, {"d": {
        "title": "FREESHIP", "code": "FREESHIP", "startsAt": START,
        "customerSelection": {"all": True}, "destination": {"all": True},
        # a shipping discount cannot combine with other shipping discounts
        "combinesWith": {"orderDiscounts": True, "productDiscounts": True, "shippingDiscounts": False},
        "minimumRequirement": {"subtotal": {"greaterThanOrEqualToSubtotal": "200.0"}}}})["discountCodeFreeShippingCreate"]
    made.append(("code FREESHIP (over 200)", r.get("userErrors")))

    # 5. Automatic Buy X Get Y (buy 2 get 1 free in Glassware)
    m = """mutation($d:DiscountAutomaticBxgyInput!){ discountAutomaticBxgyCreate(automaticBxgyDiscount:$d){
      automaticDiscountNode{id} userErrors{field message} } }"""
    r = s.gql(m, {"d": {
        "title": "Glassware: Buy 2 Get 1 Free", "startsAt": START, "combinesWith": COMBINE,
        "customerBuys": {"value": {"quantity": "2"}, "items": {"collections": {"add": [glassware]}}},
        "customerGets": {"value": {"discountOnQuantity": {"quantity": "1", "effect": {"percentage": 1.0}}},
                         "items": {"collections": {"add": [glassware]}}}}})["discountAutomaticBxgyCreate"]
    made.append(("auto BXGY Glassware buy2get1", r.get("userErrors")))

    print("=== discounts created ===")
    for name, errs in made:
        print(f"  {'ERR '+str(errs[:1]) if errs else 'OK '} {name}")

if __name__ == "__main__":
    main()
