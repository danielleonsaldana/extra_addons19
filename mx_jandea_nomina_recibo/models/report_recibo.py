# -*- coding: utf-8 -*-
from odoo import api, models


# Días completos según la periodicidad de la nómina.
# El recibo debe mostrar los días del PERÍODO (15 quincenal, 7 semanal...),
# no únicamente los efectivamente laborados.
DIAS_POR_PERIODICIDAD = {
    'daily': 1,
    'weekly': 7,
    'bi-weekly': 14,        # catorcenal
    'semi-monthly': 15,     # quincenal
    'monthly': 30,
    'bi-monthly': 60,
    'quarterly': 90,
    'semi-annually': 180,
    'annually': 360,
}

PERIODICIDAD_ES = {
    'daily': 'Diaria',
    'weekly': 'Semanal',
    'bi-weekly': 'Catorcenal',
    'semi-monthly': 'Quincenal',
    'monthly': 'Mensual',
    'bi-monthly': 'Bimestral',
    'quarterly': 'Trimestral',
    'semi-annually': 'Semestral',
    'annually': 'Anual',
}

# Traducción de conceptos al español por CÓDIGO de regla salarial.
# Se traduce solo en el PDF: no se modifican los registros nativos de
# l10n_mx_hr_payroll, así que nada se rompe al actualizar la localización.
# Si un código no está aquí, se usa el nombre de la regla tal cual.
CONCEPTOS_ES = {
    # --- Percepciones ---
    'BASIC': 'Sueldo',
    'GROSS': 'Total Percepciones',
    'COMMISSIONS': 'Comisiones',
    'BONUS': 'Bono',
    'CHRISTMAS_BONUS': 'Aguinaldo',
    'HOLIDAYS_ON_TIME': 'Vacaciones',
    'HOLIDAY_BONUS': 'Prima Vacacional',
    'PROVISIONS_HOLIDAY_BONUS': 'Provisión Prima Vacacional',
    'SAVINGS_FUND_EMPLOYER_ALW': 'Fondo de Ahorro (Patrón)',
    'MEAL_VOUCHER': 'Vales de Despensa',
    'NO_TAX_MEAL_VOUCHER': 'Vales de Despensa (Exento)',
    'TAX_MEAL_VOUCHER': 'Vales de Despensa (Gravado)',
    'GAS': 'Gasolina',
    'NO_TAX_GAS': 'Gasolina (Exento)',
    'TAX_GAS': 'Gasolina (Gravado)',
    'TRANSPORT': 'Transporte',
    'NO_TAX_TRANSPORT': 'Transporte (Exento)',
    'TAX_TRANSPORT': 'Transporte (Gravado)',
    'EXEMPT': 'Ingreso Exento',
    'EXPENSES': 'Gastos',
    'REIMBURSEMENT': 'Reembolso',
    'SUBSIDY': 'Subsidio para el Empleo',
    'SUBSIDY_CURRENT_MONTH': 'Subsidio para el Empleo (Mes Actual)',
    'SUBSIDY_NEXT_MONTH': 'Subsidio para el Empleo (Mes Siguiente)',
    'INT_DAY_WAGE': 'Salario Diario Integrado',
    # --- Percepciones de módulos Jandea ---
    'HRS_EXTRA_DOBLE': 'Horas Extra Dobles',
    'HRS_EXTRA_TRIPLE': 'Horas Extra Triples',
    'FESTIVO_LABORADO': 'Festivo Laborado',
    'PRIMA_DOM': 'Prima Dominical',
    'PTU': 'Reparto de Utilidades (PTU)',
    'PREMIO_ASISTENCIA': 'Premio de Asistencia',
    'PREMIO_PUNTUALIDAD': 'Premio de Puntualidad',
    'COMPENSACION': 'Compensación',
    'HABITACION': 'Habitación',
    # --- Listado de Nómina (v1.25.0 de mx_jandea_reglas_mx) ---
    'PRIMA_VAC_MX': 'Prima Vacacional (Gravado)',
    'PRIMA_VAC_MX_EXE': 'Prima Vacacional (Exento)',
    'PRIMA_DOM_EXE': 'Prima Dominical (Exento)',
    'FESTIVO_LABORADO_EXE': 'Festivo Laborado (Exento)',
    'HRS_EXTRA_DOBLE_EXE': 'Horas Extra Dobles (Exento)',
    'HRS_EXTRA_TRIPLE_EXE': 'Horas Extra Triples (Exento)',
    'DESCANSO_LABORADO': 'Descanso Laborado (Gravado)',
    'DESCANSO_LABORADO_EXE': 'Descanso Laborado (Exento)',
    'OTRAS_PERCEPCIONES': 'Otras Percepciones',
    'FONDO_AHORRO_GRAV': 'Fondo de Ahorro (Gravado)',
    'FONDO_AHORRO_EXENTO': 'Fondo de Ahorro (Exento)',
    'VALES_DESPENSA_GRAV': 'Vales de Despensa (Gravado)',
    'VALES_DESPENSA_EXENTO': 'Vales de Despensa (Exento)',
    'VALES_COMPENSACION': 'Compensación Vales de Despensa',
    'DESCUENTO_VALES': 'Descuento Vales de Despensa',
    'FONDO_AHORRO_EMPLEADO': 'Fondo de Ahorro (Empleado)',
    'FONDO_AHORRO_PATRON_DED': 'Fondo de Ahorro (Descuento Patrón)',
    # --- Finiquito ---
    'FNQT_SALARIO': 'Salario Pendiente',
    'FNQT_AGUINALDO': 'Aguinaldo Proporcional',
    'FNQT_VACACIONES': 'Vacaciones',
    'FNQT_PRIMA_VAC': 'Prima Vacacional',
    'FNQT_IND90': 'Indemnización Constitucional',
    'FNQT_IND20': 'Indemnización 20 Días por Año',
    'FNQT_PRIMA_ANT': 'Prima de Antigüedad',
    'FNQT_OTRAS_PERC': 'Otras Percepciones',
    # --- Deducciones ---
    'ISR': 'ISR',
    'ISR_MINIMUM_WAGE': 'ISR (Salario Mínimo)',
    'ISR_ADJUSTMENT': 'Ajuste de ISR',
    'ISR_HOLIDAY_TAX': 'ISR Prima Vacacional',
    'IMSS_EMPLOYEE_TOTAL': 'Cuotas IMSS',
    'CEAV_IMSS': 'Cesantía y Vejez (IMSS)',
    'DIS_LIF_IMSS': 'Invalidez y Vida (IMSS)',
    'DIS_MED_IMSS': 'Gastos Médicos Pensionados (IMSS)',
    'DIS_MON_IMSS': 'Prestaciones en Dinero (IMSS)',
    'DIS_ADD_IMSS': 'Enfermedad y Maternidad Excedente (IMSS)',
    'INFONAVIT': 'Crédito INFONAVIT',
    'FONACOT': 'Crédito FONACOT',
    'CHILD_SUPPORT': 'Pensión Alimenticia',
    'SAVINGS_FUND_EMPLOYEE': 'Fondo de Ahorro (Empleado)',
    'SAVINGS_FUND_EMPLOYER_DED': 'Fondo de Ahorro (Descuento Patrón)',
    'ATTACH_SALARY': 'Embargo Salarial',
    'ASSIG_SALARY': 'Asignación Salarial',
    'DEDUCTION': 'Otras Deducciones',
    'NET': 'Neto a Pagar',
    # --- Deducciones de módulos Jandea ---
    'ANTICIPO_NOMINA': 'Anticipo de Nómina',
    'CAJA_AHORRO': 'Caja de Ahorro',
    'SAR_VOLUNTARIO': 'SAR Voluntario',
    'INFONAVIT_VOLUNTARIO': 'INFONAVIT Voluntario',
    'PRESTAMO': 'Préstamo Personal',
    'FNQT_IMSS': 'Cuotas IMSS',
    'FNQT_ISR': 'ISR',
    'FNQT_INFONAVIT': 'INFONAVIT',
    'FNQT_FONACOT': 'FONACOT',
    'FNQT_OTRAS_DED': 'Otras Deducciones',
}

