{
    'name': 'HR View Only Recruitment Process',
    'version': '11.0.1.0',
    'category': 'hr',
    'summary': 'HR View Only Recruitment Process',
    'author': 'Muhammad Syarif',
    'email': 'mhdsyarif.ms@gmail.com',
    'website': 'https://www.mhdsyarif.com',
    'maintainer': 'Riau Programmer',
    'license': 'AGPL-3',
    "description": """
        Hr Applicant Kanban View Only
    """,
    'license':'LGPL-3',
    'data': [
        'security/hr_security.xml',
        'security/ir.model.access.csv',
        'views/hr_recruitment_views.xml',
        'views/menus.xml',
        'views/templates.xml',
    ],
    'depends': ['hr_recruitment'],
    'images': ['static/description/syarif.png'],
    'installable': True,
}
