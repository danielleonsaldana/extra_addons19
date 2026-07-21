# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    mx_jandea_nomina_origen = fields.Boolean(
        'Origen nómina', copy=False,
        help='Orden generada automáticamente desde la nómina.',
    )
    mx_jandea_nomina_run_id = fields.Many2one(
        'hr.payslip.run', string='Lote de nómina', copy=False, readonly=True,
        help='Lote de nómina que originó esta orden (si aplica).',
    )
    mx_jandea_nomina_company_id = fields.Many2one(
        'res.company', string='Empresa de la nómina', copy=False, readonly=True,
        help='Empresa que corrió la nómina (cliente/receptor de la factura).',
    )
    mx_jandea_nomina_periodo = fields.Char(
        'Período de nómina', copy=False, readonly=True,
    )
    mx_jandea_nomina_num_empleados = fields.Integer(
        '# Empleados en nómina', copy=False, readonly=True,
    )
