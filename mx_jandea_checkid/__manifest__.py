# -*- coding: utf-8 -*-
{
    'name': 'Jandea - CheckId Integration',
    'version': '19.0.1.0.0',
    'summary': 'Consulta de datos fiscales vía API CheckId (Canicalabs)',
    'description': '''
        Integración con la API CheckId de Canicalabs para consulta automática
        de datos fiscales (RFC, CURP, NSS, Régimen Fiscal, CP, Estado 69/69B)
        al crear o actualizar empleados en Odoo.
    ''',
    'author': 'Jandea - IT',
    'website': 'https://www.jandea.com.mx',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'base_setup',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/checkid_data.xml',
        'views/res_config_settings_views.xml',
        'views/checkid_log_views.xml',
        'views/hr_employee_views.xml',
        'wizard/checkid_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
