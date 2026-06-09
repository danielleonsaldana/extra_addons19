# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    checkid_api_key = fields.Char(
        string='API Key CheckId',
        config_parameter='mx_jandea_checkid.api_key',
        help='API Key obtenida en https://www.checkid.mx/App/ControlApi',
    )
    checkid_auto_query = fields.Boolean(
        string='Consulta automática al guardar',
        config_parameter='mx_jandea_checkid.auto_query',
        default=True,
        help='Si está activo, se consultará CheckId automáticamente al crear '
             'o modificar el RFC/CURP de un empleado.',
    )
    checkid_obtain_rfc = fields.Boolean(
        string='Obtener RFC',
        config_parameter='mx_jandea_checkid.obtain_rfc',
        default=True,
    )
    checkid_obtain_curp = fields.Boolean(
        string='Obtener CURP',
        config_parameter='mx_jandea_checkid.obtain_curp',
        default=True,
    )
    checkid_obtain_nss = fields.Boolean(
        string='Obtener NSS',
        config_parameter='mx_jandea_checkid.obtain_nss',
        default=True,
    )
    checkid_obtain_regimen = fields.Boolean(
        string='Obtener Régimen Fiscal',
        config_parameter='mx_jandea_checkid.obtain_regimen',
        default=True,
    )
    checkid_obtain_cp = fields.Boolean(
        string='Obtener CP Fiscal',
        config_parameter='mx_jandea_checkid.obtain_cp',
        default=True,
    )
    checkid_obtain_69 = fields.Boolean(
        string='Verificar Estado 69/69B (EFOS)',
        config_parameter='mx_jandea_checkid.obtain_69',
        default=True,
    )
