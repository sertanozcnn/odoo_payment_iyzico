# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
iyzico Payment Controller

This controller handles:
1. Callback from iyzico after payment completion
2. Return URL for redirecting users back to Odoo
3. Error handling and logging
"""

import logging
import pprint
import hmac
import hashlib
from datetime import timedelta

from odoo import http, _
from odoo.exceptions import ValidationError, AccessDenied
from odoo.http import request
from odoo import fields


_logger = logging.getLogger(__name__)


class IyzicoController(http.Controller):
    """
    Controller for handling iyzico payment callbacks and returns.
    
    Security considerations:
    - All callbacks are validated by retrieving payment result from iyzico API
    - The token received in callback is used to fetch actual payment status
    - No sensitive data is trusted from client-side POST data
    """
    
    _callback_url = '/payment/iyzico/callback'
    _return_url = '/payment/iyzico/return'
    
    def _verify_webhook_signature(self, token, provider):
        """
        Verify the authenticity of iyzico webhook/callback.
        
        For enhanced security, this method can be used to verify that the callback
        is genuinely from iyzico by checking the token signature.
        
        Note: iyzico primarily relies on token-based verification where we retrieve
        the payment result from their API using the token. This provides strong
        security as we never trust the callback data directly.
        
        Additional signature verification can be implemented here if iyzico sends
        signature headers in their callbacks (check their latest documentation).
        
        :param str token: The token received from iyzico callback
        :param recordset provider: The payment provider (payment.provider)
        :return: True if signature is valid
        :rtype: bool
        :raises AccessDenied: If signature verification fails
        """
        # Get the signature header if sent by iyzico
        signature_header = request.httprequest.headers.get('X-Iyzico-Signature')
        
        if not signature_header:
            # If no signature header is present, we still have security through
            # token-based verification (retrieving result from iyzico API)
            _logger.debug("No iyzico signature header found, relying on token verification")
            return True
        
        # If signature is present, verify it
        try:
            # Generate expected signature using secret key
            # The exact signature algorithm should match iyzico's webhook documentation
            secret_key = provider.iyzico_secret_key
            expected_signature = hmac.new(
                secret_key.encode('utf-8'),
                token.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures (constant-time comparison to prevent timing attacks)
            if not hmac.compare_digest(signature_header, expected_signature):
                _logger.error(
                    "Invalid iyzico webhook signature. Expected: %s, Received: %s",
                    expected_signature[:10] + "...",
                    signature_header[:10] + "..."
                )
                raise AccessDenied(_("Invalid webhook signature"))
            
            _logger.debug("Webhook signature verified successfully")
            return True
            
        except Exception as e:
            _logger.exception("Error verifying iyzico webhook signature: %s", str(e))
            raise AccessDenied(_("Webhook signature verification failed"))
    
    @http.route(
        _callback_url,
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def iyzico_callback(self, **post_data):
        """
        Handle the callback from iyzico after payment.
        
        iyzico sends a POST request to this URL after the customer
        completes or cancels the payment on their checkout page.
        
        The callback contains a token that we use to retrieve the
        actual payment result from iyzico API - we never trust
        the status sent directly in the callback.
        
        :param dict post_data: The POST data from iyzico
        :return: Redirect to the payment status page
        :rtype: werkzeug.wrappers.Response
        """
        _logger.info(
            "Received iyzico callback with data:\n%s",
            pprint.pformat({k: v for k, v in post_data.items() 
                           if k not in ('checkoutFormContent',)})
        )
        
        # Extract the token from callback
        token = post_data.get('token')
        
        if not token:
            _logger.error("iyzico callback received without token")
            return request.redirect('/payment/status?error=missing_token')
        
        try:
            # Find the transaction by token (stored in provider_reference)
            tx_sudo = request.env['payment.transaction'].sudo().search([
                ('provider_reference', '=', token),
                ('provider_code', '=', 'iyzico'),
            ], limit=1)
            
            if not tx_sudo:
                _logger.error("No transaction found for iyzico token: %s", token)
                return request.redirect('/payment/status?error=transaction_not_found')
            
            # Check if token has expired
            if tx_sudo.iyzico_token_expire_time:
                now = fields.Datetime.now()
                if now > tx_sudo.iyzico_token_expire_time:
                    _logger.warning(
                        "Received callback for expired token. Transaction: %s, Token expired at: %s, Current time: %s",
                        tx_sudo.reference,
                        tx_sudo.iyzico_token_expire_time,
                        now
                    )
                    # Still try to retrieve result from iyzico as the payment might have been completed
                    # The expiry is mainly for preventing new payment attempts
            
            # Verify webhook signature for additional security
            # This is optional but recommended for production environments
            try:
                self._verify_webhook_signature(token, tx_sudo.provider_id)
            except AccessDenied:
                _logger.error("Webhook signature verification failed for token: %s", token)
                return request.redirect('/payment/status?error=invalid_signature')
            
            # Retrieve the actual payment result from iyzico
            # This is the secure way - we don't trust the callback data
            payment_result = tx_sudo.provider_id.sudo()._iyzico_retrieve_checkout_result(token)
            
            _logger.info(
                "Retrieved iyzico payment result for transaction %s:\n%s",
                tx_sudo.reference,
                pprint.pformat({k: v for k, v in payment_result.items() 
                               if k not in ('checkoutFormContent',)})
            )
            
            # Prepare notification data with the verified result
            notification_data = {
                'token': token,
                'reference': tx_sudo.reference,
                **payment_result
            }
            
            # Process the notification
            tx_sudo._handle_notification_data('iyzico', notification_data)
            
        except ValidationError as e:
            _logger.exception("Error processing iyzico callback: %s", str(e))
            return request.redirect('/payment/status?error=processing_error')
        except Exception as e:
            _logger.exception("Unexpected error in iyzico callback: %s", str(e))
            return request.redirect('/payment/status?error=unexpected_error')
        
        # Redirect to the payment status page
        return request.redirect('/payment/status')
    
    @http.route(
        _return_url,
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def iyzico_return(self, **data):
        """
        Handle the return from iyzico checkout page.
        
        This is called when the user clicks "return to merchant" on iyzico's page.
        By this point, the callback should have already processed the payment.
        
        :param dict data: The GET parameters
        :return: Redirect to the payment status page
        :rtype: werkzeug.wrappers.Response
        """
        _logger.info("iyzico return with data: %s", data)
        
        # Simply redirect to the payment status page
        # The callback should have already processed everything
        return request.redirect('/payment/status')

    @http.route(
        '/payment/iyzico/checkout',
        type='json',
        auth='public',
        methods=['POST'],
    )
    def iyzico_checkout(self, **data):
        """
        Initialize an iyzico checkout session.
        
        This endpoint is called by the JavaScript frontend to get
        the checkout form content or redirect URL.
        
        :param dict data: The checkout initialization data
        :return: The checkout form data
        :rtype: dict
        """
        _logger.info("iyzico checkout initialization request: %s", data)
        
        # Get the transaction reference from the request
        reference = data.get('reference')
        
        if not reference:
            return {'error': _("Missing transaction reference.")}
        
        try:
            # Find the transaction
            tx_sudo = request.env['payment.transaction'].sudo().search([
                ('reference', '=', reference),
                ('provider_code', '=', 'iyzico'),
            ], limit=1)
            
            if not tx_sudo:
                return {'error': _("Transaction not found.")}
            
            # The checkout form should already be initialized during rendering
            # Return the stored checkout form content
            return {
                'success': True,
                'reference': reference,
            }
            
        except Exception as e:
            _logger.exception("Error in iyzico checkout: %s", str(e))
            return {'error': str(e)}
