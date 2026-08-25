# -*- coding: utf-8 -*-
import base64
from datetime import date

from odoo import api, fields, models


MESES_ES = [
    'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO',
    'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE',
]

# wage (Monto por Periodo) * factor = sueldo mensual aproximado.
FACTOR_MENSUAL = {
    'monthly': 1.0,
    'semi-monthly': 2.0,       # quincenal
    'bi-weekly': 26.0 / 12.0,  # catorcenal
    'weekly': 52.0 / 12.0,
    'daily': 30.0,
    'bi-monthly': 0.5,
    'quarterly': 1.0 / 3.0,
    'semi-annually': 1.0 / 6.0,
    'annually': 1.0 / 12.0,
}

# --------------------------------------------------------------------------
# Conversión de número a letras (español) sin dependencias externas.
# 20351.5 -> "VEINTE MIL TRESCIENTOS CINCUENTA Y UNO 50/100"
# --------------------------------------------------------------------------
_UNIDADES = ['', 'UNO', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE',
             'OCHO', 'NUEVE', 'DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE',
             'QUINCE', 'DIECISEIS', 'DIECISIETE', 'DIECIOCHO', 'DIECINUEVE',
             'VEINTE']
_DECENAS = ['', '', 'VEINTI', 'TREINTA', 'CUARENTA', 'CINCUENTA', 'SESENTA',
            'SETENTA', 'OCHENTA', 'NOVENTA']
_CENTENAS = ['', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS',
             'QUINIENTOS', 'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS',
             'NOVECIENTOS']


def _centenas_a_letras(n):
    """0..999 a letras."""
    if n == 0:
        return ''
    if n == 100:
        return 'CIEN'
    c, r = divmod(n, 100)
    partes = []
    if c:
        partes.append(_CENTENAS[c])
    if r:
        if r <= 20:
            partes.append(_UNIDADES[r])
        elif r < 30:
            partes.append('VEINTI' + _UNIDADES[r - 20])
        else:
            d, u = divmod(r, 10)
            partes.append(_DECENAS[d] + (' Y ' + _UNIDADES[u] if u else ''))
    return ' '.join(partes)


def _entero_a_letras(n):
    if n == 0:
        return 'CERO'
    millones, resto = divmod(n, 1_000_000)
    miles, cientos = divmod(resto, 1000)
    partes = []
    if millones:
        partes.append('UN MILLON' if millones == 1
                      else _centenas_a_letras(millones) + ' MILLONES')
    if miles:
        partes.append('MIL' if miles == 1
                      else _centenas_a_letras(miles) + ' MIL')
    if cientos:
        partes.append(_centenas_a_letras(cientos))
    return ' '.join(p for p in partes if p).strip()


