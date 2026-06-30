# -*- coding: utf-8 -*-
{
    'name': 'MX Labkan - Reglas Salariales Complementarias',
    'version': '19.0.1.0.0',
    'summary': 'Reglas salariales mexicanas no incluidas en l10n_mx_hr_payroll',
    'description': """
        Agrega a la estructura "Mexico: Regular Pay" las percepciones y
        deducciones mexicanas que el módulo nativo l10n_mx_hr_payroll no
        incluye:

        Percepciones (entran al GROSS / ISR nativos vía categoría
        TAXABLE_ALW, igual que Commissions/Bonus nativos):
        - Horas Extra Dobles / Triples
        - Festivo Laborado
        - Prima Dominical
        - PTU (Reparto de Utilidades)
        - Premios de Asistencia / Puntualidad
        - Compensación
        - Habitación

        Deducciones (categoría DED nativa, se reflejan en NET):
        - Anticipo de Nómina
        - Caja de Ahorro
        - SAR Voluntario
        - INFONAVIT Voluntario
        - Impuesto Local (placeholder de tasa, ajustar por estado)

        Todas se alimentan por hr.payslip.input (captura manual por recibo),
        igual que Commissions/Bonus en el módulo nativo.
    """,
    'author': 'Labkan IT',
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
