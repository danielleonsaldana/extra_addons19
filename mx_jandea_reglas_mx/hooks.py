# -*- coding: utf-8 -*-
"""Creación de la estructura de nómina "Finiquito / Liquidación" (México).

Se hace en un post_init_hook y no en XML porque la estructura necesita un
``type_id`` (hr.payroll.structure.type) cuyo XML-ID varía entre versiones de
``l10n_mx_hr_payroll``. Aquí se toma el mismo tipo que ya usa la estructura
nativa ``l10n_mx_regular_pay``, que es el único XML-ID del que dependemos y que
ya está referenciado por el resto del módulo.

Todos los registros creados se enlazan a ``ir.model.data`` para que:
  * la reinstalación no los duplique, y
  * la desinstalación del módulo los elimine.

Una vez creadas, las reglas son registros normales y se pueden editar desde
Nómina → Configuración → Reglas Salariales.

Las fórmulas replican el archivo "Calculo_Fnqt2026.xlsx" (hoja Calculo).
"""
import logging

_logger = logging.getLogger(__name__)

MODULE = 'mx_jandea_reglas_mx'
STRUCT_XMLID = 'struct_finiquito'

# Códigos de entrada del finiquito -> se enlazan a la estructura al instalar.
FNQT_INPUT_CODES = [
    'FNQT_DIAS_SAL', 'FNQT_SD_IMSS', 'FNQT_SDI_IMSS', 'FNQT_SDI_REAL',
    'FNQT_DIAS_AGUI',
    'FNQT_DIAS_LAB', 'FNQT_ANIOS_ANTIG', 'FNQT_DIAS_VAC_BASE',
    'FNQT_VAC_PEND', 'FNQT_PV_PEND',
    'FNQT_IND_90', 'FNQT_IND_DIAS', 'FNQT_IND_20', 'FNQT_PRIMA_ANT',
    'FNQT_AGUI_PAGADO',
    'FNQT_FACTOR_LIQ', 'FNQT_FACTOR_ISR',
    'FNQT_OTRAS_PERC', 'FNQT_INFONAVIT', 'FNQT_FONACOT', 'FNQT_OTRAS_DED',
]


