# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging
import os

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IyzicoIconWizard(models.TransientModel):
    """Wizard to update iyzico icons for provider and payment methods."""
    
    _name = 'iyzico.icon.wizard'
    _description = 'Update Iyzico Icons'

    def _get_default_info(self):
        """Get info about current icon status."""
        provider = self.env['payment.provider'].search([('code', '=', 'iyzico')], limit=1)
        if provider and provider.image_128:
            return _("Provider icon is currently set.")
        return _("Provider icon is NOT set (showing placeholder).")

    info = fields.Text(
        string="Current Status",
        default=_get_default_info,
        readonly=True,
    )

    def _get_image_as_base64(self, image_filename):
        """Read an image file and return its base64 encoded content."""
        try:
            import odoo.addons.payment_iyzico as iyzico_module
            module_path = os.path.dirname(iyzico_module.__file__)
            image_path = os.path.join(module_path, 'static', 'description', image_filename)
            
            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    return base64.b64encode(f.read())
            _logger.warning("Image file not found: %s", image_path)
        except Exception as e:
            _logger.error("Failed to read image %s: %s", image_filename, e)
        return None

    def action_update_icons(self):
        """Update all iyzico provider and payment method icons."""
        self.ensure_one()
        
        updated_count = 0
        
        # Update provider icons
        provider_icon = self._get_image_as_base64('icon.png')
        if provider_icon:
            providers = self.env['payment.provider'].sudo().search([('code', '=', 'iyzico')])
            for provider in providers:
                provider.write({'image_128': provider_icon})
                updated_count += 1
                _logger.info("Updated icon for iyzico provider: %s", provider.name)
        else:
            _logger.warning("Provider icon (icon.png) not found")

        # Update payment method icons
        checkout_icon = self._get_image_as_base64('checkout_icon.png')
        if checkout_icon:
            # Get all payment methods linked to iyzico providers
            iyzico_providers = self.env['payment.provider'].sudo().search([('code', '=', 'iyzico')])
            payment_methods = iyzico_providers.mapped('payment_method_ids')
            
            for pm in payment_methods:
                pm.write({'image': checkout_icon})
                updated_count += 1
                _logger.info("Updated icon for payment method: %s", pm.name)
        else:
            _logger.warning("Checkout icon (checkout_icon.png) not found")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Icons Updated"),
                'message': _("%s icon(s) updated successfully. Please refresh the page to see changes.") % updated_count,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_open_wizard(self):
        """Action to open the wizard from provider form."""
        return {
            'type': 'ir.actions.act_window',
            'name': _("Update Iyzico Icons"),
            'res_model': 'iyzico.icon.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
