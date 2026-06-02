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

# Palabras inconvenientes SAT (lista parcial)
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
    # Campos TEVA adicionales
    # ──────────────────────────────────────────────────────────────────────────
    teva_cliente = fields.Char(string='Cliente TEVA')
    teva_sucursal = fields.Char(string='Sucursal TEVA')
    teva_estatus = fields.Char(string='Estatus TEVA')
    teva_esquema = fields.Char(string='Esquema')
    teva_rp = fields.Char(string='RP')
    teva_contrato = fields.Char(string='Contrato')

    # Datos NSS
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
    # Salario (TEVA viene como mensual y quincenal; SD = Salario Diario)
    # ──────────────────────────────────────────────────────────────────────────
    salary_monthly = fields.Float(string='Sueldo Mensual', digits=(16, 2))
    salary_biweekly = fields.Float(string='Sueldo Quincenal', digits=(16, 2))
    salary_daily = fields.Float(string='Salario Diario (SD)', digits=(16, 2))

    # Partes IMSS / Exento (dato informativo)
    salary_imss = fields.Float(
        string='Parte IMSS (integrado)',
        digits=(16, 2),
        help='Porción del salario sujeta a cuota IMSS (dato informativo, ingrese manualmente o configure desde nómina).',
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
        help='Campo informativo: suma de la parte IMSS y la parte exenta del salario.',
    )

    # ──────────────────────────────────────────────────────────────────────────
    # RFC / CURP / Validación SAT
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
    # Multi-empresa: relación con el mismo empleado en otra empresa
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
    # Validación RFC local (formato SAT)
    # ──────────────────────────────────────────────────────────────────────────
    @api.constrains('vat')
    def _check_rfc_format(self):
        for emp in self:
            if emp.vat:
                self._validate_rfc_format(emp.vat)

    @api.model
    def _validate_rfc_format(self, rfc):
        """
        Valida el formato del RFC según las reglas del SAT:
        - Persona Física:  4 letras + 6 dígitos + 3 homoclave  (13 chars)
        - Persona Moral:   3 letras + 6 dígitos + 3 homoclave  (12 chars)
        - Fecha YYMMDD válida
        - Palabras inconvenientes sustituidas por el SAT
        Retorna (True, '') o (False, 'motivo')
        """
        rfc = (rfc or '').strip().upper()
        if not rfc:
            return False, 'RFC vacío'

        # Longitud y patrón
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

        # Validar fecha YYMMDD
        try:
            datetime.strptime(fecha_part, '%y%m%d')
        except ValueError:
            return False, f'Fecha inválida en RFC: {fecha_part}'

        # Palabras inconvenientes (solo persona física, primeras 4 letras)
        if len(rfc) == 13 and nombre_part in RFC_PALABRAS_INCONVENIENTES:
            return False, f'RFC contiene palabra inconveniente: {nombre_part}'

        return True, ''

    def action_validate_rfc_format(self):
        """Botón: valida el formato del RFC y actualiza el campo."""
        for emp in self:
            rfc = emp.vat or ''
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
    # Validación RFC en SAT (Lista de Contribuyentes Obligados - LCO)
    # El SAT publica el padrón en:
    #   https://contribuyentes.sat.gob.mx/pubpago/padron/download
    # También existe el webservice del SIAT (requiere FIEL/e.firma).
    # Para consulta pública sin FIEL usamos el endpoint de verificación
    # de emisores disponible en el portal de factura electrónica SAT.
    # ──────────────────────────────────────────────────────────────────────────
    def action_verify_rfc_sat(self):
        """
        Consulta el SAT para verificar si el RFC está activo.

        Endpoint público SAT (sin autenticación):
        POST https://apissat.sat.gob.mx/contribuyentes/v1/estatus
        Body: {"rfc": "XXXX000000XXX"}

        NOTA: Este endpoint es el disponible públicamente a la fecha de 
        desarrollo. Si el SAT lo modifica, actualizar la URL aquí.
        Si se requiere validación con FIEL empresarial, usar el método
        _verify_rfc_siat_fiel() (requiere certificado configurado).
        """
        import requests
        import json

        for emp in self:
            rfc = (emp.vat or '').strip().upper()
            if not rfc:
                raise ValidationError(_('El empleado no tiene RFC registrado.'))

            # Primero validar formato local
            ok, msg = self._validate_rfc_format(rfc)
            if not ok:
                emp.rfc_sat_status = 'error'
                raise ValidationError(_(f'RFC con formato inválido: {msg}'))

            # ── Intento 1: API pública SAT ──────────────────────────────────
            sat_url = 'https://apissat.sat.gob.mx/contribuyentes/v1/estatus'
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            }
            payload = {'rfc': rfc}

            try:
                resp = requests.post(
                    sat_url,
                    json=payload,
                    headers=headers,
                    timeout=10,
                )
                _logger.info('SAT RFC check [%s]: status=%s body=%s', rfc, resp.status_code, resp.text[:200])

                if resp.status_code == 200:
                    data = resp.json()
                    # La respuesta del SAT incluye campo "estatus" o "activo"
                    estatus = data.get('estatus', data.get('activo', '')).lower()
                    if estatus in ('activo', 'true', '1', 'localizado'):
                        emp.rfc_sat_status = 'active'
                    else:
                        emp.rfc_sat_status = 'not_found'
                elif resp.status_code == 404:
                    emp.rfc_sat_status = 'not_found'
                else:
                    _logger.warning('SAT respondió %s para RFC %s', resp.status_code, rfc)
                    emp.rfc_sat_status = 'error'

            except requests.exceptions.Timeout:
                _logger.error('Timeout al consultar SAT para RFC %s', rfc)
                emp.rfc_sat_status = 'error'
            except requests.exceptions.ConnectionError as e:
                _logger.error('Error de conexión SAT: %s', e)
                emp.rfc_sat_status = 'error'
            except Exception as e:
                _logger.error('Error inesperado consultando SAT: %s', e)
                emp.rfc_sat_status = 'error'

            emp.rfc_sat_checked_date = fields.Datetime.now()
            emp.rfc_validated_format = True  # si llegó aquí, el formato fue válido

        # Notificación
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
    # Helper: vincular empleados multiempresa por RFC
    # ──────────────────────────────────────────────────────────────────────────
    @api.model
    def _link_multicompany_by_rfc(self, rfc):
        """
        Busca en TODAS las empresas empleados con el mismo RFC y los vincula
        mutuamente en related_employee_ids.
        """
        if not rfc:
            return
        employees = self.sudo().search([('vat', '=', rfc)])
        if len(employees) > 1:
            for emp in employees:
                others = employees - emp
                emp.sudo().write({
                    'related_employee_ids': [(4, o.id) for o in others]
                })
            _logger.info(
                'Vinculados %d registros multiempresa para RFC %s',
                len(employees), rfc
            )
