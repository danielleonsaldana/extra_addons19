# -*- coding: utf-8 -*-
{
    'name': 'MX Jandea - Préstamos a Empleados',
    'version': '19.0.1.0.4',
    'summary': 'Préstamos con calendario de pagos y descuento automático en nómina',
    'description': """
        Gestión de préstamos a empleados con calendario de pagos sobre el
        mecanismo nativo de Ajustes Salariales (hr.salary.attachment).

        Qué agrega:
        - Menú "Préstamos" dentro de Nómina, con su propio modelo.
        - Captura simple: empleado, monto total, periodicidad y monto por período.
        - Al confirmar, genera el calendario de pagos (período, fecha, descuento
          y saldo restante) y crea automáticamente el ajuste salarial nativo que
          descuenta en cada nómina hasta saldarlo.
        - Balance en vivo (descontado / restante) y marcado de cada período como
          pagado conforme las nóminas aplican el descuento.
        - Regla salarial de deducción que descuenta el préstamo en el recibo.

        19.0.1.0.3
        - Reglas de registro multiempresa en mx.jandea.prestamo y su línea.
          Antes el modelo no filtraba por compañía y al leer el
          hr.salary.attachment vinculado (que sí tiene regla nativa) se
          producía un "Error de acceso".
        - company_id almacenado en la línea de calendario.
        - Lectura del ajuste salarial con sudo() en los campos calculados.
        - Creación del ajuste con with_company().
    """,
    'author': 'Jandea IT',
    'website': 'https://www.jandea.com',
    'category': 'Human Resources/Payroll',
    'depends': [
        'hr_payroll',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/prestamo_security.xml',
        'data/hr_payslip_input_type_data.xml',
        'views/prestamo_views.xml',
    ],
    'post_init_hook': 'post_init_attach_rule',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
