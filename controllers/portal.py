# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request

from odoo.addons.sale.controllers.portal import CustomerPortal as SaleCustomerPortal


class CustomerPortal(SaleCustomerPortal):
    """Override to show paid-but-not-confirmed orders in portal."""

    def _prepare_orders_domain(self, partner):
        """
        Override to also show draft orders that have successful payment transactions.
        
        This allows customers to see their orders even when confirmation failed
        due to PDF generation issues or other errors.
        """
        # Get base domain (confirmed orders only)
        # Original: [('message_partner_ids', 'child_of', [partner_id]), ('state', '=', 'sale')]
        
        # Find draft orders that have successful iyzico payment transactions
        PaymentTransaction = request.env['payment.transaction'].sudo()
        paid_transactions = PaymentTransaction.search([
            ('state', '=', 'done'),
            ('provider_code', '=', 'iyzico'),
        ])
        
        paid_order_ids = []
        for tx in paid_transactions:
            if tx.sale_order_ids:
                for order in tx.sale_order_ids:
                    if order.state in ['draft', 'sent']:
                        paid_order_ids.append(order.id)
        
        # Build domain: confirmed orders OR paid draft orders
        partner_id = partner.commercial_partner_id.id
        
        if paid_order_ids:
            return [
                ('message_partner_ids', 'child_of', [partner_id]),
                '|',
                ('state', '=', 'sale'),
                '&',
                ('state', 'in', ['draft', 'sent']),
                ('id', 'in', paid_order_ids),
            ]
        else:
            # No paid draft orders, use original domain
            return [
                ('message_partner_ids', 'child_of', [partner_id]),
                ('state', '=', 'sale'),
            ]
