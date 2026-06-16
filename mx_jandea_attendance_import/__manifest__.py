# -*- coding: utf-8 -*-
{
    'name': 'MX Jandea - Importación de Faltas',
    'version': '19.0.1.0.0',
    'summary': 'Carga masiva de faltas, retardos y permisos desde Excel',
    'description': """
        Módulo para registrar faltas, retardos y permisos de empleados.

        Características:
        - Tipos de falta preconfigurados para México (IMSS/nómina)
        - Importación masiva desde Excel/CSV (RFC + tipo + fechas)
        - Vista previa editable antes de confirmar
        - Integración con hr.leave (Tiempo Personal nativo de Odoo)
        - Compatible con hr.payslip (nómina) y hr.attendance (asistencias)
        - Reporte de faltas por período / empleado / tipo
    """,
    'author': 'Jandea IT',
    'website': 'https://www.jandea.com',
    'category': 'Human Resources',
    'depends': [
        'hr',
        'hr_holidays',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_leave_type_data.xml',
        'views/hr_leave_views.xml',
        'views/menu_views.xml',
        'wizard/leave_import_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