# ---------------------------------------------------------------------------
# Preámbulo compartido por todas las reglas del finiquito.
#
# Replica la hoja "Calculo" del Excel:
#   dias_lab      = B14 = (BAJA - ALTA) + 1
#   dias_vac_base = B15 = (BAJA - FECHA VACACIONES) + 5
#   anios_lab     = B16 = ROUND(B14/365.25, 0)
#   anios_antig   = B17 = ROUND(((BAJA - F.ANTIGÜEDAD)+1)/365.25, 2)
#   agui_prop     = B20  vacaciones/pv proporcionales = B22 / B24
#
# Columna REAL  -> lo que se le paga al trabajador (usa version.wage / 30).
# Columna IMSS  -> base reportada al IMSS (usa FNQT_SD_IMSS / FNQT_SDI_IMSS).
#                  Sobre ella se calculan ISR e IMSS, igual que en el Excel.
# ---------------------------------------------------------------------------
PREAMBLE = '''
def _in(c, d=0.0):
    # 1) Via el objeto navegable 'inputs' (subindice + atributo, sin getattr,
    #    que NO existe dentro de las reglas de salario).
    try:
        v = inputs[c]
        if v:
            a = v.amount
            if a not in (None, False):
                return a
    except Exception:
        pass
    # 2) Respaldo DIRECTO: leer la entrada capturada del recibo por codigo.
    #    Garantiza que FNQT_IND_DIAS, FNQT_DIAS_SAL, FNQT_SD_IMSS, etc. SI se
    #    lean cuando el usuario las captura.
    try:
        for _il in payslip.input_line_ids:
            try:
                _code = _il.input_type_id.code if _il.input_type_id else False
            except Exception:
                _code = False
            if not _code:
                try:
                    _code = _il.code
                except Exception:
                    _code = False
            if _code == c:
                return _il.amount
    except Exception:
        pass
    return d

def _param(c, d):
    try:
        v = payslip._rule_parameter(c)
        return float(v) if v else d
    except Exception:
        return d

UMA = _param('mx_jandea_uma', 117.31)
SMG = _param('mx_jandea_smg', 315.04)

fecha_baja = payslip.date_to
# Si la baja ocurrio a mitad del periodo, los conceptos proporcionales
# (aguinaldo, vacaciones, prima vacacional) deben cortarse en la FECHA REAL
# DE BAJA, no al cierre de la quincena.
for _o, _f in ((version, 'contract_date_end'), (version, 'date_end'),
               (employee, 'departure_date')):
    try:
        _v = _o[_f]
    except Exception:
        _v = False
    if _v and payslip.date_from <= _v <= payslip.date_to:
        fecha_baja = _v
        break
# La fecha de ALTA (antiguedad) es dificil de obtener de forma fiable en Odoo
# 19. IMPORTANTE: dentro de las reglas de salario NO existe getattr(obj, campo,
# default); por eso se usa acceso por SUBINDICE obj[campo] (como categories[..]
# o inputs[..]), envuelto en try/except. Con getattr todo caia en el except y
# la fecha nunca se leia -> antiguedad de ~1 dia.
try:
    _ver = payslip['version_id']
except Exception:
    _ver = False
if not _ver:
    try:
        _ver = payslip['contract_id']
    except Exception:
        _ver = False
if not _ver:
    _ver = version

# Buscar la fecha de ALTA mas antigua (subindice + comparacion, sin getattr).
fecha_alta = False
for _o, _f in ((_ver, 'contract_date_start'), (_ver, 'date_start'),
               (_ver, 'date_version'), (employee, 'first_contract_date')):
    try:
        _v = _o[_f]
    except Exception:
        _v = False
    if _v:
        try:
            _v = _v.date()   # datetime -> date
        except Exception:
            pass
        if (not fecha_alta) or (_v < fecha_alta):
            fecha_alta = _v
# Recorrer TODAS las versiones/contratos del empleado: la mas antigua = ingreso.
for _coll in ('version_ids', 'contract_ids'):
    try:
        _recs = employee[_coll]
    except Exception:
        _recs = False
    if not _recs:
        continue
    for _r in _recs:
        for _f in ('contract_date_start', 'date_start', 'date_version'):
            try:
                _v = _r[_f]
            except Exception:
                _v = False
            if not _v:
                continue
            try:
                _v = _v.date()
            except Exception:
                pass
            if (not fecha_alta) or (_v < fecha_alta):
                fecha_alta = _v
if not fecha_alta:
    fecha_alta = payslip.date_from

# PALANCA MANUAL infalible: si se captura FNQT_DIAS_LAB, la fecha de alta se
# deriva de la baja (alta = baja - (dias_laborados - 1)). Sirve cuando el
# contrato trae fechas recientes/equivocadas. Ej.: 839 dias -> 16/03/2024.
_dl_cap = _in('FNQT_DIAS_LAB', 0.0)
if _dl_cap:
    try:
        fecha_alta = type(fecha_baja).fromordinal(
            fecha_baja.toordinal() - (int(round(_dl_cap)) - 1))
    except Exception:
        pass
inicio_anio = fecha_baja.replace(month=1, day=1)

dias_lab = _in('FNQT_DIAS_LAB', 0.0) or ((fecha_baja - fecha_alta).days + 1)

# "FECHA VACACIONES" del Excel = inicio del periodo vacacional en curso, es
# decir el ULTIMO ANIVERSARIO de la fecha de alta anterior a la baja (no la
# fecha de alta original: eso inflaria las vacaciones de un empleado antiguo).
try:
    _aniv = fecha_alta.replace(year=fecha_baja.year)
except ValueError:          # 29 de febrero en anio no bisiesto
    _aniv = fecha_alta.replace(year=fecha_baja.year, day=28)
if _aniv > fecha_baja:
    try:
        _aniv = fecha_alta.replace(year=fecha_baja.year - 1)
    except ValueError:
        _aniv = fecha_alta.replace(year=fecha_baja.year - 1, day=28)
if _aniv < fecha_alta:
    _aniv = fecha_alta
dias_vac_base = _in('FNQT_DIAS_VAC_BASE', 0.0) or ((fecha_baja - _aniv).days + 1)
anios_lab = int(round(dias_lab / 365.25))
# Antiguedad en años CON DECIMALES (para montos de Ind20 y Prima de antiguedad),
# igual que el Excel B17 = ROUND((BAJA - FECHA_ANTIGUEDAD)/365, 4). Nota: usa los
# dias sin el +1 y /365.  Ej.: 838/365 -> 2.2959.
anios_antig = _in('FNQT_ANIOS_ANTIG', 0.0) or round(
    (fecha_baja - fecha_alta).days / 365.0, 4)
# Años REDONDEADOS (>= 6 meses sube) SOLO para la exencion de indemnizaciones,
# igual que el Excel B16 = ROUND(DIAS_LABORADOS/365, 0).  Ej.: 839/365 -> 2.
anios_cerr = int(round(anios_antig))
anios_exencion = int(round(dias_lab / 365.0))

dias_agui = _in('FNQT_DIAS_AGUI', 15.0) or 15.0
if fecha_alta < inicio_anio:
    agui_prop = (((fecha_baja - inicio_anio).days + 1) / 365.0) * dias_agui
else:
    agui_prop = (((fecha_baja - fecha_alta).days + 1) / 365.0) * dias_agui

def _dias_vac_lft(a):
    # Años SIN redondear: se trunca al rango inferior, igual que el VLOOKUP
    # aproximado del Excel (p. ej. 4.82 años -> rango de 4 -> 18 dias, NO 20).
    a = int(a)
    if a <= 1:
        return 12
    if a == 2:
        return 14
    if a == 3:
        return 16
    if a == 4:
        return 18
    if a == 5:
        return 20
    if a <= 10:
        return 22
    if a <= 14:
        return 24
    if a <= 19:
        return 26
    if a <= 24:
        return 28
    if a <= 29:
        return 30
    return 32

dias_tab = _dias_vac_lft(anios_antig)
vac_prop = (dias_vac_base / 365.0) * dias_tab
pv_prop = vac_prop * 0.25
vac_pend = _in('FNQT_VAC_PEND', 0.0)
pv_pend = _in('FNQT_PV_PEND', 0.0)

# El recibo puede no tener version/contrato asignado ("Version: False") o el
# contrato puede venir SIN sueldo (wage = 0). En ese caso el salario diario se
# toma del que se capture en FNQT_SD_IMSS, para que el finiquito SI calcule.
_wage = 0.0
for _o in (version, employee):
    for _f in ('wage', 'contract_wage'):
        try:
            _w = _o[_f]
        except Exception:
            _w = False
        if _w:
            _wage = _w
            break
    if _wage:
        break
# Salario diario capturado (override manual opcional para excepciones).
_sd_cap = _in('FNQT_SD_IMSS', 0.0)
# El campo "Sueldo" del contrato trae el importe del PERIODO de pago (en estos
# contratos, la QUINCENA). El salario diario se obtiene dividiendo entre los
# dias del periodo segun la periodicidad:  quincenal /15 | semanal /7 |
# mensual /30.  Ej.: 6424.95 (quincena) / 15 = 428.33.  Por defecto: quincena.
_div = 15.0
try:
    _spw = (version['schedule_pay'] or '').lower()
except Exception:
    _spw = ''
if not _spw:
    try:
        _spw = (employee['schedule_pay'] or '').lower()
    except Exception:
        _spw = ''
if _spw == 'monthly':
    _div = 30.0
elif _spw == 'weekly':
    _div = 7.0
elif _spw in ('semi-monthly', 'bi-weekly'):
    _div = 15.0
# 1) diario capturado (manda)  2) diario del contrato (wage / dias del periodo).
sd_real = _sd_cap or ((_wage / _div) if _wage else 0.0)
# Factor de integración (art. 30 LSS): (365 + días de aguinaldo + días de
# vacaciones * 25% de prima vacacional) / 365. Con esto el SDI queda INTEGRADO
# igual que en el Excel (p. ej. 428.33 -> 450.05 con 15 de aguinaldo y 14 de
# vacaciones). Se puede sobre-escribir capturando FNQT_SDI_REAL / FNQT_SDI_IMSS
# cuando el SBC real trae partes variables (bonos, comisiones, etc.).
factor_integ = round((365.0 + dias_agui + dias_tab * 0.25) / 365.0, 4)
sd_imss = _sd_cap or sd_real
sdi_real = round(_in('FNQT_SDI_REAL', 0.0) or (sd_real * factor_integ), 2)
sdi_imss = round(_in('FNQT_SDI_IMSS', 0.0) or (sd_imss * factor_integ), 2)

dias_sal = _in('FNQT_DIAS_SAL', 0.0)
if not dias_sal:
    # Sin captura manual, se toman los DIAS EFECTIVAMENTE TRABAJADOS del
    # periodo (los ultimos dias laborados antes de la baja), NO el periodo
    # completo de la quincena. Se excluyen las entradas no pagadas
    # (faltas / "Sin pagar"), que no generan salario.
    _wd = 0.0
    for _l in payslip.worked_days_line_ids:
        _n = _l.number_of_days or 0.0
        if _n <= 0:
            continue
        _pagado = True
        try:
            _pagado = bool(_l.is_paid)
        except Exception:
            try:
                _pagado = (_l.work_entry_type_id.paid_amount_rate or 0.0) > 0
            except Exception:
                _pagado = True
        if _pagado:
            _wd += _n
    # Respaldo: si el conteo "pagado" quedo en 0 pero SI hay dias de
    # asistencia capturados, contar los dias que NO sean ausencia/incapacidad
    # (para que "Salario Pendiente" refleje los dias trabajados del periodo).
    if not _wd:
        for _l in payslip.worked_days_line_ids:
            _n = _l.number_of_days or 0.0
            if _n <= 0:
                continue
            _es_leave = False
            try:
                _es_leave = bool(_l.work_entry_type_id.is_leave)
            except Exception:
                _es_leave = False
            if not _es_leave:
                _wd += _n
    dias_sal = _wd
factor_liq = _in('FNQT_FACTOR_LIQ', 0.0) or 1.0
agui_pagado = _in('FNQT_AGUI_PAGADO', 0.0)
# Indemnización constitucional: se aplica capturando DIRECTAMENTE los días a
# pagar en FNQT_IND_DIAS (90, 60, 45...). Con días > 0 aplica; ya NO hace falta
# poner FNQT_IND_90=1. (Compatibilidad: si aún usan el switch viejo
# FNQT_IND_90=1 sin días, se asumen 90.) El % FNQT_FACTOR_LIQ sigue aplicando
# encima: 45 días al 100% == 90 días al 50%.
ind_dias = _in('FNQT_IND_DIAS', 0.0)
if not ind_dias and _in('FNQT_IND_90', 0.0):
    ind_dias = 90.0
aplica_ind = ind_dias > 0
ind_20 = _in('FNQT_IND_20', 0.0)
prima_ant_on = _in('FNQT_PRIMA_ANT', 0.0)

# --- % de ajuste por concepto (boton/wizard "Aplicar % a conceptos") ---
# payslip.x_fnqt_pct = porcentaje que SI se paga (80 = 80%). Vacio/0/100 = 100%.
# payslip.x_fnqt_pct_codes = codigos de conceptos afectados, separados por coma.
# Cada concepto solo se ajusta si SU codigo esta en la lista -> imposible que
# afecte a un concepto no seleccionado.
try:
    _pct_val = payslip['x_fnqt_pct']
except Exception:
    _pct_val = 0.0
if not _pct_val or _pct_val <= 0:
    _pct_val = 100.0
try:
    _pct_codes = (payslip['x_fnqt_pct_codes'] or '')
except Exception:
    _pct_codes = ''
_pct_list = [_c.strip() for _c in (_pct_codes or '').split(',') if _c.strip()]
_pf = _pct_val / 100.0
_f_salario = _pf if 'FNQT_SALARIO' in _pct_list else 1.0
_f_agui = _pf if 'FNQT_AGUINALDO' in _pct_list else 1.0
_f_vac = _pf if 'FNQT_VACACIONES' in _pct_list else 1.0
_f_pv = _pf if 'FNQT_PRIMA_VAC' in _pct_list else 1.0
_f_ind90 = _pf if 'FNQT_IND90' in _pct_list else 1.0
_f_ind20 = _pf if 'FNQT_IND20' in _pct_list else 1.0
_f_pant = _pf if 'FNQT_PRIMA_ANT' in _pct_list else 1.0
_f_otras = _pf if 'FNQT_OTRAS_PERC' in _pct_list else 1.0

# --- Percepciones, columna REAL (lo que se paga) ---
p_salario_r = dias_sal * sd_real * _f_salario
p_agui_r = (0.0 if agui_pagado else sd_real * agui_prop) * _f_agui
p_vac_r = (vac_prop + vac_pend) * sd_real * _f_vac
p_pv_r = ((vac_prop + pv_pend) * 0.25) * sd_real * _f_pv
p_ind90_r = (ind_dias * sdi_real if aplica_ind else 0.0) * factor_liq * _f_ind90
p_ind20_r = ((sdi_real * 20.0) * anios_antig if ind_20 else 0.0) * factor_liq * _f_ind20
_tope_pa = SMG * 2.0
p_pant_r = 0.0
if prima_ant_on:
    _base_pa_r = _tope_pa if sd_real > _tope_pa else sd_real
    p_pant_r = (_base_pa_r * 12.0) * anios_antig * factor_liq * _f_pant
p_otras = _in('FNQT_OTRAS_PERC', 0.0) * _f_otras

# --- Percepciones, columna IMSS (base reportada) ---
p_salario_i = dias_sal * sd_imss * _f_salario
p_agui_i = (0.0 if agui_pagado else sd_imss * agui_prop) * _f_agui
p_vac_i = (vac_prop + vac_pend) * sd_imss * _f_vac
p_pv_i = pv_prop * sd_imss * _f_pv
p_ind90_i = (ind_dias * sdi_imss if aplica_ind else 0.0) * factor_liq * _f_ind90
p_ind20_i = ((sdi_imss * 20.0) * anios_antig if ind_20 else 0.0) * factor_liq * _f_ind20
p_pant_i = 0.0
if prima_ant_on:
    _base_pa_i = _tope_pa if sd_imss > _tope_pa else sd_imss
    p_pant_i = (_base_pa_i * 12.0) * anios_antig * factor_liq * _f_pant

total_perc_real = (p_salario_r + p_agui_r + p_vac_r + p_pv_r
                   + p_ind90_r + p_ind20_r + p_pant_r + p_otras)
total_perc_imss = (p_salario_i + p_agui_i + p_vac_i + p_pv_i
                   + p_ind90_i + p_ind20_i + p_pant_i + p_otras)

# --- Base gravable ISR (art. 93 LISR: exenciones en UMA) ---
_ex_agui = UMA * 30.0
_ex_pv = UMA * 15.0
# Exencion de indemnizaciones: 90 UMA por año REDONDEADO, aplicada a la SUMA de
# las 3 indemnizaciones (Ind90 + Ind20 + Prima de antiguedad), igual que el
# Excel: IF(SUMA(G12:G14) > (UMA*90)*años_red, SUMA - (UMA*90)*años_red, 0).
_ex_sep = (UMA * 90.0) * anios_exencion
_suma_indem = p_ind90_i + p_ind20_i + p_pant_i
base_gravable = (
    p_salario_i
    + (0.0 if p_agui_i < _ex_agui else p_agui_i - _ex_agui)
    + p_vac_i
    + (p_pv_i - _ex_pv if p_pv_i > _ex_pv else 0.0)
    + (_suma_indem - _ex_sep if _suma_indem > _ex_sep else 0.0)
    + p_otras
)
'''

