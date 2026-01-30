# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_iyzico import const
from odoo.addons.payment_iyzico import utils as iyzico_utils


_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'
    
    # === FIELDS ===#
    # 3D Secure tracking fields
    iyzico_3ds_status = fields.Char(
        string="3D Secure Status",
        help="The 3D Secure authentication status from iyzico",
        readonly=True,
    )
    
    iyzico_eci = fields.Char(
        string="ECI (Electronic Commerce Indicator)",
        help="Electronic Commerce Indicator - shows the level of 3D Secure authentication",
        readonly=True,
    )
    
    iyzico_installment = fields.Integer(
        string="Installment Count",
        help="Number of installments for this payment (1 = no installments)",
        default=1,
        readonly=True,
    )
    
    iyzico_card_family = fields.Char(
        string="Card Family",
        help="Card family/brand (e.g., Bonus, WorldCard, MaxiPuan)",
        readonly=True,
    )
    
    iyzico_card_association = fields.Char(
        string="Card Association",
        help="Card association (e.g., VISA, MASTER_CARD, TROY)",
        readonly=True,
    )
    
    iyzico_card_type = fields.Char(
        string="Card Type",
        help="Card type (CREDIT_CARD or DEBIT_CARD)",
        readonly=True,
    )

    iyzico_token_expire_time = fields.Datetime(
        string="Token Expiry Time",
        help="When the iyzico token expires (typically 30 minutes after creation)",
        readonly=True,
    )

    # === BUSINESS METHODS - PAYMENT FLOW ===#

    def _get_specific_secret_keys(self):
        """Override of payment to return iyzico-specific secret keys.
        
        These keys should not be logged for security reasons.
        
        Note: self.ensure_one() from `_get_processing_values`
        
        :return: The provider-specific secret keys
        :rtype: dict_keys
        """
        if self.provider_code == 'iyzico':
            return {'token': None}.keys()
        return super()._get_specific_secret_keys()

    def _get_specific_rendering_values(self, processing_values):
        """
        Override to return iyzico-specific rendering values.

        For iyzico, we need to initialize the checkout form and return
        the payment page URL for redirect.

        :param dict processing_values: The generic processing values
        :return: The dict of iyzico-specific rendering values
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)

        if self.provider_code != 'iyzico':
            return res

        # Get shipping and billing partners from sale order if available
        # This allows proper separation of delivery and invoice addresses
        shipping_partner = self.partner_id
        billing_partner = self.partner_id

        # Check if this transaction is linked to a sale order
        if self.sale_order_ids:
            sale_order = self.sale_order_ids[0]  # Take first order if multiple
            shipping_partner = sale_order.partner_shipping_id or self.partner_id
            billing_partner = sale_order.partner_invoice_id or self.partner_id

        # Helper function to format address from partner
        def _format_partner_address(partner):
            """Format partner address for iyzico."""
            from odoo.addons.payment import utils as payment_utils
            return payment_utils.format_partner_address(partner.street, partner.street2)

        # Prepare transaction values for iyzico with separate shipping/billing
        tx_values = {
            'reference': self.reference,
            'amount': self.amount,
            'currency': self.currency_id,
            'partner_id': self.partner_id.id,
            # Billing partner (invoice) information
            'billing_partner_id': billing_partner.id,
            'billing_partner_name': billing_partner.name,
            'billing_partner_email': billing_partner.email,
            'billing_partner_phone': billing_partner.phone or billing_partner.mobile,
            'billing_partner_address': _format_partner_address(billing_partner),
            'billing_partner_city': billing_partner.city,
            'billing_partner_zip': billing_partner.zip,
            'billing_partner_state': billing_partner.state_id.name if billing_partner.state_id else '',
            'billing_partner_country': billing_partner.country_id.name if billing_partner.country_id else 'Turkey',
            # Shipping partner (delivery) information
            'shipping_partner_id': shipping_partner.id,
            'shipping_partner_name': shipping_partner.name,
            'shipping_partner_email': shipping_partner.email,
            'shipping_partner_phone': shipping_partner.phone or shipping_partner.mobile,
            'shipping_partner_address': _format_partner_address(shipping_partner),
            'shipping_partner_city': shipping_partner.city,
            'shipping_partner_zip': shipping_partner.zip,
            'shipping_partner_state': shipping_partner.state_id.name if shipping_partner.state_id else '',
            'shipping_partner_country': shipping_partner.country_id.name if shipping_partner.country_id else 'Turkey',
            # General information (fallback to billing for buyer info)
            'partner_name': self.partner_name or billing_partner.name,
            'partner_email': self.partner_email or billing_partner.email,
            'partner_phone': self.partner_phone or billing_partner.phone or billing_partner.mobile,
            'partner_address': self.partner_address,
            'partner_city': self.partner_city,
            'partner_zip': self.partner_zip,
            'partner_country': self.partner_country_id.name if self.partner_country_id else 'Turkey',
            'partner_lang': self.partner_lang,
            'partner_ip': payment_utils.get_customer_ip_address(),
            # Store sale order reference for debugging
            'sale_order_id': self.sale_order_ids[0].id if self.sale_order_ids else None,
        }

        error_message = None
        checkout_response = {}

        try:
            # Check if we need to refresh the token (expired or will expire soon)
            should_refresh = True
            if self.iyzico_token_expire_time and self.provider_reference:
                # If token exists and won't expire in next 5 minutes, reuse it
                now = fields.Datetime.now()
                buffer_time = timedelta(minutes=5)
                if self.iyzico_token_expire_time > (now + buffer_time):
                    should_refresh = False
                    _logger.info(
                        "Reusing existing token for %s (expires at %s)",
                        self.reference,
                        self.iyzico_token_expire_time
                    )

            if should_refresh:
                # Create new checkout form/token
                checkout_response = self.provider_id.sudo()._iyzico_create_checkout_form(tx_values)

                # Store the token and expiry time
                token = checkout_response.get('token')
                token_expire_seconds = checkout_response.get('tokenExpireTime', 1800)  # Default 30 min
                
                if token:
                    self.provider_reference = token
                    # Calculate expiry time
                    self.iyzico_token_expire_time = fields.Datetime.now() + timedelta(seconds=token_expire_seconds)
                
                _logger.info(
                    "iyzico checkout form response for %s: token=%s..., expires_at=%s",
                    self.reference,
                    token[:20] if token else 'None',
                    self.iyzico_token_expire_time
                )
            else:
                # Reconstruct payment page URL from existing token
                # Use dynamic checkout URL based on provider state
                checkout_url = iyzico_utils.get_checkout_url(self.provider_id)
                checkout_response = {
                    'token': self.provider_reference,
                    'paymentPageUrl': f"{checkout_url}?token={self.provider_reference}&lang=tr"
                }
                _logger.info("Reconstructed payment URL from existing token for %s", self.reference)

        except ValidationError as e:
            _logger.error(
                "Error creating iyzico checkout form for %s: %s",
                self.reference,
                str(e)
            )
            error_message = str(e)
            # Set transaction to error state
            self._set_error(error_message)

        # Return the values needed for the redirect form
        # For Odoo 18, we return api_url and the template will render the form
        if error_message:
            _logger.error("Returning error for %s: %s", self.reference, error_message)
            # For errors, we return empty api_url to trigger error display
            return {
                'api_url': '',
                'error': error_message,
            }

        # Success case - return the iyzico payment page URL
        payment_page_url = checkout_response.get('paymentPageUrl', '')
        _logger.info("Returning api_url for %s: %s", self.reference, payment_page_url[:50] + '...')
        
        if not payment_page_url:
            _logger.error("No paymentPageUrl returned for %s", self.reference)
            return {
                'api_url': '',
                'error': 'Ödeme sayfası yüklenemedi.',
            }

        # Parse URL to separate base URL and query params
        # HTML form method="get" replaces query string, so we pass params as hidden inputs
        from urllib.parse import urlparse, parse_qs
        
        parsed = urlparse(payment_page_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        # Parse query params into a dict (parse_qs returns lists, we need single values)
        url_params = {}
        if parsed.query:
            for key, values in parse_qs(parsed.query).items():
                url_params[key] = values[0] if values else ''
        
        _logger.info("Parsed URL for %s: base=%s, params=%s", self.reference, base_url, url_params)

        # Return the api_url and url_params - the template will render the form
        return {
            'api_url': base_url,    
            'url_params': url_params,
        }

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """
        Override to find the transaction based on iyzico notification data.
        
        iyzico returns the conversationId (our reference) in the callback.
        
        :param str provider_code: The provider code
        :param dict notification_data: The notification data from iyzico
        :return: The transaction matching the notification data
        :rtype: recordset of `payment.transaction`
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        
        if provider_code != 'iyzico' or len(tx) == 1:
            return tx
        
        # Get reference from notification data
        reference = notification_data.get('conversationId') or notification_data.get('reference')
        token = notification_data.get('token')
        
        if not reference and not token:
            raise ValidationError(_("iyzico: No reference or token found in notification data."))
        
        # Search by reference first
        if reference:
            tx = self.search([
                ('reference', '=', reference),
                ('provider_code', '=', 'iyzico'),
            ])
        
        # If not found by reference, search by token (stored in provider_reference)
        if not tx and token:
            tx = self.search([
                ('provider_reference', '=', token),
                ('provider_code', '=', 'iyzico'),
            ])
        
        if not tx:
            raise ValidationError(_(
                "iyzico: No transaction found for reference %(ref)s or token %(token)s.",
                ref=reference,
                token=token
            ))
        
        return tx

    def _process_notification_data(self, notification_data):
        """
        Override to process iyzico notification data.
        
        This method updates the transaction state based on the payment result
        from iyzico.
        
        :param dict notification_data: The notification data from iyzico
        :return: None
        """
        super()._process_notification_data(notification_data)
        
        if self.provider_code != 'iyzico':
            return
        
        _logger.info(
            "Processing iyzico notification for transaction %s:\n%s",
            self.reference,
            pprint.pformat({k: v for k, v in notification_data.items() 
                           if k not in ('checkoutFormContent',)})
        )
        
        # Get the payment result from notification data
        # If we only have the token, we need to retrieve the full result
        if 'paymentStatus' not in notification_data and notification_data.get('token'):
            payment_result = self.provider_id.sudo()._iyzico_retrieve_checkout_result(
                notification_data.get('token')
            )
            notification_data.update(payment_result)
        
        # Extract payment information
        payment_status = notification_data.get('paymentStatus') or notification_data.get('status')
        payment_id = notification_data.get('paymentId')
        error_code = notification_data.get('errorCode')
        error_message = notification_data.get('errorMessage')
        
        # Extract 3D Secure and card information
        auth_code = notification_data.get('authCode')
        installment = notification_data.get('installment', 1)
        card_family = notification_data.get('cardFamily')
        card_association = notification_data.get('cardAssociation')
        card_type = notification_data.get('cardType')
        eci = notification_data.get('eci')
        
        # Update transaction with 3D Secure and card details
        self.write({
            'iyzico_installment': installment,
            'iyzico_card_family': card_family,
            'iyzico_card_association': card_association,
            'iyzico_card_type': card_type,
            'iyzico_eci': eci,
            'iyzico_3ds_status': payment_status,
        })
        
        # Log 3D Secure information
        if eci:
            _logger.info(
                "iyzico 3DS info for %s: ECI=%s, Status=%s, Card=%s %s",
                self.reference,
                eci,
                payment_status,
                card_association,
                card_type
            )
        
        # Update provider reference with payment ID if available
        if payment_id:
            self.provider_reference = payment_id
        
        # Process based on payment status using STATUS_MAPPING
        # Normalize status to uppercase for consistent comparison
        normalized_status = payment_status.upper() if payment_status else ''
        
        if normalized_status in const.STATUS_MAPPING['done']:
            # Payment successful
            self._set_done()
            _logger.info(
                "iyzico payment successful for transaction %s (paymentId: %s)",
                self.reference,
                payment_id
            )
            
        elif normalized_status in const.STATUS_MAPPING['error']:
            # Payment failed
            state_message = iyzico_utils.get_error_message(error_code) if error_code else error_message
            self._set_error(state_message or _("Payment failed."))
            _logger.warning(
                "iyzico payment failed for transaction %s: %s (code: %s)",
                self.reference,
                error_message,
                error_code
            )
            
        elif normalized_status in const.STATUS_MAPPING['pending']:
            # 3DS authentication in progress or pending
            self._set_pending(_("3D Secure authentication in progress."))
            _logger.info(
                "iyzico 3DS in progress for transaction %s",
                self.reference
            )
            
        elif normalized_status in const.STATUS_MAPPING['draft']:
            # Still in initial state
            self._set_pending(_("Payment initialization in progress."))
            _logger.info(
                "iyzico payment initialization for transaction %s",
                self.reference
            )
            
        else:
            # Unknown status - set as pending for manual review
            self._set_pending(
                _("Payment status: %(status)s. Please check iyzico panel.", status=payment_status)
            )
            _logger.warning(
                "iyzico unknown payment status for transaction %s: %s",
                self.reference,
                payment_status
            )

    def _send_refund_request(self, amount_to_refund=None):
        """
        Override to create a refund with iyzico.
        
        :param float amount_to_refund: The amount to refund
        :return: The refund transaction
        :rtype: recordset of `payment.transaction`
        """
        if self.provider_code != 'iyzico':
            return super()._send_refund_request(amount_to_refund=amount_to_refund)
        
        # Create refund transaction first
        refund_tx = super()._send_refund_request(amount_to_refund=amount_to_refund)
        
        # Get the payment transaction ID from iyzico
        # We need to retrieve the original payment details first
        if not self.provider_reference:
            raise ValidationError(_(
                "Cannot refund: No iyzico payment reference found for transaction %s.",
                self.reference
            ))
        
        try:
            # IMPORTANT: iyzico refund uses paymentId (which we store in provider_reference)
            # NOT paymentTransactionId!
            refund_amount = amount_to_refund or self.amount
            
            refund_result = self.provider_id.sudo()._iyzico_create_refund(
                self.provider_reference,  # This is the paymentId
                refund_amount,
                self.currency_id
            )
            
            # Update refund transaction based on result
            if refund_result.get('status') == 'success':
                # Store the payment ID from refund response
                refund_tx.provider_reference = refund_result.get('paymentId')
                refund_tx._set_done()
            else:
                error_message = refund_result.get('errorMessage', 'Refund failed')
                refund_tx._set_error(error_message)
                
        except ValidationError as e:
            refund_tx._set_error(str(e))
            raise
        
        return refund_tx

    def _get_specific_create_values(self, provider_code, values):
        """
        Override to add iyzico-specific create values.
        
        :param str provider_code: The code of the provider
        :param dict values: The original create values
        :return: The dict of iyzico-specific create values
        :rtype: dict
        """
        res = super()._get_specific_create_values(provider_code, values)
        
        if provider_code != 'iyzico':
            return res
        
        # No additional create values needed for iyzico
        return res

    def _get_specific_processing_values(self, processing_values):
        """
        Override to return iyzico-specific processing values.
        
        :param dict processing_values: The generic processing values
        :return: The dict of iyzico-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_processing_values(processing_values)
        
        if self.provider_code != 'iyzico':
            return res
        
        # Return values needed for the payment form
        return {
            'iyzico_checkout_url': '/payment/iyzico/checkout',
        }
