{
    "name": "Cloud Storage AWS",
    "summary": """Store attachments in the Amazon S3 cloud""",
    'author': "Muhammad Syarif",
    'email': "mhdsyarif.ms@gmail.com",
    'website': "https://mhdsyarif.com",
    "version": "20.0.1.0.0",
    "category": "Technical Settings",
    "depends": ["cloud_storage"],
    "data": [
        "views/settings.xml",
    ],
    "external_dependencies": {
        "python": ["boto3"],
    },
    "uninstall_hook": "uninstall_hook",
    "images": [
        "static/description/icon.png",
    ],
    "license": "LGPL-3",
    "installable": True,
}
