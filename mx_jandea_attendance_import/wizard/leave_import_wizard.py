# -*- coding: utf-8 -*-
"""
mx_jandea_attendance_import / wizard / leave_import_wizard.py

Wizard para importación masiva de faltas desde Excel/CSV.

Columnas esperadas (en cualquier orden, por nombre de cabecera):
  rfc          → identifica al empleado (mx_rfc del módulo de empleados)
  tipo_falta   → código mx_code del hr.leave.type (ej: FALT_INJ, RETARDO)
  fecha_inicio → DD/MM/YYYY o YYYY-MM-DD
  fecha_fin    → DD/MM/YYYY o YYYY-MM-DD (puede ser igual a fecha_inicio)
  horas        → float, opcional (obligatorio si el tipo requiere horas)
  motivo       → texto libre, opcional

Flujo:
  1. Usuario sube el archivo → [Vista previa]
  2. Se muestra tabla editable con los registros detectados
  3. Usuario puede corregir directamente en la tabla
  4. [Confirmar importación] → crea hr.leave por cada línea válida
  5. Resumen: creados / errores / empleados no encontrados
"""
import base64
import io
import logging
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

FECHA_FORMATOS = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d', '%d/%m/%y']


def _parse_date(raw):
    """Convierte string de fecha a date. Retorna False si no puede parsear."""
    raw = str(raw or '').strip()
    if not raw or raw in ('nan', 'NaT', 'None'):
        return False
    for fmt in FECHA_FORMATOS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    # Número serial Excel
    try:
        import xlrd
        tup = xlrd.xldate_as_tuple(float(raw), 0)
        from datetime import date
        return date(*tup[:3])
    except Exception:
        pass
    return False


def _clean(val, default=''):
    """Limpia un valor de celda pandas."""
    if val is None:
        return default
    s = str(val).strip()
    return default if s in ('nan', 'NaT', 'None', '') else s


