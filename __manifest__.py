{
    'name': 'Bravo Product Multibarcode',
    'version': '19.0.1.1.0',
    'category': 'Inventory/Inventory',
    'summary': 'Global additional product barcodes for Odoo 19 products and POS',
    'description': '''Independent source of truth for additional product barcodes.''',
    'author': 'Bravo Market',
    'license': 'LGPL-3',
    'depends': ['product', 'point_of_sale'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/product_barcode_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'bravo_product_multibarcode/static/src/app/models/bravo_pos_barcodes.esm.js',
        ],
    },
    'installable': True,
    'application': False,
}
