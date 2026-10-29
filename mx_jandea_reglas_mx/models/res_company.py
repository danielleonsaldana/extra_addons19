# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Casilla POR SUCURSAL (cada sucursal es una empresa/rama en Odoo).
    mx_jandea_isr_retener_minimo = fields.Boolean(
        string='Retener ISR aunque gane el salario mínimo',
        default=False,
        help='Marcada: a los empleados de esta sucursal que ganan el salario '
             'mínimo (y que por eso no llegarían a ISR) se les retiene el '
             'mismo ISR que a los demás: tarifa mensualizada menos subsidio '
             'para el empleo.\n'
             'Desmarcada: quien gana el salario mínimo no paga ISR '
             '(art. 96 LISR).')
