# -*- coding: utf-8 -*-
"""
mx_jandea_employee_import / models / hr_employee.py

Extiende hr.employee con los campos mínimos necesarios para México
que NO existen de forma nativa en Odoo 17:
  - mx_rfc     → RFC del empleado
  - mx_curp    → CURP del empleado
  - nss        → NSS (número de seguridad social IMSS)
  - rfc_validated_format → bandera de validación local de RFC

Todo lo demás (género, estado civil, fecha de nacimiento, domicilio,
correo, puesto, departamento, salario, fecha de inicio de contrato, etc.)
se escribe directamente en campos nativos de hr.employee / hr.version.
"""
import re
import logging
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Patrones de RFC (SAT)
# ─────────────────────────────────────────────────────────────────────────────
RFC_PERSONA_FISICA = re.compile(r'^[A-ZÑ&]{4}\d{6}[A-Z0-9]{3}$', re.IGNORECASE)
RFC_PERSONA_MORAL = re.compile(r'^[A-ZÑ&]{3}\d{6}[A-Z0-9]{3}$', re.IGNORECASE)

RFC_PALABRAS_INCONVENIENTES = {
    'BACA','BAKA','BUEI','BUEY','CACA','CACO','CAGA','CAGO','CAKA','CAKO',
    'COGE','COGI','COJA','COJE','COJI','COJO','COLA','CULO','FALO','FETO',
    'GETA','GUEI','GUEY','JETA','JOTO','KACA','KACO','KAGA','KAGO','KAKA',
    'KAKO','KOGE','KOGI','KOJA','KOJE','KOJI','KOJO','KOLA','KULO','LELO',
    'LOCA','LOCO','LOKA','LOKO','MAME','MAMO','MEAR','MEAS','MEON','MIAR',
    'MION','MOCO','MOKO','MULA','MULO','NACA','NACO','PEDA','PEDO','PENE',
    'PIPI','PITO','POPO','PUTA','PUTO','QULO','RATA','ROBA','ROBE','ROBO',
    'RUIN','SENO','TETA','VACA','VAGA','VAGO','VAKA','VUEI','VUEY','WUEI',
    'WUEY',
}


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # ──────────────────────────────────────────────────────────────────────────
    # Campos fiscales MX (no existen de forma nativa en Odoo 17)
    # ──────────────────────────────────────────────────────────────────────────
    mx_rfc = fields.Char(
        string='RFC',
        size=13,
        tracking=True,
        groups='hr.group_hr_user',
        help='Registro Federal de Contribuyentes.',
    )
    mx_curp = fields.Char(
        string='CURP',
        size=18,
        tracking=True,
        groups='hr.group_hr_user',
        help='Clave Única de Registro de Población.',
    )
    nss = fields.Char(
        string='NSS (IMSS)',
        size=11,
        tracking=True,
        groups='hr.group_hr_user',
        help='Número de Seguridad Social IMSS.',
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Validación RFC
    # ──────────────────────────────────────────────────────────────────────────
    rfc_validated_format = fields.Boolean(
        string='RFC Formato Válido',
        default=False,
        readonly=True,
        groups='hr.group_hr_user',
        help='Indica si el RFC pasó la validación de formato local (SAT).',
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Multi-empresa: vínculos entre registros del mismo empleado
    # ──────────────────────────────────────────────────────────────────────────
    related_employee_ids = fields.Many2many(
        'hr.employee',
        'hr_employee_jandea_multicompany_rel',
        'employee_id',
        'related_id',
        string='Empleado en otras empresas',
        domain="[('id', '!=', id)]",
        groups='hr.group_hr_user',
        help='Registros del mismo empleado en otras empresas del grupo.',
    )
    is_multicompany_employee = fields.Boolean(
        string='Empleado multiempresa',
        compute='_compute_is_multicompany',
        store=True,
        groups='hr.group_hr_user',
    )

    @api.depends('related_employee_ids')
    def _compute_is_multicompany(self):
        for emp in self:
            emp.is_multicompany_employee = bool(emp.related_employee_ids)

    # ──────────────────────────────────────────────────────────────────────────
    # Lógica de validación RFC
    # ──────────────────────────────────────────────────────────────────────────
    @api.model
    def _validate_rfc_format(self, rfc):
        """
        Valida el formato del RFC contra los patrones del SAT.
        Retorna (bool, str): (es_válido, mensaje_de_error).
        """
        rfc = (rfc or '').strip().upper()
        if not rfc:
            return False, _('RFC vacío.')

        if len(rfc) == 13:
            if not RFC_PERSONA_FISICA.match(rfc):
                return False, _('Formato inválido para persona física (debe ser LLLL999999XXX).')
            nombre_part = rfc[:4]
            fecha_part = rfc[4:10]
        elif len(rfc) == 12:
            if not RFC_PERSONA_MORAL.match(rfc):
                return False, _('Formato inválido para persona moral (debe ser LLL999999XXX).')
            nombre_part = rfc[:3]
            fecha_part = rfc[3:9]
        else:
            return False, _(f'Longitud incorrecta: {len(rfc)} caracteres (debe ser 12 o 13).')

        try:
            datetime.strptime(fecha_part, '%y%m%d')
        except ValueError:
            return False, _(f'Fecha inválida en RFC: {fecha_part}.')

        if len(rfc) == 13 and nombre_part in RFC_PALABRAS_INCONVENIENTES:
            return False, _(f'RFC contiene palabra inconveniente: {nombre_part}.')

        return True, ''

    def action_validate_rfc_format(self):
        """Botón en el formulario del empleado para validar el RFC localmente."""
        for emp in self:
            ok, msg = self._validate_rfc_format(emp.mx_rfc)
            emp.rfc_validated_format = ok
            if not ok:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('RFC inválido'),
                        'message': msg,
                        'type': 'warning',
                        'sticky': False,
                    },
                }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('RFC válido'),
                'message': _('El formato del RFC es correcto.'),
                'type': 'success',
                'sticky': False,
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Helper multi-empresa
    # ──────────────────────────────────────────────────────────────────────────
    @api.model
    def _link_multicompany_by_rfc(self, rfc):
        """
        Busca todos los registros hr.employee con el mismo RFC y los
        vincula entre sí en el campo related_employee_ids.
        Se llama después de crear/actualizar empleados en la importación.
        """
        if not rfc:
            return
        employees = self.sudo().search([('mx_rfc', '=', rfc)])
        if len(employees) > 1:
            for emp in employees:
                others = employees - emp
                emp.sudo().write({
                    'related_employee_ids': [(4, o.id) for o in others]
                })
            _logger.info(
                'Multi-empresa: vinculados %d registros para RFC %s',
                len(employees), rfc,
            )
