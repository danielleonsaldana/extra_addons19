# -*- coding: utf-8 -*-
import json
import logging
import re
import urllib.request
import urllib.error

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

CHECKID_BASE_URL = 'https://www.checkid.mx/api/'
CHECKID_BUSQUEDA_URL = CHECKID_BASE_URL + 'Busqueda'
CHECKID_SOLICITUDES_URL = CHECKID_BASE_URL + 'SolicitudesRestantes'

RFC_REGEX = re.compile(
    r'^([A-ZÑ&]{3,4})(\d{6})([A-Z\d]{3})$', re.IGNORECASE
)
CURP_REGEX = re.compile(
    r'^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z\d]\d$', re.IGNORECASE
)


def _detectar_tipo(termino):
    """Detecta si el término es RFC o CURP. Retorna 'rfc', 'curp' o None."""
    t = (termino or '').strip().upper()
    if CURP_REGEX.match(t):
        return 'curp'
    if RFC_REGEX.match(t):
        return 'rfc'
    return None


def _post_json(url, payload, timeout=15):
    """Realiza un POST JSON usando urllib (sin dependencias externas)."""
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8')), None
    except urllib.error.HTTPError as e:
        return None, f'HTTP {e.code}: {e.reason}'
    except urllib.error.URLError as e:
        return None, f'URLError: {e.reason}'
    except Exception as e:
        return None, str(e)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # ─── Campos CheckId ────────────────────────────────────────────────────
    checkid_curp = fields.Char(
        string='CURP (CheckId)',
        tracking=True,
        groups='hr.group_hr_user',
    )
    checkid_fecha_nacimiento = fields.Date(
        string='Fecha Nacimiento (CheckId)',
        groups='hr.group_hr_user',
    )
    checkid_nombres = fields.Char(
        string='Nombres (CheckId)',
        groups='hr.group_hr_user',
    )
    checkid_primer_apellido = fields.Char(
        string='Primer Apellido (CheckId)',
        groups='hr.group_hr_user',
    )
    checkid_segundo_apellido = fields.Char(
        string='Segundo Apellido (CheckId)',
        groups='hr.group_hr_user',
    )
    checkid_sexo = fields.Char(
        string='Sexo (CheckId)',
        groups='hr.group_hr_user',
    )
    checkid_nacionalidad = fields.Char(
        string='Nacionalidad (CheckId)',
        groups='hr.group_hr_user',
    )
    checkid_entidad = fields.Char(
        string='Entidad Nacimiento (CheckId)',
        groups='hr.group_hr_user',
    )
    checkid_municipio_registro = fields.Char(
        string='Municipio Registro (CheckId)',
        groups='hr.group_hr_user',
    )
    checkid_razon_social = fields.Char(
        string='Razón Social SAT (CheckId)',
        groups='hr.group_hr_user',
    )
    checkid_rfc_valido = fields.Boolean(
        string='RFC Válido (CheckId)',
        default=False,
        groups='hr.group_hr_user',
    )
    checkid_rfc_valido_hasta = fields.Date(
        string='RFC Válido Hasta (CheckId)',
        groups='hr.group_hr_user',
    )
    checkid_email_contacto = fields.Char(
        string='Email Contacto SAT (CheckId)',
        groups='hr.group_hr_user',
    )
    checkid_nss = fields.Char(
        string='NSS (CheckId)',
        tracking=True,
        groups='hr.group_hr_user',
    )
    checkid_regimen_fiscal = fields.Char(
        string='Régimen Fiscal (CheckId)',
        groups='hr.group_hr_user',
    )
    checkid_cp_fiscal = fields.Char(
        string='CP Fiscal (CheckId)',
        groups='hr.group_hr_user',
    )
    checkid_con_problema_69 = fields.Boolean(
        string='Problema 69/69B',
        default=False,
        groups='hr.group_hr_user',
        help='Indica si el contribuyente aparece en el listado 69 o 69B del SAT (EFOS/EDOS).',
    )
    checkid_situacion_contribuyente = fields.Char(
        string='Situación Contribuyente (CheckId)',
        groups='hr.group_hr_user',
    )
    checkid_detalle_efos = fields.Text(
        string='Detalle EFOS (CheckId)',
        groups='hr.group_hr_user',
    )
    checkid_ultima_consulta = fields.Datetime(
        string='Última Consulta CheckId',
        readonly=True,
        groups='hr.group_hr_user',
    )
    checkid_estado_consulta = fields.Selection(
        selection=[
            ('sin_consulta', 'Sin consultar'),
            ('ok', 'Consulta exitosa'),
            ('advertencia', 'Con advertencia 69/69B'),
            ('error', 'Error en consulta'),
        ],
        string='Estado CheckId',
        default='sin_consulta',
        readonly=True,
        groups='hr.group_hr_user',
    )
    checkid_log_ids = fields.One2many(
        'mx.checkid.log',
        'employee_id',
        string='Historial CheckId',
        readonly=True,
    )
    checkid_log_count = fields.Integer(
        string='Consultas',
        compute='_compute_checkid_log_count',
    )

    # ─── Campos de trigger (internos) ──────────────────────────────────────
    checkid_rfc_trigger = fields.Char(
        string='RFC para consulta',
        compute='_compute_trigger_fields',
        store=False,
    )

    # ─── Computes ──────────────────────────────────────────────────────────
    @api.depends('checkid_log_ids')
    def _compute_checkid_log_count(self):
        for rec in self:
            rec.checkid_log_count = len(rec.checkid_log_ids)

    @api.depends('ssnid')
    def _compute_trigger_fields(self):
        """Placeholder — el trigger real es por write/create."""
        for rec in self:
            rec.checkid_rfc_trigger = ''

    # ─── ORM Overrides ─────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        auto = self._get_param_bool('mx_jandea_checkid.auto_query', True)
        if auto:
            for rec in records:
                termino = rec._get_termino_busqueda()
                if termino:
                    try:
                        rec._ejecutar_consulta_checkid(termino)
                    except Exception as e:
                        _logger.warning('CheckId create error: %s', e)
        return records

    def write(self, vals):
        # Detectar si cambian campos relevantes
        campos_trigger = {'ssnid', 'l10n_mx_edi_curp', 'barcode'}
        trigger = bool(campos_trigger & set(vals.keys()))
        result = super().write(vals)
        auto = self._get_param_bool('mx_jandea_checkid.auto_query', True)
        if auto and trigger:
            for rec in self:
                termino = rec._get_termino_busqueda()
                if termino:
                    try:
                        rec._ejecutar_consulta_checkid(termino)
                    except Exception as e:
                        _logger.warning('CheckId write error: %s', e)
        return result

    # ─── Acciones de botón ─────────────────────────────────────────────────
    def action_checkid_consultar(self):
        """Botón manual: abre wizard si no hay término, o consulta directo."""
        self.ensure_one()
        termino = self._get_termino_busqueda()
        if not termino:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Consultar CheckId'),
                'res_model': 'mx.checkid.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_employee_id': self.id},
            }
        self._ejecutar_consulta_checkid(termino)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('CheckId'),
                'message': _('Consulta realizada. Revisa la pestaña CheckId.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_checkid_ver_log(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Historial CheckId - %s') % self.name,
            'res_model': 'mx.checkid.log',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def action_checkid_solicitudes(self):
        """Consulta cuántas solicitudes quedan en la cuenta."""
        self.ensure_one()
        api_key = self._get_api_key()
        payload = {'ApiKey': api_key}
        resp, err = _post_json(CHECKID_SOLICITUDES_URL, payload)
        if err:
            raise UserError(_('Error de conexión CheckId: %s') % err)
        if not resp.get('exitoso'):
            raise UserError(
                _('Error CheckId [%s]: %s') % (
                    resp.get('codigoError'), resp.get('error')
                )
            )
        restantes = resp.get('resultado', 0)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Solicitudes CheckId restantes'),
                'message': _('Su cuenta tiene %d solicitudes disponibles.') % restantes,
                'type': 'info',
                'sticky': True,
            },
        }

    # ─── Lógica principal de consulta ──────────────────────────────────────
    def _get_termino_busqueda(self):
        """Obtiene el término más adecuado para buscar: CURP > RFC."""
        self.ensure_one()
        # CURP desde campo mexicano estándar
        curp = getattr(self, 'l10n_mx_edi_curp', None) or ''
        if curp and _detectar_tipo(curp) == 'curp':
            return curp.strip().upper()
        # RFC desde campo ssnid (usado en localización MX) o vat en partner
        rfc = getattr(self, 'ssnid', None) or ''
        if rfc and _detectar_tipo(rfc) == 'rfc':
            return rfc.strip().upper()
        # Intentar desde el partner vinculado
        if self.address_home_id and self.address_home_id.vat:
            vat = self.address_home_id.vat.strip().upper()
            if _detectar_tipo(vat) in ('rfc', 'curp'):
                return vat
        return ''

    def _get_api_key(self):
        api_key = self.env['ir.config_parameter'].sudo().get_param(
            'mx_jandea_checkid.api_key', ''
        )
        if not api_key:
            raise UserError(
                _('No se ha configurado la API Key de CheckId. '
                  'Ve a Configuración → CheckId.')
            )
        return api_key

    def _get_param_bool(self, key, default=False):
        val = self.env['ir.config_parameter'].sudo().get_param(key, str(default))
        return str(val).lower() in ('true', '1', 'yes')

    def _ejecutar_consulta_checkid(self, termino):
        """
        Realiza la consulta a la API CheckId y almacena los resultados
        en los campos del empleado, registrando el log.
        """
        self.ensure_one()
        api_key = self._get_api_key()
        tipo = _detectar_tipo(termino)

        if not tipo:
            _logger.info('CheckId: término "%s" no reconocido como RFC ni CURP', termino)
            return

        # Configuración de campos a obtener
        def pb(key, default=True):
            return self._get_param_bool(key, default)

        payload = {
            'ApiKey': api_key,
            'TerminoBusqueda': termino,
            'ObtenerRFC': pb('mx_jandea_checkid.obtain_rfc'),
            'ObtenerCURP': pb('mx_jandea_checkid.obtain_curp'),
            'ObtenerNSS': pb('mx_jandea_checkid.obtain_nss'),
            'ObtenerRegimenFiscal': pb('mx_jandea_checkid.obtain_regimen'),
            'ObtenerCP': pb('mx_jandea_checkid.obtain_cp'),
            'Obtener69o69B': pb('mx_jandea_checkid.obtain_69'),
        }

        _logger.info('CheckId: consultando "%s" para empleado %s', termino, self.name)
        resp, err = _post_json(CHECKID_BUSQUEDA_URL, payload)

        # ── Error de red ──
        if err:
            self._registrar_log(
                termino=termino,
                tipo=tipo,
                exitoso=False,
                codigo_error='NET',
                descripcion_error=err,
            )
            self.sudo().write({'checkid_estado_consulta': 'error'})
            _logger.error('CheckId red error: %s', err)
            return

        # ── Error de API ──
        if not resp.get('exitoso'):
            codigo = resp.get('codigoError', '?')
            desc = resp.get('error', '')
            self._registrar_log(
                termino=termino,
                tipo=tipo,
                exitoso=False,
                codigo_error=codigo,
                descripcion_error=desc,
            )
            self.sudo().write({'checkid_estado_consulta': 'error'})
            _logger.warning('CheckId API error [%s]: %s', codigo, desc)
            return

        # ── Procesar resultado ──
        resultado = resp.get('resultado', {})
        vals = {'checkid_ultima_consulta': fields.Datetime.now()}
        resumen = []

        # RFC
        rfc_data = resultado.get('rfc')
        if rfc_data and rfc_data.get('exitoso'):
            vals['checkid_razon_social'] = rfc_data.get('razonSocial', '')
            vals['checkid_rfc_valido'] = rfc_data.get('valido', False)
            vals['checkid_email_contacto'] = rfc_data.get('emailContacto', '')
            vh = rfc_data.get('validoHasta')
            if vh:
                vals['checkid_rfc_valido_hasta'] = vh[:10]
            resumen.append('RFC: %s (%s)' % (
                rfc_data.get('rfc', ''),
                'Válido' if rfc_data.get('valido') else 'Inválido'
            ))

        # CURP
        curp_data = resultado.get('curp')
        if curp_data and curp_data.get('exitoso'):
            vals['checkid_curp'] = curp_data.get('curp', '')
            vals['checkid_nombres'] = curp_data.get('nombres', '')
            vals['checkid_primer_apellido'] = curp_data.get('primerApellido', '')
            vals['checkid_segundo_apellido'] = curp_data.get('segundoApellido', '')
            vals['checkid_sexo'] = curp_data.get('sexo', '')
            vals['checkid_nacionalidad'] = curp_data.get('nacionalidad', '')
            vals['checkid_entidad'] = curp_data.get('entidad', '')
            vals['checkid_municipio_registro'] = curp_data.get('municipioRegistro', '')
            fn = curp_data.get('fechaNacimiento')
            if fn:
                vals['checkid_fecha_nacimiento'] = fn[:10]
            resumen.append('CURP: %s' % curp_data.get('curp', ''))

        # NSS
        nss_data = resultado.get('nss')
        if nss_data and nss_data.get('exitoso'):
            vals['checkid_nss'] = nss_data.get('nss', '')
            resumen.append('NSS: %s' % nss_data.get('nss', ''))

        # Régimen Fiscal
        reg_data = resultado.get('regimenFiscal')
        if reg_data and reg_data.get('exitoso'):
            vals['checkid_regimen_fiscal'] = reg_data.get('regimenesFiscales', '')
            resumen.append('Régimen: %s' % reg_data.get('regimenesFiscales', ''))

        # CP Fiscal
        cp_data = resultado.get('codigoPostal')
        if cp_data and cp_data.get('exitoso'):
            vals['checkid_cp_fiscal'] = cp_data.get('codigoPostal', '')
            resumen.append('CP: %s' % cp_data.get('codigoPostal', ''))

        # Estado 69/69B
        estado69 = resultado.get('estado69o69B')
        con_problema = False
        detalle_efos = ''
        if estado69 and estado69.get('exitoso'):
            con_problema = estado69.get('conProblema', False)
            vals['checkid_con_problema_69'] = con_problema
            if con_problema:
                detalles = estado69.get('detalles', {})
                vals['checkid_situacion_contribuyente'] = detalles.get(
                    'situacionContribuyente', ''
                )
                problemas = detalles.get('problemas', [])
                oficios = detalles.get('oficiosEFOS', [])
                lineas = []
                for p in problemas:
                    lineas.append('• Problema: %s (Pub: %s)' % (
                        p.get('descripcion', ''),
                        (p.get('fechaPublicacion') or '')[:10],
                    ))
                for o in oficios:
                    lineas.append('• Oficio %s [%s] SAT: %s DOF: %s' % (
                        o.get('oficioID', ''),
                        o.get('tipo', ''),
                        (o.get('fechaPublicacionSAT') or '')[:10],
                        (o.get('fechaPublicacionDOF') or '')[:10],
                    ))
                detalle_efos = '\n'.join(lineas)
                vals['checkid_detalle_efos'] = detalle_efos
                resumen.append('⚠️ PROBLEMA 69/69B: %s' % detalles.get('situacionContribuyente'))
            else:
                vals['checkid_detalle_efos'] = ''
                vals['checkid_situacion_contribuyente'] = ''
                resumen.append('69/69B: Sin problemas')

        # Estado general
        if con_problema:
            vals['checkid_estado_consulta'] = 'advertencia'
        else:
            vals['checkid_estado_consulta'] = 'ok'

        self.sudo().write(vals)

        # Registrar log
        self._registrar_log(
            termino=termino,
            tipo=tipo,
            exitoso=True,
            datos_obtenidos='\n'.join(resumen),
            con_problema_69=con_problema,
            estado_efos=detalle_efos,
        )

        _logger.info('CheckId: consulta exitosa para %s | %s', self.name, termino)

    def _registrar_log(self, termino, tipo, exitoso, codigo_error=None,
                       descripcion_error=None, datos_obtenidos=None,
                       con_problema_69=False, estado_efos='',
                       solicitudes_restantes=0):
        self.env['mx.checkid.log'].sudo().create({
            'employee_id': self.id,
            'termino_busqueda': termino,
            'tipo_busqueda': tipo,
            'exitoso': exitoso,
            'codigo_error': codigo_error,
            'descripcion_error': descripcion_error,
            'datos_obtenidos': datos_obtenidos,
            'con_problema_69': con_problema_69,
            'estado_efos': estado_efos,
            'solicitudes_restantes': solicitudes_restantes,
        })
