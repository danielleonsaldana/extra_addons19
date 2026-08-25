# -*- coding: utf-8 -*-
"""
mx_jandea_employee_import / wizard / employee_import_wizard.py

Wizard de importación masiva de empleados.

Cambios respecto a la versión anterior
──────────────────────────────────────
1. Mapeo por NOMBRE de columna (no por índice fijo): el orden de las
   columnas del archivo ya no importa; se reconoce por encabezado.
2. Paso de VISTA PREVIA: [Previsualizar] parsea el archivo y muestra en
   tabla cómo caería cada dato en los campos de Odoo, SIN escribir en la
   base. Desde ahí se confirma con [Importar].
3. Cuenta bancaria: Banco / Cuenta / CLABE ahora sí se cargan como
   res.partner.bank del empleado (BUG corregido).
4. Salario: una sola "Periodicidad" + "Monto por Periodo" → schedule_pay
   + wage del contrato (el wage es el importe DEL PERIODO, como lo lee
   mx_jandea_reglas_mx).
5. "Categoría de pago" → hr.payroll.structure.type del contrato.
6. "Fecha de Ingreso" calcula el inicio del contrato/versión. Se eliminó
   por completo la "Fecha de Antigüedad".
7. El contrato/versión se rellena automáticamente al crear al empleado.

Flujo:
  Configuración → [Previsualizar] → Vista previa → [Importar] → Resultados
  (y, si está instalado mx_jandea_checkid, validación CheckId de los
   seleccionados).
"""
import base64
import io
import logging
import unicodedata
from datetime import datetime, date

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Normalización de encabezados y mapeo por nombre de columna
# ─────────────────────────────────────────────────────────────────────────────
def _norm(text):
    """minúsculas, sin acentos, sin signos, espacios colapsados."""
    if text is None:
        return ''
    s = str(text).strip().lower()
    s = ''.join(
        c for c in unicodedata.normalize('NFKD', s)
        if not unicodedata.combining(c)
    )
    out = []
    for ch in s:
        out.append(ch if ch.isalnum() else ' ')
    return ' '.join(''.join(out).split())


# canonical_key -> lista de encabezados aceptados (ya normalizados por _norm)
HEADER_ALIASES = {
    'apellido_pat':   ['apellido paterno', 'app', 'ap paterno'],
    'apellido_mat':   ['apellido materno', 'apm', 'ap materno'],
    'nombre':         ['nombres', 'nombre s', 'nombre', 'primer nombre'],
    'rfc':            ['rfc'],
    'curp':           ['curp'],
    'nss':            ['nss', 'nss imss', 'numero de seguridad social', 'seguro social'],
    'fecha_nac':      ['fecha de nacimiento', 'fecha nacimiento', 'f nac', 'nacimiento'],
    'genero':         ['genero', 'sexo'],
    'estado_civil':   ['estado civil'],
    'nacionalidad':   ['nacionalidad'],
    'correo':         ['correo', 'email', 'correo electronico', 'e mail'],
    'calle':          ['calle'],
    'num_ext':        ['numero exterior', 'num ext', 'no ext', 'no exterior', 'numext'],
    'colonia':        ['colonia'],
    'cp':             ['cp', 'c p', 'codigo postal'],
    'municipio':      ['municipio', 'ciudad', 'delegacion', 'alcaldia'],
    'estado':         ['estado', 'entidad'],
    'f_ingreso':      ['fecha de ingreso', 'fecha ingreso', 'f ingreso', 'ingreso', 'fecha de alta'],
    'puesto':         ['puesto', 'descripcion del puesto', 'desc puesto', 'cargo'],
    'periodicidad':   ['periodicidad', 'periodo de pago', 'frecuencia de pago'],
    'monto_periodo':  ['monto por periodo', 'monto periodo', 'monto', 'sueldo', 'importe'],
    'categoria_pago': ['categoria de pago', 'categoria pago', 'tipo de estructura',
                       'estructura', 'tipo estructura'],
    'banco':          ['banco'],
    'cuenta':         ['cuenta', 'no cuenta', 'numero de cuenta', 'no de cuenta'],
    'clabe':          ['clabe', 'clabe interbancaria'],
    'tarjeta':        ['tarjeta', 'no tarjeta', 'numero de tarjeta'],
    'reg_patronal':   ['registro patronal', 'rp'],
    'f_baja':         ['fecha de baja', 'f baja', 'baja'],
    'no_empleado':    ['numero de empleado', 'no empleado', 'num empleado',
                       'no de empleado', 'clave empleado', 'referencia', 'no emp'],
    'prima_vac':      ['prima vacacional', 'prima vac', 'prima'],
    'tipo_contrato':  ['tipo de contrato', 'tipo contrato', 'contrato tipo'],
    'departamento':   ['departamento', 'depto', 'area', 'área', 'dpto'],
    # --- Ajustes salariales recurrentes (hr.salary.attachment) — opcionales ---
    'vales_despensa': ['vales de despensa', 'vales despensa', 'vales', 'despensa'],
    'fondo_ahorro':   ['fondo de ahorro', 'fondo ahorro'],
    'ajuste_salarial': ['ajuste salarial', 'ajustes salariales', 'ajuste'],
    'ajuste_concepto': ['ajuste salarial concepto', 'concepto ajuste',
                        'ajuste concepto', 'descripcion ajuste'],
}

# Ajustes recurrentes: columna del machote → (xmlid del tipo de entrada, etiqueta)
SALARY_ADJUSTMENTS = {
    'vales_despensa':  ('mx_jandea_employee_import.input_type_vales_despensa', 'Vales de Despensa'),
    'fondo_ahorro':    ('mx_jandea_employee_import.input_type_fondo_ahorro', 'Fondo de Ahorro'),
    'ajuste_salarial': ('mx_jandea_employee_import.input_type_ajuste_salarial', 'Ajuste Salarial'),
}