# Tabla ISR mensual + cálculo (se agrega solo a las reglas que lo necesitan).
ISR_BLOCK = '''
def _isr_tabla():
    try:
        t = payslip._rule_parameter('l10n_mx_isr_tables')['monthly']
        if t:
            return t
    except Exception:
        pass
    return [
        (0.01, 844.59, 0.0, 0.0192),
        (844.60, 7168.51, 16.22, 0.064),
        (7168.52, 12598.02, 420.95, 0.1088),
        (12598.03, 14644.64, 1011.68, 0.16),
        (14644.65, 17533.64, 1339.14, 0.1792),
        (17533.65, 35362.83, 1856.84, 0.2136),
        (35362.84, 55736.68, 5665.16, 0.2352),
        (55736.69, 106410.50, 10457.09, 0.30),
        (106410.51, 141880.66, 25659.23, 0.32),
        (141880.67, 425641.99, 37009.69, 0.34),
        (425642.00, 999999999.0, 133488.54, 0.35),
    ]

factor_isr = _in('FNQT_FACTOR_ISR', 0.0)
if not factor_isr:
    # Finiquitos QUINCENALES por politica: factor de proporcion mensual fijo en
    # 2.0267 (30.4/15). No se usa version.schedule_pay porque en estos contratos
    # suele venir mal marcado (p.ej. 'bi-weekly'), lo que desviaba el ISR.
    # Si algun finiquito fuera semanal/catorcenal/mensual, capturar
    # FNQT_FACTOR_ISR (semanal 4.3429, catorcenal 2.1714, mensual 1.0).
    factor_isr = 2.0267
_bg_mensual = base_gravable * factor_isr
_isr = 0.0
if _bg_mensual > 0:
    _low, _fix, _rate = 0.01, 0.0, 0.0192
    for _l, _h, _f, _r in _isr_tabla():
        if _bg_mensual >= _l:
            _low, _fix, _rate = _l, _f, _r
    _isr = ((_bg_mensual - _low) * _rate + _fix) / factor_isr
'''