# ─────────────────────────────────────────────────────────────────────────────
# Wizard principal
# ─────────────────────────────────────────────────────────────────────────────
class LeaveImportWizard(models.TransientModel):
    _name = 'mx.jandea.leave.import.wizard'
    _description = 'Importación Masiva de Faltas'

    # ── Paso 1: archivo ───────────────────────────────────────────────────────
    file_data = fields.Binary(string='Archivo Excel / CSV', required=True, attachment=False)
    file_name = fields.Char(string='Nombre del archivo')

    # ── Configuración ─────────────────────────────────────────────────────────
    company_id = fields.Many2one(
        'res.company', string='Empresa',
        required=True, default=lambda self: self.env.company,
    )
    mode = fields.Selection([
        ('draft',    'Guardar como borrador (requiere aprobación)'),
        ('validate', 'Aprobar directamente'),
    ], string='Modo de importación', default='draft', required=True,
        help='Borrador: las faltas quedan pendientes de aprobación.\n'
             'Aprobar directamente: solo disponible para Gerentes de RRHH.',
    )

    # ── Estado del wizard ─────────────────────────────────────────────────────
    state = fields.Selection([
        ('upload',  'Subir archivo'),
        ('preview', 'Vista previa'),
        ('done',    'Completado'),
    ], default='upload', readonly=True)

    # ── Líneas de vista previa ────────────────────────────────────────────────
    line_ids = fields.One2many(
        'mx.jandea.leave.import.line', 'wizard_id',
        string='Registros a importar',
    )

    # ── Resumen ───────────────────────────────────────────────────────────────
    count_ok      = fields.Integer(string='Creados', readonly=True)
    count_error   = fields.Integer(string='Errores', readonly=True)
    count_warning = fields.Integer(string='Advertencias', readonly=True)

    # ──────────────────────────────────────────────────────────────────────────
    # PASO 1 → Vista previa: leer archivo y generar líneas editables
    # ──────────────────────────────────────────────────────────────────────────
    def action_preview(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_('Selecciona un archivo Excel o CSV.'))

        try:
            import pandas as pd
        except ImportError:
            raise UserError(_('pandas no está instalado en el servidor.'))

        file_bytes = base64.b64decode(self.file_data)
        fname = (self.file_name or '').lower()

        try:
            if fname.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
            elif fname.endswith('.xls'):
                df = pd.read_excel(io.BytesIO(file_bytes), engine='xlrd', dtype=str)
            else:
                df = pd.read_excel(io.BytesIO(file_bytes), engine='openpyxl', dtype=str)
        except Exception as e:
            raise UserError(_(f'Error al leer el archivo: {e}'))

        # Normalizar nombres de columnas (minúsculas, sin espacios)
        df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]

        required_cols = {'rfc', 'tipo_falta', 'fecha_inicio', 'fecha_fin'}
        missing = required_cols - set(df.columns)
        if missing:
            raise UserError(_(
                f'Faltan columnas en el archivo: {", ".join(sorted(missing))}\n'
                f'Columnas encontradas: {", ".join(df.columns)}'
            ))

        # Eliminar líneas existentes
        self.line_ids.unlink()

        # Cargar catálogo de tipos por código
        tipos = {
            t.mx_code: t
            for t in self.env['hr.leave.type'].sudo().search([
                ('mx_code', '!=', False),
            ])
        }

        # Cargar empleados por RFC
        empleados = {
            e.mx_rfc: e
            for e in self.env['hr.employee'].sudo().search([
                ('mx_rfc', '!=', False),
                ('company_id', '=', self.company_id.id),
            ])
            if e.mx_rfc
        }

        lines_vals = []
        for idx, row in df.iterrows():
            rfc         = _clean(row.get('rfc', '')).upper().replace(' ', '')
            tipo_code   = _clean(row.get('tipo_falta', '')).upper().strip()
            fecha_ini   = _parse_date(row.get('fecha_inicio', ''))
            fecha_fin   = _parse_date(row.get('fecha_fin', ''))
            horas_raw   = _clean(row.get('horas', ''))
            motivo      = _clean(row.get('motivo', ''))

            # Validar datos
            errores = []
            emp = empleados.get(rfc)
            if not rfc:
                errores.append('RFC vacío')
            elif not emp:
                errores.append(f'RFC {rfc} no encontrado en esta empresa')

            tipo = tipos.get(tipo_code)
            if not tipo_code:
                errores.append('tipo_falta vacío')
            elif not tipo:
                errores.append(f'Tipo "{tipo_code}" no existe (ver catálogo)')

            if not fecha_ini:
                errores.append('fecha_inicio inválida')
            if not fecha_fin:
                errores.append('fecha_fin inválida')
            elif fecha_ini and fecha_fin < fecha_ini:
                errores.append('fecha_fin es anterior a fecha_inicio')

            horas = 0.0
            if horas_raw:
                try:
                    horas = float(horas_raw)
                except ValueError:
                    errores.append(f'Horas inválidas: "{horas_raw}"')

            if tipo and tipo.mx_requires_hours and not horas:
                errores.append(f'El tipo {tipo_code} requiere indicar horas')

            status = 'error' if errores else 'ok'
            msg    = '; '.join(errores) if errores else 'Listo para importar'

            lines_vals.append({
                'wizard_id':    self.id,
                'row_number':   idx + 2,
                'rfc':          rfc,
                'employee_id':  emp.id if emp else False,
                'tipo_code':    tipo_code,
                'leave_type_id': tipo.id if tipo else False,
                'fecha_inicio': fecha_ini or False,
                'fecha_fin':    fecha_fin or False,
                'horas':        horas,
                'motivo':       motivo,
                'status':       status,
                'message':      msg,
            })

        self.env['mx.jandea.leave.import.line'].create(lines_vals)

        self.state = 'preview'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mx.jandea.leave.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ──────────────────────────────────────────────────────────────────────────
    # PASO 2 → Confirmar: crear hr.leave por cada línea válida
    # ──────────────────────────────────────────────────────────────────────────
    def action_confirm(self):
        self.ensure_one()

        lines_ok = self.line_ids.filtered(lambda l: l.status == 'ok')
        if not lines_ok:
            raise UserError(_(
                'No hay registros válidos para importar. '
                'Revisa los errores en la tabla.'
            ))

        ok = errors = warnings = 0

        for line in lines_ok:
            try:
                # Construir fechas con hora (hr.leave requiere datetime)
                date_from = datetime.combine(line.fecha_inicio, datetime.min.time().replace(hour=8))
                date_to   = datetime.combine(line.fecha_fin,   datetime.min.time().replace(hour=17))

                leave_vals = {
                    'employee_id':      line.employee_id.id,
                    'holiday_status_id': line.leave_type_id.id,
                    'date_from':        date_from,
                    'date_to':          date_to,
                    'name':             line.motivo or line.tipo_code,
                    'mx_horas_parciales': line.horas,
                    'mx_motivo':        line.motivo,
                    'mx_origen':        'importacion',
                }

                leave = self.env['hr.leave'].sudo().with_company(self.company_id).create(leave_vals)

                if self.mode == 'validate':
                    leave.sudo().action_validate()

                line.write({
                    'status':   'imported',
                    'message':  'Creada' if self.mode == 'draft' else 'Aprobada',
                    'leave_id': leave.id,
                })
                ok += 1

            except Exception as e:
                _logger.error('Error creando falta línea %d: %s', line.row_number, e)
                line.write({'status': 'error', 'message': repr(e)[:200]})
                errors += 1

        self.write({
            'state':         'done',
            'count_ok':      ok,
            'count_error':   errors,
            'count_warning': warnings,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mx.jandea.leave.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back(self):
        """Volver al paso de subir archivo para cargar otro."""
        self.line_ids.unlink()
        self.state = 'upload'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mx.jandea.leave.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}

    def action_open_leaves(self):
        leave_ids = self.line_ids.filtered('leave_id').mapped('leave_id').ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('Faltas Importadas'),
            'res_model': 'hr.leave',
            'view_mode': 'list,form',
            'domain': [('id', 'in', leave_ids)],
            'target': 'current',
        }


# ─────────────────────────────────────────────────────────────────────────────
# Líneas del wizard (vista previa editable)
# ─────────────────────────────────────────────────────────────────────────────
class LeaveImportLine(models.TransientModel):
    _name = 'mx.jandea.leave.import.line'
    _description = 'Línea de importación de falta'

    wizard_id    = fields.Many2one('mx.jandea.leave.import.wizard', ondelete='cascade')
    row_number   = fields.Integer(string='Fila', readonly=True)

    # Datos editables en la vista previa
    rfc          = fields.Char(string='RFC')
    employee_id  = fields.Many2one('hr.employee', string='Empleado')
    tipo_code    = fields.Char(string='Código tipo')
    leave_type_id = fields.Many2one('hr.leave.type', string='Tipo de falta')
    fecha_inicio = fields.Date(string='Fecha inicio')
    fecha_fin    = fields.Date(string='Fecha fin')
    horas        = fields.Float(string='Horas', digits=(5, 2))
    motivo       = fields.Char(string='Motivo')

    # Estado de cada línea
    status = fields.Selection([
        ('ok',       'Listo'),
        ('error',    'Error'),
        ('imported', 'Importado'),
    ], string='Estado', default='ok', readonly=True)
    message  = fields.Char(string='Mensaje', readonly=True)
    leave_id = fields.Many2one('hr.leave', string='Falta creada', readonly=True)