# Columnas mínimas obligatorias en el archivo
REQUIRED_KEYS = ('nombre', 'apellido_pat', 'rfc', 'f_ingreso', 'periodicidad', 'monto_periodo')

MARITAL_MAP = {
    'SOLTERO': 'single',  'SOLTERA': 'single',  'S': 'single',
    'CASADO': 'married',  'CASADA': 'married',  'C': 'married',
    'DIVORCIADO': 'divorced', 'DIVORCIADA': 'divorced', 'D': 'divorced',
    'VIUDO': 'widower',   'VIUDA': 'widower',   'V': 'widower',
    'U': 'single',
}

GENDER_MAP = {
    'MASCULINO': 'male', 'HOMBRE': 'male', 'H': 'male',
    'FEMENINO': 'female', 'MUJER': 'female', 'F': 'female', 'M': 'female',
}

# Periodicidad (texto del machote) → schedule_pay nativo de Odoo
PERIOD_MAP = {
    'MENSUAL': 'monthly', 'MES': 'monthly', 'MENSUALIDAD': 'monthly',
    'QUINCENAL': 'semi-monthly', 'QUINCENA': 'semi-monthly', 'SEMI-MONTHLY': 'semi-monthly',
    'CATORCENAL': 'bi-weekly', 'BI-WEEKLY': 'bi-weekly',
    'SEMANAL': 'weekly', 'SEMANA': 'weekly', 'WEEKLY': 'weekly',
}
SCHEDULE_LABEL = {
    'monthly': 'Mensual', 'semi-monthly': 'Quincenal',
    'bi-weekly': 'Catorcenal', 'weekly': 'Semanal',
}