# Cuota obrera IMSS (hoja "Tablas" del Excel).
IMSS_BLOCK = '''
# Tope legal del salario base de cotización: 25 UMA (LSS art. 28).
_sbc = sdi_imss if sdi_imss < UMA * 25.0 else UMA * 25.0
_exc_eym = _sbc - (UMA * 3.0)
if _exc_eym < 0:
    _exc_eym = 0.0
_ret_dia = (
    _exc_eym * 0.0040      # E y M excedente 3 UMA, cuota obrera
    + _sbc * 0.0025        # E y M prestaciones en dinero
    + _sbc * 0.00375       # E y M gastos médicos pensionados
    + _sbc * 0.00625       # Invalidez y vida
    + _sbc * 0.01125       # Cesantía y vejez
)
_cuota_imss = _ret_dia * dias_sal
# LSS art. 36: si el trabajador percibe el salario minimo, el patron absorbe
# la cuota obrera -> retencion 0 (igual que el Excel: IF(SD=SMG,0,...)).
if sd_imss <= SMG + 0.01:
    _cuota_imss = 0.0
'''


def _rules_spec():
    """Definición de las reglas: (xmlid, nombre, código, categoría, seq, code)."""
    p = PREAMBLE
    return [
        # ---------------- PERCEPCIONES ----------------
        (
            'rule_fnqt_salario', 'Salario Pendiente', 'FNQT_SALARIO',
            'BASIC', 10, p + '\nresult = sd_real * _f_salario\nresult_qty = dias_sal\n'
        ),
        (
            'rule_fnqt_aguinaldo', 'Aguinaldo Proporcional', 'FNQT_AGUINALDO',
            'ALW', 20, p + '\nresult = (0.0 if agui_pagado else sd_real) * _f_agui\nresult_qty = agui_prop\n'
        ),
        (
            'rule_fnqt_vacaciones', 'Vacaciones', 'FNQT_VACACIONES',
            'ALW', 30, p + '\nresult = sd_real * _f_vac\nresult_qty = vac_prop + vac_pend\n'
        ),
        (
            'rule_fnqt_prima_vac', 'Prima Vacacional', 'FNQT_PRIMA_VAC',
            'ALW', 40, p + '\nresult = p_pv_r\n'
        ),
        (
            'rule_fnqt_ind90', 'Indemnización Constitucional', 'FNQT_IND90',
            'ALW', 50, p + '\nresult = ((sdi_real * factor_liq) if aplica_ind else 0.0) * _f_ind90\nresult_qty = ind_dias if aplica_ind else 0.0\n'
        ),
        (
            'rule_fnqt_ind20', 'Indemnización 20 Días por Año', 'FNQT_IND20',
            'ALW', 60, p + '\nresult = p_ind20_r\n'
        ),
        (
            'rule_fnqt_prima_ant', 'Prima de Antigüedad', 'FNQT_PRIMA_ANT',
            'ALW', 70, p + '\nresult = p_pant_r\n'
        ),
        (
            'rule_fnqt_otras_perc', 'Otras Percepciones', 'FNQT_OTRAS_PERC',
            'ALW', 80, p + '\nresult = p_otras\n'
        ),
        (
            'rule_fnqt_gross', 'Total Percepciones', 'GROSS',
            'GROSS', 100,
            "result = categories['BASIC'] + categories['ALW']\n"
        ),
        # ---------------- DEDUCCIONES ----------------
        (
            'rule_fnqt_imss', 'Cuota IMSS', 'FNQT_IMSS',
            'DED', 150, p + IMSS_BLOCK + '\nresult = -_cuota_imss\n'
        ),
        (
            'rule_fnqt_isr', 'ISR', 'FNQT_ISR',
            'DED', 160, p + ISR_BLOCK + '\nresult = -_isr\n'
        ),
        (
            'rule_fnqt_infonavit', 'INFONAVIT', 'FNQT_INFONAVIT',
            'DED', 170, p + "\nresult = -_in('FNQT_INFONAVIT', 0.0)\n"
        ),
        (
            'rule_fnqt_fonacot', 'FONACOT', 'FNQT_FONACOT',
            'DED', 180, p + "\nresult = -_in('FNQT_FONACOT', 0.0)\n"
        ),
        (
            'rule_fnqt_otras_ded', 'Otras Deducciones', 'FNQT_OTRAS_DED',
            'DED', 190, p + "\nresult = -_in('FNQT_OTRAS_DED', 0.0)\n"
        ),
        (
            'rule_fnqt_net', 'Neto a Pagar', 'NET',
            'NET', 200,
            "result = categories['BASIC'] + categories['ALW'] + categories['DED']\n"
        ),
        # ---------------- INFORMATIVAS / COSTO PATRONAL ----------------
        (
            'rule_fnqt_info_imss', 'Info · Total Percepciones IMSS',
            'FNQT_INFO_PERC_IMSS', 'PATRONAL', 210,
            p + '\nresult = total_perc_imss\n'
        ),
        (
            'rule_fnqt_info_base', 'Info · Base Gravable ISR',
            'FNQT_INFO_BASE_GRAV', 'PATRONAL', 220,
            p + '\nresult = base_gravable\n'
        ),
        # ISN eliminado: es impuesto estatal a cargo del patron; ya no aparece
        # en el recibo del empleado (migracion 19.0.1.6.0 borra la regla vieja).
    ]


