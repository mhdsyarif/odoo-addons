# -*- coding: utf-8 -*-
{
    'name': "Google Chat Notification",
    'summary': "Send notifications to Google Chat using webhooks",
    'description': "This module allows sending messages to Google Chat when specific events occur in Odoo.",
    
    'author': "Muhammad Syarif",
    'email': "mhdsyarif.ms@gmail.com",
    'website': "https://mhdsyarif.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/11.0/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Tools',
    'version': '15.0.0.0.1',
    'license': 'AGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail'],

    # always loaded
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'views/google_chat_views.xml',
    ],
    'images': ['static/description/icon.png'],
}