# Categorías que NO se listan como conceptos del trabajador.
# PATRONAL incluye el ISN: es impuesto estatal a cargo del patrón, no un
# concepto aplicable al colaborador, por eso no debe salir en su recibo.
CATEGORIAS_EXCLUIDAS = ('GROSS', 'NET', 'PATRONAL', 'COMP')

UNIDADES = ('', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE',
            'OCHO', 'NUEVE', 'DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE',
            'QUINCE', 'DIECISEIS', 'DIECISIETE', 'DIECIOCHO', 'DIECINUEVE',
            'VEINTE')
DECENAS = ('', '', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA', 'SESENTA',
           'SETENTA', 'OCHENTA', 'NOVENTA')
CENTENAS = ('', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS',
            'QUINIENTOS', 'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS',
            'NOVECIENTOS')


def _centenas_a_letras(n):
    """Convierte 0-999 a letras."""
    if n == 0:
        return ''
    if n == 100:
        return 'CIEN'
    texto = ''
    c, resto = divmod(n, 100)
    if c:
        texto = CENTENAS[c]
    if resto:
        if resto <= 20:
            palabra = UNIDADES[resto]
        else:
            d, u = divmod(resto, 10)
            palabra = DECENAS[d]
            if u:
                palabra += ' Y ' + UNIDADES[u] if d != 2 else 'I' + UNIDADES[u].lower()
                if d == 2:
                    palabra = 'VEINTI' + UNIDADES[u]
        texto = (texto + ' ' + palabra).strip()
    return texto


