# -*- coding: utf-8 -*-
{
    'name': 'MX Jandea - Préstamos a Empleados',
    'version': '19.0.1.0.0',
    'summary': 'Registro y descuento automático de préstamos en nómina',
    'description': """
        Gestión de préstamos a empleados sobre el mecanismo nativo de
        Ajustes Salariales (hr.salary.attachment) de Odoo.

        Qué agrega:
        - Menú "Préstamos" dentro de Nómina.
        - Concepto "Préstamo" preconfigurado y asignado por default.
        - Registro y seguimiento por empleado: total, recuperado, pendiente
          y estado (en curso / cerrado), todo nativo del ajuste salarial.
        - Regla salarial de deducción que descuenta el préstamo en cada
          recibo de nómina hasta saldarlo.

        Uso recomendado: al dar de alta el préstamo, elegir Duración =
        "Limitado", capturar el monto total y el monto por recibo. Odoo
        descuenta en cada nómina hasta completar el total y cierra el
        registro automáticamente.
    """,
    'author': 'Jandea IT',
    'website': 'https://www.jandea.com',
    'category': 'Human Resources/Payroll',
    'depends': [
        'hr_payroll',
    ],
    'data': [
        'data/hr_payslip_input_type_data.xml',
        'views/salary_attachment_views.xml',
    ],
    'post_init_hook': 'post_init_attach_rule',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
