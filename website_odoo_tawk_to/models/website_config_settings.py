from odoo import models, fields


class WebsiteConfigSettings(models.TransientModel):
    _inherit = 'website.config.settings'

    tawk_siteid = fields.Char(
        related=['website_id', 'tawk_siteid'])