# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    # Código corto para identificar el tipo en la importación Excel
    mx_code = fields.Char(
        string='Código MX',
        size=16,
        index=True,
        help='Código corto usado en el archivo de importación (ej: FALT_INJ, RETARDO).',
    )

    # Tipo de descuento en nómina (informativo para la regla salarial)
    mx_deduction_type = fields.Selection([
        ('none',         'Sin descuento'),
        ('full_day',     'Día completo'),
        ('proportional', 'Proporcional a horas'),
    ], string='Descuento en nómina',
        default='none',
        help='Indica cómo afecta esta falta al cálculo de nómina.\n'
             'El módulo de nómina debe tener una regla salarial que lea este campo.',
    )

    # Si requiere capturar horas (retardos, salida anticipada)
    mx_requires_hours = fields.Boolean(
        string='Requiere horas',
        default=False,
        help='Si está activo, la importación exige un valor en la columna "horas".',
    )

    # Sincronía con hr.attendance al aprobar
    mx_sync_attendance = fields.Boolean(
        string='Sincronizar con Asistencias',
        default=False,
        help='Al validar la falta, crea o ajusta el registro de hr.attendance del día.',
    )
