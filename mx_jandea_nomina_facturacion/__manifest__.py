# -*- coding: utf-8 -*-
{
    'name': 'MX Jandea - Facturación de Nómina entre Empresas',
    'version': '19.0.1.0.0',
    'summary': 'Genera Orden de Venta (y factura) entre empresas a partir de la nómina, con conceptos y comisión configurables',
    'description': """
        A partir de la nómina de una empresa (la de la nómina = CLIENTE/receptor),
        otra empresa seleccionable (EMISORA) genera una Orden de Venta con
        conceptos configurables. Uno de esos conceptos suele ser una comisión
        con porcentaje configurable sobre una base de la nómina.

        Flujo:
        1. Configuras los CONCEPTOS de facturación (producto + tipo de cálculo:
           % sobre base de nómina, monto fijo, o manual).
        2. Generas la facturación eligiendo:
             - Origen: por LOTE de nómina (hr.payslip.run) o MENSUAL (mes+empresa).
             - Empresa EMISORA (la que factura) -> se puede cambiar cada vez.
             - Cliente = empresa de la nómina (editable).
        3. El asistente calcula la base y precarga los conceptos (editables).
        4. Genera la ORDEN DE VENTA en la empresa emisora.
        5. Desde la Orden de Venta creas la FACTURA con el flujo nativo de Odoo.

        Multiempresa: lecturas de nómina con sudo() y creación de la orden con
        with_company() para evitar errores de acceso entre compañías.
    """,
    'author': 'Jandea IT',
    'website': 'https://www.jandea.com',
    'category': 'Human Resources/Payroll',
    'depends': [
        'hr_payroll',
        'sale_management',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/nomina_concepto_views.xml',
        'wizard/facturacion_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
