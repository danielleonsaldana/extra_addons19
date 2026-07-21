# -*- coding: utf-8 -*-
from odoo import models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def action_print_document(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Imprimir Documento'),
            'res_model': 'hr.document.print.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_employee_id': self.id},
        }