def _get_category(env, code, name=None):
    """Categoría por código (no por XML-ID, que varía entre localizaciones)."""
    Cat = env['hr.salary.rule.category']
    cat = Cat.search([('code', '=', code)], limit=1)
    if cat:
        return cat
    if not name:
        return False
    cat = Cat.create({'name': name, 'code': code})
    env['ir.model.data'].create({
        'name': 'category_%s' % code.lower(),
        'module': MODULE,
        'model': 'hr.salary.rule.category',
        'res_id': cat.id,
        'noupdate': True,
    })
    _logger.info('%s: categoría "%s" creada.', MODULE, code)
    return cat


def _link(env, xmlid, model, res_id):
    exists = env['ir.model.data'].search([
        ('module', '=', MODULE), ('name', '=', xmlid),
    ], limit=1)
    if exists:
        return
    env['ir.model.data'].create({
        'name': xmlid,
        'module': MODULE,
        'model': model,
        'res_id': res_id,
        'noupdate': True,
    })


def _safe_remove_rules(env, rules):
    """Elimina reglas de forma SEGURA para la transacción.

    Si una regla tiene líneas de recibo históricas, un ``unlink`` dispara un
    error de llave foránea a nivel SQL que ABORTA la transacción (y entonces
    cualquier operación posterior falla con InFailedSqlTransaction). Para
    evitarlo:
      * si la regla YA tiene líneas de recibo -> se DESACTIVA (conserva el
        histórico y deja de calcular en recibos nuevos);
      * si no tiene líneas -> se borra, pero dentro de un SAVEPOINT para que,
        si algo falla, se revierta solo ese paso sin tumbar la instalación.
    """
    Line = env['hr.payslip.line']
    Rule = env['hr.salary.rule']
    has_active = 'active' in Rule._fields

    def _desactivar(rule):
        vals = {'appears_on_payslip': False}
        if has_active:
            vals['active'] = False
        try:
            with env.cr.savepoint():
                rule.write(vals)
        except Exception:
            _logger.exception('%s: no se pudo desactivar la regla %s.',
                              MODULE, rule.code)

    for rule in rules:
        if not rule.exists():
            continue
        tiene_lineas = Line.search_count(
            [('salary_rule_id', '=', rule.id)]) > 0
        if tiene_lineas:
            _desactivar(rule)
            continue
        try:
            with env.cr.savepoint():
                rule.unlink()
        except Exception:
            _desactivar(rule)


