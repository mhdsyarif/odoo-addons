from odoo import models, fields


class Website(models.Model):
    _inherit = 'website'

    tawk_siteid = fields.Char(
        'Tawk Site ID', help='The site ID from settings in tawk.to',
        default='')