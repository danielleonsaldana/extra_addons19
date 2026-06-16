# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    # Horas parciales (para retardos y salidas anticipadas)
    mx_horas_parciales = fields.Float(
        string='Horas de ausencia',
        digits=(5, 2),
        help='Horas que estuvo ausente (para retardos o salidas anticipadas).',
    )

    # Motivo libre (además de la descripción nativa)
    mx_motivo = fields.Char(
        string='Motivo',
        help='Descripción breve del motivo de la falta.',
    )

    # Origen de la falta (manual o importación)
    mx_origen = fields.Selection([
        ('manual',     'Captura manual'),
        ('importacion', 'Importación masiva'),
    ], string='Origen', default='manual', readonly=True)

    # ──────────────────────────────────────────────────────────────────────────
    # Al validar: sincronizar con hr.attendance si el tipo lo requiere
    # ──────────────────────────────────────────────────────────────────────────
    def action_validate(self):
        result = super().action_validate()
        for leave in self.filtered(
            lambda l: l.holiday_status_id.mx_sync_attendance
        ):
            try:
                leave._mx_sync_attendance()
            except Exception as e:
                _logger.warning(
                    'Error sincronizando falta %s con asistencias: %s',
                    leave.id, e,
                )
        return result

    def _mx_sync_attendance(self):
        """
        Crea un registro en hr.attendance que refleja la ausencia del día.
        Solo aplica si el módulo hr_attendance está instalado.
        """
        self.ensure_one()
        if 'hr.attendance' not in self.env:
            return

        AttModel = self.env['hr.attendance']
        emp = self.employee_id
        date_from = self.date_from
        date_to = self.date_to

        # Para faltas de día completo: marcar entrada y salida iguales (0 horas)
        # El reporte de asistencias mostrará el día como ausente
        tz = emp.resource_id.tz or 'America/Mexico_City'

        existing = AttModel.sudo().search([
            ('employee_id', '=', emp.id),
            ('check_in', '>=', datetime.combine(date_from.date(), time.min)
             if hasattr(date_from, 'date') else datetime.combine(date_from, time.min)),
            ('check_in', '<=', datetime.combine(date_from.date(), time.max)
             if hasattr(date_from, 'date') else datetime.combine(date_from, time.max)),
        ], limit=1)

        if not existing:
            check_dt = datetime.combine(
                date_from.date() if hasattr(date_from, 'date') else date_from,
                time(8, 0)
            )
            AttModel.sudo().create({
                'employee_id': emp.id,
                'check_in': check_dt,
                'check_out': check_dt,
                'mx_falta_id': self.id,
            })
            _logger.info(
                'Asistencia creada para falta %s - empleado %s - fecha %s',
                self.id, emp.name, date_from,
            )
