# -*- coding: utf-8 -*-
import base64
import io
import logging
from datetime import datetime, date

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Mapa de columnas TEVA → índice (fila 0 = cabeceras)
# Basado en el archivo 01__ALTA_TEVA__1_.xls analizado
# ─────────────────────────────────────────────────────────────────────────────
COL = {
    'num':              0,
    'cliente':          1,
    'sucursal':         2,
    'estatus':          3,
    'esquema':          4,
    'rp':               5,
    'contrato':         6,
    'apellido_pat':     7,
    'apellido_mat':     8,
    'nombre':           9,
    'nombre_completo':  10,
    'revc':             11,
    'revdupli':         12,
    'fecha_nac':        13,
    'nacionalidad':     14,
    'estado_civil':     15,
    'genero':           16,
    'domicilio':        17,
    'calle':            18,
    'num_ext':          19,
    'colonia':          20,
    'cp':               21,
    'municipio':        22,
    'estado':           23,
    'correo':           24,
    'nss':              25,
    'nss_formulado':    26,
    'nss_dupli':        27,
    'rfc':              28,
    'rfc_formulado':    29,
    'rfc_dupli':        30,
    'curp':             31,
    'curp_formulado':   32,
    'curp_dupli':       33,
    'f_ingreso':        34,
    'f_antiguedad':     35,
    'puesto':           36,
    'desc_puesto':      37,
    'sueldo_mensual':   38,
    'sueldo_quincenal': 39,
    'sd':               40,
    'credito_infonavit':41,
    'factor_desc':      42,
    'pct_info':         43,
    'pesos_info':       44,
    'fonacot':          45,
    'retencion_fonacot':46,
    'banco':            47,
    'cuenta':           48,
    'tarjeta':          49,
    'clabe':            50,
    'f_baja':           51,
}

STATE_MAP = {
    'AGS': 'AGS', 'BC': 'BC', 'BCS': 'BCS', 'CAMP': 'CAMP', 'CDMX': 'CDMX',
    'CHIH': 'CHIH', 'CHIS': 'CHIS', 'COAH': 'COAH', 'COL': 'COL', 'DGO': 'DGO',
    'GTO': 'GTO', 'GRO': 'GRO', 'HGO': 'HGO', 'JAL': 'JAL', 'MEX': 'MEX',
    'MICH': 'MICH', 'MOR': 'MOR', 'NAY': 'NAY', 'NL': 'NL', 'OAX': 'OAX',
    'PUE': 'PUE', 'QRO': 'QRO', 'QROO': 'QROO', 'SLP': 'SLP', 'SIN': 'SIN',
    'SON': 'SON', 'TAB': 'TAB', 'TAMPS': 'TAMPS', 'TLAX': 'TLAX', 'VER': 'VER',
    'YUC': 'YUC', 'ZAC': 'ZAC',
}

GENDER_MAP = {
    'M': 'male', 'H': 'male', 'MASCULINO': 'male',
    'F': 'female', 'FEMENINO': 'female',
}

MARITAL_MAP = {
    'SOLTERO': 'single', 'SOLTERA': 'single', 'S': 'single',
    'CASADO': 'married', 'CASADA': 'married', 'C': 'married',
    'DIVORCIADO': 'divorced', 'DIVORCIADA': 'divorced', 'D': 'divorced',
    'VIUDO': 'widower', 'VIUDA': 'widower', 'V': 'widower',
}