def _patch_native_rules(env):
    """Reaplica sobre reglas NATIVAS de l10n_mx dos parches que, de otro modo,
    solo vivirian en la BD y se perderian al actualizar l10n_mx_hr_payroll:

    1) Aguinaldo con DIAS capturables: crea la entrada 'DIAS_AGUINALDO' y hace
       que la regla BASIC de las estructuras 'Christmas Bonus' use los dias
       capturados en el recibo (si no se captura, usa el parametro, 15).
    2) Fix getattr: en las reglas de salario que usan getattr(obj,'campo',def)
       -que revienta con NameError en el evaluador de Odoo (p. ej. ISR de
       'Regular Pay' con TODAS las faltas)- se reemplaza por acceso seguro por
       subindice obj['campo']. Es idempotente (tras el fix ya no hay getattr).
    """
    import re
    Rule = env['hr.salary.rule']

    # --- 1) Aguinaldo capturable ---
    InType = env['hr.payslip.input.type']
    it = InType.search([('code', '=', 'DIAS_AGUINALDO')], limit=1)
    if not it:
        _vals = {'name': 'Días de aguinaldo', 'code': 'DIAS_AGUINALDO'}
        _mx = env.ref('base.mx', raise_if_not_found=False)
        if _mx:
            _vals['country_id'] = _mx.id
        it = InType.create(_vals)

    structs = env['hr.payroll.structure'].search(
        [('name', 'ilike', 'Christmas Bonus')])
    for st in structs:
        if 'input_line_type_ids' in st._fields and it not in st.input_line_type_ids:
            st.input_line_type_ids = [(4, it.id)]

    _agui_code = '''
first_day = max(date(payslip.date_to.year, 1, 1), employee._get_first_version_date())
days_of_year_in_contract_until_payslip = (payslip.date_to - first_day).days + 1
unpaid_worked_days = payslip.env['hr.payslip'].search([
    ('employee_id', '=', employee.id),
    ('structure_code', '=', 'MX_REGULAR'),
    ('state', 'in', ['paid', 'validated']),
    ('date_from', '>=', date(payslip.date_to.year, 1, 1)),
    ('date_to', '<=', payslip.date_to),
])._get_worked_days_line_values(['LEAVE90', 'LEAVE1000', 'LEAVE1100', 'LEAVE1200'], ['number_of_days'], True)
unpaid_days = sum(worked_day_line['sum']['number_of_days'] for worked_day_line in unpaid_worked_days.values())

work_ratio = (days_of_year_in_contract_until_payslip - unpaid_days) / payslip.l10n_mx_days_of_year

# Dias de aguinaldo: 1) capturado en el recibo (DIAS_AGUINALDO)  2) parametro (15)
_dias_agui = 0.0
try:
    _e = inputs['DIAS_AGUINALDO']
    _dias_agui = _e.amount if _e else 0.0
except Exception:
    _dias_agui = 0.0
if not _dias_agui or _dias_agui <= 0:
    _dias_agui = payslip._rule_parameter('l10n_mx_christmas_bonus')

result = payslip.l10n_mx_daily_salary * _dias_agui * work_ratio
'''
    _agui_rules = Rule.search([('code', '=', 'BASIC')]).filtered(
        lambda r: r.struct_id and 'christmas bonus' in (r.struct_id.name or '').lower())
    for r in _agui_rules:
        if r.amount_python_compute != _agui_code:
            r.amount_python_compute = _agui_code

    # --- 2) Fix getattr(obj,'campo',default) -> obj['campo'] (seguro) ---
    _pat = re.compile(
        r"getattr\(\s*([a-zA-Z_][\w\.]*)\s*,\s*'([^']+)'\s*,\s*([^)]+)\)")

    def _repl(m):
        obj, campo, default = m.group(1).strip(), m.group(2), m.group(3).strip()
        return ("(%s['%s'] if ('%s' in %s._fields and %s['%s'] "
                "not in (None, False)) else %s)"
                % (obj, campo, campo, obj, obj, campo, default))

    for r in Rule.search([]):
        c = r.amount_python_compute or ''
        if 'getattr(' not in c:
            continue
        c2 = _pat.sub(_repl, c)
        if c2 != c and 'getattr(' not in c2:
            r.amount_python_compute = c2

    _logger.info('%s: parches nativos reaplicados (aguinaldo + getattr).',
                 MODULE)


def _clean_foreign_rules(env, struct):
    """Quita del Finiquito las reglas estructurales NATIVAS de Odoo.

    Al crear una estructura, Odoo/l10n_mx le agrega la regla ``Basic Salary``
    (código BASIC), que PRORRATEA el sueldo por los dias trabajados del periodo
    y DUPLICA el concepto de salario del finiquito (aqui el salario va en
    ``Salario Pendiente`` / FNQT_SALARIO, controlado por FNQT_DIAS_SAL).

    Se eliminan del finiquito solo las reglas con codigo BASIC/GROSS/NET que NO
    sean propias del modulo (mx_jandea_*). Asi se respetan las reglas propias y
    cualquier regla que el usuario haya agregado con otro codigo (p. ej.
    ``Prestamo a empleado``).
    """
    IMD = env['ir.model.data']
    quitar = env['hr.salary.rule']
    for rule in struct.rule_ids:
        if rule.code not in ('BASIC', 'GROSS', 'NET'):
            continue
        imd = IMD.search([('model', '=', 'hr.salary.rule'),
                          ('res_id', '=', rule.id)], limit=1)
        propia = bool(imd) and (imd.module or '').startswith('mx_jandea')
        if not propia:
            quitar |= rule
    _safe_remove_rules(env, quitar)


