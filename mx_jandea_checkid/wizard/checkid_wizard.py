# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from ..models.hr_employee import _detectar_tipo


class CheckidWizard(models.TransientModel):
    _name = 'mx.checkid.wizard'
    _description = 'Consulta Manual CheckId'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        readonly=True,
    )
    termino_busqueda = fields.Char(
        string='RFC o CURP a consultar',
        required=True,
        help='Ingrese el RFC (12-13 caracteres) o CURP (18 caracteres) del empleado.',
    )
    tipo_detectado = fields.Char(
        string='Tipo detectado',
        compute='_compute_tipo_detectado',
    )

    @api.depends('termino_busqueda')
    def _compute_tipo_detectado(self):
        for rec in self:
            t = _detectar_tipo(rec.termino_busqueda or '')
            if t == 'rfc':
                rec.tipo_detectado = '✓ RFC válido'
            elif t == 'curp':
                rec.tipo_detectado = '✓ CURP válida'
            else:
                rec.tipo_detectado = '✗ No reconocido' if rec.termino_busqueda else ''

    def action_consultar(self):
        self.ensure_one()
        termino = (self.termino_busqueda or '').strip().upper()
        tipo = _detectar_tipo(termino)
        if not tipo:
            raise UserError(
                _('El término "%s" no es un RFC ni una CURP válida.') % termino
            )
        self.employee_id._ejecutar_consulta_checkid(termino)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('CheckId'),
                'message': _('Consulta realizada para %s. Revisa la pestaña CheckId.')
                           % self.employee_id.name,
                'type': 'success',
                'sticky': False,
            },
        }
