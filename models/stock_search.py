# -*- coding: utf-8 -*-

from odoo import api, fields, models


class BravoStockBarcodeAliasSearchMixin(models.AbstractModel):
    _name = 'bravo.stock.barcode.alias.search.mixin'
    _description = 'Bravo stock product barcode alias search helper'

    @api.model
    def _bravo_stock_product_ids_for_alias_search(self, operator, value):
        Product = self.env['product.product'].with_context(active_test=False)
        operator = operator or 'ilike'
        if hasattr(Product, '_bravo_product_ids_by_any_barcode'):
            return Product._bravo_product_ids_by_any_barcode(value, operator=operator)
        return Product.search([('barcode', operator, value)]).ids


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    bravo_product_barcode_alias_search = fields.Char(
        string='Product Additional Barcode Search',
        compute='_compute_bravo_product_barcode_alias_search',
        search='_search_bravo_product_barcode_alias_search',
    )

    @api.depends('product_id.bravo_all_barcodes')
    def _compute_bravo_product_barcode_alias_search(self):
        for quant in self:
            quant.bravo_product_barcode_alias_search = quant.product_id.bravo_all_barcodes or ''

    @api.model
    def _search_bravo_product_barcode_alias_search(self, operator, value):
        product_ids = self.env['bravo.stock.barcode.alias.search.mixin']._bravo_stock_product_ids_for_alias_search(operator, value)
        return [('product_id', 'in', product_ids or [0])]


class StockMove(models.Model):
    _inherit = 'stock.move'

    bravo_product_barcode_alias_search = fields.Char(
        string='Product Additional Barcode Search',
        compute='_compute_bravo_product_barcode_alias_search',
        search='_search_bravo_product_barcode_alias_search',
    )

    @api.depends('product_id.bravo_all_barcodes')
    def _compute_bravo_product_barcode_alias_search(self):
        for move in self:
            move.bravo_product_barcode_alias_search = move.product_id.bravo_all_barcodes or ''

    @api.model
    def _search_bravo_product_barcode_alias_search(self, operator, value):
        product_ids = self.env['bravo.stock.barcode.alias.search.mixin']._bravo_stock_product_ids_for_alias_search(operator, value)
        return [('product_id', 'in', product_ids or [0])]


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    bravo_product_barcode_alias_search = fields.Char(
        string='Product Additional Barcode Search',
        compute='_compute_bravo_product_barcode_alias_search',
        search='_search_bravo_product_barcode_alias_search',
    )

    @api.depends('product_id.bravo_all_barcodes')
    def _compute_bravo_product_barcode_alias_search(self):
        for line in self:
            line.bravo_product_barcode_alias_search = line.product_id.bravo_all_barcodes or ''

    @api.model
    def _search_bravo_product_barcode_alias_search(self, operator, value):
        product_ids = self.env['bravo.stock.barcode.alias.search.mixin']._bravo_stock_product_ids_for_alias_search(operator, value)
        return [('product_id', 'in', product_ids or [0])]
