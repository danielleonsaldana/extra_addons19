# -*- coding: utf-8 -*-
{
    'name': 'MX Jandea - Reporte Listado de Nómina (Excel)',
    'version': '19.0.1.0.0',
    'summary': 'Genera el Listado de Nómina en Excel (percepciones y deducciones por empleado)',
    'description': """
        Exporta a Excel el Listado de Nómina con el mismo formato del ejemplo:
        identificación del empleado (Clave, Nombre, RFC, CURP, IMSS, Días),
        percepciones (Sueldo, Vacaciones, Prima Vacacional, Festivo, Vales,
        Fondo de Ahorro, Prima Dominical, Aguinaldo, PTU...), Total Percepciones,
        y deducciones (ISR, Cuotas IMSS, Anticipo, Préstamo, Pensión, Caja de
        Ahorro...).

        Origen: por LOTE de nómina (hr.payslip.run) o MENSUAL (mes + empresa).

        El importe de cada columna de dinero se toma de las líneas del recibo
        según un MAPEO configurable columna -> códigos de regla salarial
        (Nómina -> Reportes -> Mapeo de Columnas), para que coincida con los
        códigos de tu instancia.
    """,
    'author': 'Jandea IT',
    'website': 'https://www.jandea.com',
    'category': 'Human Resources/Payroll',
    'depends': [
        'hr_payroll',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/reporte_map_data.xml',
        'views/reporte_map_views.xml',
        'wizard/reporte_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
