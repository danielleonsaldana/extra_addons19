# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CheckidLog(models.Model):
    _name = 'mx.checkid.log'
    _description = 'Historial de Consultas CheckId'
    _order = 'create_date desc'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        ondelete='cascade',
        required=True,
        index=True,
    )
    termino_busqueda = fields.Char(
        string='Término Buscado',
        readonly=True,
    )
    tipo_busqueda = fields.Selection(
        selection=[('rfc', 'RFC'), ('curp', 'CURP')],
        string='Tipo',
        readonly=True,
    )
    exitoso = fields.Boolean(
        string='Exitoso',
        readonly=True,
    )
    codigo_error = fields.Char(
        string='Código Error',
        readonly=True,
    )
    descripcion_error = fields.Char(
        string='Descripción Error',
        readonly=True,
    )
    create_date = fields.Datetime(
        string='Fecha Consulta',
        readonly=True,
    )
    solicitudes_restantes = fields.Integer(
        string='Solicitudes Restantes',
        readonly=True,
        default=0,
    )
    # Resumen de datos obtenidos
    datos_obtenidos = fields.Text(
        string='Resumen de Datos Obtenidos',
        readonly=True,
    )
    con_problema_69 = fields.Boolean(
        string='Problema 69/69B',
        readonly=True,
    )
    estado_efos = fields.Text(
        string='Detalle EFOS',
        readonly=True,
    )