# ===========================================================================
# FONDO DE AHORRO / VALES DE DESPENSA  (nómina NORMAL, no finiquito)
#
# Se agregan a la estructura nativa 'l10n_mx_regular_pay' cuatro reglas:
#   FONDO_AHORRO_GRAV   (J) -> percepción GRAVADA  (integra IMSS/ISR)
#   FONDO_AHORRO_EXENTO (K) -> percepción EXENTA   (suma al neto, no a ISR)
#   VALES_DESPENSA_GRAV (M) -> percepción GRAVADA
#   VALES_DESPENSA_EXENTO (N) -> percepción EXENTA
#
# Las cuatro se disparan solo si en el recibo se captura "Sueldo Neto (FA/VD)"
# (SUELDO_NETO_FAVD), así la nómina normal no se altera cuando no se usan.
#
# Se construyen aquí (no en XML) porque la categoría EXENTA de l10n_mx tiene
# un XML-ID que puede variar; se resuelve de forma robusta en tiempo de
# instalación/actualización con varios respaldos.
# ===========================================================================

FAVD_PREAMBLE = '''
def _p(c, d):
    try:
        v = payslip._rule_parameter(c)
        return float(v) if v not in (None, False, "") else d
    except Exception:
        return d

def _in(c, d=0.0):
    # 1) objeto navegable 'inputs' (subíndice + atributo).
    try:
        v = inputs[c]
        if v and v.amount not in (None, False):
            return v.amount
    except Exception:
        pass
    # 2) respaldo directo: leer la entrada del recibo por código.
    try:
        for _il in payslip.input_line_ids:
            try:
                _code = _il.input_type_id.code if _il.input_type_id else False
            except Exception:
                _code = False
            if _code == c and _il.amount not in (None, False):
                return _il.amount
    except Exception:
        pass
    return d

def _cap(x, tope):
    return x if x < tope else tope

UMA       = _p("mx_jandea_uma", 117.31)
_dias_mes = _p("mx_jandea_favd_dias_mes", 30.4)
_dias_q   = _p("mx_jandea_favd_dias_quincena", 15.0)
_fa_mult  = _p("mx_jandea_fa_uma_mult", 1.3)
_fa_tasa  = _p("mx_jandea_fa_tasa", 0.13)
_vd_tasa  = _p("mx_jandea_vd_tasa", 0.10)
# Días que multiplican el tope de Vales total: 15 = H4 (patron dominante),
# 30.4 = H3 (variante de la fila atipica). Configurable sin tocar codigo.
_vd_dias_tope = _p("mx_jandea_vd_dias_tope", 15.0)

# Topes derivados de la UMA (equivalen a G3 y H4 del Excel):
_tope_g = UMA * _fa_mult * _dias_mes     # 1.3 * UMA * 30.4  (FA total / Vales gravable mensual)
_tope_h = UMA * _dias_q                  # UMA * 15          (FA gravable quincenal)
_tope_vd_total = UMA * _vd_dias_tope     # UMA * 15 (H4, def.) o UMA * 30.4 (H3)  (Vales total)

# Bases mensuales. Si no se capturan, se usa el sueldo del contrato.
_wage = (version and version.wage) or 0.0
sn = _in("SUELDO_NETO_FAVD", 0.0) or _wage     # D: comp objetivo (Sueldo Neto)
si = _in("SUELDO_IMSS_FAVD", 0.0) or _wage     # E: sueldo mensual registrado ante IMSS
f_q = si / 2.0                                  # F: sueldo quincenal IMSS

# Días para prorratear los totales (default: días del período del recibo).
_dias_periodo = (payslip.date_to - payslip.date_from).days + 1
dias = _in("DIAS_FAVD", 0.0) or _dias_periodo

# --- Fondo de Ahorro ---
fa_total  = (_cap(sn * _fa_tasa, _tope_g) / 30.0) * dias   # G "FA Real"
fa_grav   = _cap(f_q * _fa_tasa, _tope_h)                  # J  (gravable / integra IMSS)
fa_exento = fa_total - fa_grav                             # K
if fa_exento < 0:
    fa_exento = 0.0

# --- Vales de Despensa ---
vd_total  = 0.0 if si == 0 else (_cap(sn * _vd_tasa, _tope_vd_total) / 30.0) * dias   # H "VD Real"
vd_grav   = (_cap(si * _vd_tasa, _tope_g) / 30.0) * dias                       # M (gravable)
vd_exento = vd_total - vd_grav                                                 # N
if vd_exento < 0:
    vd_exento = 0.0
'''


def _favd_rules_spec():
    """Reglas de Fondo de Ahorro / Vales: (xmlid, nombre, código, tipo, seq, code).

    tipo: 'GRAV' -> categoría gravada (taxable);  'EXE' -> categoría exenta.
    """
    p = FAVD_PREAMBLE
    return [
        ('rule_fondo_ahorro_grav', 'Fondo de Ahorro (Gravado)',
         'FONDO_AHORRO_GRAV', 'GRAV', 90, p + '\nresult = fa_grav\n'),
        ('rule_fondo_ahorro_exento', 'Fondo de Ahorro (Exento)',
         'FONDO_AHORRO_EXENTO', 'EXE', 91, p + '\nresult = fa_exento\n'),
        ('rule_vales_despensa_grav', 'Vales de Despensa (Gravado)',
         'VALES_DESPENSA_GRAV', 'GRAV', 92, p + '\nresult = vd_grav\n'),
        ('rule_vales_despensa_exento', 'Vales de Despensa (Exento)',
         'VALES_DESPENSA_EXENTO', 'EXE', 93, p + '\nresult = vd_exento\n'),
    ]


