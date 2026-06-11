# Bravo Odoo 19 split modules

This archive contains two Odoo 19 addon folders:

- `bravo_product_multibarcode` — global additional product barcodes.
- `bravo_mobile_inventory` — mobile inventory terminal depending on `bravo_product_multibarcode`.

## What was preserved from the working module

The multi-barcode engine is taken from the working `bravo_mobile_inventory_odoo19_v2.2.5_fixed` code path:

- `product.product.barcode` uses the working field search handler `search='_search_bravo_barcode'`.
- It does **not** override `product.product._search()`.
- `env['product.product'].search([('barcode', '=', alias_code)])` is handled by `_search_bravo_barcode()`.
- `product.product.name_search(alias_code)` and `product.template.name_search(alias_code)` keep the working alias lookup.
- POS data loading keeps `bravo_barcodes_json` and `bravo_all_barcodes`.
- The technical model name `bravo.product.barcode.alias` is preserved.

## Versions

- `bravo_product_multibarcode`: `19.0.1.0.0`
- `bravo_mobile_inventory`: `19.0.3.0.0`

## Safe update order from old combined module

1. Back up the database.
2. Stop Odoo.
3. Replace the old `bravo_mobile_inventory` folder with both folders from this ZIP:
   - `bravo_product_multibarcode`
   - `bravo_mobile_inventory`
4. Start Odoo.
5. Update the apps list.
6. Install/upgrade `Bravo Product Multibarcode` first if Odoo does not install it automatically as dependency.
7. Upgrade `Bravo Mobile Inventory`.

Do not uninstall the old module before backup. The alias table is kept by using the same model name: `bravo.product.barcode.alias`.

## Rights

Assign these groups as needed:

- `Bravo Multibarcode User`: read additional barcodes.
- `Bravo Multibarcode Manager`: create/edit/delete/archive additional barcodes.
- `Bind Product Barcodes`: mobile users allowed to bind unknown barcodes; this group implies `Bravo Multibarcode Manager`.
- `Apply Inventory Adjustments`: can apply mobile inventory sessions.
- `Cancel and Delete Sessions`: can cancel/delete non-applied sessions.

## Checks after installation

Run these in Odoo shell after creating a product and alias:

```python
p = env['product.product'].search([('barcode', '=', 'MAIN_CODE')], limit=1)
a = env['bravo.product.barcode.alias'].create({'barcode': 'ALIAS_CODE', 'product_id': p.id})
assert env['product.product'].search([('barcode', '=', 'ALIAS_CODE')]) == p
assert env['product.product'].name_search('ALIAS_CODE')
assert env['product.template'].name_search('ALIAS_CODE')
assert env['product.product'].bravo_find_by_any_barcode('ALIAS_CODE') == p
```

Then verify manually:

1. Open product list and product form.
2. Add an alias in the Additional Barcodes page/button.
3. Search product in Sales/Purchase lines by alias.
4. Fully reload POS session and scan alias.
5. Open `/mobile/inventory`, scan main barcode, scan alias, scan unknown barcode and bind it.
6. Start a count session, scan product, enter quantity, refresh page, continue session, finish and preview/apply with the correct rights.

## Notes

This split intentionally does **not** override `product.product._search()`. The direct barcode-domain behavior is implemented through the working field search handler from the previous working module.
