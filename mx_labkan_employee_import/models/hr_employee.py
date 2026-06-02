# -*- coding: utf-8 -*-
import re
import logging
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constantes RFC
# ─────────────────────────────────────────────────────────────────────────────
RFC_PATTERN_PERSONA_FISICA = re.compile(
    r'^[A-ZÑ&]{4}\d{6}[A-Z0-9]{3}$', re.IGNORECASE
)
RFC_PATTERN_PERSONA_MORAL = re.compile(
    r'^[A-ZÑ&]{3}\d{6}[A-Z0-9]{3}$', re.IGNORECASE
)

RFC_PALABRAS_INCONVENIENTES = [
    'BACA','BAKA','BUEI','BUEY','CACA','CACO','CAGA','CAGO','CAKA','CAKO',
    'COGE','COGI','COJA','COJE','COJI','COJO','COLA','CULO','FALO','FETO',
    'GETA','GUEI','GUEY','JETA','JOTO','KACA','KACO','KAGA','KAGO','KAKA',
    'KAKO','KOGE','KOGI','KOJA','KOJE','KOJI','KOJO','KOLA','KULO','LELO',
    'LOCA','LOCO','LOKA','LOKO','MAME','MAMO','MEAR','MEAS','MEON','MIAR',
    'MION','MOCO','MOKO','MULA','MULO','NACA','NACO','PEDA','PEDO','PENE',
    'PIPI','PITO','POPO','PUTA','PUTO','QULO','RATA','ROBA','ROBE','ROBO',
    'RUIN','SENO','TETA','VACA','VAGA','VAGO','VAKA','VUEI','VUEY','WUEI',
    'WUEY',
]


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # ──────────────────────────────────────────────────────────────────────────
    # RFC / CURP propios (Odoo 19 quitó vat de hr.employee)
    # ──────────────────────────────────────────────────────────────────────────
    mx_rfc = fields.Char(
        string='RFC',
        size=13,
        help='Registro Federal de Contribuyentes del empleado.',
    )
    mx_curp = fields.Char(
        string='CURP',
        size=18,
        help='Clave Única de Registro de Población.',
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Campos TEVA adicionales
    # ──────────────────────────────────────────────────────────────────────────
    teva_cliente = fields.Char(string='Cliente TEVA')
    teva_sucursal = fields.Char(string='Sucursal TEVA')
    teva_estatus = fields.Char(string='Estatus TEVA')
    teva_esquema = fields.Char(string='Esquema')
    teva_rp = fields.Char(string='RP')
    teva_contrato = fields.Char(string='Contrato')

    # NSS
    nss = fields.Char(string='NSS (IMSS)', size=11)

    # Datos bancarios
    bank_account_number = fields.Char(string='Número de Cuenta')
    bank_card_number = fields.Char(string='Número de Tarjeta')
    bank_clabe = fields.Char(string='CLABE Interbancaria', size=18)
    bank_name = fields.Char(string='Banco')

    # Créditos
    infonavit_credit = fields.Char(string='Crédito Infonavit')
    infonavit_factor = fields.Char(string='Factor Descuento Infonavit')
    infonavit_pct = fields.Float(string='% Infonavit')
    infonavit_pesos = fields.Float(string='Infonavit en Pesos')
    fonacot_retention = fields.Float(string='Retención Mensual Fonacot')

    # Fechas TEVA
    fecha_antiguedad = fields.Date(string='Fecha de Antigüedad')
    fecha_baja = fields.Date(string='Fecha de Baja')

    # Puesto TEVA
    teva_puesto = fields.Char(string='Puesto (TEVA)')
    teva_descripcion_puesto = fields.Char(string='Descripción de Puesto (TEVA)')

    # ──────────────────────────────────────────────────────────────────────────
    # Salario informativo
    # ──────────────────────────────────────────────────────────────────────────
    salary_monthly = fields.Float(string='Sueldo Mensual', digits=(16, 2))
    salary_biweekly = fields.Float(string='Sueldo Quincenal', digits=(16, 2))
    salary_daily = fields.Float(string='Salario Diario (SD)', digits=(16, 2))

    salary_imss = fields.Float(
        string='Parte IMSS (integrado)',
        digits=(16, 2),
        help='Porción del salario sujeta a cuota IMSS (dato informativo).',
    )
    salary_exempt = fields.Float(
        string='Parte Exenta',
        digits=(16, 2),
        help='Porción exenta de cuota IMSS (vales, fondo ahorro, etc.).',
    )
    salary_total_info = fields.Float(
        string='Salario Total (IMSS + Exento)',
        compute='_compute_salary_total_info',
        store=True,
        digits=(16, 2),
        help='Campo informativo: suma de la parte IMSS y la parte exenta.',
    )

    # ──────────────────────────────────────────────────────────────────────────
    # RFC validación
    # ──────────────────────────────────────────────────────────────────────────
    rfc_validated_format = fields.Boolean(
        string='RFC Formato Válido',
        default=False,
        readonly=True,
    )
    rfc_sat_status = fields.Selection([
        ('not_checked', 'No verificado'),
        ('active', 'Activo en SAT (LCO)'),
        ('not_found', 'No encontrado en SAT'),
        ('error', 'Error al consultar SAT'),
    ], string='Estatus SAT', default='not_checked', readonly=True)

    rfc_sat_checked_date = fields.Datetime(
        string='Última consulta SAT',
        readonly=True,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Multi-empresa
    # ──────────────────────────────────────────────────────────────────────────
    related_employee_ids = fields.Many2many(
        'hr.employee',
        'hr_employee_multicompany_rel',
        'employee_id',
        'related_id',
        string='Empleado en otras empresas',
        domain="[('id', '!=', id)]",
        help='Registros del mismo empleado en otras empresas del grupo.',
    )
    is_multicompany_employee = fields.Boolean(
        string='Empleado multiempresa',
        compute='_compute_is_multicompany',
        store=True,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Computes
    # ──────────────────────────────────────────────────────────────────────────
    @api.depends('salary_imss', 'salary_exempt')
    def _compute_salary_total_info(self):
        for emp in self:
            emp.salary_total_info = (emp.salary_imss or 0.0) + (emp.salary_exempt or 0.0)

    @api.depends('related_employee_ids')
    def _compute_is_multicompany(self):
        for emp in self:
            emp.is_multicompany_employee = bool(emp.related_employee_ids)

    # ──────────────────────────────────────────────────────────────────────────
    # Validación RFC local
    # ──────────────────────────────────────────────────────────────────────────
    @api.model
    def _validate_rfc_format(self, rfc):
        rfc = (rfc or '').strip().upper()
        if not rfc:
            return False, 'RFC vacío'

        if len(rfc) == 13:
            if not RFC_PATTERN_PERSONA_FISICA.match(rfc):
                return False, 'Formato de persona física inválido (LLLL999999XXX)'
            nombre_part = rfc[:4]
            fecha_part = rfc[4:10]
        elif len(rfc) == 12:
            if not RFC_PATTERN_PERSONA_MORAL.match(rfc):
                return False, 'Formato de persona moral inválido (LLL999999XXX)'
            nombre_part = rfc[:3]
            fecha_part = rfc[3:9]
        else:
            return False, f'Longitud incorrecta ({len(rfc)} chars, debe ser 12 o 13)'

        try:
            datetime.strptime(fecha_part, '%y%m%d')
        except ValueError:
            return False, f'Fecha inválida en RFC: {fecha_part}'

        if len(rfc) == 13 and nombre_part in RFC_PALABRAS_INCONVENIENTES:
            return False, f'RFC contiene palabra inconveniente: {nombre_part}'

        return True, ''

    def action_validate_rfc_format(self):
        for emp in self:
            rfc = emp.mx_rfc or ''
            ok, msg = self._validate_rfc_format(rfc)
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
    # Verificación SAT
    # ──────────────────────────────────────────────────────────────────────────
    def action_verify_rfc_sat(self):
        import requests

        for emp in self:
            rfc = (emp.mx_rfc or '').strip().upper()
            if not rfc:
                raise ValidationError(_('El empleado no tiene RFC registrado.'))

            ok, msg = self._validate_rfc_format(rfc)
            if not ok:
                emp.rfc_sat_status = 'error'
                raise ValidationError(_(f'RFC con formato inválido: {msg}'))

            sat_url = 'https://apissat.sat.gob.mx/contribuyentes/v1/estatus'
            headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

            try:
                resp = requests.post(sat_url, json={'rfc': rfc}, headers=headers, timeout=10)
                _logger.info('SAT RFC check [%s]: status=%s body=%s', rfc, resp.status_code, resp.text[:200])

                if resp.status_code == 200:
                    data = resp.json()
                    estatus = data.get('estatus', data.get('activo', '')).lower()
                    emp.rfc_sat_status = 'active' if estatus in ('activo', 'true', '1', 'localizado') else 'not_found'
                elif resp.status_code == 404:
                    emp.rfc_sat_status = 'not_found'
                else:
                    emp.rfc_sat_status = 'error'

            except Exception as e:
                _logger.error('Error consultando SAT: %s', e)
                emp.rfc_sat_status = 'error'

            emp.rfc_sat_checked_date = fields.Datetime.now()
            emp.rfc_validated_format = True

        msg_map = {
            'active': (_('RFC Activo en SAT'), 'success'),
            'not_found': (_('RFC no encontrado en el padrón SAT'), 'warning'),
            'error': (_('Error al consultar el SAT. Verifique conectividad.'), 'danger'),
        }
        status = self[0].rfc_sat_status if self else 'error'
        msg_text, msg_type = msg_map.get(status, (_('Estado desconocido'), 'warning'))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Validación SAT'),
                'message': msg_text,
                'type': msg_type,
                'sticky': False,
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Helper multiempresa
    # ──────────────────────────────────────────────────────────────────────────
    @api.model
    def _link_multicompany_by_rfc(self, rfc):
        if not rfc:
            return
        employees = self.sudo().search([('mx_rfc', '=', rfc)])
        if len(employees) > 1:
            for emp in employees:
                others = employees - emp
                emp.sudo().write({
                    'related_employee_ids': [(4, o.id) for o in others]
                })
            _logger.info('Vinculados %d registros multiempresa para RFC %s', len(employees), rfc)