STATE_ABBR = {
    'AGS': 'Aguascalientes',      'BC': 'Baja California',
    'BCS': 'Baja California Sur', 'CAMP': 'Campeche',
    'CDMX': 'Ciudad de México',   'CHIH': 'Chihuahua',
    'CHIS': 'Chiapas',            'COAH': 'Coahuila',
    'COL': 'Colima',              'DGO': 'Durango',
    'GTO': 'Guanajuato',          'GRO': 'Guerrero',
    'HGO': 'Hidalgo',             'JAL': 'Jalisco',
    'MEX': 'Estado de México',    'MICH': 'Michoacán',
    'MOR': 'Morelos',             'NAY': 'Nayarit',
    'NL': 'Nuevo León',           'OAX': 'Oaxaca',
    'PUE': 'Puebla',              'QRO': 'Querétaro',
    'QROO': 'Quintana Roo',       'SLP': 'San Luis Potosí',
    'SIN': 'Sinaloa',             'SON': 'Sonora',
    'TAB': 'Tabasco',             'TAMPS': 'Tamaulipas',
    'TLAX': 'Tlaxcala',           'VER': 'Veracruz',
    'YUC': 'Yucatán',             'ZAC': 'Zacatecas',
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de extracción de celda (usan colmap: canonical_key -> índice)
# ─────────────────────────────────────────────────────────────────────────────
def _val(row, colmap, key, default=''):
    idx = colmap.get(key)
    if idx is None:
        return default
    try:
        v = row[idx]
    except (IndexError, KeyError):
        return default
    if v is None or str(v).strip() in ('nan', 'NaT', 'None', ''):
        return default
    return str(v).strip()


def _float_val(row, colmap, key, default=0.0):
    idx = colmap.get(key)
    if idx is None:
        return default
    try:
        v = row[idx]
        if v is None or str(v).strip() in ('nan', 'NaT', 'None', ''):
            return default
        return float(str(v).replace(',', '').replace('$', '').strip())
    except (IndexError, KeyError, ValueError, TypeError):
        return default


def _date_val(row, colmap, key):
    raw = _val(row, colmap, key)
    if not raw or raw == 'NaT':
        return False
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d', '%d/%m/%y', '%m/%d/%Y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    # Serial de Excel
    try:
        import xlrd
        tup = xlrd.xldate_as_tuple(float(raw), 0)
        return date(*tup[:3])
    except Exception:
        pass
    # pandas Timestamp string
    try:
        return datetime.strptime(raw[:10], '%Y-%m-%d').date()
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Wizard principal
# ─────────────────────────────────────────────────────────────────────────────
class EmployeeImportWizard(models.TransientModel):
    _name = 'mx.jandea.employee.import.wizard'
    _description = 'Importación Masiva de Empleados'

    state = fields.Selection([
        ('draft', 'Configuración'),
        ('preview', 'Vista previa'),
        ('done', 'Resultados'),
    ], default='draft', readonly=True)

    # ── Archivo ───────────────────────────────────────────────────────────────
    file_data = fields.Binary(string='Archivo XLS/XLSX', required=True, attachment=False)
    file_name = fields.Char(string='Nombre del archivo')

    # ── Configuración ─────────────────────────────────────────────────────────
    company_id = fields.Many2one(
        'res.company', string='Empresa destino', required=True,
        default=lambda self: self.env.company,
    )
    header_row = fields.Integer(
        string='Fila de encabezados (1 = primera fila)', default=1,
        help='Número de fila donde están los encabezados. Los datos inician en la siguiente.',
    )
    skip_duplicates = fields.Boolean(
        string='Omitir duplicados (mismo RFC/empresa)', default=True,
    )
    update_existing = fields.Boolean(
        string='Actualizar existentes', default=False,
        help='Si está activo junto con "Omitir duplicados", actualiza datos del empleado existente.',
    )
    validate_rfc_format = fields.Boolean(
        string='Validar formato RFC al importar', default=True,
    )
    link_multicompany = fields.Boolean(
        string='Vincular empleados multiempresa por RFC', default=True,
    )

    # ── Vista previa ──────────────────────────────────────────────────────────
    preview_line_ids = fields.One2many(
        'mx.jandea.employee.import.preview', 'wizard_id',
        string='Vista previa',
    )
    preview_total = fields.Integer(string='Filas', readonly=True)
    preview_new = fields.Integer(string='A crear', readonly=True)
    preview_update = fields.Integer(string='A actualizar', readonly=True)
    preview_skip = fields.Integer(string='A omitir', readonly=True)
    preview_warn = fields.Integer(string='Con observaciones', readonly=True)

    # ── Resultados ────────────────────────────────────────────────────────────
    result_line_ids = fields.One2many(
        'mx.jandea.employee.import.result', 'wizard_id',
        string='Resultados', readonly=False,
    )
    import_done = fields.Boolean(default=False, readonly=True)
    count_created = fields.Integer(string='Creados', readonly=True)
    count_updated = fields.Integer(string='Actualizados', readonly=True)
    count_skipped = fields.Integer(string='Omitidos', readonly=True)
    count_error = fields.Integer(string='Errores', readonly=True)

    # ── CheckId ───────────────────────────────────────────────────────────────
    checkid_available = fields.Boolean(
        string='CheckId disponible',
        compute='_compute_checkid_available',
    )
    checkid_done = fields.Boolean(default=False, readonly=True)
    checkid_count_ok = fields.Integer(string='CheckId OK', readonly=True)
    checkid_count_error = fields.Integer(string='CheckId Error', readonly=True)
    checkid_selected_count = fields.Integer(
        string='Seleccionados para CheckId',
        compute='_compute_checkid_selected_count',
    )

    @api.depends()
    def _compute_checkid_available(self):
        module = self.env['ir.module.module'].sudo().search([
            ('name', '=', 'mx_jandea_checkid'),
            ('state', '=', 'installed'),
        ], limit=1)
        for rec in self:
            rec.checkid_available = bool(module)

    @api.depends('result_line_ids.checkid_selected')
    def _compute_checkid_selected_count(self):
        for rec in self:
            rec.checkid_selected_count = len(
                rec.result_line_ids.filtered('checkid_selected')
            )

    # ──────────────────────────────────────────────────────────────────────────
    # Lectura del archivo → (data_rows, colmap)
    # ──────────────────────────────────────────────────────────────────────────
    def _read_source(self):
        """Lee el binario y devuelve (data_rows, colmap). Valida encabezados."""
        self.ensure_one()
        if not self.file_data:
            raise UserError(_('Seleccione un archivo XLS o XLSX.'))
        try:
            import pandas as pd
        except ImportError:
            raise UserError(_('La librería pandas no está instalada en el servidor.'))

        file_bytes = base64.b64decode(self.file_data)
        fname = (self.file_name or '').lower()
        try:
            engine = 'xlrd' if fname.endswith('.xls') else 'openpyxl'
            df = pd.read_excel(io.BytesIO(file_bytes), engine=engine, header=None, dtype=str)
        except Exception as e:
            raise UserError(_('Error al leer el archivo: %s') % e)

        hdr_idx = max(self.header_row - 1, 0)
        try:
            header_row = df.values[hdr_idx]
        except IndexError:
            raise UserError(_('El archivo no tiene la fila de encabezados indicada.'))

        colmap = self._build_colmap(header_row)

        missing = [k for k in REQUIRED_KEYS if k not in colmap]
        if missing:
            legibles = {
                'nombre': 'Nombre(s)', 'apellido_pat': 'Apellido Paterno',
                'rfc': 'RFC', 'f_ingreso': 'Fecha de Ingreso',
                'periodicidad': 'Periodicidad', 'monto_periodo': 'Monto por Periodo',
            }
            raise UserError(_(
                'No se encontraron estas columnas obligatorias en el archivo:\n%s\n\n'
                'Revisa que los encabezados coincidan con el machote.'
            ) % '\n'.join('• ' + legibles.get(m, m) for m in missing))

        data_rows = df.values[hdr_idx + 1:]
        return data_rows, colmap

    def _build_colmap(self, header_values):
        """Construye {canonical_key: índice_columna} a partir de la fila de encabezados."""
        lookup = {}
        for key, aliases in HEADER_ALIASES.items():
            for a in aliases:
                lookup[a] = key
        colmap = {}
        for idx, raw in enumerate(header_values):
            n = _norm(raw)
            if not n:
                continue
            key = lookup.get(n)
            if key and key not in colmap:
                colmap[key] = idx
        return colmap

    # ──────────────────────────────────────────────────────────────────────────
    # PASO 1: Vista previa (no escribe empleados)
    # ──────────────────────────────────────────────────────────────────────────
    def action_preview(self):
        self.ensure_one()
        data_rows, colmap = self._read_source()

        self.preview_line_ids.unlink()
        lines = []
        total = new = upd = skip = warn = 0

        for row_idx, row in enumerate(data_rows, start=self.header_row + 1):
            nombre = _val(row, colmap, 'nombre')
            ap_pat = _val(row, colmap, 'apellido_pat')
            if not nombre and not ap_pat:
                continue
            total += 1

            rfc = _val(row, colmap, 'rfc').upper().replace(' ', '')
            ap_mat = _val(row, colmap, 'apellido_mat')
            full_name = ' '.join(filter(None, [ap_pat, ap_mat, nombre]))

            obs = []

            rfc_ok = False
            if rfc and self.validate_rfc_format:
                rfc_ok, msg = self.env['hr.employee']._validate_rfc_format(rfc)
                if not rfc_ok:
                    obs.append(_('RFC: %s') % msg)
            elif rfc:
                rfc_ok = True
            if not rfc:
                obs.append(_('Sin RFC'))

            per_raw = _val(row, colmap, 'periodicidad')
            schedule = PERIOD_MAP.get(per_raw.upper())
            if per_raw and not schedule:
                obs.append(_('Periodicidad "%s" no reconocida') % per_raw)

            monto = _float_val(row, colmap, 'monto_periodo')
            if not monto:
                obs.append(_('Sin monto por periodo'))

            f_ing = _date_val(row, colmap, 'f_ingreso')
            if not f_ing:
                obs.append(_('Fecha de ingreso inválida'))

            categoria = _val(row, colmap, 'categoria_pago')
            stype = self._resolve_structure_type(categoria) if categoria else False
            if categoria and not stype:
                obs.append(_('Categoría de pago "%s" no encontrada') % categoria)

            banco = _val(row, colmap, 'banco')
            clabe = _val(row, colmap, 'clabe')
            cuenta = _val(row, colmap, 'cuenta')
            cta_display = clabe or cuenta
            if banco and not self._find_bank(banco):
                obs.append(_('Banco "%s" no está en el catálogo (se guardará la cuenta igual)') % banco)

            existing = False
            if rfc:
                existing = self.env['hr.employee'].sudo().search([
                    ('mx_rfc', '=', rfc), ('company_id', '=', self.company_id.id),
                ], limit=1)
            if existing and self.skip_duplicates and not self.update_existing:
                planned = 'skip'; skip += 1
            elif existing and self.update_existing:
                planned = 'update'; upd += 1
            else:
                planned = 'new'; new += 1

            if obs:
                warn += 1

            lines.append((0, 0, {
                'row_number': row_idx,
                'full_name': full_name,
                'rfc': rfc,
                'rfc_format_ok': rfc_ok,
                'curp': _val(row, colmap, 'curp').upper().replace(' ', ''),
                'nss': _val(row, colmap, 'nss'),
                'f_ingreso': f_ing or False,
                'periodicidad': SCHEDULE_LABEL.get(schedule, per_raw),
                'monto_periodo': monto,
                'categoria_pago': categoria,
                'banco': banco,
                'cuenta_clabe': cta_display,
                'planned_action': planned,
                'observaciones': ' | '.join(obs),
            }))

        self.write({
            'preview_line_ids': lines,
            'preview_total': total,
            'preview_new': new,
            'preview_update': upd,
            'preview_skip': skip,
            'preview_warn': warn,
            'state': 'preview',
        })
        return self._reopen()

    # ──────────────────────────────────────────────────────────────────────────
    # PASO 2: Importación real
    # ──────────────────────────────────────────────────────────────────────────
    def action_import(self):
        self.ensure_one()
        data_rows, colmap = self._read_source()

        results = []
        created = updated = skipped = errors = 0

        for row_idx, row in enumerate(data_rows, start=self.header_row + 1):
            nombre = _val(row, colmap, 'nombre')
            apellido_pat = _val(row, colmap, 'apellido_pat')
            if not nombre and not apellido_pat:
                continue

            rfc = _val(row, colmap, 'rfc').upper().replace(' ', '')
            full_name = ' '.join(filter(None, [
                apellido_pat, _val(row, colmap, 'apellido_mat'), nombre
            ])).strip()

            rfc_format_ok = False
            if rfc and self.validate_rfc_format:
                rfc_format_ok, _m = self.env['hr.employee']._validate_rfc_format(rfc)
            elif rfc:
                rfc_format_ok = True

            existing = False
            if rfc:
                existing = self.env['hr.employee'].sudo().search([
                    ('mx_rfc', '=', rfc), ('company_id', '=', self.company_id.id),
                ], limit=1)

            if existing and self.skip_duplicates and not self.update_existing:
                results.append({
                    'row': row_idx, 'name': full_name, 'rfc': rfc, 'status': 'skipped',
                    'message': _('Empleado ya existe (RFC duplicado en esta empresa).'),
                    'rfc_format_ok': rfc_format_ok, 'employee_id': existing.id,
                    'checkid_selected': False,
                })
                skipped += 1
                continue

            try:
                vals_create, vals_write, version_vals, bank_data = self._build_employee_vals(
                    row, colmap, rfc, rfc_format_ok
                )
            except Exception as e:
                results.append({
                    'row': row_idx, 'name': full_name, 'rfc': rfc, 'status': 'error',
                    'message': repr(e), 'rfc_format_ok': rfc_format_ok,
                    'checkid_selected': False,
                })
                errors += 1
                continue

            try:
                if existing and self.update_existing:
                    existing.sudo().write({**vals_create, **vals_write})
                    emp = existing
                    action = 'updated'; updated += 1
                else:
                    emp = (
                        self.env['hr.employee'].sudo()
                        .with_company(self.company_id).create(vals_create)
                    )
                    for fname, fval in vals_write.items():
                        try:
                            emp.sudo().write({fname: fval})
                        except Exception:
                            import traceback
                            _logger.error(
                                'IMPORT write FAIL campo="%s" val=%r\n%s',
                                fname, fval, traceback.format_exc()
                            )
                    action = 'created'; created += 1

                # Campos que viven en la versión/contrato (periodicidad, prima,
                # tipo de contrato). Se aplican aparte por robustez en Odoo 19.
                try:
                    self._apply_version_fields(emp, version_vals)
                except Exception:
                    import traceback
                    _logger.error('IMPORT version FAIL fila %d\n%s',
                                  row_idx, traceback.format_exc())

                # Cuenta bancaria (BUG corregido)
                bank_msg = ''
                try:
                    if bank_data.get('acc'):
                        self._set_bank_account(emp, bank_data)
                except Exception:
                    import traceback
                    _logger.error('IMPORT bank FAIL fila %d\n%s', row_idx, traceback.format_exc())
                    bank_msg = _(' (cuenta bancaria no cargada)')

                # Ajustes salariales recurrentes (vales, fondo de ahorro, ajuste)
                adj_msg = ''
                try:
                    aplicados = self._apply_salary_attachments(emp, row, colmap)
                    if aplicados:
                        adj_msg = _(' + ajustes: %s') % ', '.join(aplicados)
                except Exception:
                    import traceback
                    _logger.error('IMPORT ajustes FAIL fila %d\n%s', row_idx, traceback.format_exc())
                    adj_msg = _(' (ajustes salariales no cargados)')

                results.append({
                    'row': row_idx, 'name': emp.name, 'rfc': rfc, 'status': action,
                    'message': _('OK') + bank_msg + adj_msg, 'employee_id': emp.id,
                    'rfc_format_ok': rfc_format_ok, 'checkid_selected': True,
                })

            except Exception as e:
                import traceback as _tb
                _logger.error('IMPORT ERROR fila %d:\n%s', row_idx, _tb.format_exc())
                results.append({
                    'row': row_idx, 'name': full_name, 'rfc': rfc, 'status': 'error',
                    'message': repr(e)[:200], 'rfc_format_ok': rfc_format_ok,
                    'checkid_selected': False,
                })
                errors += 1

        if self.link_multicompany:
            rfcs_ok = {
                r['rfc'] for r in results
                if r.get('rfc') and r['status'] in ('created', 'updated')
            }
            for rfc in rfcs_ok:
                self.env['hr.employee']._link_multicompany_by_rfc(rfc)

        self.write({
            'result_line_ids': [
                (0, 0, {
                    'row_number': r['row'], 'employee_name': r['name'], 'rfc': r['rfc'],
                    'status': r['status'], 'message': r['message'],
                    'employee_id': r.get('employee_id', False),
                    'rfc_format_ok': r.get('rfc_format_ok', False),
                    'checkid_selected': r.get('checkid_selected', False),
                    'checkid_status': 'pending',
                }) for r in results
            ],
            'import_done': True, 'state': 'done',
            'count_created': created, 'count_updated': updated,
            'count_skipped': skipped, 'count_error': errors,
        })
        return self._reopen()

    def action_back_to_config(self):
        self.ensure_one()
        self.write({'state': 'draft'})
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mx.jandea.employee.import.wizard',
            'res_id': self.id, 'view_mode': 'form', 'target': 'new',
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Construcción de vals → campos nativos
    # ──────────────────────────────────────────────────────────────────────────
    def _build_employee_vals(self, row, colmap, rfc, rfc_format_ok):
        """Retorna (vals_create, vals_write, bank_data)."""
        emp_fields = self.env['hr.employee']._fields

        nombre = _val(row, colmap, 'nombre')
        ap_pat = _val(row, colmap, 'apellido_pat')
        ap_mat = _val(row, colmap, 'apellido_mat')
        full_name = ' '.join(filter(None, [ap_pat, ap_mat, nombre])) or 'Sin nombre'

        vals_create = {'name': full_name, 'company_id': self.company_id.id}
        vals_write = {}

        correo = _val(row, colmap, 'correo')
        if correo:
            vals_write['work_email'] = correo

        curp = _val(row, colmap, 'curp').upper().replace(' ', '')
        if rfc:
            vals_write['mx_rfc'] = rfc
            vals_write['rfc_validated_format'] = rfc_format_ok
            # También a los campos nativos de la localización (los que ve el
            # usuario en la pestaña Personal y usa el CFDI), si existen.
            for f in ('l10n_mx_rfc', 'l10n_mx_edi_rfc'):
                if f in emp_fields:
                    vals_write[f] = rfc
        if curp:
            vals_write['mx_curp'] = curp
            vals_write['identification_id'] = curp
            for f in ('l10n_mx_curp', 'l10n_mx_edi_curp'):
                if f in emp_fields:
                    vals_write[f] = curp

        # Número de empleado → código de barras (gafete) y referencia
        no_emp = _val(row, colmap, 'no_empleado')
        if no_emp:
            if 'barcode' in emp_fields:
                vals_write['barcode'] = no_emp
            for f in ('registration_number', 'ref', 'employee_number'):
                if f in emp_fields:
                    vals_write[f] = no_emp
                    break

        nss_raw = _val(row, colmap, 'nss')
        if nss_raw:
            vals_write['nss'] = nss_raw
            if 'ssnid' in emp_fields:
                vals_write['ssnid'] = nss_raw

        marital = MARITAL_MAP.get(_val(row, colmap, 'estado_civil').upper())
        if marital:
            vals_write['marital'] = marital

        genero = GENDER_MAP.get(_val(row, colmap, 'genero').upper().strip())
        if genero and 'gender' in emp_fields:
            vals_write['gender'] = genero

        fnac = _date_val(row, colmap, 'fecha_nac')
        if fnac:
            vals_write['birthday'] = fnac

        # Domicilio
        calle = _val(row, colmap, 'calle')
        numext = _val(row, colmap, 'num_ext')
        colonia = _val(row, colmap, 'colonia')
        street = ' '.join(filter(None, [calle, numext]))
        if colonia:
            street = (street + ', ' + colonia).strip(', ')
        if street and 'private_street' in emp_fields:
            vals_write['private_street'] = street
        ciudad = _val(row, colmap, 'municipio')
        if ciudad and 'private_city' in emp_fields:
            vals_write['private_city'] = ciudad
        cp = _val(row, colmap, 'cp')
        if cp and 'private_zip' in emp_fields:
            vals_write['private_zip'] = cp
        estado_raw = _val(row, colmap, 'estado').upper()
        if estado_raw and 'private_state_id' in emp_fields:
            state_name = STATE_ABBR.get(estado_raw, estado_raw)
            mx_country = self.env.ref('base.mx', raise_if_not_found=False)
            if mx_country:
                state = self.env['res.country.state'].sudo().search([
                    ('country_id', '=', mx_country.id),
                    '|', ('name', 'ilike', state_name), ('code', '=ilike', estado_raw),
                ], limit=1)
                if state:
                    vals_write['private_state_id'] = state.id
                    if 'private_country_id' in emp_fields:
                        vals_write['private_country_id'] = mx_country.id

        # ── CONTRATO / VERSIÓN (automático) ───────────────────────────────
        # Fecha de ingreso → inicio de contrato (ya NO se usa antigüedad)
        f_ingreso = _date_val(row, colmap, 'f_ingreso')
        if f_ingreso:
            if 'contract_date_start' in emp_fields:
                vals_write['contract_date_start'] = f_ingreso
            if 'date_version' in emp_fields:
                vals_write['date_version'] = f_ingreso

        # ── CONTRATO / VERSIÓN ────────────────────────────────────────────
        # Estos campos viven en la versión/contrato (hr.version) en Odoo 19;
        # se aplican con _apply_version_fields tras crear al empleado.
        version_vals = {}

        # Periodicidad → schedule_pay
        schedule = PERIOD_MAP.get(_val(row, colmap, 'periodicidad').upper())
        if schedule:
            version_vals['schedule_pay'] = schedule

        # Prima vacacional (%) → campo de la versión (nombre según build)
        prima = _float_val(row, colmap, 'prima_vac')
        if prima:
            version_vals['_prima_vacacional'] = prima  # se resuelve el campo real

        # Tipo de contrato → contract_type_id (se resuelve por nombre)
        tipo_contrato = _val(row, colmap, 'tipo_contrato')
        if tipo_contrato:
            ct = self._resolve_contract_type(tipo_contrato)
            if ct:
                version_vals['contract_type_id'] = ct

        # Monto por periodo → wage (importe del periodo)
        monto = _float_val(row, colmap, 'monto_periodo')
        if monto and 'wage' in emp_fields:
            vals_write['wage'] = monto

        # Categoría de pago → tipo de estructura
        categoria = _val(row, colmap, 'categoria_pago')
        if categoria:
            stype = self._resolve_structure_type(categoria)
            if stype and 'structure_type_id' in emp_fields:
                vals_write['structure_type_id'] = stype

        # Puesto (texto libre) + Puesto de trabajo (job_id) + Departamento
        puesto = _val(row, colmap, 'puesto')
        if puesto and 'job_title' in emp_fields:
            vals_write['job_title'] = puesto

        departamento = _val(row, colmap, 'departamento')
        dept_id = self._resolve_department(departamento) if departamento else False
        if dept_id and 'department_id' in emp_fields:
            vals_write['department_id'] = dept_id

        if puesto and 'job_id' in emp_fields:
            job_id = self._resolve_job(puesto, dept_id)
            if job_id:
                vals_write['job_id'] = job_id

        # Fecha de baja
        f_baja = _date_val(row, colmap, 'f_baja')
        if f_baja and 'departure_date' in emp_fields:
            vals_write['departure_date'] = f_baja

        # Datos de banco (se procesan aparte, post-create)
        bank_data = {
            'banco':  _val(row, colmap, 'banco'),
            'clabe':  _val(row, colmap, 'clabe').replace(' ', ''),
            'cuenta': _val(row, colmap, 'cuenta').replace(' ', ''),
        }
        bank_data['acc'] = bank_data['clabe'] or bank_data['cuenta']

        return vals_create, vals_write, version_vals, bank_data

    # ──────────────────────────────────────────────────────────────────────────
    # Catálogos: tipo de estructura y banco
    # ──────────────────────────────────────────────────────────────────────────
    def _resolve_department(self, text):
        """Busca el departamento por nombre; lo crea si no existe."""
        text = (text or '').strip()
        if not text:
            return False
        Dept = self.env['hr.department']
        dept = Dept.sudo().search([
            ('name', 'ilike', text), ('company_id', '=', self.company_id.id),
        ], limit=1) or Dept.sudo().search([('name', 'ilike', text)], limit=1)
        if not dept:
            dept = Dept.sudo().with_company(self.company_id).create({
                'name': text, 'company_id': self.company_id.id,
            })
        return dept.id

    def _resolve_job(self, text, dept_id=False):
        """Busca el puesto de trabajo (hr.job) por nombre; lo crea si no existe."""
        text = (text or '').strip()
        if not text:
            return False
        Job = self.env['hr.job']
        dom = [('name', 'ilike', text), ('company_id', '=', self.company_id.id)]
        if dept_id:
            dom = dom + [('department_id', '=', dept_id)]
        job = Job.sudo().search(dom, limit=1) \
            or Job.sudo().search([('name', 'ilike', text),
                                  ('company_id', '=', self.company_id.id)], limit=1) \
            or Job.sudo().search([('name', 'ilike', text)], limit=1)
        if not job:
            vals = {'name': text, 'company_id': self.company_id.id}
            if dept_id:
                vals['department_id'] = dept_id
            job = Job.sudo().with_company(self.company_id).create(vals)
        return job.id

    def _resolve_contract_type(self, text):
        """Resuelve el tipo de contrato (contract_type_id) por nombre."""
        text = (text or '').strip()
        if not text:
            return False
        CT = self.env.get('hr.contract.type')
        if CT is None:
            return False
        ct = CT.sudo().search([('name', 'ilike', text)], limit=1)
        return ct.id if ct else False

    # Nombres candidatos del campo de prima vacacional en la versión/contrato,
    # según localización/build. Se escribe en el primero que exista.
    _PRIMA_FIELDS = (
        'l10n_mx_vacation_bonus', 'vacation_bonus', 'prima_vacacional',
        'l10n_mx_edi_vacation_bonus', 'holidays_premium',
    )

    def _apply_version_fields(self, emp, version_vals):
        """Escribe los campos de contrato/versión. En Odoo 19 viven en
        hr.version (emp.version_id); algunos se exponen como related en
        hr.employee. Se prefiere escribir en la VERSIÓN y, si el campo no está
        ahí, en el empleado. Defensivo: si no existe, se omite (log)."""
        if not version_vals:
            return
        vals = dict(version_vals)

        ver = self._env_version_record(emp)
        emp_fields = emp._fields
        ver_fields = ver._fields if ver else {}

        # Resolver el nombre real del campo de prima vacacional
        prima = vals.pop('_prima_vacacional', None)
        if prima is not None:
            for f in self._PRIMA_FIELDS:
                if f in ver_fields or f in emp_fields:
                    vals[f] = prima
                    break

        # Preferir la versión; el empleado como respaldo.
        ver_part = {k: v for k, v in vals.items() if ver and k in ver_fields}
        emp_part = {k: v for k, v in vals.items()
                    if k not in ver_part and k in emp_fields}

        if ver_part and ver:
            try:
                ver.sudo().write(ver_part)
            except Exception:
                import traceback
                _logger.error('IMPORT version(ver) FAIL %r\n%s',
                              ver_part, traceback.format_exc())
        if emp_part:
            try:
                emp.sudo().write(emp_part)
            except Exception:
                import traceback
                _logger.error('IMPORT version(emp) FAIL %r\n%s',
                              emp_part, traceback.format_exc())

    @staticmethod
    def _env_version_record(emp):
        """Devuelve la versión/contrato actual del empleado, probando los
        nombres de relación que varían por versión de Odoo."""
        for attr in ('version_id', 'current_version_id', 'contract_id'):
            rec = getattr(emp, attr, False)
            if rec:
                return rec
        return False

    def _resolve_structure_type(self, text):
        if not text:
            return False
        STT = self.env['hr.payroll.structure.type'].sudo()
        st = STT.search([('name', 'ilike', text)], limit=1)
        return st.id if st else False

    def _find_bank(self, banco):
        if not banco:
            return False
        return self.env['res.bank'].sudo().search([
            '|', ('name', 'ilike', banco), ('bic', '=ilike', banco)
        ], limit=1)

    def _set_bank_account(self, emp, bank_data):
        """Crea/asigna la cuenta bancaria (res.partner.bank) del empleado."""
        acc = bank_data.get('acc')
        if not acc:
            return False

        # Partner destino de la cuenta: el contacto de trabajo del empleado.
        partner = getattr(emp, 'work_contact_id', False)
        if not partner:
            partner = self.env['res.partner'].sudo().create({
                'name': emp.name, 'company_id': emp.company_id.id,
            })
            if 'work_contact_id' in emp._fields:
                emp.sudo().write({'work_contact_id': partner.id})

        bank = self._find_bank(bank_data.get('banco'))

        RPB = self.env['res.partner.bank'].sudo()
        existing = RPB.search([
            ('acc_number', '=', acc), ('partner_id', '=', partner.id)
        ], limit=1)
        if existing:
            partner_bank = existing
            if bank and not existing.bank_id:
                existing.write({'bank_id': bank.id})
        else:
            partner_bank = RPB.with_company(emp.company_id).create({
                'acc_number': acc,
                'partner_id': partner.id,
                'bank_id': bank.id if bank else False,
                'company_id': emp.company_id.id,
            })

        # Asignar como cuenta de nómina del empleado (el nombre del campo varía por versión)
        if 'bank_account_id' in emp._fields:
            emp.sudo().write({'bank_account_id': partner_bank.id})
        elif 'bank_account_ids' in emp._fields:
            emp.sudo().write({'bank_account_ids': [(4, partner_bank.id)]})
        return partner_bank

    def _recurring_duration_type(self):
        """Valor de duration_type que representa un ajuste SIN fin (recurrente).

        El nombre del valor varía por versión de Odoo; se detecta leyendo la
        selección del campo. Si no se encuentra, devuelve None (usa el
        predeterminado del modelo).
        """
        Att = self.env.get('hr.salary.attachment')
        if Att is None or 'duration_type' not in Att._fields:
            return None
        try:
            valores = [v for v, _lbl in Att._fields['duration_type'].selection]
        except Exception:
            return None
        for v in valores:
            if any(t in v for t in ('indef', 'no_end', 'unlimited', 'permanent', 'recurr')):
                return v
        # fallback: el primero que no sea limitado / de una sola vez
        for v in valores:
            if v not in ('limited', 'one_time', 'once'):
                return v
        return None

    def _apply_salary_attachments(self, emp, row, colmap):
        """Crea/actualiza los ajustes salariales recurrentes (hr.salary.attachment)
        capturados en el machote: Vales de Despensa, Fondo de Ahorro y Ajuste
        Salarial. Devuelve la lista de etiquetas aplicadas."""
        Att = self.env.get('hr.salary.attachment')
        if Att is None:
            return []
        date_start = (getattr(emp, 'contract_date_start', False)
                      or getattr(emp, 'date_start', False)
                      or fields.Date.context_today(self))
        concepto = _val(row, colmap, 'ajuste_concepto')
        recurrente = self._recurring_duration_type()
        aplicados = []
        for col, (xmlid, etiqueta) in SALARY_ADJUSTMENTS.items():
            monto = _float_val(row, colmap, col)
            if not monto:
                continue
            try:
                input_type = self.env.ref(xmlid)
            except ValueError:
                continue
            descripcion = etiqueta
            if col == 'ajuste_salarial' and concepto:
                descripcion = concepto
            vals = {
                'employee_ids': [(6, 0, [emp.id])],
                'company_id': emp.company_id.id,
                'description': descripcion,
                'other_input_type_id': input_type.id,
                'monthly_amount': monto,
                'date_start': date_start,
                'state': 'open',
            }
            if recurrente:
                vals['duration_type'] = recurrente
            # Evitar duplicados al reimportar: reutilizar el ajuste abierto del
            # mismo empleado y tipo, si existe.
            dominio = [
                ('employee_ids', 'in', emp.id),
                ('other_input_type_id', '=', input_type.id),
                ('state', 'in', ('open', 'draft')),
            ]
            existente = Att.with_company(emp.company_id).sudo().search(dominio, limit=1)
            if existente and self.update_existing:
                upd = {'monthly_amount': monto, 'description': descripcion}
                if recurrente:
                    upd['duration_type'] = recurrente
                existente.sudo().write(upd)
            elif not existente:
                Att.with_company(emp.company_id).sudo().create(vals)
            aplicados.append(etiqueta)
        return aplicados

    # ──────────────────────────────────────────────────────────────────────────
    # CheckId (sin cambios funcionales)
    # ──────────────────────────────────────────────────────────────────────────
    def action_select_all_checkid(self):
        self.ensure_one()
        self.result_line_ids.filtered(
            lambda l: l.employee_id and l.status in ('created', 'updated', 'skipped')
        ).write({'checkid_selected': True})
        return self._reopen()

    def action_deselect_all_checkid(self):
        self.ensure_one()
        self.result_line_ids.write({'checkid_selected': False})
        return self._reopen()

    def action_checkid_validate_selected(self):
        self.ensure_one()
        lines_selected = self.result_line_ids.filtered(
            lambda l: l.checkid_selected and l.employee_id
        )
        if not lines_selected:
            raise UserError(_(
                'No hay registros seleccionados para validar.\n'
                'Marca el checkbox ✓ en la columna "CheckId".'
            ))

        ok = errors = 0
        for line in lines_selected:
            emp = line.employee_id
            termino = ''
            try:
                if hasattr(emp, '_get_termino_busqueda'):
                    termino = (emp._get_termino_busqueda() or '').strip()
            except Exception as te:
                _logger.warning('_get_termino_busqueda error: %s', te)
            if not termino:
                for fname in ('mx_curp', 'mx_rfc'):
                    val = emp._fields.get(fname) and emp[fname]
                    if val and isinstance(val, str) and val.strip():
                        termino = val.strip().upper()
                        break
            if not termino:
                line.write({'checkid_status': 'error',
                            'checkid_message': 'Sin RFC ni CURP registrado en el empleado.'})
                errors += 1
                continue
            try:
                emp.sudo()._ejecutar_consulta_checkid(termino)
                emp.invalidate_recordcache(['checkid_estado_consulta'])
                estado = emp.sudo().checkid_estado_consulta or 'ok'
                if estado == 'advertencia':
                    line.write({'checkid_status': 'warning',
                                'checkid_message': 'Advertencia: problema 69/69B detectado.'})
                else:
                    line.write({'checkid_status': 'ok', 'checkid_message': 'Consulta exitosa.'})
                ok += 1
            except Exception as e:
                try:
                    err_msg = repr(e)
                except Exception:
                    err_msg = 'Error desconocido en CheckId'
                _logger.warning('CheckId error para %s: %s', emp.name, err_msg)
                line.write({'checkid_status': 'error', 'checkid_message': err_msg[:200]})
                errors += 1

        self.write({'checkid_done': True, 'checkid_count_ok': ok, 'checkid_count_error': errors})
        return self._reopen()

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}

    def action_open_employees(self):
        emp_ids = self.result_line_ids.filtered(
            lambda l: l.employee_id
        ).mapped('employee_id').ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('Empleados Importados'),
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', emp_ids)],
            'target': 'current',
        }


