from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BravoProductBarcodeAlias(models.Model):
    _name = 'bravo.product.barcode.alias'
    _description = 'Bravo Additional Product Barcode'
    _order = 'create_date desc, id desc'

    barcode = fields.Char(required=True, index=True)
    product_id = fields.Many2one('product.product', required=True, ondelete='cascade', index=True)
    product_tmpl_id = fields.Many2one(related='product_id.product_tmpl_id', store=True, index=True, readonly=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True)
    created_during_inventory = fields.Boolean(default=False, readonly=True)
    created_by_id = fields.Many2one('res.users', readonly=True, default=lambda self: self.env.user)
    note = fields.Char()

    _barcode_unique = models.Constraint(
        'UNIQUE(barcode)',
        'This additional barcode is already registered.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['barcode'] = (vals.get('barcode') or '').strip()
        for vals in vals_list:
            if not vals.get('barcode'):
                raise ValidationError(_('Barcode cannot be empty.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'barcode' in vals:
            vals['barcode'] = (vals.get('barcode') or '').strip()
        if 'barcode' in vals and not vals.get('barcode'):
            raise ValidationError(_('Barcode cannot be empty.'))
        return super().write(vals)

    @api.constrains('barcode', 'product_id', 'active')
    def _check_barcode_against_primary(self):
        # Do not use Product.search([('barcode', '=', code)]) here: the
        # multibarcode module intentionally makes that domain include aliases.
        # For this constraint we must check only the real product_product.barcode
        # column, otherwise creating a valid alias would detect itself.
        Packaging = self.env['product.packaging'].sudo() if 'product.packaging' in self.env else False
        for rec in self.filtered(lambda alias: alias.active and alias.barcode):
            self.env.cr.execute(
                'SELECT id FROM product_product WHERE barcode = %s LIMIT 1',
                (rec.barcode,),
            )
            row = self.env.cr.fetchone()
            primary = self.env['product.product'].sudo().browse(row[0]) if row else self.env['product.product']
            if primary:
                if primary == rec.product_id:
                    raise ValidationError(_('This barcode is already the primary barcode of the selected product.'))
                raise ValidationError(_('This barcode is already the primary barcode of another product.'))
            if Packaging:
                packaging = Packaging.search([('barcode', '=', rec.barcode)], limit=1)
                if packaging:
                    raise ValidationError(_('This barcode is already used as a product packaging barcode. Use a unique code.'))

    def name_get(self):
        return [(rec.id, '%s → %s' % (rec.barcode, rec.product_id.display_name)) for rec in self]
