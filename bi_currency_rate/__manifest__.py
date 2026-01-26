# -*- coding: utf-8 -*-
{
    "name": "Bank Indonesia Currency Rate Integration",
    "version": "16.0.1.0.0",
    "author": "Muhammad Syarif",
    "email": "mhdsyarif.ms@gmail.com",
    "website": "https://www.mhdsyarif.com",
    "license": "LGPL-3",
    "category": "Accounting",
    "summary": "Automatically fetch daily exchange rates from Bank Indonesia (JISDOR & Transaction Rates).",
    "description": """
Bank Indonesia Currency Rate Integration
========================================
This module integrates Odoo with Bank Indonesia’s official exchange rate data.

Features:
---------
* Extends `res.currency.rate` with a method to fetch BI rates.
* Automatic daily updates via scheduled cron job.
* USD/IDR using JISDOR (Jakarta Interbank Spot Dollar Rate).
* Other currencies (AED, AUD, SGD, CNY, CNH, MYR, etc.) using BI Transaction Rates (mid-rate).
* Updates only active currencies in Odoo (excluding IDR).
* Multi-company support: rates are created/updated for all active companies.
* Detailed logging for audit and troubleshooting.
* Audit-ready for Indonesian accounting compliance.
    """,
    "depends": ["base"],
    "data": [
        "data/ir_cron.xml",
    ],
    'images': ['static/description/icon.png'],
}