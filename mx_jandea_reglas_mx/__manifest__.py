# -*- coding: utf-8 -*-
{
    'name': 'MX Jandea - Reglas Salariales Complementarias',
    'version': '19.0.1.1.0',
    'summary': 'Reglas salariales mexicanas no incluidas en l10n_mx_hr_payroll + fix ISR GROSS=0',
    'author': 'Jandea IT',
    'category': 'Human Resources/Payroll',
    'depends': [
        'l10n_mx_hr_payroll',
    ],
    'data': [
        'data/hr_payslip_input_type_data.xml',
        'data/hr_salary_rule_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
