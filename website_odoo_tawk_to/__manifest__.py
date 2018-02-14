# -*- coding: utf-8 -*-

{
    'name': 'Live Chat Tawk.to',
    'version': '10.0.1.0',
    'category': 'Website',
    'summary': 'Use tawk.to service to embedded Live Chat in Odoo',
    'author': 'Muhammad Syarif',
    'email': 'mhdsyarif.ms@gmail.com',
    'website': 'http://www.mhdsyarif.com',
    'maintainer': 'Riau Programmer',
    'license': 'AGPL-3',
    "description": 'Use tawk.to service to embedded Live Chat in Odoo',
    'depends': ['website'],
    'data': [
        'views/templates.xml',
        'views/website_config_settings.xml',
    ],
    'images': ['static/description/syarif.png'],
    'installable': True,
    'auto_install': False
}