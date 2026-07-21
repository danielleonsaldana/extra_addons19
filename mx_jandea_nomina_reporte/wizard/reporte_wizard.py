# -*- coding: utf-8 -*-
import base64
import io

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..models.reporte_map import COLUMNAS_REPORTE


class MxJandeaNominaReporteWizard(models.TransientModel):
    _name = 'mx.jandea.nomina.reporte.wizard'
    _description = 'Generar Listado de Nómina (Excel)'

    modo = fields.Selection(
        [('lote', 'Por lote de nómina'), ('mensual', 'Mensual (mes + empresa)')],
        string='Origen', required=True, default='lote',
    )
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Lote de nómina')
    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date('Desde')
    date_to = fields.Date('Hasta')

    archivo = fields.Binary('Archivo', readonly=True)
    nombre_archivo = fields.Char('Nombre', readonly=True)

    @api.onchange('payslip_run_id')
    def _onchange_run(self):
        if self.payslip_run_id:
            self.company_id = self.payslip_run_id.company_id
            self.date_from = self.payslip_run_id.date_start
            self.date_to = self.payslip_run_id.date_end

    # ------------------------------------------------------------------ #
    def _get_payslips(self):
        Payslip = self.env['hr.payslip'].sudo()
        if self.modo == 'lote':
            if not self.payslip_run_id:
                raise UserError(_('Selecciona un lote de nómina.'))
            slips = self.payslip_run_id.sudo().slip_ids
        else:
            if not (self.date_from and self.date_to):
                raise UserError(_('Indica el rango de fechas (Desde/Hasta).'))
            slips = Payslip.search([
                ('company_id', '=', self.company_id.id),
                ('date_from', '>=', self.date_from),
                ('date_to', '<=', self.date_to),
                ('state', 'not in', ('draft', 'cancel')),
            ])
        slips = slips.filtered(lambda s: s.state not in ('draft', 'cancel'))
        if not slips:
            raise UserError(_('No se encontraron recibos para el origen indicado.'))
        return slips.sorted(key=lambda s: (s.employee_id.name or ''))

    def _get_map(self):
        """dict columna -> [codes] considerando empresa (empresa gana a global)."""
        Map = self.env['mx.jandea.nomina.reporte.map'].sudo()
        recs = Map.search([
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id),
        ])
        result = {}
        # primero global, luego empresa (sobrescribe)
        for rec in recs.sorted(key=lambda r: 1 if r.company_id else 0):
            codes = [c.strip() for c in (rec.codes or '').split(',') if c.strip()]
            result[rec.columna] = codes
        return result

    @staticmethod
    def _emp_val(employee, *field_names):
        for fname in field_names:
            if fname in employee._fields:
                val = employee[fname]
                if val:
                    return val
        return ''

    def _build_row(self, payslip, mapa):
        emp = payslip.employee_id
        lines = payslip.line_ids

        code_totals = {}
        cat_totals = {}
        for l in lines:
            code_totals[l.code] = code_totals.get(l.code, 0.0) + l.total
            ccode = l.category_id.code
            if ccode:
                cat_totals[ccode] = cat_totals.get(ccode, 0.0) + l.total

        def suma_codes(columna, tipo):
            codes = mapa.get(columna) or []
            val = sum(code_totals.get(c, 0.0) for c in codes)
            return abs(val) if tipo == 'D' else val

        # Identificación
        clave = self._emp_val(emp, 'barcode', 'registration_number') or str(emp.id)
        rfc = self._emp_val(emp, 'mx_rfc', 'l10n_mx_rfc', 'vat')
        curp = self._emp_val(emp, 'mx_curp', 'l10n_mx_edi_curp')
        imss = self._emp_val(emp, 'nss', 'ssnid')

        # Días laborados
        wds = payslip.worked_days_line_ids
        dias = sum(wd.number_of_days for wd in wds if wd.code == 'WORK100')
        if not dias:
            dias = sum(wds.mapped('number_of_days'))

        # Sueldo real = salario del contrato/versión (mensual)
        version = getattr(payslip, 'version_id', False) or getattr(payslip, 'contract_id', False)
        sueldo_real = version.wage if version else 0.0

        row = {
            'clave': clave,
            'nombre': emp.name or '',
            'rfc': rfc,
            'curp': curp,
            'imss': imss,
            'dias': dias,
            'sueldo_real': sueldo_real,
            'total_percepciones': cat_totals.get('GROSS', 0.0),
        }
        for key, _label, tipo in COLUMNAS_REPORTE:
            if key == 'sueldo' and not mapa.get('sueldo'):
                row[key] = cat_totals.get('BASIC', 0.0)
            else:
                row[key] = suma_codes(key, tipo)
        return row

    # ------------------------------------------------------------------ #
    def action_generar(self):
        self.ensure_one()
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_('Falta la librería Python "xlsxwriter" en el servidor.'))

        slips = self._get_payslips()
        mapa = self._get_map()
        rows = [self._build_row(s, mapa) for s in slips]

        # Encabezados en el orden del ejemplo
        headers = ['Clave', 'Nombre completo', 'RFC', 'CURP', 'Afiliación IMSS',
                   'Días Laborados', 'Sueldo Real']
        perc = [(k, lbl) for (k, lbl, t) in COLUMNAS_REPORTE if t == 'P']
        ded = [(k, lbl) for (k, lbl, t) in COLUMNAS_REPORTE if t == 'D']
        headers += [lbl for (_k, lbl) in perc]
        headers += ['Total Percepciones']
        headers += [lbl for (_k, lbl) in ded]

        # Orden de claves para leer cada fila
        keys = ['clave', 'nombre', 'rfc', 'curp', 'imss', 'dias', 'sueldo_real']
        keys += [k for (k, _l) in perc]
        keys += ['total_percepciones']
        keys += [k for (k, _l) in ded]

        buffer = io.BytesIO()
        wb = xlsxwriter.Workbook(buffer, {'in_memory': True})
        ws = wb.add_worksheet('Nómina')

        f_title = wb.add_format({'bold': True, 'font_size': 13})
        f_sub = wb.add_format({'italic': True, 'font_color': '#666666'})
        f_head = wb.add_format({
            'bold': True, 'bg_color': '#1F4E78', 'font_color': 'white',
            'border': 1, 'text_wrap': True, 'valign': 'vcenter', 'align': 'center',
        })
        f_text = wb.add_format({'border': 1})
        f_num = wb.add_format({'border': 1, 'num_format': '#,##0.00'})
        f_int = wb.add_format({'border': 1, 'num_format': '0'})
        f_tot = wb.add_format({'bold': True, 'border': 1, 'num_format': '#,##0.00',
                               'bg_color': '#D9E1F2'})
        f_tot_lbl = wb.add_format({'bold': True, 'border': 1, 'bg_color': '#D9E1F2'})

        periodo = ''
        if self.modo == 'lote' and self.payslip_run_id:
            periodo = self.payslip_run_id.name
        elif self.date_from and self.date_to:
            periodo = '%s a %s' % (self.date_from, self.date_to)

        ws.write(0, 0, 'Listado de Nómina', f_title)
        ws.write(1, 0, '%s  |  %s  |  %s empleados' % (
            self.company_id.name, periodo, len(rows)), f_sub)

        head_row = 3
        for col, title in enumerate(headers):
            ws.write(head_row, col, title, f_head)

        # Anchos: identificación más ancha
        ws.set_column(0, 0, 8)
        ws.set_column(1, 1, 28)
        ws.set_column(2, 4, 16)
        ws.set_column(5, len(headers) - 1, 13)

        numeric_from = 5  # 'Días Laborados' en adelante son numéricos
        r = head_row + 1
        for row in rows:
            for col, key in enumerate(keys):
                val = row[key]
                if col < 5:
                    ws.write(r, col, val or '', f_text)
                elif key == 'dias':
                    ws.write_number(r, col, val or 0, f_int)
                else:
                    ws.write_number(r, col, val or 0.0, f_num)
            r += 1

        # Fila de totales
        ws.write(r, 0, 'TOTALES', f_tot_lbl)
        for col in range(1, len(keys)):
            if col < 5:
                ws.write(r, col, '', f_tot_lbl)
            elif keys[col] == 'dias':
                ws.write(r, col, '', f_tot_lbl)
            else:
                col_letter = xlsxwriter.utility.xl_col_to_name(col)
                ws.write_formula(
                    r, col,
                    '=SUM(%s%d:%s%d)' % (col_letter, head_row + 2, col_letter, r),
                    f_tot)

        ws.freeze_panes(head_row + 1, 2)
        wb.close()
        buffer.seek(0)

        fname = 'Listado_Nomina_%s.xlsx' % (periodo or fields.Date.today()).replace('/', '-').replace(' ', '_')
        self.write({
            'archivo': base64.b64encode(buffer.read()),
            'nombre_archivo': fname,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content?model=%s&id=%s&field=archivo&filename_field=nombre_archivo&download=true' % (
                self._name, self.id),
            'target': 'self',
        }