def _val(row, col_name, default=''):
    """Extrae y limpia un valor de la fila por nombre de columna."""
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
    """Convierte el valor de fecha a date, soporta Excel serial y strings."""
    raw = _val(row, col_name)
    if not raw or raw in ('NaT',):
        return False
    # Intenta varios formatos comunes
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d', '%d/%m/%y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    # Número serial de Excel (xlrd lo retorna como float)
    try:
        import xlrd
        tup = xlrd.xldate_as_tuple(float(raw), 0)
        return date(*tup[:3])
    except Exception:
        pass
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Wizard
# ─────────────────────────────────────────────────────────────────────────────
class EmployeeImportWizard(models.TransientModel):
    _name = 'mx.employee.import.wizard'
    _description = 'Importación Masiva de Empleados - Formato TEVA'

    # ── Archivo ───────────────────────────────────────────────────────────────
    file_data = fields.Binary(string='Archivo XLS/XLSX', required=True, attachment=False)
    file_name = fields.Char(string='Nombre del archivo')

    # ── Configuración ─────────────────────────────────────────────────────────
    company_id = fields.Many2one(
        'res.company',
        string='Empresa destino',
        required=True,
        default=lambda self: self.env.company,
    )
    header_row = fields.Integer(
        string='Fila de encabezados (1 = primera fila)',
        default=1,
        help='Número de fila donde están los encabezados TEVA. Los datos inician en la siguiente.',
    )
    skip_duplicates = fields.Boolean(
        string='Omitir duplicados (mismo RFC/empresa)',
        default=True,
        help='Si está activo, los empleados ya existentes en esta empresa no se vuelven a crear.',
    )
    update_existing = fields.Boolean(
        string='Actualizar existentes',
        default=False,
        help='Si está activo (y Omitir duplicados también), actualiza los datos del empleado existente.',
    )
    validate_rfc_format = fields.Boolean(
        string='Validar formato RFC al importar',
        default=True,
    )
    link_multicompany = fields.Boolean(
        string='Vincular empleados multiempresa por RFC',
        default=True,
        help='Al terminar, busca empleados con el mismo RFC en otras empresas y los vincula.',
    )

    # ── Salario ───────────────────────────────────────────────────────────────
    salary_imss_pct = fields.Float(
        string='% Salario IMSS (del mensual)',
        default=100.0,
        digits=(5, 2),
        help='Porcentaje del sueldo mensual que corresponde a la parte IMSS. El resto se considera exento.',
    )

    # ── Resultados ────────────────────────────────────────────────────────────
    result_line_ids = fields.One2many(
        'mx.employee.import.result',
        'wizard_id',
        string='Resultados',
        readonly=True,
    )
    import_done = fields.Boolean(default=False, readonly=True)
    count_created = fields.Integer(string='Creados', readonly=True)
    count_updated = fields.Integer(string='Actualizados', readonly=True)
    count_skipped = fields.Integer(string='Omitidos', readonly=True)
    count_error = fields.Integer(string='Errores', readonly=True)

    # ──────────────────────────────────────────────────────────────────────────
    # Acción principal de importación
    # ──────────────────────────────────────────────────────────────────────────
    def action_import(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_('Seleccione un archivo XLS o XLSX para importar.'))

        # Leer el archivo con pandas
        try:
            import pandas as pd
        except ImportError:
            raise UserError(_('La librería pandas no está instalada en el servidor. Contacte al administrador.'))

        file_bytes = base64.b64decode(self.file_data)
        fname = (self.file_name or '').lower()

        try:
            if fname.endswith('.xls'):
                df = pd.read_excel(io.BytesIO(file_bytes), engine='xlrd', header=None)
            else:
                df = pd.read_excel(io.BytesIO(file_bytes), engine='openpyxl', header=None)
        except Exception as e:
            raise UserError(_(f'Error al leer el archivo: {e}'))

        # Descartar filas de encabezado
        data_rows = df.values[self.header_row:]  # fila 0 = cabeceras TEVA

        results = []
        created = updated = skipped = errors = 0

        for row_idx, row in enumerate(data_rows, start=self.header_row + 1):
            row_num = row_idx

            # Ignorar filas completamente vacías
            nombre = _val(row, 'nombre')
            apellido_pat = _val(row, 'apellido_pat')
            if not nombre and not apellido_pat:
                continue

            rfc = _val(row, 'rfc').upper().replace(' ', '')
            curp = _val(row, 'curp').upper().replace(' ', '')

            # ── Validación RFC formato ────────────────────────────────────────
            rfc_format_ok = False
            rfc_format_msg = ''
            if rfc and self.validate_rfc_format:
                rfc_format_ok, rfc_format_msg = self.env['hr.employee']._validate_rfc_format(rfc)
            elif rfc:
                rfc_format_ok = True  # no se valida pero se acepta

            # ── Buscar empleado existente ─────────────────────────────────────
            domain_dup = [
                ('mx_rfc', '=', rfc),
                ('company_id', '=', self.company_id.id),
            ]
            existing = self.env['hr.employee'].sudo().search(domain_dup, limit=1) if rfc else None

            if existing and self.skip_duplicates and not self.update_existing:
                results.append({
                    'row': row_num,
                    'name': f'{apellido_pat} {_val(row, "apellido_mat")} {nombre}'.strip(),
                    'rfc': rfc,
                    'status': 'skipped',
                    'message': _('Empleado ya existe en esta empresa (RFC duplicado).'),
                    'rfc_format_ok': rfc_format_ok,
                })
                skipped += 1
                continue

            # ── Preparar valores ──────────────────────────────────────────────
            try:
                vals = self._build_employee_vals(row, rfc, curp, rfc_format_ok)
            except Exception as e:
                results.append({
                    'row': row_num,
                    'name': f'{apellido_pat} {_val(row, "apellido_mat")} {nombre}'.strip(),
                    'rfc': rfc,
                    'status': 'error',
                    'message': str(e),
                    'rfc_format_ok': rfc_format_ok,
                })
                errors += 1
                continue

            # ── Crear o actualizar ────────────────────────────────────────────
            try:
                if existing and self.update_existing:
                    existing.sudo().write(vals)
                    emp = existing
                    action = 'updated'
                    updated += 1
                else:
                    emp = self.env['hr.employee'].sudo().with_company(self.company_id).create(vals)
                    action = 'created'
                    created += 1

                results.append({
                    'row': row_num,
                    'name': emp.name,
                    'rfc': rfc,
                    'status': action,
                    'message': _('OK'),
                    'employee_id': emp.id,
                    'rfc_format_ok': rfc_format_ok,
                })

            except Exception as e:
                _logger.error('Error al crear empleado fila %d: %s', row_num, e)
                results.append({
                    'row': row_num,
                    'name': f'{apellido_pat} {_val(row, "apellido_mat")} {nombre}'.strip(),
                    'rfc': rfc,
                    'status': 'error',
                    'message': str(e),
                    'rfc_format_ok': rfc_format_ok,
                })
                errors += 1

        # ── Vincular multiempresa ─────────────────────────────────────────────
        if self.link_multicompany:
            rfcs_procesados = {r['rfc'] for r in results if r.get('rfc') and r['status'] in ('created', 'updated')}
            for rfc in rfcs_procesados:
                self.env['hr.employee']._link_multicompany_by_rfc(rfc)

        # ── Guardar resultados ────────────────────────────────────────────────
        result_records = []
        for r in results:
            result_records.append((0, 0, {
                'wizard_id': self.id,
                'row_number': r['row'],
                'employee_name': r['name'],
                'rfc': r['rfc'],
                'status': r['status'],
                'message': r['message'],
                'employee_id': r.get('employee_id', False),
                'rfc_format_ok': r.get('rfc_format_ok', False),
            }))

        self.write({
            'result_line_ids': result_records,
            'import_done': True,
            'count_created': created,
            'count_updated': updated,
            'count_skipped': skipped,
            'count_error': errors,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mx.employee.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Constructor de vals para hr.employee
    # ──────────────────────────────────────────────────────────────────────────
    def _build_employee_vals(self, row, rfc, curp, rfc_format_ok):
        nombre = _val(row, 'nombre')
        ap_pat = _val(row, 'apellido_pat')
        ap_mat = _val(row, 'apellido_mat')
        full_name = f'{ap_pat} {ap_mat} {nombre}'.strip()

        # Salario
        sueldo_mensual = _float_val(row, 'sueldo_mensual')
        sueldo_quincenal = _float_val(row, 'sueldo_quincenal')
        sd = _float_val(row, 'sd')

        # Calcular partes IMSS / exento
        pct = self.salary_imss_pct / 100.0
        salary_imss = round(sueldo_mensual * pct, 2)
        salary_exempt = round(sueldo_mensual * (1 - pct), 2)

        # Género

        # Estado civil
        civil_raw = _val(row, 'estado_civil').upper()
        marital = MARITAL_MAP.get(civil_raw, 'single')

        vals = {
            'name': full_name,
            'company_id': self.company_id.id,
            # Datos fiscales
            'mx_rfc': rfc or False,
            'mx_curp': curp or False,
            'rfc_validated_format': rfc_format_ok,
            # Datos personales
            'birthday': _date_val(row, 'fecha_nac') or False,
            'marital': marital,
            'work_email': _val(row, 'correo') or False,
            # TEVA meta
            'teva_cliente': _val(row, 'cliente') or False,
            'teva_sucursal': _val(row, 'sucursal') or False,
            'teva_estatus': _val(row, 'estatus') or False,
            'teva_esquema': _val(row, 'esquema') or False,
            'teva_rp': _val(row, 'rp') or False,
            'teva_contrato': _val(row, 'contrato') or False,
            'teva_puesto': _val(row, 'puesto') or False,
            'teva_descripcion_puesto': _val(row, 'desc_puesto') or False,
            # NSS
            'nss': _val(row, 'nss') or False,
            # Salario
            'salary_monthly': sueldo_mensual,
            'salary_biweekly': sueldo_quincenal,
            'salary_daily': sd,
            'salary_imss': salary_imss,
            'salary_exempt': salary_exempt,
            # Créditos
            'infonavit_credit': _val(row, 'credito_infonavit') or False,
            'infonavit_factor': _val(row, 'factor_desc') or False,
            'infonavit_pct': _float_val(row, 'pct_info'),
            'infonavit_pesos': _float_val(row, 'pesos_info'),
            'fonacot_retention': _float_val(row, 'retencion_fonacot'),
            # Banco
            'bank_name': _val(row, 'banco') or False,
            'bank_account_number': _val(row, 'cuenta') or False,
            'bank_card_number': _val(row, 'tarjeta') or False,
            'bank_clabe': _val(row, 'clabe') or False,
            # Fechas laborales
            'fecha_antiguedad': _date_val(row, 'f_antiguedad') or False,
            'fecha_baja': _date_val(row, 'f_baja') or False,
        }

        # Fecha de ingreso → date de contrato
        f_ingreso = _date_val(row, 'f_ingreso')
        if f_ingreso:
            vals['contract_ids'] = [(0, 0, {
                'name': f'Contrato {full_name}',
                'date_start': f_ingreso,
                'wage': sueldo_mensual,
                'company_id': self.company_id.id,
            })]

        # Dirección privada (res.partner)
        calle = _val(row, 'calle')
        num_ext = _val(row, 'num_ext')
        colonia = _val(row, 'colonia')
        cp = _val(row, 'cp')
        municipio = _val(row, 'municipio')
        estado = _val(row, 'estado')

        if any([calle, colonia, cp, municipio, estado]):
            street = f'{calle} {num_ext}'.strip() if calle else ''
            country_mx = self.env.ref('base.mx', raise_if_not_found=False)
            private_partner_vals = {
                'name': full_name,
                'street': street or False,
                'street2': colonia or False,
                'zip': cp or False,
                'city': municipio or False,
                'country_id': country_mx.id if country_mx else False,
                'email': _val(row, 'correo') or False,
                'type': 'contact',
            }
            # Buscar estado de México por nombre/clave
            if estado:
                state_rec = self.env['res.country.state'].search([
                    ('country_id.code', '=', 'MX'),
                    '|',
                    ('name', 'ilike', estado),
                    ('code', 'ilike', estado),
                ], limit=1)
                if state_rec:
                    private_partner_vals['state_id'] = state_rec.id

            partner = self.env['res.partner'].sudo().create(private_partner_vals)
            vals['address_home_id'] = partner.id

        return vals

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
# Modelo de resultados (líneas del wizard)
# ─────────────────────────────────────────────────────────────────────────────
class EmployeeImportResult(models.TransientModel):
    _name = 'mx.employee.import.result'
    _description = 'Resultado de importación de empleado'

    wizard_id = fields.Many2one('mx.employee.import.wizard', ondelete='cascade')
    row_number = fields.Integer(string='Fila')
    employee_name = fields.Char(string='Nombre')
    rfc = fields.Char(string='RFC')
    rfc_format_ok = fields.Boolean(string='RFC Formato OK')
    status = fields.Selection([
        ('created', 'Creado'),
        ('updated', 'Actualizado'),
        ('skipped', 'Omitido'),
        ('error', 'Error'),
    ], string='Resultado')
    message = fields.Char(string='Mensaje')
    employee_id = fields.Many2one('hr.employee', string='Empleado')