# ─────────────────────────────────────────────────────────────────────────────
# Línea de VISTA PREVIA
# ─────────────────────────────────────────────────────────────────────────────
class EmployeeImportPreview(models.TransientModel):
    _name = 'mx.jandea.employee.import.preview'
    _description = 'Vista previa de importación de empleado'
    _order = 'row_number'

    wizard_id = fields.Many2one('mx.jandea.employee.import.wizard', ondelete='cascade')
    row_number = fields.Integer(string='Fila')
    full_name = fields.Char(string='Nombre')
    rfc = fields.Char(string='RFC')
    rfc_format_ok = fields.Boolean(string='RFC ✓')
    curp = fields.Char(string='CURP')
    nss = fields.Char(string='NSS')
    f_ingreso = fields.Date(string='Fecha ingreso')
    periodicidad = fields.Char(string='Periodicidad')
    monto_periodo = fields.Float(string='Monto/periodo')
    categoria_pago = fields.Char(string='Categoría de pago')
    banco = fields.Char(string='Banco')
    cuenta_clabe = fields.Char(string='Cuenta/CLABE')
    planned_action = fields.Selection([
        ('new', 'Crear'), ('update', 'Actualizar'), ('skip', 'Omitir'),
    ], string='Acción')
    observaciones = fields.Char(string='Observaciones')