def numero_a_letras(monto, moneda='PESOS', centavos='M.N.'):
    """Importe a letra para el recibo (formato mexicano)."""
    try:
        monto = float(monto)
    except (TypeError, ValueError):
        return ''
    negativo = monto < 0
    monto = abs(monto)
    entero = int(monto)
    cents = int(round((monto - entero) * 100))
    if cents == 100:
        entero += 1
        cents = 0

    if entero == 0:
        letras = 'CERO'
    else:
        millones, resto = divmod(entero, 1000000)
        miles, unidades = divmod(resto, 1000)
        partes = []
        if millones:
            if millones == 1:
                partes.append('UN MILLON')
            else:
                partes.append(_centenas_a_letras(millones) + ' MILLONES')
        if miles:
            if miles == 1:
                partes.append('MIL')
            else:
                partes.append(_centenas_a_letras(miles) + ' MIL')
        if unidades:
            partes.append(_centenas_a_letras(unidades))
        letras = ' '.join(p for p in partes if p).strip()

    unidad = moneda
    if entero == 1:
        unidad = 'PESO' if moneda == 'PESOS' else moneda
    texto = '%s %s %02d/100 %s' % (letras, unidad, cents, centavos)
    if negativo:
        texto = 'MENOS ' + texto
    return texto.replace('  ', ' ').strip()