def _resolve_favd_categories(env):
    """Devuelve (cat_gravada, cat_exenta) de forma robusta.

    - Gravada: categoría taxable_alw de l10n_mx (ya usada por el módulo).
    - Exenta:  se intenta por XML-ID; si no, por nombre ('exent'/'exempt');
      como último respaldo se crea una categoría propia (informa en el log).
      La categoría exenta debe sumar al NETO pero NO a la base de ISR.
    """
    Cat = env['hr.salary.rule.category']

    gravada = env.ref('l10n_mx_hr_payroll.l10n_mx_category_taxable_alw',
                      raise_if_not_found=False)
    if not gravada:
        gravada = Cat.search([('code', '=', 'ALW')], limit=1) \
            or _get_category(env, 'ALW', 'Allowance')

    exenta = env.ref('l10n_mx_hr_payroll.l10n_mx_category_exempt_alw',
                     raise_if_not_found=False)
    if not exenta:
        exenta = Cat.search(['|', ('name', 'ilike', 'exent'),
                             ('name', 'ilike', 'exempt')], limit=1)
    if not exenta:
        exenta = Cat.search(['|', ('code', 'ilike', 'exent'),
                             ('code', 'ilike', 'exempt')], limit=1)
    if not exenta:
        # Respaldo: crear categoría propia. OJO: para que quede realmente
        # EXENTA (fuera de la base de ISR) puede requerir ajustar la regla NET
        # de la localización; se avisa para revisión manual.
        exenta = _get_category(env, 'PERCEP_EXE', 'Percepción Exenta (MX)')
        _logger.warning(
            '%s: no se encontró la categoría EXENTA de l10n_mx; se usó una '
            'categoría propia "PERCEP_EXE". Verifica que no entre a la base '
            'de ISR.', MODULE)
    return gravada, exenta


def _build_favd_rules(env):
    """Crea/enlaza las 4 reglas de Fondo de Ahorro / Vales en 'regular_pay'."""
    struct = env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay',
                     raise_if_not_found=False)
    if not struct:
        _logger.warning('%s: no se encontró l10n_mx_regular_pay; no se '
                        'crearon las reglas de FA/Vales.', MODULE)
        return

    gravada, exenta = _resolve_favd_categories(env)

    # Entrada disparadora: "Sueldo Neto (FA/VD)".
    trigger = env['hr.payslip.input.type'].search(
        [('code', '=', 'SUELDO_NETO_FAVD')], limit=1)

    Rule = env['hr.salary.rule']
    creadas = 0
    for xmlid, name, code, tipo, seq, python_code in _favd_rules_spec():
        if env.ref('%s.%s' % (MODULE, xmlid), raise_if_not_found=False):
            continue
        vals = {
            'name': name,
            'code': code,
            'category_id': (gravada if tipo == 'GRAV' else exenta).id,
            'struct_id': struct.id,
            'sequence': seq,
            'appears_on_payslip': True,
            'amount_select': 'code',
            'amount_python_compute': python_code,
        }
        # Solo se calculan si se captura el Sueldo Neto (FA/VD).
        if trigger:
            vals['condition_select'] = 'input'
            vals['condition_other_input_id'] = trigger.id
        else:
            vals['condition_select'] = 'none'
        rule = Rule.create(vals)
        _link(env, xmlid, 'hr.salary.rule', rule.id)
        creadas += 1

    _logger.info('%s: %s regla(s) de Fondo de Ahorro / Vales creadas.',
                 MODULE, creadas)


def post_init_hook(env):
    """Crea la estructura de Finiquito con todas sus reglas."""
    struct = env.ref('%s.%s' % (MODULE, STRUCT_XMLID), raise_if_not_found=False)

    if not struct:
        regular = env.ref(
            'l10n_mx_hr_payroll.l10n_mx_regular_pay', raise_if_not_found=False)
        if not regular:
            _logger.warning(
                '%s: no se encontró l10n_mx_regular_pay; no se creó la '
                'estructura de Finiquito.', MODULE)
            return
        vals = {
            'name': 'Mexico: Finiquito / Liquidación',
            'type_id': regular.type_id.id,
        }
        if 'country_id' in env['hr.payroll.structure']._fields:
            vals['country_id'] = regular.country_id.id
        struct = env['hr.payroll.structure'].create(vals)
        _link(env, STRUCT_XMLID, 'hr.payroll.structure', struct.id)
        _logger.info('%s: estructura de Finiquito creada (id=%s).',
                     MODULE, struct.id)

    # Enlazar las entradas del finiquito a la estructura.
    InputType = env['hr.payslip.input.type']
    inputs = InputType.search([('code', 'in', FNQT_INPUT_CODES)])
    for it in inputs:
        if struct not in it.struct_ids:
            it.struct_ids = [(4, struct.id)]

    # Categorías. PATRONAL se crea si no existe (costo patronal, fuera del neto).
    cats = {}
    for code, name in (('BASIC', None), ('ALW', None), ('DED', None),
                       ('GROSS', None), ('NET', None),
                       ('PATRONAL', 'Costo Patronal (informativo)')):
        cats[code] = _get_category(env, code, name)

    Rule = env['hr.salary.rule']
    created = 0
    for xmlid, name, code, cat_code, seq, python_code in _rules_spec():
        if env.ref('%s.%s' % (MODULE, xmlid), raise_if_not_found=False):
            continue
        category = cats.get(cat_code)
        if not category:
            _logger.warning('%s: sin categoría "%s"; se omite la regla %s.',
                            MODULE, cat_code, code)
            continue
        rule = Rule.create({
            'name': name,
            'code': code,
            'category_id': category.id,
            'struct_id': struct.id,
            'sequence': seq,
            'appears_on_payslip': True,
            'condition_select': 'none',
            'amount_select': 'code',
            'amount_python_compute': python_code,
        })
        _link(env, xmlid, 'hr.salary.rule', rule.id)
        created += 1

    # Quitar la regla nativa "Basic Salary" que Odoo agrega a la estructura.
    _clean_foreign_rules(env, struct)

    # Reaplicar parches sobre reglas nativas (aguinaldo capturable + getattr).
    _patch_native_rules(env)

    # Reglas de Fondo de Ahorro / Vales de Despensa en la nómina NORMAL.
    _build_favd_rules(env)

    _logger.info('%s: %s regla(s) de finiquito creadas.', MODULE, created)
