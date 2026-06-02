# -*- coding: utf-8 -*-
{
    'name': 'MX Labkan - Importación Masiva de Empleados (TEVA)',
    'version': '19.0.1.0.0',
    'summary': 'Importación masiva de empleados desde formato TEVA con validación de RFC SAT',
    'description': """
        Módulo para carga masiva de empleados desde el formato TEVA (.xls/.xlsx).
        
        Características:
        - Importación desde plantilla TEVA (50+ columnas)
        - Validación de RFC: formato local + consulta al SAT (SIAT LCO)
        - Campo informativo de salario integrado (IMSS + Exento)
        - Soporte multi-empresa: un empleado puede estar en 2 empresas con relación entre registros
        - Detección de duplicados por RFC/CURP/NSS
        - Reporte de resultados por registro
    """,
    'author': 'Labkan IT',
    'website': 'https://www.labkan.mx',
    'category': 'Human Resources',
    'depends': [
        'hr',
        'hr_payroll',
        'l10n_mx_hr_payroll',
        'base_setup',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
        'views/import_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
