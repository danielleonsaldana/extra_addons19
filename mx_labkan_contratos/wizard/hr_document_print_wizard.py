# -*- coding: utf-8 -*-
import base64

from odoo import api, fields, models


MESES_ES = [
    'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO',
    'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE',
]


class HrDocumentPrintWizard(models.TransientModel):
    _name = 'hr.document.print.wizard'
    _description = 'Asistente para imprimir documentos del empleado'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)

    doc_type = fields.Selection([
        ('contrato', 'Contrato Individual de Trabajo'),
        ('alta', 'Formato de Alta'),
        ('baja', 'Formato de Baja'),
    ], string='Tipo de documento', required=True, default='contrato')

    template_id = fields.Many2one(
        'hr.document.template', string='Plantilla', required=True,
        domain="[('doc_type', '=', doc_type), "
               "'|', ('gender', '=', 'unisex'), ('gender', '=', genero)]",
    )
    genero = fields.Selection([
        ('hombre', 'Hombre'),
        ('mujer', 'Mujer'),
    ], string='Género (para filtrar plantilla)')

    # --- Campos editables que se inyectan en la plantilla como {{ }} ---
    nombre_trabajador = fields.Char('Nombre completo')
    estado_civil = fields.Char('Estado civil', default='SOLTERO(A)')
    rfc = fields.Char('RFC')
    curp = fields.Char('CURP')
    nss = fields.Char('Número de Seguridad Social')
    domicilio = fields.Char('Domicilio')
    puesto = fields.Char('Puesto')
    actividades = fields.Text('Actividades / funciones del puesto')
    dia = fields.Char('Día (inicio)')
    mes = fields.Char('Mes (inicio)')
    anio = fields.Char('Año (inicio)')
    salario_numero = fields.Char('Salario diario (número)')
    salario_letra = fields.Char('Salario diario (con letra)')
    periodicidad = fields.Selection([
        ('SEMANAL', 'Semanal'),
        ('QUINCENAL', 'Quincenal'),
        ('MENSUAL', 'Mensual'),
    ], string='Periodicidad de pago', default='QUINCENAL')
    fecha_firma = fields.Char('Fecha de firma (texto)')

    @api.onchange('employee_id', 'doc_type')
    def _onchange_employee_id(self):
        for w in self:
            if not w.employee_id:
                continue
            emp = w.employee_id
            w.nombre_trabajador = (emp.name or '').upper()
            w.rfc = getattr(emp, 'l10n_mx_rfc', False) or ''
            w.curp = getattr(emp, 'l10n_mx_curp', False) or ''
            w.nss = emp.ssnid or ''
            w.puesto = emp.job_id.name or ''
            w.domicilio = ' '.join(filter(None, [
                emp.private_street, emp.private_city, emp.private_state_id.name,
            ])) or ''
            date_start = emp.date_start
            if date_start:
                w.dia = str(date_start.day)
                w.mes = MESES_ES[date_start.month - 1]
                w.anio = str(date_start.year)
                w.fecha_firma = date_start.strftime('%d de %B de %Y')
            wage = emp.wage or 0.0
            if wage:
                w.salario_numero = '%.2f' % (wage / 30.0)

    def action_generate(self):
        self.ensure_one()
        ctx = {
            'nombre_trabajador': self.nombre_trabajador or '',
            'estado_civil': self.estado_civil or '',
            'rfc': self.rfc or '',
            'curp': self.curp or '',
            'nss': self.nss or '',
            'domicilio': self.domicilio or '',
            'puesto': self.puesto or '',
            'actividades': self.actividades or '',
            'dia': self.dia or '',
            'mes': self.mes or '',
            'anio': self.anio or '',
            'salario_numero': self.salario_numero or '',
            'salario_letra': self.salario_letra or '',
            'periodicidad': self.periodicidad or '',
            'fecha_firma': self.fecha_firma or '',
        }
        content = self.template_id._render(ctx)
        filename = '%s - %s.docx' % (self.template_id.name, self.employee_id.name)
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(content),
            'res_model': 'hr.employee',
            'res_id': self.employee_id.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