class ReportReciboNomina(models.AbstractModel):
    _name = 'report.mx_jandea_nomina_recibo.report_recibo_nomina'
    _description = 'Recibo de Nómina (México)'

    def _es_finiquito(self, payslip):
        """El recibo corresponde a un finiquito/liquidación."""
        for linea in payslip.line_ids:
            if (linea.code or '').startswith('FNQT_'):
                return True
        return False

    def _dias_trabajados(self, payslip):
        """Días efectivamente trabajados (pagados) del período."""
        total = 0.0
        for linea in payslip.worked_days_line_ids:
            dias = linea.number_of_days or 0.0
            if dias <= 0:
                continue
            pagado = True
            try:
                pagado = bool(linea.is_paid)
            except Exception:
                try:
                    pagado = (linea.work_entry_type_id.paid_amount_rate or 0.0) > 0
                except Exception:
                    pagado = True
            if pagado:
                total += dias
        return total

    def _dias_periodo(self, payslip):
        """Días a imprimir en el recibo.

        Días COMPLETOS del período según la periodicidad de la nómina
        (15 quincenal, 7 semanal, 14 catorcenal, 30 mensual...), tanto en la
        nómina ordinaria como en el FINIQUITO. Las faltas, incapacidades o
        una baja a mitad de período se reflejan en los IMPORTES (salario
        pendiente = días efectivamente laborados), no en los días del período.
        """
        version = getattr(payslip, 'version_id', False) or \
            getattr(payslip, 'contract_id', False)
        schedule = getattr(version, 'schedule_pay', False) if version else False
        if not schedule:
            schedule = getattr(payslip, 'schedule_pay', False)
        etiqueta = PERIODICIDAD_ES.get(schedule, '')

        dias = DIAS_POR_PERIODICIDAD.get(schedule)
        if dias:
            return dias, etiqueta
        # Respaldo: días naturales del período del recibo.
        if payslip.date_from and payslip.date_to:
            return (payslip.date_to - payslip.date_from).days + 1, etiqueta
        return 0, etiqueta

    def _campo(self, record, *nombres):
        """Primer campo existente y con valor, entre varios nombres posibles."""
        for nombre in nombres:
            if record and nombre in record._fields:
                valor = record[nombre]
                if valor:
                    return valor
        return ''

    def _datos_recibo(self, payslip):
        empleado = payslip.employee_id
        version = getattr(payslip, 'version_id', False) or \
            getattr(payslip, 'contract_id', False)

        percepciones, deducciones = [], []
        for linea in payslip.line_ids:
            categoria = linea.category_id.code or ''
            if categoria in CATEGORIAS_EXCLUIDAS:
                continue
            if not linea.appears_on_payslip:
                continue
            if not linea.total:
                continue
            nombre = CONCEPTOS_ES.get(linea.code) or linea.name
            # La indemnización constitucional muestra los días realmente
            # pagados (90 por defecto; 60, 45, etc. si se capturaron).
            if linea.code == 'FNQT_IND90' and linea.quantity:
                nombre = '%s (%d días)' % (nombre, int(round(linea.quantity)))
            # El salario pendiente muestra los días pagados (admite más de 15:
            # varias quincenas atrasadas capturadas en FNQT_DIAS_SAL).
            elif linea.code == 'FNQT_SALARIO' and linea.quantity:
                nombre = '%s (%s días)' % (nombre, round(linea.quantity, 2))
            item = {
                'codigo': linea.code,
                'nombre': nombre,
                'cantidad': linea.quantity,
                'importe': abs(linea.total),
            }
            if categoria == 'DED':
                deducciones.append(item)
            else:
                percepciones.append(item)

        total_perc = sum(i['importe'] for i in percepciones)
        total_ded = sum(i['importe'] for i in deducciones)
        neto = total_perc - total_ded
        dias, periodicidad = self._dias_periodo(payslip)

        return {
            'payslip': payslip,
            'empleado': empleado,
            'version': version,
            'percepciones': percepciones,
            'deducciones': deducciones,
            'total_percepciones': total_perc,
            'total_deducciones': total_ded,
            'neto': neto,
            'neto_letras': numero_a_letras(neto),
            'dias_periodo': dias,
            'periodicidad': periodicidad,
            'rfc': self._campo(empleado, 'mx_rfc', 'l10n_mx_rfc', 'vat'),
            'curp': self._campo(empleado, 'mx_curp', 'l10n_mx_edi_curp'),
            'nss': self._campo(empleado, 'nss', 'ssnid'),
            'puesto': empleado.job_title or (
                empleado.job_id.name if empleado.job_id else ''),
            'departamento': (
                empleado.department_id.name if empleado.department_id else ''),
            'fecha_ingreso': self._campo(
                version, 'contract_date_start', 'date_start', 'date_version'
            ) or self._campo(empleado, 'first_contract_date'),
            'registro_patronal': self._campo(
                payslip.company_id, 'l10n_mx_edi_employer_registration',
                'company_registry'),
            'rfc_empresa': self._campo(payslip.company_id, 'vat'),
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        payslips = self.env['hr.payslip'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'hr.payslip',
            'docs': payslips,
            'datos': {p.id: self._datos_recibo(p) for p in payslips},
        }
