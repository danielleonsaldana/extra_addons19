# -*- coding: utf-8 -*-
from odoo import models, fields


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # Porcentaje que SI se paga de los conceptos seleccionados (100 = completo).
    x_fnqt_pct = fields.Float(
        string='% aplicado a conceptos', default=100.0,
        help='Porcentaje que se paga de los conceptos marcados en el wizard '
             '"Aplicar % a conceptos" (100 = completo). Vacio/0/100 = sin ajuste.')
    # Codigos de conceptos afectados, separados por coma.
    x_fnqt_pct_codes = fields.Char(
        string='Conceptos afectados por %',
        help='Codigos de las reglas a las que se aplica el porcentaje '
             '(las que no esten aqui NO se ven afectadas).')

    def action_fnqt_pct_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Aplicar % a conceptos',
            'res_model': 'fnqt.pct.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_payslip_id': self.id},
        }
