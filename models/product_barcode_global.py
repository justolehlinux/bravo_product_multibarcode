# -*- coding: utf-8 -*-
import json

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Critical for "everywhere in Odoo": any direct domain like
    # [('barcode', '=', scanned_code)] must also resolve Bravo aliases.
    # We keep the real database column, only add a custom search handler.
    barcode = fields.Char(search='_search_bravo_barcode')

    bravo_barcode_alias_ids = fields.One2many(
        'bravo.product.barcode.alias',
        'product_id',
        string='Additional Barcodes',
        help='Extra barcodes that resolve to this product in Bravo Mobile Inventory and supported Odoo screens.',
    )
    bravo_barcode_alias_count = fields.Integer(
        string='Additional Barcode Count',
        compute='_compute_bravo_barcode_alias_count',
    )
    bravo_barcodes_json = fields.Char(
        string='Bravo Additional Barcodes JSON',
        compute='_compute_bravo_barcodes_json',
        help='Technical field loaded into POS. Do not edit manually.',
    )
    bravo_all_barcodes = fields.Char(
        string='All Barcodes',
        compute='_compute_bravo_all_barcodes',
        help='Primary barcode plus Bravo additional barcodes. Used for display/search.',
    )
    bravo_barcode_alias_search = fields.Char(
        string='Additional Barcode Search',
        compute='_compute_bravo_all_barcodes',
        search='_search_bravo_barcode_alias_search',
        help='Technical searchable field for additional barcodes.',
    )

    @api.depends('bravo_barcode_alias_ids', 'bravo_barcode_alias_ids.active')
    def _compute_bravo_barcode_alias_count(self):
        grouped = self.env['bravo.product.barcode.alias'].sudo().read_group(
            [('product_id', 'in', self.ids), ('active', '=', True)],
            ['product_id'],
            ['product_id'],
        ) if self.ids else []
        count_by_id = {row['product_id'][0]: row['product_id_count'] for row in grouped}
        for product in self:
            product.bravo_barcode_alias_count = count_by_id.get(product.id, 0)

    @api.depends('bravo_barcode_alias_ids.barcode', 'bravo_barcode_alias_ids.active')
    def _compute_bravo_barcodes_json(self):
        Alias = self.env['bravo.product.barcode.alias'].sudo()
        for product in self:
            aliases = Alias.search([
                ('product_id', '=', product.id),
                ('active', '=', True),
                ('barcode', '!=', False),
            ], order='id')
            product.bravo_barcodes_json = json.dumps(aliases.mapped('barcode'))

    @api.depends('barcode', 'bravo_barcode_alias_ids.barcode', 'bravo_barcode_alias_ids.active')
    def _compute_bravo_all_barcodes(self):
        Alias = self.env['bravo.product.barcode.alias'].sudo()
        for product in self:
            aliases = Alias.search([
                ('product_id', '=', product.id),
                ('active', '=', True),
                ('barcode', '!=', False),
            ], order='barcode').mapped('barcode')
            codes = []
            if product.barcode:
                codes.append(product.barcode)
            codes += aliases
            value = ' '.join(dict.fromkeys([code for code in codes if code]))
            product.bravo_all_barcodes = value
            product.bravo_barcode_alias_search = value

    @api.model
    def _bravo_normalize_barcode(self, barcode):
        if barcode in (False, None):
            return ''
        return str(barcode).strip()

    @api.model
    def _bravo_non_empty_values(self, values):
        return [self._bravo_normalize_barcode(v) for v in (values or []) if self._bravo_normalize_barcode(v)]

    @api.model
    def _bravo_contains_false_value(self, values):
        return any(not self._bravo_normalize_barcode(v) for v in (values or []))

    @api.model
    def _bravo_ean13_check_digit(self, first_12_digits):
        """Return the EAN-13 check digit for the first 12 digits.

        Odoo POS barcode nomenclature can resolve variable weight/price
        barcodes before product lookup. Normal backend list/search screens do
        not run that parser. This helper lets backend search normalize common
        weighted EAN-13 labels such as 2801280002214 to the product barcode
        2801280000005.
        """
        digits = [int(d) for d in str(first_12_digits)]
        total = sum(digits[0::2]) + 3 * sum(digits[1::2])
        return str((10 - (total % 10)) % 10)

    @api.model
    def _bravo_weight_barcode_candidates(self, barcode):
        """Return possible fixed product barcodes for variable EAN-13 labels.

        Common retail scales print EAN-13 labels where the first 7 digits
        identify the product, the next 5 digits carry weight/price, and the
        last digit is the EAN checksum. Odoo POS resolves this via barcode
        nomenclature; backend product list searches need the same practical
        normalization.

        Example:
            scanned label: 2801280002214
            product code:  2801280000005
        """
        code = self._bravo_normalize_barcode(barcode)
        if not (len(code) == 13 and code.isdigit() and code[:2] >= '20' and code[:2] <= '29'):
            return []

        candidates = []

        # Default EAN weighted/price format: PP + 5 product digits + 5 value digits + C
        first_12 = code[:7] + '00000'
        candidates.append(first_12 + self._bravo_ean13_check_digit(first_12))

        return [candidate for candidate in dict.fromkeys(candidates) if candidate != code]

    @api.model
    def _bravo_expand_barcode_values(self, values):
        expanded = []
        for value in (values or []):
            normalized = self._bravo_normalize_barcode(value)
            if normalized:
                expanded.append(normalized)
                expanded.extend(self._bravo_weight_barcode_candidates(normalized))
        return list(dict.fromkeys(expanded))

    @api.model
    def _bravo_positive_operator(self, operator):
        return operator in ('=', '==', '=ilike', '=like', 'ilike', 'like', 'in')

    @api.model
    def _bravo_negative_operator_to_positive(self, operator):
        return {
            '!=': '=',
            '<>': '=',
            'not ilike': 'ilike',
            'not like': 'like',
            'not in': 'in',
        }.get(operator)

    @api.model
    def _bravo_sql_like_value(self, operator, value):
        text = self._bravo_normalize_barcode(value)
        if operator in ('ilike', 'like'):
            return f'%{text}%'
        return text

    @api.model
    def _bravo_primary_barcode_ids(self, value, operator='='):
        """Search the real product_product.barcode column without ORM recursion.

        Odoo 19 calls barcode searches from many different places. Use direct SQL
        and btrim() so a barcode accidentally saved with spaces still resolves.
        """
        operator = operator or '='
        if not self._bravo_positive_operator(operator):
            return []
        table = self._table
        if operator == 'in':
            values = self._bravo_expand_barcode_values(value)
            if not values:
                return []
            self.env.cr.execute(
                f"SELECT id FROM {table} WHERE btrim(barcode) = ANY(%s)",
                (values,),
            )
            return [row[0] for row in self.env.cr.fetchall()]

        needle = self._bravo_normalize_barcode(value)
        if not needle:
            return []

        candidates = self._bravo_weight_barcode_candidates(needle)

        sql_operator = {
            '=': '=',
            '==': '=',
            '=ilike': 'ILIKE',
            '=like': 'LIKE',
            'ilike': 'ILIKE',
            'like': 'LIKE',
        }.get(operator)
        if not sql_operator:
            return []
        self.env.cr.execute(
            f"SELECT id FROM {table} WHERE btrim(barcode) {sql_operator} %s",
            (self._bravo_sql_like_value(operator, needle),),
        )
        ids = [row[0] for row in self.env.cr.fetchall()]
        if candidates:
            self.env.cr.execute(
                f"SELECT id FROM {table} WHERE btrim(barcode) = ANY(%s)",
                (candidates,),
            )
            ids += [row[0] for row in self.env.cr.fetchall()]
        return list(dict.fromkeys(ids))

    @api.model
    def _bravo_alias_product_ids_for_barcode(self, barcode, operator='='):
        """Return product IDs matching Bravo aliases using direct SQL.

        This avoids depending on search views/name_search and is the backend
        source of truth for product.product, product.template and stock screens.
        """
        operator = operator or '='
        if not self._bravo_positive_operator(operator):
            return []

        table = self.env['bravo.product.barcode.alias']._table
        if operator == 'in':
            values = self._bravo_expand_barcode_values(barcode)
            if not values:
                return []
            self.env.cr.execute(
                f"""
                SELECT product_id
                  FROM {table}
                 WHERE active IS TRUE
                   AND product_id IS NOT NULL
                   AND btrim(barcode) = ANY(%s)
                """,
                (values,),
            )
            return [row[0] for row in self.env.cr.fetchall()]

        needle = self._bravo_normalize_barcode(barcode)
        if not needle:
            return []

        candidates = self._bravo_weight_barcode_candidates(needle)

        sql_operator = {
            '=': '=',
            '==': '=',
            '=ilike': 'ILIKE',
            '=like': 'LIKE',
            'ilike': 'ILIKE',
            'like': 'LIKE',
        }.get(operator)
        if not sql_operator:
            return []

        self.env.cr.execute(
            f"""
            SELECT product_id
              FROM {table}
             WHERE active IS TRUE
               AND product_id IS NOT NULL
               AND btrim(barcode) {sql_operator} %s
            """,
            (self._bravo_sql_like_value(operator, needle),),
        )
        ids = [row[0] for row in self.env.cr.fetchall()]
        if candidates:
            self.env.cr.execute(
                f"""
                SELECT product_id
                  FROM {table}
                 WHERE active IS TRUE
                   AND product_id IS NOT NULL
                   AND btrim(barcode) = ANY(%s)
                """,
                (candidates,),
            )
            ids += [row[0] for row in self.env.cr.fetchall()]
        return list(dict.fromkeys(ids))

    @api.model
    def _bravo_product_ids_by_any_barcode(self, barcode, operator='='):
        op = operator or '='
        if op == 'in':
            values = self._bravo_non_empty_values(barcode)
            if not values:
                return []
            ids = self._bravo_primary_barcode_ids(values, operator='in')
            ids += self._bravo_alias_product_ids_for_barcode(values, operator='in')
            return list(dict.fromkeys(ids))
        if not self._bravo_normalize_barcode(barcode):
            return []
        ids = self._bravo_primary_barcode_ids(barcode, operator=op)
        ids += self._bravo_alias_product_ids_for_barcode(barcode, operator=op)
        return list(dict.fromkeys(ids))

    @api.model
    def _bravo_all_barcoded_product_ids(self):
        """Products that have either a primary barcode or at least one active Bravo alias."""
        self.env.cr.execute(f"""
            SELECT id
              FROM {self._table}
             WHERE barcode IS NOT NULL
               AND btrim(barcode) != ''
            UNION
            SELECT product_id
              FROM bravo_product_barcode_alias
             WHERE active IS TRUE
               AND barcode IS NOT NULL
               AND btrim(barcode) != ''
        """)
        return [row[0] for row in self.env.cr.fetchall()]

    @api.model
    def _search_bravo_barcode(self, operator, value):
        """Search handler for product.product.barcode.

        The previous version only handled positive operators. That is dangerous
        because normal Odoo filters also emit domains such as ('barcode', '!=', False)
        and ('barcode', 'not in', ...). Returning no records for those domains breaks
        standard product searches and POS/server loading in subtle ways.
        """
        operator = operator or '='

        # Odoo "is set" / "is not set" style domains.
        if operator in ('=', '==') and not self._bravo_normalize_barcode(value):
            return [('id', 'not in', self._bravo_all_barcoded_product_ids() or [0])]
        if operator in ('!=', '<>') and not self._bravo_normalize_barcode(value):
            return [('id', 'in', self._bravo_all_barcoded_product_ids() or [0])]

        if operator == 'in':
            values = value if isinstance(value, (list, tuple, set)) else [value]
            ids = self._bravo_product_ids_by_any_barcode(values, operator='in')
            if self._bravo_contains_false_value(values):
                return expression.OR([
                    [('id', 'in', ids or [0])],
                    [('id', 'not in', self._bravo_all_barcoded_product_ids() or [0])],
                ])
            return [('id', 'in', ids or [0])]

        if operator == 'not in':
            values = value if isinstance(value, (list, tuple, set)) else [value]
            ids = self._bravo_product_ids_by_any_barcode(values, operator='in')
            if self._bravo_contains_false_value(values):
                return [
                    ('id', 'in', self._bravo_all_barcoded_product_ids() or [0]),
                    ('id', 'not in', ids or [0]),
                ]
            return [('id', 'not in', ids or [0])]

        positive_operator = self._bravo_negative_operator_to_positive(operator)
        if positive_operator:
            ids = self._bravo_product_ids_by_any_barcode(value, operator=positive_operator)
            return [('id', 'not in', ids or [0])]

        if self._bravo_positive_operator(operator):
            ids = self._bravo_product_ids_by_any_barcode(value, operator=operator)
            return [('id', 'in', ids or [0])]

        # Keep unsupported operators safe instead of returning false positives.
        return [('id', 'in', [0])]

    @api.model
    def bravo_find_by_any_barcode(self, barcode, company=None):
        """Public API: return exactly one product matching primary barcode or Bravo alias.

        Other modules should call this method instead of duplicating barcode
        lookup logic. It reuses the Bravo field-search implementation and does
        not override product.product._search().
        """
        normalized = self._bravo_normalize_barcode(barcode)
        if not normalized:
            raise ValidationError(_('Barcode is empty.'))
        ids = self._bravo_product_ids_by_any_barcode(normalized, operator='=')
        products = self.browse(ids).exists()
        if company and 'company_id' in self._fields:
            company = self.env['res.company'].browse(company.id if hasattr(company, 'id') else int(company))
            products = products.filtered(lambda p: not p.company_id or p.company_id == company)
        if len(products) > 1:
            raise ValidationError(_('Barcode %(barcode)s resolves to more than one product. Fix duplicate barcodes before using it.', barcode=normalized))
        return products[:1]

    @api.model
    def _bravo_product_by_any_barcode(self, barcode, strict=True):
        ids = self._bravo_product_ids_by_any_barcode(barcode, operator='=')
        if strict and len(ids) > 1:
            raise ValidationError(_('Barcode %(barcode)s resolves to more than one product. Fix duplicate barcodes before using it.', barcode=barcode))
        return self.browse(ids[:1])

    @api.model
    def _search_bravo_barcode_alias_search(self, operator, value):
        ids = self._bravo_product_ids_by_any_barcode(value, operator=operator or 'ilike')
        return [('id', 'in', ids or [0])]

    @api.model
    def _bravo_alias_domain_for_search_value(self, value, operator='ilike'):
        ids = self._bravo_product_ids_by_any_barcode(value, operator=operator or 'ilike')
        return [('id', 'in', ids or [0])]

    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        if value:
            return expression.OR([domain, self._bravo_alias_domain_for_search_value(value, operator)])
        return domain

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        """Make Many2one/product autocomplete find Bravo alias barcodes.

        Alias matches are returned first. The earlier implementation called
        super() first and only appended aliases afterwards; in some stock screens
        Odoo's optimized product search never reached the alias part reliably.
        """
        domain = domain or []
        if name and operator not in ('not ilike', 'not like', '!=', '<>', 'not in'):
            alias_domain = expression.AND([
                domain,
                self._bravo_alias_domain_for_search_value(name, operator),
            ])
            alias_products = self.search(alias_domain, limit=limit)
            alias_results = [(product.id, product.display_name) for product in alias_products.sudo()]
            if limit and len(alias_results) >= limit:
                return alias_results

            existing_ids = [record_id for record_id, _display_name in alias_results]
            remaining = False if not limit else max(limit - len(existing_ids), 0)
            super_domain = domain
            if existing_ids:
                super_domain = expression.AND([super_domain, [('id', 'not in', existing_ids)]])
            return alias_results + super().name_search(name=name, domain=super_domain, operator=operator, limit=remaining)

        return super().name_search(name=name, domain=domain, operator=operator, limit=limit)

    @api.model
    def _search_by_barcode(self, barcode, *args, **kwargs):
        super_method = getattr(super(ProductProduct, self), '_search_by_barcode', None)
        if super_method:
            product = super_method(barcode, *args, **kwargs)
            if product:
                return product
        return self._bravo_product_by_any_barcode(barcode, strict=False)

    @api.model
    def _get_product_by_barcode(self, barcode, *args, **kwargs):
        """Compatibility hook used by some barcode/POS addons."""
        super_method = getattr(super(ProductProduct, self), '_get_product_by_barcode', None)
        if super_method:
            product = super_method(barcode, *args, **kwargs)
            if product:
                return product
        return self._bravo_product_by_any_barcode(barcode, strict=False)

    @api.constrains('barcode')
    def _check_primary_barcode_against_aliases(self):
        Alias = self.env['bravo.product.barcode.alias'].sudo()
        for product in self.filtered('barcode'):
            alias = Alias.search([
                ('barcode', '=', product.barcode),
                ('active', '=', True),
                ('product_id', '!=', product.id),
            ], limit=1)
            if alias:
                raise ValidationError(_('This primary barcode is already used as an additional barcode on another product.'))

    def action_open_bravo_barcode_aliases(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Additional Barcodes'),
            'res_model': 'bravo.product.barcode.alias',
            'view_mode': 'list,form',
            'domain': [('product_id', '=', self.id)],
            'context': {'default_product_id': self.id},
        }

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        for field_name in ('bravo_barcodes_json', 'bravo_all_barcodes'):
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Odoo product.template has its own computed barcode field with a custom
    # _search_barcode() that only delegates to product_variant_ids.barcode.
    # In the normal Products / Номенклатура screen the search view already
    # searches ('barcode', 'ilike', typed_text). If we do not replace the
    # template barcode search handler too, that standard search can still miss
    # Bravo alias barcodes even when product.product and POS work correctly.
    barcode = fields.Char(search='_search_bravo_template_barcode')

    bravo_barcode_alias_count = fields.Integer(
        string='Additional Barcode Count',
        compute='_compute_bravo_barcode_alias_count',
    )
    bravo_barcode_alias_search = fields.Char(
        string='Additional Barcode Search',
        compute='_compute_bravo_barcode_alias_search',
        search='_search_bravo_barcode_alias_search',
    )

    @api.depends('product_variant_ids.bravo_barcode_alias_count')
    def _compute_bravo_barcode_alias_count(self):
        for template in self:
            template.bravo_barcode_alias_count = sum(template.product_variant_ids.mapped('bravo_barcode_alias_count'))

    @api.depends('product_variant_ids.bravo_all_barcodes')
    def _compute_bravo_barcode_alias_search(self):
        for template in self:
            template.bravo_barcode_alias_search = ' '.join(template.product_variant_ids.mapped('bravo_all_barcodes'))

    @api.model
    def _bravo_template_ids_by_any_barcode(self, value, operator='ilike'):
        """Return template IDs for primary or Bravo alias barcodes.

        This is deliberately direct and low-level: Inventory → Products is a
        product.template screen, so template search must not depend on product
        name_search or search-view behavior.
        """
        Product = self.env['product.product'].with_context(active_test=False)
        product_ids = Product._bravo_product_ids_by_any_barcode(value, operator=operator or 'ilike')
        if not product_ids:
            return []
        self.env.cr.execute(
            "SELECT DISTINCT product_tmpl_id FROM product_product WHERE id = ANY(%s)",
            (product_ids,),
        )
        return [row[0] for row in self.env.cr.fetchall() if row[0]]

    @api.model
    def _search_bravo_template_barcode(self, operator, value):
        """Make the standard product.template barcode search resolve Bravo aliases."""
        template_ids = self._bravo_template_ids_by_any_barcode(value, operator or 'ilike')
        return [('id', 'in', template_ids or [0])]

    @api.model
    def _search_bravo_barcode_alias_search(self, operator, value):
        template_ids = self._bravo_template_ids_by_any_barcode(value, operator or 'ilike')
        return [('id', 'in', template_ids or [0])]

    @api.model
    def _bravo_template_alias_domain(self, value, operator='ilike'):
        template_ids = self._bravo_template_ids_by_any_barcode(value, operator or 'ilike')
        return [('id', 'in', template_ids or [0])]

    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        if value:
            return expression.OR([domain, self._bravo_template_alias_domain(value, operator)])
        return domain

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        """Make product.template autocomplete find Bravo alias barcodes too.

        Alias matches are returned first. This is important for Inventory →
        Products because that screen is product.template-based.
        """
        domain = domain or []
        if name and operator not in ('not ilike', 'not like', '!=', '<>', 'not in'):
            alias_domain = expression.AND([
                domain,
                self._bravo_template_alias_domain(name, operator),
            ])
            alias_templates = self.search(alias_domain, limit=limit)
            alias_results = [(template.id, template.display_name) for template in alias_templates.sudo()]
            if limit and len(alias_results) >= limit:
                return alias_results

            existing_ids = [record_id for record_id, _display_name in alias_results]
            remaining = False if not limit else max(limit - len(existing_ids), 0)
            super_domain = domain
            if existing_ids:
                super_domain = expression.AND([super_domain, [('id', 'not in', existing_ids)]])
            return alias_results + super().name_search(name=name, domain=super_domain, operator=operator, limit=remaining)

        return super().name_search(name=name, domain=domain, operator=operator, limit=limit)

    def action_open_bravo_barcode_aliases(self):
        self.ensure_one()
        products = self.product_variant_ids
        context = {}
        if len(products) == 1:
            context['default_product_id'] = products.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Additional Barcodes'),
            'res_model': 'bravo.product.barcode.alias',
            'view_mode': 'list,form',
            'domain': [('product_id', 'in', products.ids)],
            'context': context,
        }


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_product_product(self):
        result = super()._loader_params_product_product()
        fields_list = result.get('search_params', {}).get('fields')
        if isinstance(fields_list, list):
            for field_name in ('bravo_barcodes_json', 'bravo_all_barcodes'):
                if field_name not in fields_list:
                    fields_list.append(field_name)
        return result
