# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
import uuid

import requests
from werkzeug.urls import url_join

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.payment_iyzico import const
from odoo.addons.payment_iyzico import utils as iyzico_utils


_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    # === FIELDS ===#
    code = fields.Selection(
        selection_add=[('iyzico', "iyzico")],
        ondelete={'iyzico': 'set default'}
    )

    iyzico_website_ids = fields.Many2many(
        'website',
        'payment_provider_iyzico_website_rel',
        'provider_id',
        'website_id',
        string='Websites',
        help='Select the websites where this provider should be available.',
    )
    
    iyzico_api_key = fields.Char(
        string="Iyzico API Key",
        help="The API Key obtained from iyzico merchant panel.",
        required_if_provider='iyzico',
        groups='base.group_system',
    )
    
    iyzico_secret_key = fields.Char(
        string="Iyzico Secret Key",
        help="The Secret Key obtained from iyzico merchant panel.",
        required_if_provider='iyzico',
        groups='base.group_system',
    )
    
    # Installment (Taksit) configuration
    iyzico_enable_installments = fields.Boolean(
        string="Enable Installments",
        default=True,
        help="Allow customers to pay in installments (taksit). "
             "Available for credit cards in Turkey.",
    )
    
    iyzico_max_installments = fields.Selection(
        selection=[
            ('1', 'No Installments (Tek Çekim)'),
            ('3', 'Up to 3 Installments'),
            ('6', 'Up to 6 Installments'),
            ('9', 'Up to 9 Installments'),
            ('12', 'Up to 12 Installments'),
        ],
        string="Maximum Installments",
        default='12',
        help="Maximum number of installments to offer to customers.",
    )
    
    iyzico_force_3ds = fields.Boolean(
        string="Force 3D Secure",
        default=True,
        help="Always use 3D Secure authentication for payments. "
             "Recommended for security and lower fraud rates.",
    )
    
    iyzico_api_verified = fields.Boolean(
        string="API Verified",
        readonly=True,
        copy=False,
        help="Indicates whether the API credentials have been successfully verified.",
    )

    # === COMPUTE METHODS ===#

    @api.model
    def _get_compatible_providers(self, *args, website_id=None, currency_id=None, report=None, **kwargs):
        """Override to filter providers based on website.

        iyzico providers only appear on the websites that are selected in the iyzico_website_ids field.
        If no website is selected, the provider will not appear on any website.

        :param int website_id: The website ID to filter by (from context or parameter)
        :param int currency_id: The currency to filter by
        :param dict report: The availability report to log filtering reasons
        :return: The filtered recordset of compatible providers
        :rtype: recordset
        """
        # Initialize report if not provided
        if report is None:
            report = {}

        # Log incoming parameters for debugging
        _logger.info(
            "iyzico _get_compatible_providers called: website_id=%s, currency_id=%s, args=%s",
            website_id,
            currency_id,
            args[:2] if args else None  # Log only first 2 args to avoid too much output
        )

        # Log the currency details if currency_id is provided
        if currency_id:
            currency = self.env['res.currency'].browse(currency_id)
            _logger.info("Request currency: %s (id=%s)", currency.name, currency_id)

        providers = super()._get_compatible_providers(*args, website_id=website_id, currency_id=currency_id, report=report, **kwargs)

        # Log providers after super call
        _logger.info(
            "Providers after super(): %s",
            [(p.code, p.name, p.available_currency_ids.mapped('name')) for p in providers]
        )

        # Get current website from multiple sources for public users with access_token
        if website_id is None:
            website_id = self.env.context.get('website_id')

        # CRITICAL FIX: For public users accessing via access_token, get website from request
        if website_id is None:
            try:
                # Try to get current website from the HTTP request
                if request and hasattr(request, 'website') and request.website:
                    website_id = request.website.id
                    _logger.info("Got website_id from request.website: %s", website_id)
                else:
                    # Try to get current website using website model
                    website = self.env['website'].get_current_website()
                    if website:
                        website_id = website.id
                        _logger.info("Got website_id from get_current_website(): %s", website_id)
            except Exception as e:
                _logger.debug("Could not get website from request: %s", e)

        # Get all iyzico providers (including filtered ones) for reporting
        all_iyzico_providers = self.search([('code', '=', 'iyzico')])

        # Filter iyzico providers based on website
        if website_id:
            providers_before_website_filter = providers
            providers = providers.filtered(
                lambda p: p.code != 'iyzico' or not p.iyzico_website_ids or website_id in p.iyzico_website_ids.ids
            )
            # Log filtered providers in availability report
            for provider in all_iyzico_providers:
                if provider not in providers and provider in providers_before_website_filter:
                    # Provider was filtered due to website restriction
                    report.setdefault('providers', {})[provider] = {
                        'available': False,
                        'reason': f'Website {website_id} not allowed. Allowed websites: {provider.iyzico_website_ids.mapped("name") or "None"}',
                    }
                    _logger.warning(
                        "iyzico provider %s filtered out by website: %s (website_id=%s)",
                        provider.name, provider.iyzico_website_ids.ids, website_id
                    )
        else:
            providers_before_website_filter = providers
            providers = providers.filtered(
                lambda p: p.code != 'iyzico' or not p.iyzico_website_ids
            )
            for provider in all_iyzico_providers:
                if provider not in providers and provider in providers_before_website_filter:
                    report.setdefault('providers', {})[provider] = {
                        'available': False,
                        'reason': 'Website restriction - specific websites required but none detected',
                    }

        _logger.info(
            "Final providers after iyzico filter: %s",
            [(p.code, p.name) for p in providers]
        )

        return providers

    @api.depends('code')
    def _compute_available_currency_ids(self):
        """Compute available currencies for iyzico provider.

        IMPORTANT: For iyzico, we intentionally leave available_currency_ids empty.
        This means iyzico accepts ALL currencies. The actual currency validation
        happens at the iyzico API level during payment processing.

        If you want to restrict to specific currencies, you can manually add them
        in the provider form view.
        """
        super()._compute_available_currency_ids()
        for provider in self:
            if provider.code == 'iyzico':
                # Leave empty to accept all currencies
                # This allows customers from any country to use iyzico
                provider.available_currency_ids = [(5, 0, 0)]  # Remove all currencies
                _logger.info(
                    "iyzico provider %s: available_currency_ids cleared (accepts all currencies)",
                    provider.id
                )

    def _compute_feature_support_fields(self):
        """Override to enable iyzico-specific features."""
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'iyzico').update({
            'support_express_checkout': False,
            'support_manual_capture': False,  # iyzico doesn't support manual capture
            'support_refund': 'partial',  # iyzico supports partial refunds
            'support_tokenization': False,  # Not implementing tokenization for now
        })

    @api.onchange('state')
    def _onchange_state_switch_is_published(self):
        """Override to keep iyzico published even in test mode.

        For testing purposes, we want iyzico to remain visible on the website
        even when the provider is in test mode.
        """
        # For iyzico, always keep it published when state is 'test' or 'enabled'
        if self.code == 'iyzico' and self.state in ('test', 'enabled'):
            self.is_published = True
        else:
            # Use default behavior for other providers
            super()._onchange_state_switch_is_published()

    # === BUSINESS METHODS ===#

    @api.model
    def _setup_provider(self, provider_code):
        """Setup iyzico provider with payment methods after installation.
        
        This method is called by the post_init_hook to configure the iyzico provider.
        It links the 'card' payment method to the iyzico provider.
        
        :param str provider_code: The code of the provider to setup.
        :return: None
        """
        super()._setup_provider(provider_code)
        
        if provider_code != 'iyzico':
            return
        
        _logger.info("Setting up iyzico payment provider...")
        
        # Find the iyzico provider
        iyzico_provider = self.search([('code', '=', 'iyzico')], limit=1)
        if not iyzico_provider:
            _logger.warning("iyzico provider not found during setup")
            return
        
        # Find the 'card' payment method
        card_payment_method = self.env['payment.method'].search([
            ('code', '=', 'card')
        ], limit=1)
        
        if not card_payment_method:
            _logger.warning("Card payment method not found during iyzico setup")
            return
        
        # Link the payment method to the provider if not already linked
        if card_payment_method.id not in iyzico_provider.payment_method_ids.ids:
            iyzico_provider.write({
                'payment_method_ids': [(4, card_payment_method.id)]
            })
            _logger.info(
                "Linked 'card' payment method (id=%s) to iyzico provider (id=%s)",
                card_payment_method.id,
                iyzico_provider.id
            )
        
        # Activate the card payment method if it's not active
        if not card_payment_method.active:
            card_payment_method.write({'active': True})
            _logger.info("Activated 'card' payment method for iyzico")
        
        _logger.info("iyzico payment provider setup completed successfully")

    def _get_supported_currencies(self):
        """Override to return iyzico supported currencies."""
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'iyzico':
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in const.SUPPORTED_CURRENCIES
            )
            _logger.info(
                "iyzico supported currencies: %s (from const: %s)",
                supported_currencies.mapped('name'),
                const.SUPPORTED_CURRENCIES
            )
        return supported_currencies

    def _get_default_payment_method_codes(self):
        """Override to return the default payment method codes for iyzico."""
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'iyzico':
            return default_codes
        return const.DEFAULT_PAYMENT_METHOD_CODES

    def _get_default_payment_method_id(self, provider_code, mapping=None):
        """Override of `payment` to return the default payment method for iyzico."""
        default_method = super()._get_default_payment_method_id(provider_code, mapping)
        if provider_code != 'iyzico':
            return default_method
        # iyzico uses 'card' as the default payment method
        return self.env['payment.method'].search([
            ('code', '=', 'card'),
            ('provider_ids', 'in', self.id),
        ], limit=1) or self.env['payment.method'].search([('code', '=', 'card')], limit=1)

    def _iyzico_make_request(self, endpoint, payload=None, method='POST'):
        """
        Make a request to iyzico API.
        
        :param str endpoint: The API endpoint to call (e.g., '/payment/iyzipos/checkoutform/initialize/auth/ecom')
        :param dict payload: The request payload
        :param str method: HTTP method (POST, GET)
        :return: The JSON response from iyzico
        :rtype: dict
        :raises ValidationError: If the API request fails
        """
        self.ensure_one()
        
        # Get API URL based on provider state
        api_url = iyzico_utils.get_api_url(self)
        url = url_join(api_url, endpoint)
        
        # Get credentials
        api_key = iyzico_utils.get_api_key(self)
        secret_key = iyzico_utils.get_secret_key(self)
        
        if not api_key or not secret_key:
            raise ValidationError(_("iyzico API credentials are not configured."))
        
        # Prepare request body
        request_body = json.dumps(payload, separators=(',', ':')) if payload else ''
        
        # Generate random key for this request
        random_key = str(uuid.uuid4()).replace('-', '')[:16]
        
        # Add conversationId to payload
        if payload:
            payload['conversationId'] = payload.get('conversationId', random_key)
            # Regenerate request body with conversationId
            request_body = json.dumps(payload, separators=(',', ':'))
        
        # Get URI path from endpoint (ensure it starts with /)
        uri_path = '/' + endpoint.lstrip('/')
        
        # Generate authorization header with HMACSHA256
        authorization = iyzico_utils.generate_authorization_header(
            api_key, secret_key, random_key, uri_path, request_body
        )
        
        headers = {
            'Authorization': authorization,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'x-iyzi-rnd': random_key,
        }
        
        try:
            # Log the API request (sanitized)
            iyzico_utils.log_api_request(endpoint, payload, sanitize=True)
            
            if method == 'POST':
                response = requests.post(
                    url, 
                    data=request_body, 
                    headers=headers, 
                    timeout=const.API_TIMEOUT
                )
            else:
                response = requests.get(
                    url, 
                    headers=headers, 
                    timeout=const.API_TIMEOUT
                )
            
            response_data = response.json()
            
            # Log the API response (sanitized)
            iyzico_utils.log_api_response(endpoint, response_data, sanitize=True)
            
            # Check for API errors
            if response_data.get('status') != 'success':
                error_code = response_data.get('errorCode', 'unknown')
                error_message = response_data.get('errorMessage', 'Unknown error')
                _logger.warning(
                    "iyzico API error: code=%s, message=%s",
                    error_code, error_message
                )
                raise ValidationError(_(
                    "iyzico Error (%(code)s): %(message)s",
                    code=error_code,
                    message=error_message
                ))
            
            return response_data
            
        except requests.exceptions.ConnectionError:
            _logger.exception("Failed to connect to iyzico API at %s", url)
            raise ValidationError(_("Could not connect to iyzico. Please try again later."))
        except requests.exceptions.Timeout:
            _logger.exception("Timeout connecting to iyzico API at %s", url)
            raise ValidationError(_("iyzico request timed out. Please try again."))
        except json.JSONDecodeError:
            _logger.exception("Invalid JSON response from iyzico API")
            raise ValidationError(_("Invalid response from iyzico. Please try again."))

    def _iyzico_create_checkout_form(self, tx_values):
        """
        Create an iyzico checkout form initialization request.
        
        This creates a checkout session on iyzico's side and returns
        the payment page URL and token.
        
        :param dict tx_values: The transaction values
        :return: The checkout form initialization response
        :rtype: dict
        """
        self.ensure_one()
        
        # Get base URL for callbacks
        base_url = self.get_base_url()
        
        # FORCE HTTPS for callback URL (security requirement)
        # İyzico requires HTTPS callback URL in production
        if base_url.startswith('http://'):
            base_url = base_url.replace('http://', 'https://', 1)
            _logger.warning(
                "Converted callback base URL from HTTP to HTTPS: %s",
                base_url
            )
        
        # Determine enabled installments based on provider configuration
        enabled_installments = [1]  # Always allow single payment
        if self.iyzico_enable_installments:
            max_installments = int(self.iyzico_max_installments)
            # Build installment list: [1, 2, 3, 6, 9, 12] up to max
            for count in [2, 3, 6, 9, 12]:
                if count <= max_installments:
                    enabled_installments.append(count)
        
        _logger.info(
            "Creating iyzico checkout for %s with installments: %s (force_3ds=%s)",
            tx_values.get('reference'),
            enabled_installments,
            self.iyzico_force_3ds
        )

        # Helper function to parse name into first and last name
        def _parse_name(full_name):
            """Parse full name into first name and last name."""
            if not full_name:
                return 'Guest', 'User'
            parts = full_name.strip().split()
            if len(parts) == 0:
                return 'Guest', 'User'
            elif len(parts) == 1:
                return parts[0][:50], 'User'
            else:
                # First word is first name, rest is last name
                first_name = parts[0][:50]
                last_name = ' '.join(parts[1:])[:50]
                return first_name, last_name

        # Get billing information (invoice address)
        billing_name = tx_values.get('billing_partner_name') or tx_values.get('partner_name', 'Guest')
        billing_first_name, billing_last_name = _parse_name(billing_name)

        # Get shipping information (delivery address)
        shipping_name = tx_values.get('shipping_partner_name') or tx_values.get('partner_name', 'Guest')
        shipping_first_name, shipping_last_name = _parse_name(shipping_name)

        # Buyer information - use billing partner as buyer
        buyer_name = tx_values.get('partner_name') or billing_name
        buyer_first_name, buyer_last_name = _parse_name(buyer_name)

        # Prepare the checkout form request
        payload = {
            'locale': iyzico_utils.get_locale(tx_values.get('partner_lang', 'tr_TR')),
            'conversationId': tx_values.get('reference'),
            'price': iyzico_utils.format_amount(
                tx_values.get('amount', 0),
                tx_values.get('currency')
            ),
            'paidPrice': iyzico_utils.format_amount(
                tx_values.get('amount', 0),
                tx_values.get('currency')
            ),
            'currency': tx_values.get('currency').name if tx_values.get('currency') else 'TRY',
            'basketId': tx_values.get('reference'),
            'paymentGroup': const.PAYMENT_GROUP,
            'callbackUrl': url_join(base_url, '/payment/iyzico/callback'),
            'enabledInstallments': enabled_installments,  # Use dynamic installments
            'forceThreeDS': 1 if self.iyzico_force_3ds else 0,  # Force 3D Secure if enabled
            'buyer': {
                'id': str(tx_values.get('partner_id', 'guest')),
                'name': buyer_first_name,
                'surname': buyer_last_name,
                'gsmNumber': iyzico_utils.format_phone(
                    tx_values.get('billing_partner_phone') or tx_values.get('partner_phone')
                ),
                'email': tx_values.get('billing_partner_email') or tx_values.get('partner_email') or 'customer@example.com',
                'identityNumber': '11111111111',  # Required by iyzico, using placeholder
                'registrationAddress': tx_values.get('billing_partner_address') or tx_values.get('partner_address') or 'Address not provided',
                'ip': tx_values.get('partner_ip', '127.0.0.1'),
                'city': tx_values.get('billing_partner_city') or tx_values.get('partner_city') or 'Istanbul',
                'country': tx_values.get('billing_partner_country') or tx_values.get('partner_country') or 'Turkey',
                'zipCode': tx_values.get('billing_partner_zip') or tx_values.get('partner_zip') or '34000',
            },
            'shippingAddress': {
                'contactName': shipping_name[:100],
                'city': tx_values.get('shipping_partner_city') or tx_values.get('partner_city') or 'Istanbul',
                'country': tx_values.get('shipping_partner_country') or tx_values.get('partner_country') or 'Turkey',
                'address': tx_values.get('shipping_partner_address') or tx_values.get('partner_address') or 'Address not provided',
                'zipCode': tx_values.get('shipping_partner_zip') or tx_values.get('partner_zip') or '34000',
            },
            'billingAddress': {
                'contactName': billing_name[:100],
                'city': tx_values.get('billing_partner_city') or tx_values.get('partner_city') or 'Istanbul',
                'country': tx_values.get('billing_partner_country') or tx_values.get('partner_country') or 'Turkey',
                'address': tx_values.get('billing_partner_address') or tx_values.get('partner_address') or 'Address not provided',
                'zipCode': tx_values.get('billing_partner_zip') or tx_values.get('partner_zip') or '34000',
            },
            'basketItems': iyzico_utils.prepare_single_basket_item(
                tx_values.get('amount', 0),
                tx_values.get('reference'),
                tx_values.get('currency')
            ),
        }

        # Log the address information for debugging
        _logger.info(
            "iyzico checkout addresses for %s:\n"
            "  Buyer: %s %s (%s)\n"
            "  Billing: %s - %s, %s, %s\n"
            "  Shipping: %s - %s, %s, %s\n"
            "  Sale Order ID: %s",
            tx_values.get('reference'),
            buyer_first_name, buyer_last_name,
            tx_values.get('billing_partner_email'),
            billing_name[:30],
            tx_values.get('billing_partner_city'),
            tx_values.get('billing_partner_country'),
            tx_values.get('billing_partner_address', '')[:50] + '...' if tx_values.get('billing_partner_address') else 'N/A',
            shipping_name[:30],
            tx_values.get('shipping_partner_city'),
            tx_values.get('shipping_partner_country'),
            tx_values.get('shipping_partner_address', '')[:50] + '...' if tx_values.get('shipping_partner_address') else 'N/A',
            tx_values.get('sale_order_id')
        )
        
        return self._iyzico_make_request(
            const.ENDPOINT_CHECKOUT_FORM_INIT,
            payload
        )

    def _iyzico_retrieve_checkout_result(self, token):
        """
        Retrieve the checkout form payment result from iyzico.
        
        After the customer completes payment on iyzico's checkout page,
        we need to retrieve the result using the token.
        
        :param str token: The checkout form token
        :return: The payment result
        :rtype: dict
        """
        self.ensure_one()
        
        payload = {
            'locale': 'tr',
            'conversationId': str(uuid.uuid4()).replace('-', '')[:16],
            'token': token,
        }
        
        return self._iyzico_make_request(
            const.ENDPOINT_CHECKOUT_FORM_RETRIEVE,
            payload
        )

    def _iyzico_create_refund(self, payment_id, amount, currency):
        """
        Create a refund request to iyzico.
        
        IMPORTANT: iyzico refund requires paymentId (not paymentTransactionId!)
        
        :param str payment_id: The iyzico payment ID (from original payment response)
        :param float amount: The amount to refund
        :param currency: The res.currency record
        :return: The refund result
        :rtype: dict
        """
        self.ensure_one()
        
        payload = {
            'locale': 'tr',
            'conversationId': str(uuid.uuid4()).replace('-', '')[:16],
            'paymentId': payment_id,  # CRITICAL: Use paymentId, not paymentTransactionId!
            'price': iyzico_utils.format_amount(amount, currency),
            'currency': currency.name,
            'ip': '127.0.0.1',  # TODO: Get actual customer IP from request
        }
        
        return self._iyzico_make_request(
            const.ENDPOINT_REFUND,
            payload
        )

    def _iyzico_bin_check(self, bin_number):
        """
        Check card BIN (Bank Identification Number) to get card details.
        
        BIN check allows you to:
        - Validate if a card is valid
        - Get card type (credit/debit)
        - Get bank name
        - Get card brand (Visa, MasterCard, etc.)
        - Get available installment options for the card
        - Check card family and commercial card status
        
        This is useful for:
        - Early validation before checkout
        - Dynamic installment options based on card
        - Better UX by showing card info to customer
        
        :param str bin_number: First 6 digits of the card number
        :return: Card information including bank, card type, installments
        :rtype: dict
        :raises ValidationError: If BIN check fails
        
        Example response:
        {
            "status": "success",
            "binNumber": "589004",
            "cardType": "CREDIT_CARD",
            "cardAssociation": "MASTER_CARD",
            "cardFamily": "Bonus",
            "bankName": "Garanti Bankası",
            "bankCode": 62,
            "commercial": 0
        }
        """
        self.ensure_one()
        
        # Validate BIN number format
        if not bin_number or len(str(bin_number)) != 6:
            raise ValidationError(_(
                "BIN number must be exactly 6 digits. Provided: %s",
                bin_number
            ))
        
        # Ensure BIN is numeric
        if not str(bin_number).isdigit():
            raise ValidationError(_(
                "BIN number must contain only digits. Provided: %s",
                bin_number
            ))
        
        payload = {
            'locale': 'tr',
            'conversationId': str(uuid.uuid4()).replace('-', '')[:16],
            'binNumber': str(bin_number),
        }
        
        _logger.info("Performing BIN check for: %s", bin_number)
        
        try:
            result = self._iyzico_make_request(
                const.ENDPOINT_BIN_CHECK,
                payload
            )
            
            _logger.info(
                "BIN check successful for %s: %s %s (%s)",
                bin_number,
                result.get('cardAssociation'),
                result.get('cardType'),
                result.get('bankName')
            )
            
            return result
            
        except ValidationError as e:
            _logger.warning("BIN check failed for %s: %s", bin_number, str(e))
            raise
    
    def _iyzico_get_installment_info(self, bin_number, price):
        """
        Get available installment options for a specific card BIN and price.
        
        This method combines BIN check with installment calculation to provide
        detailed information about available installment plans for a card.
        
        Note: Some cards may not support installments, or may have minimum
        amounts for installment purchases.
        
        :param str bin_number: First 6 digits of the card number
        :param float price: The total price for installment calculation
        :return: Dictionary with card info and installment options
        :rtype: dict
        
        Example return:
        {
            "cardType": "CREDIT_CARD",
            "cardAssociation": "VISA",
            "bankName": "Akbank",
            "commercial": False,
            "installments": [
                {"count": 1, "totalPrice": 100.00},
                {"count": 3, "totalPrice": 102.50},
                {"count": 6, "totalPrice": 105.00},
            ]
        }
        """
        self.ensure_one()
        
        # First, get BIN information
        bin_info = self._iyzico_bin_check(bin_number)
        
        # Extract relevant information
        card_info = {
            'binNumber': bin_number,
            'cardType': bin_info.get('cardType'),
            'cardAssociation': bin_info.get('cardAssociation'),
            'cardFamily': bin_info.get('cardFamily'),
            'bankName': bin_info.get('bankName'),
            'bankCode': bin_info.get('bankCode'),
            'commercial': bin_info.get('commercial', 0) == 1,
        }
        
        # Determine available installments based on card type
        # Debit cards typically don't support installments in Turkey
        if bin_info.get('cardType') == 'DEBIT_CARD':
            card_info['installments'] = [{'count': 1, 'totalPrice': price}]
            card_info['installmentSupport'] = False
            _logger.info(
                "Debit card detected for BIN %s, no installments available",
                bin_number
            )
        else:
            # Credit cards support installments
            # Note: Actual installment rates should come from merchant agreements
            # This is a simplified example
            card_info['installmentSupport'] = True
            card_info['installments'] = [
                {'count': count, 'totalPrice': price}
                for count in const.INSTALLMENT_OPTIONS
            ]
            _logger.info(
                "Credit card detected for BIN %s, installments available: %s",
                bin_number,
                const.INSTALLMENT_OPTIONS
            )
        
        return card_info

    def action_iyzico_test_connection(self):
        """
        Test the iyzico API connection to verify credentials.
        
        This method performs a BIN check request to iyzico API to verify
        that the API key and secret key are correctly configured.
        
        :return: A notification with the test result
        :rtype: dict
        """
        self.ensure_one()
        
        if self.code != 'iyzico':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _("This action is only available for iyzico providers."),
                    'type': 'warning',
                },
            }
        
        # Check if API credentials are configured
        if not self.iyzico_api_key or not self.iyzico_secret_key:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _("Please configure your API Key and Secret Key first."),
                    'type': 'danger',
                },
            }
        
        _logger.info("Testing iyzico API connection for provider %s", self.id)
        
        # Test with BIN check endpoint (uses a known test BIN)
        # 552879 is a valid test BIN from iyzico documentation
        test_bin = '552879'
        
        try:
            result = self._iyzico_bin_check(test_bin)
            
            # If we get here, the API connection is successful
            self.iyzico_api_verified = True
            
            bank_name = result.get('bankName', 'Unknown Bank')
            card_type = result.get('cardType', 'Unknown')
            card_association = result.get('cardAssociation', 'Unknown')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _(
                        "Connection successful! API credentials are valid.\n"
                        "Test BIN (%(bin)s) returned: %(bank)s - %(card)s %(association)s",
                        bin=test_bin,
                        bank=bank_name,
                        card=card_type,
                        association=card_association
                    ),
                    'type': 'success',
                    'sticky': True,
                },
            }
            
        except ValidationError as e:
            # API connection failed or credentials are invalid
            self.iyzico_api_verified = False
            
            error_msg = str(e)
            
            # Check for specific error patterns to provide better feedback
            if 'Invalid API key' in error_msg or 'authentication' in error_msg.lower():
                message = _(
                    "Connection failed: Invalid API credentials.\n"
                    "Please check your API Key and Secret Key.\n\n"
                    "Make sure you are using:\n"
                    "- Sandbox keys for Test mode\n"
                    "- Production keys for Enabled mode"
                )
            elif 'Could not connect' in error_msg:
                message = _(
                    "Connection failed: Could not reach iyzico servers.\n"
                    "Please check your internet connection and try again."
                )
            elif 'timeout' in error_msg.lower():
                message = _(
                    "Connection failed: Request timed out.\n"
                    "The iyzico servers may be unavailable. Please try again later."
                )
            else:
                message = _("Connection failed: %s", error_msg)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': message,
                    'type': 'danger',
                    'sticky': True,
                },
            }
        except Exception as e:
            # Unexpected error
            self.iyzico_api_verified = False
            _logger.exception("Unexpected error during iyzico API connection test")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _("An unexpected error occurred: %s", str(e)),
                    'type': 'danger',
                    'sticky': True,
                },
            }

    def action_update_iyzico_icons(self):
        """
        Update iyzico provider and payment method icons from static files.
        
        This method reads icon.png and checkout_icon.png from the module's
        static/description folder and updates:
        - Provider image_128 field
        - All linked payment method image fields
        
        :return: A notification with the update result
        :rtype: dict
        """
        self.ensure_one()
        
        if self.code != 'iyzico':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _("This action is only available for iyzico providers."),
                    'type': 'warning',
                },
            }
        
        import base64
        from pathlib import Path
        
        _logger.info("Updating iyzico icons for provider %s", self.id)
        
        updated_count = 0
        
        # Get module path
        import odoo.addons.payment_iyzico as iyzico_module
        module_path = Path(iyzico_module.__file__).parent
        
        # Update provider icon (image_128)
        provider_icon_path = module_path / 'static' / 'description' / 'icon.png'
        if provider_icon_path.exists():
            with open(provider_icon_path, 'rb') as f:
                self.image_128 = base64.b64encode(f.read())
            updated_count += 1
            _logger.info("Updated provider image_128 from %s", provider_icon_path)
        else:
            _logger.warning("Provider icon not found: %s", provider_icon_path)
        
        # Update payment method icons
        checkout_icon_path = module_path / 'static' / 'description' / 'checkout_icon.png'
        if checkout_icon_path.exists():
            with open(checkout_icon_path, 'rb') as f:
                checkout_icon_data = base64.b64encode(f.read())
            
            # Update ALL linked payment methods
            for pm in self.payment_method_ids:
                pm.sudo().write({'image': checkout_icon_data})
                updated_count += 1
                _logger.info("Updated payment method '%s' (id=%s) image", pm.name, pm.id)
        else:
            _logger.warning("Checkout icon not found: %s", checkout_icon_path)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _("Updated %s icon(s) successfully. Please refresh the page.", updated_count),
                'type': 'success',
                'sticky': False,
            },
        }

