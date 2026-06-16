# -*- coding: utf-8 -*-
"""
mx_jandea_employee_import / wizard / employee_import_wizard.py

Wizard de importación masiva desde plantilla TEVA (52 columnas IMSS).

Flujo de uso:
  1. Usuario sube el archivo XLS/XLSX y configura opciones → [Importar Empleados]
  2. Se muestra el resumen (creados/actualizados/omitidos/errores) y la tabla
     de resultados con una columna "checkid_selected" (checkbox).
  3. Si mx_jandea_checkid está instalado, aparece el botón
     [✓ Validar seleccionados con CheckId] que procesa SOLO los registros
     que el usuario haya marcado en la tabla.
  4. Al terminar muestra el resultado de CheckId por registro.
"""
import base64
import io
import logging
from datetime import datetime, date

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Mapa de columnas TEVA → índice (base 0)
# ─────────────────────────────────────────────────────────────────────────────
COL = {
    'num':               0,
    'cliente':           1,
    'sucursal':          2,
    'estatus':           3,
    'esquema':           4,
    'rp':                5,
    'contrato':          6,
    'apellido_pat':      7,
    'apellido_mat':      8,
    'nombre':            9,
    'nombre_completo':   10,
    'revc':              11,
    'revdupli':          12,
    'fecha_nac':         13,
    'nacionalidad':      14,
    'estado_civil':      15,
    'genero':            16,
    'domicilio':         17,
    'calle':             18,
    'num_ext':           19,
    'colonia':           20,
    'cp':                21,
    'municipio':         22,
    'estado':            23,
    'correo':            24,
    'nss':               25,
    'nss_formulado':     26,
    'nss_dupli':         27,
    'rfc':               28,
    'rfc_formulado':     29,
    'rfc_dupli':         30,
    'curp':              31,
    'curp_formulado':    32,
    'curp_dupli':        33,
    'f_ingreso':         34,
    'f_antiguedad':      35,
    'puesto':            36,
    'desc_puesto':       37,
    'sueldo_mensual':    38,
    'sueldo_quincenal':  39,
    'sd':                40,
    'credito_infonavit': 41,
    'factor_desc':       42,
    'pct_info':          43,
    'pesos_info':        44,
    'fonacot':           45,
    'retencion_fonacot': 46,
    'banco':             47,
    'cuenta':            48,
    'tarjeta':           49,
    'clabe':             50,
    'f_baja':            51,
}

