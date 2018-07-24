# -*- coding: utf-8 -*-

{
    'name': 'Add Barcode on Report Invoice',
    'version': '1.0',
    'category': 'Accounting & Finance',
    'summary': 'Custom report invoice',
    'author': 'Muhammad Syarif',
    'email': 'mhdsyarif.ms@gmail.com',
    'website': 'http://www.mhdsyarif.com',
    'maintainer': 'Riau Programmer',
    'description': 'Add Barcode(Code128) on Report Invoice',
    'license': 'AGPL-3',
    'depends': ['account','account_invoicing'],
    'data': [
        'views/account_invoice_form.xml',
        'report/report_invoice.xml',
    ],
    'images': ['static/description/syarif.png'],
    'installable': True,
    'auto_install': False
}