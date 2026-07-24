# -*- coding: utf-8 -*-
{
    'name': 'MX Jandea - Reglas Salariales Complementarias',
    'version': '19.0.1.2.0',
    'summary': 'Reglas salariales mexicanas no incluidas en l10n_mx_hr_payroll + fix ISR GROSS=0 + estructura de Finiquito/Liquidación',
    'description': """
Reglas complementarias para la nómina mexicana:

* Fix de la regla ISR nativa cuando GROSS = 0 (empleado con todas faltas).
* Percepciones complementarias (horas extra, festivo, prima dominical, PTU,
  premios, compensación, habitación).
* Deducciones complementarias (anticipo, caja de ahorro, SAR e INFONAVIT
  voluntarios).
* Estructura "Mexico: Finiquito / Liquidación" que replica el cálculo de
  finiquito: salario pendiente, aguinaldo y vacaciones proporcionales, prima
  vacacional, indemnización 90 y 20 días, prima de antigüedad (topada a 2 SMG),
  cuota obrera IMSS, ISR con exenciones en UMA (art. 93 LISR) e ISN.

ISN (Impuesto Sobre Nóminas): es un impuesto ESTATAL a cargo del PATRÓN, no una
deducción al trabajador. Por eso se calcula en la categoría PATRONAL, fuera del
neto. Si la entrada FNQT_ISN_TASA no se captura o va en 0, el ISN no aplica.

UMA y salario mínimo se leen de parámetros de regla versionados por año
(mx_jandea_uma / mx_jandea_smg), así que no requieren cambios de código.
    """,
    'author': 'Jandea IT',
    'category': 'Human Resources/Payroll',
    'depends': [
        'l10n_mx_hr_payroll',
    ],
    'data': [
        'data/hr_rule_parameter_data.xml',
        'data/hr_payslip_input_type_data.xml',
        'data/hr_payslip_input_type_finiquito_data.xml',
        'data/hr_salary_rule_data.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