def numero_a_letras(monto):
    """Importe a 'PALABRAS NN/100' en mayúsculas."""
    try:
        monto = float(monto or 0.0)
    except (TypeError, ValueError):
        return ''
    entero = int(monto)
    centavos = int(round((monto - entero) * 100))
    if centavos == 100:
        entero += 1
        centavos = 0
    return '%s %02d/100' % (_entero_a_letras(entero), centavos)


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

    # --- Datos generales (compatibles con plantillas Burdina/Krino) ---
    nombre_trabajador = fields.Char('Nombre completo')
    estado_civil = fields.Char('Estado civil', default='SOLTERO(A)')
    rfc = fields.Char('RFC')
    curp = fields.Char('CURP')
    nss = fields.Char('Número de Seguridad Social')
    domicilio = fields.Char('Domicilio (completo)')
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

    # --- Datos adicionales (Licencias Internacionales / tiempo determinado) ---
    apellido_paterno = fields.Char('Apellido paterno')
    apellido_materno = fields.Char('Apellido materno')
    nombres = fields.Char('Nombre(s)')
    nacionalidad = fields.Char('Nacionalidad', default='MEXICANA')
    edad = fields.Char('Edad')
    sexo = fields.Char('Sexo')
    calle_y_n = fields.Char('Calle y número')
    colonia = fields.Char('Colonia')
    cp = fields.Char('C.P.')
    municipio = fields.Char('Municipio / Alcaldía')
    estado = fields.Char('Estado')
    fecha_ingreso_texto = fields.Char('Fecha de ingreso (texto)')
    fecha_antiguedad_texto = fields.Char('Fecha de antigüedad reconocida (texto)')
    fecha_termino_texto = fields.Char('Fecha de término de contrato (texto)')
    vigencia_dias = fields.Char('Vigencia (p.ej. "30 DIAS")')
    sueldo_mensual = fields.Char('Sueldo mensual (número)')
    sueldo_letra = fields.Char('Sueldo mensual (con letra)')
    banco = fields.Char('Banco')
    clabe = fields.Char('CLABE interbancaria')
    sucursal = fields.Char('Sucursal')
    horario = fields.Char('Horario de trabajo')
    representante_legal = fields.Char(
        'Representante legal', default='JOSE MIGUEL MORALES ARANA')

    # -------------------------- helpers --------------------------
    @staticmethod
    def _fmt_fecha(d):
        if not d:
            return ''
        return '%02d DE %s DE %d' % (d.day, MESES_ES[d.month - 1], d.year)

    @staticmethod
    def _calcular_edad(nacimiento, ref=None):
        if not nacimiento:
            return ''
        ref = ref or date.today()
        edad = ref.year - nacimiento.year - (
            (ref.month, ref.day) < (nacimiento.month, nacimiento.day))
        return str(edad) if edad >= 0 else ''

    def _estado_civil_txt(self, emp):
        marital = getattr(emp, 'marital', False)
        fem = getattr(emp, 'gender', False) == 'female'
        base = {
            'single': ('SOLTERO', 'SOLTERA'),
            'married': ('CASADO', 'CASADA'),
            'cohabitant': ('UNIÓN LIBRE', 'UNIÓN LIBRE'),
            'widower': ('VIUDO', 'VIUDA'),
            'divorced': ('DIVORCIADO', 'DIVORCIADA'),
        }.get(marital)
        if not base:
            return 'SOLTERO(A)'
        return base[1] if fem else base[0]

    def _cuenta_bancaria(self, emp):
        acc = getattr(emp, 'bank_account_id', False)
        if not acc:
            accs = getattr(emp, 'bank_account_ids', False)
            if accs:
                acc = accs[0]
        if acc:
            banco = acc.bank_id.name if acc.bank_id else ''
            return (acc.acc_number or '', banco or '')
        return ('', '')

    def _sueldo_mensual(self, emp):
        wage = getattr(emp, 'wage', 0.0) or 0.0
        schedule = getattr(emp, 'schedule_pay', False)
        return wage * FACTOR_MENSUAL.get(schedule, 1.0)

    @api.onchange('employee_id', 'doc_type')
    def _onchange_employee_id(self):
        for w in self:
            emp = w.employee_id
            if not emp:
                continue

            nombre = (emp.name or '').strip().upper()
            w.nombre_trabajador = nombre
            toks = nombre.split()
            if len(toks) >= 3:
                w.apellido_paterno, w.apellido_materno = toks[0], toks[1]
                w.nombres = ' '.join(toks[2:])
            elif len(toks) == 2:
                w.apellido_paterno, w.apellido_materno, w.nombres = toks[0], '', toks[1]
            else:
                w.apellido_paterno, w.apellido_materno, w.nombres = nombre, '', ''

            w.rfc = (getattr(emp, 'mx_rfc', False)
                     or getattr(emp, 'l10n_mx_rfc', False) or '')
            w.curp = (getattr(emp, 'mx_curp', False)
                      or getattr(emp, 'l10n_mx_curp', False) or '')
            w.nss = (getattr(emp, 'nss', False)
                     or getattr(emp, 'ssnid', False) or '')

            pais = getattr(emp, 'country_id', False)
            if pais and getattr(pais, 'code', False) == 'MX':
                w.nacionalidad = 'MEXICANA'
            elif pais:
                w.nacionalidad = (pais.name or 'MEXICANA').upper()
            else:
                w.nacionalidad = 'MEXICANA'
            w.edad = self._calcular_edad(getattr(emp, 'birthday', False))
            g = getattr(emp, 'gender', False)
            w.sexo = 'FEMENINO' if g == 'female' else 'MASCULINO' if g == 'male' else ''
            w.estado_civil = self._estado_civil_txt(emp)

            calle = getattr(emp, 'private_street', '') or ''
            col = getattr(emp, 'private_street2', '') or ''
            cp = getattr(emp, 'private_zip', '') or ''
            ciudad = getattr(emp, 'private_city', '') or ''
            est_id = getattr(emp, 'private_state_id', False)
            est = est_id.name if est_id else ''
            w.calle_y_n, w.colonia, w.cp = calle, col, cp
            w.municipio, w.estado = ciudad, est
            w.domicilio = ', '.join([p for p in (calle, col, cp, ciudad, est) if p])

            w.puesto = (emp.job_id.name if emp.job_id else '') \
                or getattr(emp, 'job_title', '') or ''

            fecha_ini = (getattr(emp, 'contract_date_start', False)
                         or getattr(emp, 'date_start', False)
                         or getattr(emp, 'first_contract_date', False))
            if fecha_ini:
                w.dia = str(fecha_ini.day)
                w.mes = MESES_ES[fecha_ini.month - 1]
                w.anio = str(fecha_ini.year)
                w.fecha_firma = self._fmt_fecha(fecha_ini)
                w.fecha_ingreso_texto = self._fmt_fecha(fecha_ini)
            antig = getattr(emp, 'first_contract_date', False)
            w.fecha_antiguedad_texto = self._fmt_fecha(antig) if antig else ''
            fecha_fin = (getattr(emp, 'contract_date_end', False)
                         or getattr(emp, 'date_end', False))
            w.fecha_termino_texto = self._fmt_fecha(fecha_fin) if fecha_fin else ''
            if fecha_ini and fecha_fin:
                dias = (fecha_fin - fecha_ini).days
                w.vigencia_dias = '%d DIAS' % dias if dias > 0 else ''
            else:
                w.vigencia_dias = ''

            mensual = self._sueldo_mensual(emp)
            if mensual:
                w.sueldo_mensual = '{:,.2f}'.format(mensual)
                w.sueldo_letra = numero_a_letras(mensual)
                diario = mensual / 30.0
                w.salario_numero = '%.2f' % diario
                w.salario_letra = numero_a_letras(diario)
            schedule = getattr(emp, 'schedule_pay', False)
            w.periodicidad = {
                'weekly': 'SEMANAL', 'bi-weekly': 'SEMANAL',
                'semi-monthly': 'QUINCENAL', 'monthly': 'MENSUAL',
            }.get(schedule, 'QUINCENAL')

            clabe, banco = self._cuenta_bancaria(emp)
            w.clabe, w.banco, w.sucursal, w.horario = clabe, banco, '', ''

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
            'apellido_paterno': self.apellido_paterno or '',
            'apellido_materno': self.apellido_materno or '',
            'nombres': self.nombres or '',
            'nacionalidad': self.nacionalidad or '',
            'edad': self.edad or '',
            'sexo': self.sexo or '',
            'calle_y_n': self.calle_y_n or '',
            'colonia': self.colonia or '',
            'cp': self.cp or '',
            'municipio': self.municipio or '',
            'estado': self.estado or '',
            'fecha_ingreso_texto': self.fecha_ingreso_texto or '',
            'fecha_antiguedad_texto': self.fecha_antiguedad_texto or '',
            'fecha_termino_texto': self.fecha_termino_texto or '',
            'vigencia_dias': self.vigencia_dias or '',
            'sueldo_mensual': self.sueldo_mensual or '',
            'sueldo_letra': self.sueldo_letra or '',
            'banco': self.banco or '',
            'clabe': self.clabe or '',
            'sucursal': self.sucursal or '',
            'horario': self.horario or '',
            'representante_legal': self.representante_legal or '',
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
