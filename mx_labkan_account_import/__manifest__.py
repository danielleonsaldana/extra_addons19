# -*- coding: utf-8 -*-
{
    'name': 'MX Labkan - Alta Masiva de Cuentas',
    'version': '17.0.1.0.0',
    'summary': 'Importación masiva de cuentas contables y descarga TXT bancaria (Inbursa / Otros Bancos)',
    'description': """
        Módulo para Labkan / BHAANG:
        - Alta masiva de cuentas contables (account.account) desde archivo Excel/CSV
        - Descarga masiva de cuentas bancarias de beneficiarios en formato TXT
          compatible con Inbursa y Otros Bancos
    """,
    'author': 'Labkan IT',
    'category': 'Accounting/Accounting',
    'depends': ['account', 'base_setup'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/account_import_wizard_views.xml',
        'wizard/bank_account_export_wizard_views.xml',
        'views/account_menu_extend.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