# ─────────────────────────────────────────────────────────────────────────────
# Resultado de importación
# ─────────────────────────────────────────────────────────────────────────────
class EmployeeImportResult(models.TransientModel):
    _name = 'mx.jandea.employee.import.result'
    _description = 'Resultado de importación de empleado'

    wizard_id = fields.Many2one('mx.jandea.employee.import.wizard', ondelete='cascade')
    row_number = fields.Integer(string='Fila')
    employee_name = fields.Char(string='Nombre')
    rfc = fields.Char(string='RFC')
    rfc_format_ok = fields.Boolean(string='RFC ✓')
    status = fields.Selection([
        ('created', 'Creado'), ('updated', 'Actualizado'),
        ('skipped', 'Omitido'), ('error', 'Error'),
    ], string='Resultado')
    message = fields.Char(string='Mensaje')
    employee_id = fields.Many2one('hr.employee', string='Empleado')

    checkid_selected = fields.Boolean(string='CheckId', default=False)
    checkid_status = fields.Selection([
        ('pending', 'Pendiente'), ('ok', 'OK'),
        ('warning', '⚠ Advertencia 69/69B'), ('error', 'Error'),
    ], string='Estado CheckId', default='pending')
    checkid_message = fields.Char(string='Resultado CheckId', readonly=True)
