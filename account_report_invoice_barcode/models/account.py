# -*- coding: utf-8 -*-

from openerp import fields, models


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    print_barcode = fields.Boolean(
        'Print Barcode', help="""If ticked, you can see the barcode in
        report of account invoice""", 
        default=True)