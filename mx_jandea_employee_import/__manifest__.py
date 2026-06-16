# -*- coding: utf-8 -*-
{
    'name': 'MX Jandea - Importación Masiva de Empleados (TEVA)',
    'version': '17.0.1.0.0',
    'summary': 'Importación masiva de empleados desde formato TEVA con validación de RFC',
    'description': """
        Módulo para carga masiva de empleados desde el formato TEVA (.xls/.xlsx).

        Características:
        - Importación desde plantilla TEVA (52 columnas IMSS)
        - Validación de formato RFC local (persona física y moral)
        - Mapeo a campos NATIVOS de Odoo hr.employee / hr.version
        - Campos custom mínimos: mx_rfc, mx_curp, nss (mexicanos estándar)
        - Soporte multi-empresa: vincula empleados por RFC entre empresas
        - Detección y manejo de duplicados (omitir o actualizar)
        - Reporte de resultados por registro (creado/actualizado/omitido/error)
        - Integración opcional con mx_jandea_checkid para verificación fiscal
    """,
    'author': 'Jandea IT',
    'website': 'https://www.jandea.com',
    'category': 'Human Resources',
    'depends': [
        'hr',
        'base_setup',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
        'views/import_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
