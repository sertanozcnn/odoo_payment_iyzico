# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import controllers
from . import models
from . import wizard


def post_init_hook(env):
    """Post-installation hook to ensure iyzico provider is properly configured.
    
    This hook ensures that:
    1. iyzico provider image_128 is set from icon.png
    2. All linked payment methods have correct image from checkout_icon.png
    3. iyzico provider is published if in test/enabled mode
    """
    import logging
    import base64
    from pathlib import Path
    
    _logger = logging.getLogger(__name__)
    
    _logger.info("Running iyzico post-init hook...")
    
    # Get module path and load images
    module_path = Path(__file__).parent
    
    # Load provider icon (128x128)
    provider_icon_path = module_path / 'static' / 'description' / 'icon.png'
    provider_icon_data = None
    if provider_icon_path.exists():
        with open(provider_icon_path, 'rb') as f:
            provider_icon_data = base64.b64encode(f.read())
        _logger.info("Loaded provider icon from %s", provider_icon_path)
    else:
        _logger.warning("Provider icon not found: %s", provider_icon_path)
    
    # Load checkout icon (64x64) for payment methods
    checkout_icon_path = module_path / 'static' / 'description' / 'checkout_icon.png'
    checkout_icon_data = None
    if checkout_icon_path.exists():
        with open(checkout_icon_path, 'rb') as f:
            checkout_icon_data = base64.b64encode(f.read())
        _logger.info("Loaded checkout icon from %s", checkout_icon_path)
    else:
        _logger.warning("Checkout icon not found: %s", checkout_icon_path)
    
    # Find all iyzico providers
    providers = env['payment.provider'].sudo().search([('code', '=', 'iyzico')])
    _logger.info("Found %s iyzico provider(s)", len(providers))
    
    for provider in providers:
        # Update provider icon
        if provider_icon_data:
            provider.write({'image_128': provider_icon_data})
            _logger.info("Updated provider '%s' (id=%s) image_128", provider.name, provider.id)
        
        # Set published if in test or enabled mode
        if provider.state in ['test', 'enabled'] and not provider.is_published:
            provider.is_published = True
            _logger.info("Published provider '%s' (id=%s)", provider.name, provider.id)
        
        # Update ALL linked payment methods with checkout icon
        if checkout_icon_data:
            payment_methods = provider.payment_method_ids
            for pm in payment_methods:
                pm.sudo().write({'image': checkout_icon_data})
                _logger.info("Updated payment method '%s' (id=%s) image", pm.name, pm.id)
    
    _logger.info("iyzico post-init hook completed - updated %s provider(s)", len(providers))