GENDER_MAP = {
    'M': 'male', 'H': 'male', 'MASCULINO': 'male',
    'F': 'female', 'FEMENINO': 'female',
}
MARITAL_MAP = {
    'SOLTERO': 'single',  'SOLTERA': 'single',  'S': 'single',
    'CASADO': 'married',  'CASADA': 'married',  'C': 'married',
    'DIVORCIADO': 'divorced', 'DIVORCIADA': 'divorced', 'D': 'divorced',
    'VIUDO': 'widower',   'VIUDA': 'widower',   'V': 'widower',
    'U': 'single',
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
# Helpers de extracción de celda
# ─────────────────────────────────────────────────────────────────────────────
def _val(row, col_name, default=''):
    try:
        v = row[COL[col_name]]
        if v is None or str(v).strip() in ('nan', 'NaT', 'None', ''):
            return default
        return str(v).strip()
    except (IndexError, KeyError):
        return default


def _float_val(row, col_name, default=0.0):
    try:
        v = row[COL[col_name]]
        if v is None or str(v).strip() in ('nan', 'NaT', 'None', ''):
            return default
        return float(v)
    except (IndexError, KeyError, ValueError, TypeError):
        return default


def _date_val(row, col_name):
    raw = _val(row, col_name)
    if not raw or raw == 'NaT':
        return False
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d', '%d/%m/%y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    try:
        import xlrd
        tup = xlrd.xldate_as_tuple(float(raw), 0)
        return date(*tup[:3])
    except Exception:
        pass
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Wizard principal
# ─────────────────────────────────────────────────────────────────────────────
class EmployeeImportWizard(models.TransientModel):
    _name = 'mx.jandea.employee.import.wizard'
    _description = 'Importación Masiva de Empleados - Formato TEVA (IMSS)'

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
        help='Número de fila donde están los encabezados TEVA. Los datos inician en la siguiente.',
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

    # Contadores para mostrar cuántos están seleccionados
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
    # Acción principal de importación
    # ──────────────────────────────────────────────────────────────────────────
    def action_import(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_('Seleccione un archivo XLS o XLSX para importar.'))

        try:
            import pandas as pd
        except ImportError:
            raise UserError(_(
                'La librería pandas no está instalada en el servidor. '
                'Contacte al administrador.'
            ))

        file_bytes = base64.b64decode(self.file_data)
        fname = (self.file_name or '').lower()

        try:
            if fname.endswith('.xls'):
                df = pd.read_excel(io.BytesIO(file_bytes), engine='xlrd', header=None)
            else:
                df = pd.read_excel(io.BytesIO(file_bytes), engine='openpyxl', header=None)
        except Exception as e:
            raise UserError(_(f'Error al leer el archivo: {e}'))

        data_rows = df.values[self.header_row:]
        results = []
        created = updated = skipped = errors = 0

        for row_idx, row in enumerate(data_rows, start=self.header_row + 1):
            nombre = _val(row, 'nombre')
            apellido_pat = _val(row, 'apellido_pat')
            if not nombre and not apellido_pat:
                continue

            rfc = _val(row, 'rfc').upper().replace(' ', '')
            full_name = f'{apellido_pat} {_val(row, "apellido_mat")} {nombre}'.strip()

            # Validación RFC
            rfc_format_ok = False
            if rfc and self.validate_rfc_format:
                rfc_format_ok, _ = self.env['hr.employee']._validate_rfc_format(rfc)
            elif rfc:
                rfc_format_ok = True

            # Duplicado
            existing = False
            if rfc:
                existing = self.env['hr.employee'].sudo().search([
                    ('mx_rfc', '=', rfc),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)

            if existing and self.skip_duplicates and not self.update_existing:
                results.append({
                    'row': row_idx, 'name': full_name, 'rfc': rfc,
                    'status': 'skipped',
                    'message': _('Empleado ya existe (RFC duplicado en esta empresa).'),
                    'rfc_format_ok': rfc_format_ok,
                    'employee_id': existing.id,
                    # Los omitidos también pueden seleccionarse para CheckId
                    'checkid_selected': False,
                })
                skipped += 1
                continue

            # Preparar vals
            try:
                vals = self._build_employee_vals(row, rfc, rfc_format_ok)
            except Exception as e:
                results.append({
                    'row': row_idx, 'name': full_name, 'rfc': rfc,
                    'status': 'error', 'message': str(e),
                    'rfc_format_ok': rfc_format_ok,
                    'checkid_selected': False,
                })
                errors += 1
                continue

            # Crear o actualizar
            try:
                if existing and self.update_existing:
                    existing.sudo().write(vals)
                    emp = existing
                    action = 'updated'
                    updated += 1
                else:
                    emp = (
                        self.env['hr.employee']
                        .sudo()
                        .with_company(self.company_id)
                        .create(vals)
                    )
                    action = 'created'
                    created += 1

                results.append({
                    'row': row_idx, 'name': emp.name, 'rfc': rfc,
                    'status': action, 'message': _('OK'),
                    'employee_id': emp.id,
                    'rfc_format_ok': rfc_format_ok,
                    # Pre-seleccionar para CheckId solo los creados/actualizados
                    'checkid_selected': True,
                })

            except Exception as e:
                _logger.error('Error al crear empleado fila %d: %s', row_idx, e)
                results.append({
                    'row': row_idx, 'name': full_name, 'rfc': rfc,
                    'status': 'error', 'message': str(e),
                    'rfc_format_ok': rfc_format_ok,
                    'checkid_selected': False,
                })
                errors += 1

        # Vincular multiempresa
        if self.link_multicompany:
            rfcs_ok = {
                r['rfc'] for r in results
                if r.get('rfc') and r['status'] in ('created', 'updated')
            }
            for rfc in rfcs_ok:
                self.env['hr.employee']._link_multicompany_by_rfc(rfc)

        # Guardar resultados
        self.write({
            'result_line_ids': [
                (0, 0, {
                    'wizard_id': self.id,
                    'row_number': r['row'],
                    'employee_name': r['name'],
                    'rfc': r['rfc'],
                    'status': r['status'],
                    'message': r['message'],
                    'employee_id': r.get('employee_id', False),
                    'rfc_format_ok': r.get('rfc_format_ok', False),
                    'checkid_selected': r.get('checkid_selected', False),
                    'checkid_status': 'pending',
                })
                for r in results
            ],
            'import_done': True,
            'count_created': created,
            'count_updated': updated,
            'count_skipped': skipped,
            'count_error': errors,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mx.jandea.employee.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Construcción de vals → campos nativos Odoo 17
    # ──────────────────────────────────────────────────────────────────────────
    def _build_employee_vals(self, row, rfc, rfc_format_ok):
        nombre = _val(row, 'nombre')
        ap_pat = _val(row, 'apellido_pat')
        ap_mat = _val(row, 'apellido_mat')
        full_name = f'{ap_pat} {ap_mat} {nombre}'.strip()

        vals = {
            'name': full_name,
            'company_id': self.company_id.id,
        }

        # Campos fiscales MX (custom)
        curp = _val(row, 'curp').upper().replace(' ', '')
        if rfc:
            vals['mx_rfc'] = rfc
            vals['rfc_validated_format'] = rfc_format_ok
        if curp:
            vals['mx_curp'] = curp
            vals['identification_id'] = curp

        nss_raw = _val(row, 'nss')
        if nss_raw:
            vals['nss'] = nss_raw
            vals['ssnid'] = nss_raw

        # Correo
        correo = _val(row, 'correo')
        if correo:
            vals['work_email'] = correo

        # Género
        genero = GENDER_MAP.get(_val(row, 'genero').upper())
        if genero:
            vals['gender'] = genero

        # Estado civil
        marital = MARITAL_MAP.get(_val(row, 'estado_civil').upper())
        if marital:
            vals['marital'] = marital

        # Fecha de nacimiento
        fnac = _date_val(row, 'fecha_nac')
        if fnac:
            vals['birthday'] = fnac

        # Domicilio privado
        calle = _val(row, 'calle')
        num_ext = _val(row, 'num_ext')
        colonia = _val(row, 'colonia')
        private_street = ' '.join(filter(None, [calle, num_ext]))
        if colonia:
            private_street = f'{private_street}, {colonia}' if private_street else colonia
        if private_street:
            vals['private_street'] = private_street

        ciudad = _val(row, 'municipio')
        if ciudad:
            vals['private_city'] = ciudad

        cp = _val(row, 'cp')
        if cp:
            vals['private_zip'] = cp

        estado_raw = _val(row, 'estado').upper()
        if estado_raw:
            state_name = STATE_ABBR.get(estado_raw, estado_raw)
            mx_country = self.env.ref('base.mx', raise_if_not_found=False)
            if mx_country:
                state = self.env['res.country.state'].sudo().search([
                    ('country_id', '=', mx_country.id),
                    '|',
                    ('name', 'ilike', state_name),
                    ('code', '=ilike', estado_raw),
                ], limit=1)
                if state:
                    vals['private_state_id'] = state.id
                    vals['private_country_id'] = mx_country.id

        # Fecha ingreso → contract_date_start
        f_ingreso = _date_val(row, 'f_ingreso')
        if f_ingreso:
            vals['contract_date_start'] = f_ingreso

        # Puesto → job_title
        puesto = _val(row, 'desc_puesto') or _val(row, 'puesto')
        if puesto:
            vals['job_title'] = puesto

        # Salario → wage
        sueldo = _float_val(row, 'sueldo_mensual')
        if sueldo:
            vals['wage'] = sueldo

        return vals

    # ──────────────────────────────────────────────────────────────────────────
    # Selección masiva de CheckId
    # ──────────────────────────────────────────────────────────────────────────
    def action_select_all_checkid(self):
        """Marca todos los registros con empleado vinculado para CheckId."""
        self.ensure_one()
        seleccionables = self.result_line_ids.filtered(
            lambda l: l.employee_id and l.status in ('created', 'updated', 'skipped')
        )
        seleccionables.write({'checkid_selected': True})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mx.jandea.employee.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_deselect_all_checkid(self):
        """Desmarca todos los registros."""
        self.ensure_one()
        self.result_line_ids.write({'checkid_selected': False})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mx.jandea.employee.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Ejecutar CheckId sobre los seleccionados
    # ──────────────────────────────────────────────────────────────────────────
    def action_checkid_validate_selected(self):
        """
        Valida con CheckId SOLO los registros marcados con checkid_selected=True.
        Actualiza checkid_status en cada línea de resultado.
        """
        self.ensure_one()

        lines_selected = self.result_line_ids.filtered(
            lambda l: l.checkid_selected and l.employee_id
        )
        if not lines_selected:
            raise UserError(_(
                'No hay registros seleccionados para validar.\n'
                'Marca el checkbox ✓ en la columna "CheckId" de los empleados '
                'que deseas consultar.'
            ))

        ok = errors = 0
        for line in lines_selected:
            emp = line.employee_id
            # Determinar término: CURP preferente, luego RFC
            termino = ''
            curp = getattr(emp, 'mx_curp', '') or ''
            rfc = getattr(emp, 'mx_rfc', '') or ''
            if curp:
                termino = curp.strip().upper()
            elif rfc:
                termino = rfc.strip().upper()

            if not termino:
                line.write({
                    'checkid_status': 'error',
                    'checkid_message': _('Sin RFC ni CURP para consultar.'),
                })
                errors += 1
                continue

            try:
                emp._ejecutar_consulta_checkid(termino)
                # Reflejar estado real del empleado en la línea
                estado = getattr(emp, 'checkid_estado_consulta', 'ok')
                if estado == 'advertencia':
                    line.write({
                        'checkid_status': 'warning',
                        'checkid_message': _('⚠️ Problema 69/69B detectado.'),
                    })
                else:
                    line.write({
                        'checkid_status': 'ok',
                        'checkid_message': _('Consulta exitosa.'),
                    })
                ok += 1
            except Exception as e:
                _logger.warning('CheckId error para %s: %s', emp.name, e)
                line.write({
                    'checkid_status': 'error',
                    'checkid_message': str(e)[:200],
                })
                errors += 1

        self.write({
            'checkid_done': True,
            'checkid_count_ok': ok,
            'checkid_count_error': errors,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mx.jandea.employee.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

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
# Modelo de resultados — ahora con checkboxes y estado CheckId por línea
# ─────────────────────────────────────────────────────────────────────────────
class EmployeeImportResult(models.TransientModel):
    _name = 'mx.jandea.employee.import.result'
    _description = 'Resultado de importación de empleado TEVA'

    wizard_id = fields.Many2one('mx.jandea.employee.import.wizard', ondelete='cascade')
    row_number = fields.Integer(string='Fila')
    employee_name = fields.Char(string='Nombre')
    rfc = fields.Char(string='RFC')
    rfc_format_ok = fields.Boolean(string='RFC ✓')
    status = fields.Selection([
        ('created', 'Creado'),
        ('updated', 'Actualizado'),
        ('skipped', 'Omitido'),
        ('error', 'Error'),
    ], string='Resultado')
    message = fields.Char(string='Mensaje')
    employee_id = fields.Many2one('hr.employee', string='Empleado')

    # ── CheckId por línea ─────────────────────────────────────────────────────
    checkid_selected = fields.Boolean(
        string='CheckId',
        default=False,
        help='Marca este registro para validarlo con CheckId.',
    )
    checkid_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('ok', 'OK'),
        ('warning', '⚠ Advertencia 69/69B'),
        ('error', 'Error'),
    ], string='Estado CheckId', default='pending')
    checkid_message = fields.Char(string='Resultado CheckId', readonly=True)
