# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Payment Provider: iyzico',
    'version': '18.0.1.0.6',
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': "iyzico payment provider for Turkey and surrounding regions.",
    'description': " ",
    'depends': ['payment', 'sale', 'website_sale'],
    'data': [
        # Security
        'security/ir.model.access.csv',
        
        # Wizard (must load before views that reference it)
        'wizard/iyzico_icon_wizard_views.xml',
        
        # Views (templates must load before data that references them)
        'views/payment_provider_views.xml',
        'views/payment_transaction_views.xml',
        'views/payment_iyzico_templates.xml',
        
        # Data (provider references templates above)
        'data/payment_provider_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_iyzico/static/src/css/payment_checkout.css',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
}
