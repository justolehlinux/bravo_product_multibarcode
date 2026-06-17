# Bravo Product Multibarcode — Odoo 19

Global additional product barcodes for `product.product` and POS.

## What this fixed build changes

- Keeps the existing source-of-truth model: `bravo.product.barcode.alias`.
- Keeps backend product lookup by both primary barcode and additional alias barcode.
- Fixes the `product.product.barcode` search handler so normal Odoo domains like `barcode != False`, `not in`, `not ilike`, etc. do not collapse to no results.
- Replaces the old POS `PosDB` patch with an Odoo 19 related-model patch.
- Loads `bravo_barcodes_json` and `bravo_all_barcodes` into POS.
- Patches the POS `product.product` model lookup so `getBy("barcode", alias)` returns the product.
- Adds alias codes to the POS product search string.
- Removes the obsolete `point_of_sale.assets` bundle entry and uses `point_of_sale._assets_pos` only.

## Install / update

1. Back up the database.
2. Replace the existing `bravo_product_multibarcode` folder with this folder.
3. Restart Odoo.
4. Upgrade the module:

```bash
./odoo-bin -d YOUR_DATABASE -u bravo_product_multibarcode --stop-after-init
```

5. Start Odoo again.
6. In the browser, fully reload assets and POS:
   - use developer mode;
   - update apps list if needed;
   - open POS with `?debug=assets` once;
   - hard refresh the browser;
   - close and reopen the POS session.

## Required checks in Odoo shell

```python
ALIAS = "PUT_ALIAS_HERE"

alias = env["bravo.product.barcode.alias"].search([("barcode", "=", ALIAS)], limit=1)
print("alias", alias, "product", alias.product_id.display_name if alias else None)

print("product search", env["product.product"].search([("barcode", "=", ALIAS)], limit=5))
print("product name_search", env["product.product"].name_search(ALIAS))
print("template name_search", env["product.template"].name_search(ALIAS))
print("public API", env["product.product"].bravo_find_by_any_barcode(ALIAS))
```

Expected: all four lookups return the product.

## POS check

Open browser console in POS and check that this appears:

```text
Bravo POS alias barcode patch loaded for Odoo 19 related models v19.0.1.1.0
```

Then scan the alias barcode. It should resolve through POS `product.product.getBy("barcode", code)`.
