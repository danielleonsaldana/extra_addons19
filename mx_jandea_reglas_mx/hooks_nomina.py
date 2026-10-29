# -*- coding: utf-8 -*-
"""Nómina NORMAL (estructura ``l10n_mx_regular_pay``).

Replica el Excel "Jandea_Ejemplo_Listado_de_Nomina.xlsx" (hoja Ejemplo):

  * Cada percepción con exención se parte en dos reglas: GRAVADA y EXENTA.
    Así la base de ISR sale sola y el CFDI queda con el desglose correcto.
  * Regla informativa ``BASE_GRAVABLE_ISR`` = columna W del Excel.
  * ISR MENSUALIZADO y luego prorrateado a la periodicidad de la nómina
    (columna X), sobre la base gravable y no sobre el GROSS completo.

Este archivo NO toca nada del finiquito: vive aparte de ``hooks.py`` y solo
escribe sobre la estructura nativa de nómina normal.

v19.0.1.26.0 — ISR quincenal alineado con Aspel:

  1. La BASE GRAVABLE se arma SUMANDO (sueldo + lo que grava) en vez de
     restarle los exentos al GROSS. Así el fondo de ahorro NO resta nada de
     la base: solo suma el EXCEDENTE del tope (1.3 UMA por día del periodo,
     es decir UMA x 15 x 1.3 en una quincena).
  2. La mensualización usa 30.4 / días del periodo (quincena = 30.4/15 =
     2.026667), no 2.0.
  3. Se calcula el SUBSIDIO PARA EL EMPLEO conforme al decreto DOF
     31/12/2025 (15.02% de la UMA mensual, prorrateado entre 30.4 por los
     días del periodo, tope de ingreso mensual $11,492.66) y se resta al
     ISR dentro de la misma regla, como lo muestra Aspel.

Correcciones aplicadas respecto del Excel original (decisión del cliente):
  * ``O9`` apuntaba a ``OJ129`` (referencia inexistente) -> salario diario.
  * ``W8`` sumaba el TOPE de vales en vez del EXCEDENTE.
  * ``N8/W8/W9/W10`` usaban ``G1``/``G2`` sin ``$`` -> se rompían al copiar.
  * Festivo y descanso laborado: se paga el DOBLE adicional al día normal
    que ya trae el sueldo (LFT arts. 73 y 75) — v1.27.0.
  * La exención de tiempo extra es SEMANAL y COMPARTIDA entre horas extra,
    festivo y descanso: 100% sin tope si gana el mínimo; 50% con bolsa de
    5 UMA por semana si gana más (art. 93 fr. I LISR) — v1.27.0.

Todo lo configurable son ``hr.rule.parameter``; no hay cifras en el código.
"""
import logging

_logger = logging.getLogger(__name__)

MODULE = 'mx_jandea_reglas_mx'

# Códigos de entrada de la nómina normal.
NOM_INPUT_CODES = [
    'SALARIO_DIARIO', 'DIAS_LABORADOS', 'DIAS_DESCANSO', 'PRIMA_VAC_DIAS',
    'PRIMA_VACACIONAL', 'VALES_DESPENSA', 'FONDO_AHORRO', 'OTRAS_PERCEPCIONES',
    'FALTAS', 'DIAS_FESTIVO', 'HRS_EXTRA_DOBLE', 'HRS_EXTRA_TRIPLE',
    'DOMINGOS_PRIMA_DOM',
]

# Reglas nativas de l10n_mx que cubren el mismo concepto. Si existen y además
# se captura la entrada Jandea, el concepto se pagaría DOS VECES: se avisa en
# el log al instalar/actualizar.
NATIVAS_EQUIVALENTES = {
    'PRIMA_VAC_MX': 'HOLIDAY_BONUS',
    'VALES_DESPENSA_GRAV': 'TAX_MEAL_VOUCHER',
    'VALES_DESPENSA_EXENTO': 'NO_TAX_MEAL_VOUCHER',
    'FONDO_AHORRO_GRAV': 'SAVINGS_FUND_EMPLOYER_ALW',
    'FONDO_AHORRO_EMPLEADO': 'SAVINGS_FUND_EMPLOYEE',
    'FONDO_AHORRO_PATRON_DED': 'SAVINGS_FUND_EMPLOYER_DED',
}


# ===========================================================================
# PREÁMBULO COMÚN
#
# Se antepone a TODAS las reglas de nómina normal para que gravado, exento,
# base gravable e ISR salgan de exactamente los mismos números.
# ===========================================================================

NOM_PREAMBLE = '''
def _p(c, d):
    try:
        v = payslip._rule_parameter(c)
        return float(v) if v not in (None, False, "") else d
    except Exception:
        return d

def _in(c, d=0.0):
    # 1) objeto navegable "inputs".
    try:
        v = inputs[c]
        if v and v.amount not in (None, False):
            return v.amount
    except Exception:
        pass
    # 2) respaldo directo: leer la entrada capturada del recibo por codigo.
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

UMA = _p("mx_jandea_uma", 117.31)
SMG = _p("mx_jandea_smg", 315.04)

# Reglas que trae la estructura del recibo. Sirve para que una estructura
# SIN fondo de ahorro / vales no los sume a la base gravable del ISR.
try:
    _codigos_struct = set(payslip.struct_id.rule_ids.mapped("code"))
except Exception:
    _codigos_struct = set()

def _en_struct(c):
    return (not _codigos_struct) or (c in _codigos_struct)

# --------------------------------------------------------------------------
# PERIODICIDAD
# Los dias de cada periodicidad salen de l10n_mx_schedule_table. En l10n_mx
# "bi-weekly" es QUINCENAL (15 dias) y la catorcenal es "14_days".
# --------------------------------------------------------------------------
_dias_calendario = (payslip.date_to - payslip.date_from).days + 1
try:
    _sched = (version and version["schedule_pay"]) or "monthly"
except Exception:
    _sched = "monthly"

_DIAS_SCHED = {"daily": 1.0, "weekly": 7.0, "10_days": 10.0, "14_days": 14.0,
               "bi-weekly": 15.0, "semi-monthly": 15.0, "monthly": 30.0,
               "bi-monthly": 60.0}
dias_nomina = 0.0
try:
    _tbl_dias = payslip._rule_parameter("l10n_mx_schedule_table") or {}
    dias_nomina = float(_tbl_dias.get(_sched) or 0.0)
except Exception:
    dias_nomina = 0.0
if not dias_nomina:
    dias_nomina = _DIAS_SCHED.get(_sched) or float(_dias_calendario or 30)

# Factor de mensualizacion del ISR: dias_mes / dias del periodo, como Aspel.
#   quincena -> 30.4 / 15 = 2.026667
#   semana   -> 30.4 / 7  = 4.342857
#   mes      -> 30.4 / 30 = 1.013333  (mx_jandea_isr_mensual_directo = 1
#                                       para aplicar la tarifa mensual tal cual)
_DIAS_MES = _p("mx_jandea_dias_mes_isr", 30.4)
if dias_nomina >= 30.0 and _p("mx_jandea_isr_mensual_directo", 0.0):
    factor_mes = 30.0 / dias_nomina
else:
    factor_mes = _DIAS_MES / (dias_nomina or _DIAS_MES)

# La exencion de tiempo extra es SEMANAL -> cuantas semanas trae el periodo.
semanas = dias_nomina / 7.0

# --------------------------------------------------------------------------
# SALARIO DIARIO
# El "wage" del contrato es el importe DEL PERIODO; se divide entre los dias
# de la periodicidad.
# --------------------------------------------------------------------------
try:
    _wage = (version and version.wage) or 0.0
except Exception:
    _wage = 0.0
sd = _in("SALARIO_DIARIO", 0.0) or (_wage / (dias_nomina or 1.0))

# --------------------------------------------------------------------------
# ASISTENCIA
# Faltas del periodo, en este orden:
#  1) entrada FALTAS capturada en el recibo (dias);
#  2) dias NO pagados (ausencias sin goce) del recibo, llevados a la escala
#     de dias de la periodicidad.
# Dias pagados = dias del periodo - faltas, salvo que se capture
# DIAS_LABORADOS. Vales y fondo de ahorro se calculan sobre esos dias.
# --------------------------------------------------------------------------
def _faltas_de(ps, dias_per):
    _f = 0.0
    _hay = False
    try:
        for _il in ps.input_line_ids:
            _c = _il.input_type_id.code if _il.input_type_id else False
            if _c == "FALTAS":
                _f += _il.amount or 0.0
                _hay = True
    except Exception:
        pass
    if _hay:
        return _f
    _tot = 0.0
    _sin_goce = 0.0
    try:
        for _wd in ps.worked_days_line_ids:
            _n = _wd.number_of_days or 0.0
            _tot += _n
            if not _wd.is_paid:
                _sin_goce += _n
    except Exception:
        return 0.0
    if _tot and _sin_goce:
        return dias_per * _sin_goce / _tot
    return 0.0

def _dias_pagados_de(ps, dias_per):
    try:
        for _il in ps.input_line_ids:
            _c = _il.input_type_id.code if _il.input_type_id else False
            if _c == "DIAS_LABORADOS" and _il.amount:
                return _il.amount
    except Exception:
        pass
    _d = dias_per - _faltas_de(ps, dias_per)
    return _d if _d > 0.0 else 0.0

faltas = _faltas_de(payslip, dias_nomina)
dias_lab = _dias_pagados_de(payslip, dias_nomina)
factor_asistencia = (dias_lab / dias_nomina) if dias_nomina else 0.0
sueldo_mensual = sd * 30.0
_prorrata = (dias_lab / 30.0) if dias_lab else 0.0

# --------------------------------------------------------------------------
# TIEMPO EXTRA / FESTIVO / DESCANSO
# Horas extra: dobles (LFT art. 67) y triples (art. 68).
# Festivo y descanso laborados: se paga el DOBLE como concepto adicional
# (LFT arts. 73 y 75); el dia normal ya viene incluido en el sueldo.
#
# Exencion art. 93 fr. I LISR:
#  - Gana el minimo: 100% exento, sin tope de UMA.
#  - Gana mas del minimo: 50% exento, con tope de 5 UMA por semana
#    (bolsa comun repartida en este orden: dobles, triples, festivo, descanso).
# --------------------------------------------------------------------------
try:
    _horas_dia = (version.resource_calendar_id.hours_per_day or 8.0)
except Exception:
    _horas_dia = 8.0
_sh = sd / (_horas_dia or 8.0)

_mult_fest = _p("mx_jandea_festivo_mult", 2.0)
_dias_fest = _in("DIAS_FESTIVO", 0.0)
_dias_desc = _in("DIAS_DESCANSO", 0.0)

he_doble_imp = _sh * 2.0 * _in("HRS_EXTRA_DOBLE", 0.0)
he_triple_imp = _sh * 3.0 * _in("HRS_EXTRA_TRIPLE", 0.0)
festivo_imp = sd * _mult_fest * _dias_fest
descanso_imp = sd * _mult_fest * _dias_desc

# Gana el minimo: SD <= SMG (tolerancia de centavos por redondeo).
gana_minimo = sd <= (SMG + 0.01)

if gana_minimo:
    _te_pct = 1.0
    _bolsa = float("inf")
else:
    _te_pct = _p("mx_jandea_te_pct_exento", 0.5)
    # 0 = semanas reales del periodo; 1 = una sola bolsa por periodo.
    _sem_exe = _p("mx_jandea_te_semanas", 0.0) or semanas
    _bolsa = UMA * _p("mx_jandea_te_uma_semana", 5.0) * _sem_exe

def _reparte(importe, bolsa):
    _tope = importe * _te_pct
    _exe = _tope if _tope < bolsa else bolsa
    if _exe < 0:
        _exe = 0.0
    return _exe, bolsa - _exe

he_doble_exe, _bolsa = _reparte(he_doble_imp, _bolsa)
he_triple_exe, _bolsa = _reparte(he_triple_imp, _bolsa)
festivo_exe, _bolsa = _reparte(festivo_imp, _bolsa)
descanso_exe, _bolsa = _reparte(descanso_imp, _bolsa)

he_doble_grav = he_doble_imp - he_doble_exe
he_triple_grav = he_triple_imp - he_triple_exe
festivo_grav = festivo_imp - festivo_exe
descanso_grav = descanso_imp - descanso_exe

# --------------------------------------------------------------------------
# PRIMA VACACIONAL - exenta 15 UMA
# --------------------------------------------------------------------------
pv_imp = _in("PRIMA_VACACIONAL", 0.0) or (
    sd * _in("PRIMA_VAC_DIAS", 0.0) * _p("mx_jandea_pv_pct", 0.25))
_pv_tope = UMA * _p("mx_jandea_pv_uma", 15.0)
pv_exe = pv_imp if pv_imp < _pv_tope else _pv_tope
pv_grav = pv_imp - pv_exe

# --------------------------------------------------------------------------
# PRIMA DOMINICAL - 25% del SD por domingo; exenta 1 UMA por domingo
# (o 1 SMG si mx_jandea_pd_base_smg = 1).
# --------------------------------------------------------------------------
_domingos = _in("DOMINGOS_PRIMA_DOM", 0.0)
pd_imp = sd * _domingos * _p("mx_jandea_pd_pct", 0.25)
_pd_base = SMG if _p("mx_jandea_pd_base_smg", 0.0) else UMA
_pd_tope = _pd_base * _domingos
pd_exe = pd_imp if pd_imp < _pd_tope else _pd_tope
pd_grav = pd_imp - pd_exe

# Dias para topar exenciones del periodo.
_dias_exe = dias_lab or dias_nomina

# --------------------------------------------------------------------------
# VALES DE DESPENSA
# Tope exento = 40% de la UMA x 30.4 (mx_jandea_vd_dias_tope_base; 0 = dias
# del periodo). Lo que rebase el tope GRAVA.
#
# Se entregan UNA vez al mes:
#   * semanal / mensual: en el recibo que cierra el mes;
#   * quincenal: en la quincena cuyo date_to sea >= mx_jandea_vd_dia_desde
#     (16 = segunda quincena; 0 = en todas).
# En automatico (mx_jandea_vd_auto = 1) el monto del mes es el 10% de
# salario diario x dias PAGADOS de cada recibo del mes (cada falta descuenta
# su parte); los periodos del mes que aun no se calculan se proyectan
# completos.
# --------------------------------------------------------------------------
_vd_dias = _p("mx_jandea_vd_dias_tope_base", 30.4) or _dias_exe
_vd_tope = UMA * _p("mx_jandea_vd_uma_pct", 0.40) * _vd_dias
_vd_calc = (sueldo_mensual * _p("mx_jandea_vd_tasa", 0.10)) * _prorrata
if _p("mx_jandea_vd_topar_importe", 0.0) and _vd_calc > _vd_tope:
    _vd_calc = _vd_tope
vd_imp = _in("VALES_DESPENSA", 0.0) or (
    _vd_calc if _p("mx_jandea_vd_auto", 0.0) else 0.0)
_vd_dia_desde = _p("mx_jandea_vd_dia_desde", 0.0)
_ultimo_mes = payslip.date_to + relativedelta(day=31)
_inicio_mes = payslip.date_from + relativedelta(day=1)
_es_fin_mes = payslip.date_from <= _ultimo_mes and payslip.date_to >= (_ultimo_mes + relativedelta(days=-2))
if _sched == "weekly" or _sched == "monthly":
    _puede_vale = _es_fin_mes
else:
    _puede_vale = (not _vd_dia_desde) or (payslip.date_to.day >= _vd_dia_desde)
if not _puede_vale:
    vd_imp = 0.0
elif not _in("VALES_DESPENSA", 0.0) and _p("mx_jandea_vd_auto", 0.0):
    _este = sd * dias_lab
    _prev = payslip.env["hr.payslip"].search([
        ("employee_id", "=", payslip.employee_id.id),
        ("state", "!=", "cancel"),
        ("date_to", ">=", _inicio_mes),
        ("date_to", "<", payslip.date_from),
    ], order="date_to desc")
    _suma = _este
    _nprev = 0
    for _ps in _prev:
        _suma += sd * _dias_pagados_de(_ps, dias_nomina)
        _nprev += 1
    _periodo_completo = sd * dias_nomina
    if _sched == "weekly":
        _faltan = 3 - _nprev
        if _faltan > 0:
            _suma += _faltan * _periodo_completo
    elif _sched != "monthly" and _nprev < 1:
        _suma += _periodo_completo
    _vd_mes = _suma * _p("mx_jandea_vd_tasa", 0.10)
    if _p("mx_jandea_vd_topar_importe", 0.0) and _vd_mes > _vd_tope:
        _vd_mes = _vd_tope
    vd_imp = _vd_mes
if not (_en_struct("VALES_DESPENSA_GRAV") or _en_struct("VALES_DESPENSA_EXENTO")):
    vd_imp = 0.0
vd_exe = vd_imp if vd_imp < _vd_tope else _vd_tope
vd_grav = vd_imp - vd_exe

# --------------------------------------------------------------------------
# FONDO DE AHORRO - art. 93 fr. XI LISR
# Exento hasta 1.3 UMA x dias (mx_jandea_fa_dias_tope_base; 0 = dias del
# periodo) y nunca mas de 1.3 UMA x 365 en el año (se descuenta lo exento de
# los recibos anteriores del año). Solo el EXCEDENTE grava.
# El importe automatico es 13% de salario diario x dias PAGADOS; un importe
# capturado fijo tambien se proporciona a la asistencia
# (mx_jandea_fa_captura_asist = 0 para respetarlo tal cual).
# --------------------------------------------------------------------------
_fa_dias = _p("mx_jandea_fa_dias_tope_base", 30.4) or _dias_exe
_fa_tope = UMA * _p("mx_jandea_fa_uma_mult", 1.3) * _fa_dias
_fa_tope_anual = UMA * _p("mx_jandea_fa_uma_mult", 1.3) * 365.0
_ytd_fa = 0.0
_prev_fa = payslip.env["hr.payslip"].search([
    ("employee_id", "=", payslip.employee_id.id),
    ("state", "!=", "cancel"),
    ("date_from", ">=", date(payslip.date_from.year, 1, 1)),
    ("date_to", "<", payslip.date_from),
])
for _ps in _prev_fa:
    for _ln in _ps.line_ids:
        if _ln.code == "FONDO_AHORRO_EXENTO":
            _ytd_fa += _ln.total
_queda_fa = _fa_tope_anual - _ytd_fa
if _queda_fa < 0.0:
    _queda_fa = 0.0
if _queda_fa < _fa_tope:
    _fa_tope = _queda_fa
_fa_calc = (sd * dias_lab) * _p("mx_jandea_fa_tasa", 0.13)
if _p("mx_jandea_fa_topar_importe", 0.0) and _fa_calc > _fa_tope:
    _fa_calc = _fa_tope
_fa_cap = _in("FONDO_AHORRO", 0.0)
if _fa_cap and _p("mx_jandea_fa_captura_asist", 1.0):
    _fa_cap = _fa_cap * factor_asistencia
fa_imp = _fa_cap or (
    _fa_calc if _p("mx_jandea_fa_auto", 0.0) else 0.0)
if not (_en_struct("FONDO_AHORRO_GRAV") or _en_struct("FONDO_AHORRO_EXENTO")):
    fa_imp = 0.0
fa_exe = fa_imp if fa_imp < _fa_tope else _fa_tope
fa_grav = fa_imp - fa_exe

# --------------------------------------------------------------------------
# OTRAS PERCEPCIONES - gravan al 100%
# --------------------------------------------------------------------------
otras_perc = _in("OTRAS_PERCEPCIONES", 0.0)

# --------------------------------------------------------------------------
# TOTAL EXENTO del periodo.
# --------------------------------------------------------------------------
total_exento = (he_doble_exe + he_triple_exe + festivo_exe + descanso_exe
                + pv_exe + pd_exe + vd_exe + fa_exe)
'''


# Base gravable (columna W) e ISR mensualizado (columna X).
NOM_BASE_BLOCK = '''
# --------------------------------------------------------------------------
# BASE GRAVABLE (columna W del Excel)
#
# METODO ADITIVO (por omision, mx_jandea_base_metodo = 0):
#     base = sueldo + SOLO lo que grava
# Se suma el sueldo del periodo mas la parte GRAVADA de cada concepto. El
# fondo de ahorro y los vales NO restan nada: solo suman su excedente del
# tope de exencion. Es el criterio de Aspel y evita depender de como arme
# l10n_mx la categoria GROSS.
#
# METODO SUSTRACTIVO (mx_jandea_base_metodo = 1): comportamiento anterior,
# base = GROSS - exentos. Se deja como escape por si alguna empresa mete
# percepciones gravadas por fuera de estas reglas.
# --------------------------------------------------------------------------
try:
    _basic = categories["BASIC"]
except Exception:
    _basic = 0.0
if not _basic:
    _basic = sd * dias_lab

base_gravable = (_basic
                 + he_doble_grav + he_triple_grav
                 + festivo_grav + descanso_grav
                 + pv_grav + pd_grav
                 + vd_grav + fa_grav
                 + otras_perc)

if _p("mx_jandea_base_metodo", 0.0):
    _gross = categories["GROSS"]
    if _p("mx_jandea_gross_incluye_exento", 1.0):
        base_gravable = _gross - total_exento
    else:
        base_gravable = _gross

if base_gravable < 0:
    base_gravable = 0.0
'''

NOM_ISR_BLOCK = '''
# --------------------------------------------------------------------------
# ISR (columna X)  —  mismo camino que Aspel:
#
#   1) base            = sueldo + solo lo que grava
#   2) base_mes        = base * (30.4 / dias del periodo)
#   3) impuesto_mes    = tarifa mensual SAT (Anexo 8 RMF)
#   4) impuesto_periodo= impuesto_mes * (dias del periodo / 30.4)
#   5) impuesto_neto   = impuesto_periodo - subsidio para el empleo
#
# El subsidio se calcula aqui (decreto DOF 31/12/2025) y se resta en la misma
# regla, para que la linea de ISR muestre el neto igual que Aspel. Las reglas
# nativas SUBSIDY / SUBSIDY_CURRENT_MONTH / SUBSIDY_NEXT_MONTH se neutralizan
# para no duplicarlo (ver _patch_subsidio). Con
# mx_jandea_isr_neto_subsidio = 0 se invierte: el ISR sale bruto y el subsidio
# vuelve a su propia linea.
# --------------------------------------------------------------------------
def _isr_tabla():
    try:
        t = payslip._rule_parameter("l10n_mx_isr_tables")["monthly"]
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

_isr_mes = 0.0
_bg_mensual = base_gravable * factor_mes
if _bg_mensual > 0:
    _low, _fix, _rate = 0.01, 0.0, 0.0192
    for _l, _h, _f, _r in _isr_tabla():
        if _bg_mensual >= _l:
            _low, _fix, _rate = _l, _f, _r
    _isr_mes = (_bg_mensual - _low) * _rate + _fix
_isr_bruto = _isr_mes / (factor_mes or 1.0)

# --------------------------------------------------------------------------
# SUBSIDIO PARA EL EMPLEO  (decreto DOF 31/12/2025, vigente 2026)
#   monto mensual = UMA mensual * 15.02%   (enero 2026: 15.59% de la UMA 2025)
#   periodos menores a un mes: monto mensual / 30.4 * dias del periodo
#   solo si el ingreso GRAVADO mensual no excede $11,492.66
# El monto mensual se toma del parametro mx_jandea_subsidio_monto_mes si esta
# capturado (asi se versiona por año/mes sin tocar codigo); si va en 0 se
# calcula con el porcentaje.
# --------------------------------------------------------------------------
_sub_mes = _p("mx_jandea_subsidio_monto_mes", 0.0)
if not _sub_mes:
    _sub_mes = (UMA * _DIAS_MES) * _p("mx_jandea_subsidio_pct", 0.1502)
subsidio = 0.0
if _bg_mensual > 0 and _bg_mensual <= _p("mx_jandea_subsidio_limite_mes",
                                         11492.66):
    subsidio = (_sub_mes / (_DIAS_MES or 30.4)) * dias_nomina

# Desde el decreto de 2024 el subsidio ya NO se entrega en efectivo cuando
# supera al impuesto: solo lo cancela.
if _p("mx_jandea_isr_neto_subsidio", 1.0):
    _isr = _isr_bruto - subsidio
else:
    _isr = _isr_bruto

# --------------------------------------------------------------------------
# SALARIO MINIMO (art. 96 LISR) — se decide POR SUCURSAL (empresa):
#   casilla "Retener ISR aunque gane el salario minimo" de la empresa del
#   recibo (res.company.mx_jandea_isr_retener_minimo).
#     marcada    -> se retiene el MISMO ISR que a los demas (tarifa - subsidio)
#     desmarcada -> quien gana el minimo no paga ISR
# Si el campo no existe se usa el parametro mx_jandea_isr_al_minimo.
# --------------------------------------------------------------------------
try:
    _retener_min = bool(payslip.company_id["mx_jandea_isr_retener_minimo"])
except Exception:
    _retener_min = bool(_p("mx_jandea_isr_al_minimo", 1.0))
isr_exento_minimo = bool(gana_minimo and not _retener_min)
if isr_exento_minimo:
    _isr = 0.0
if _isr < 0:
    _isr = 0.0
'''


# Bloque de COMPATIBILIDAD con las reglas nativas que van despues del ISR.
#
# Odoo evalua todas las reglas de un recibo sobre el MISMO diccionario
# (safe_eval con nocopy=True), asi que las variables que deja una regla las
# leen las siguientes. La formula nativa de ISR publicaba estos nombres y hay
# reglas de l10n_mx que dependen de ellos; por ejemplo ISR_MINIMUM_WAGE tiene
# como condicion "result = gross <= min_wage". Si no se publican, el recibo
# truena con NameError. Se calculan igual que en la formula nativa.
NOM_COMPAT_BLOCK = '''
def find_rates(x, rates):
    for low, high, fix, rate in rates:
        if low <= x <= high:
            return low, high, fix, rate
    # Si no cae en ningun tramo (GROSS = 0, empleado con todas faltas) se
    # devuelve el primero en vez de reventar.
    return rates[0] if rates else (0.0, 0.0, 0.0, 0.0)

gross = categories["GROSS"]

_tables = payslip._rule_parameter("l10n_mx_isr_tables") or {}
isr_table = _tables.get(_sched) or _tables.get("monthly") or []
low, high, fix, rate = find_rates(gross, isr_table) if isr_table else (
    0.0, 0.0, 0.0, 0.0)

_sched_tbl = payslip._rule_parameter("l10n_mx_schedule_table") or {}
period_factor = _sched_tbl.get(_sched, 30) or 30
if period_factor >= 15:
    period_factor = (period_factor / 30) * (365 / 12)
min_wage = (payslip._rule_parameter("l10n_mx_daily_min_wage") or 0.0) \\
    * period_factor
'''


def _por_dia(var, dias):
    """Cola de regla: importe por dia x dias (el importe ya incluye los dias,
    asi que se divide para que cantidad x importe no los multiplique dos
    veces)."""
    return ('\nif %(d)s > 0:\n'
            '    result = %(v)s / %(d)s\n'
            '    result_qty = %(d)s\n'
            'else:\n'
            '    result = 0.0\n'
            '    result_qty = 0.0\n') % {'v': var, 'd': dias}


def _nomina_rules_spec():
    """Reglas de la nómina normal.

    Devuelve tuplas (xmlid, nombre, código, tipo, secuencia, fórmula).
    tipo: 'GRAV' gravada · 'EXE' exenta · 'DED' deducción · 'INFO' informativa.
    """
    p = NOM_PREAMBLE
    return [
        # ------------------- PERCEPCIONES GRAVADAS -------------------
        ('rule_nom_prima_vac', 'Prima Vacacional (Gravado)',
         'PRIMA_VAC_MX', 'GRAV', 82, p + '\nresult = pv_grav\n'),
        ('rule_nom_prima_vac_exe', 'Prima Vacacional (Exento)',
         'PRIMA_VAC_MX_EXE', 'EXE', 83, p + '\nresult = pv_exe\n'),

        ('rule_nom_prima_dom_exe', 'Prima Dominical (Exento)',
         'PRIMA_DOM_EXE', 'EXE', 84, p + '\nresult = pd_exe\n'),

        ('rule_nom_festivo_exe', 'Festivo Laborado (Exento)',
         'FESTIVO_LABORADO_EXE', 'EXE', 85,
         p + _por_dia('festivo_exe', '_dias_fest')),

        ('rule_nom_he_doble_exe', 'Horas Extra Dobles (Exento)',
         'HRS_EXTRA_DOBLE_EXE', 'EXE', 86, p + '\nresult = he_doble_exe\n'),
        ('rule_nom_he_triple_exe', 'Horas Extra Triples (Exento)',
         'HRS_EXTRA_TRIPLE_EXE', 'EXE', 87, p + '\nresult = he_triple_exe\n'),

        ('rule_nom_descanso', 'Descanso Laborado (Gravado)',
         'DESCANSO_LABORADO', 'GRAV', 88,
         p + _por_dia('descanso_grav', '_dias_desc')),
        ('rule_nom_descanso_exe', 'Descanso Laborado (Exento)',
         'DESCANSO_LABORADO_EXE', 'EXE', 89,
         p + _por_dia('descanso_exe', '_dias_desc')),

        ('rule_nom_otras_perc', 'Otras Percepciones',
         'OTRAS_PERCEPCIONES', 'GRAV', 98, p + '\nresult = otras_perc\n'),

        # ------------------- DEDUCCIONES -------------------
        # Los vales se COMPENSAN: se pagan en especie y no suman al neto a
        # dispersar. Ademas llevan el descuento de $1.00 por entrega.
        ('rule_nom_vales_compensa', 'Compensación Vales de Despensa',
         'VALES_COMPENSACION', 'DED', 155,
         p + '\nresult = -(vd_imp) if _p("mx_jandea_vd_compensa", 1.0) else 0.0\n'),
        ('rule_nom_desc_vales', 'Descuento Vales de Despensa',
         'DESCUENTO_VALES', 'DED', 156,
         p + '\nresult = -_p("mx_jandea_vd_descuento", 1.0) if vd_imp else 0.0\n'),
        ('rule_nom_fa_empleado', 'Fondo de Ahorro (Empleado)',
         'FONDO_AHORRO_EMPLEADO', 'DED', 157, p + '\nresult = -fa_imp\n'),
        ('rule_nom_fa_patron_ded', 'Fondo de Ahorro (Descuento Patrón)',
         'FONDO_AHORRO_PATRON_DED', 'DED', 158, p + '\nresult = -fa_imp\n'),

        # ------------------- INFORMATIVAS -------------------
        ('rule_nom_base_gravable', 'Info · Total Base Gravable',
         'BASE_GRAVABLE_ISR', 'INFO', 205,
         p + NOM_BASE_BLOCK + '\nresult = base_gravable\n'),
        ('rule_nom_isr_mensualizado', 'Info · ISR Mensualizado',
         'INFO_ISR_MENSUAL', 'INFO', 206,
         p + NOM_BASE_BLOCK + NOM_ISR_BLOCK + NOM_COMPAT_BLOCK
         + '\nresult = _isr_mes\n'),
        ('rule_nom_isr_periodo', 'Info · ISR del Período (antes de subsidio)',
         'INFO_ISR_BRUTO', 'INFO', 207,
         p + NOM_BASE_BLOCK + NOM_ISR_BLOCK + NOM_COMPAT_BLOCK
         + '\nresult = _isr_bruto\n'),
        ('rule_nom_subsidio_info', 'Info · Subsidio para el Empleo aplicado',
         'INFO_SUBSIDIO', 'INFO', 208,
         p + NOM_BASE_BLOCK + NOM_ISR_BLOCK + NOM_COMPAT_BLOCK + '''
result = subsidio if _p("mx_jandea_isr_neto_subsidio", 1.0) else 0.0
if _isr_bruto < result:
    result = _isr_bruto
'''),
    ]


def _isr_rule_code():
    """Fórmula que sustituye a la regla ISR nativa de 'Regular Pay'.

    El bloque de compatibilidad va SIEMPRE al final para que las variables que
    esperan las reglas nativas posteriores queden publicadas pase lo que pase.
    """
    return (NOM_PREAMBLE + NOM_BASE_BLOCK + NOM_ISR_BLOCK + NOM_COMPAT_BLOCK + '''
result = -round(_isr, 2) if _isr else 0.0
if base_gravable <= 0:
    result = 0.0
if isr_exento_minimo:
    result_qty = 0.0
''')


# ---------------------------------------------------------------------------
# Construcción
# ---------------------------------------------------------------------------

def _resolve_categorias(env):
    """(gravada, exenta, deduccion, informativa) de forma robusta.

    EXENTA: categoría propia ``PERCEP_EXE`` HIJA de ``ALW``. La categoría
    "Exemption" (MX_EXEMPTION) de l10n_mx es INFORMATIVA (no tiene padre, no
    suma al neto: así la usa el aguinaldo nativo para reportar su parte
    exenta). Con las partes exentas ahí, el fondo de ahorro y los vales no
    entraban al NET pero sus deducciones sí, y el neto salía de menos.
    """
    from odoo.addons.mx_jandea_reglas_mx.hooks import _get_category
    Cat = env['hr.salary.rule.category']

    gravada = env.ref('l10n_mx_hr_payroll.l10n_mx_category_taxable_alw',
                      raise_if_not_found=False)
    if not gravada:
        gravada = Cat.search([('code', '=', 'ALW')], limit=1) \
            or _get_category(env, 'ALW', 'Allowance')

    alw = Cat.search([('code', '=', 'ALW')], limit=1) \
        or _get_category(env, 'ALW', 'Allowance')
    exenta = _get_category(env, 'PERCEP_EXE', 'Percepción Exenta (MX Jandea)')
    if exenta.parent_id != alw:
        exenta.parent_id = alw.id

    deduccion = Cat.search([('code', '=', 'DED')], limit=1) \
        or _get_category(env, 'DED', 'Deduction')
    informativa = _get_category(env, 'PATRONAL', 'Costo Patronal (informativo)')
    return gravada, exenta, deduccion, informativa


def _structs_regulares(env):
    """(estructura base, todas las estructuras de nómina normal MX).

    Además de la nativa ``l10n_mx_regular_pay`` se incluyen sus copias
    (código MX_REGULAR), p. ej. "Regular Pay (Sin fondo de ahorro y vales)"
    o "Regular Pay sin ISR": así ninguna se queda con fórmulas viejas.
    """
    Struct = env['hr.payroll.structure'].with_context(active_test=False)
    base = env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay',
                   raise_if_not_found=False)
    todas = Struct.browse()
    if 'code' in Struct._fields:
        todas = Struct.search([('code', '=', 'MX_REGULAR')])
    if base:
        todas |= base
    return base, todas


def _build_nomina_rules(env):
    """Crea/actualiza las reglas de nómina normal.

    * Las reglas que falten se CREAN solo en la estructura base.
    * En TODAS las estructuras MX_REGULAR se reescribe la fórmula de las
      reglas que ya existan con ese código (no se agregan a las copias:
      p. ej. la estructura "sin fondo de ahorro y vales" no gana esas reglas).
    """
    from odoo.addons.mx_jandea_reglas_mx.hooks import _link

    _ensure_params(env)

    base, structs = _structs_regulares(env)
    if not base:
        _logger.warning('%s: no se encontró l10n_mx_regular_pay; no se crearon '
                        'las reglas de nómina normal.', MODULE)
        return

    gravada, exenta, deduccion, informativa = _resolve_categorias(env)
    cats = {'GRAV': gravada, 'EXE': exenta, 'DED': deduccion,
            'INFO': informativa}

    Rule = env['hr.salary.rule'].with_context(active_test=False)
    InputType = env['hr.payslip.input.type']
    creadas = actualizadas = 0

    for xmlid, name, code, tipo, seq, python_code in _nomina_rules_spec():
        regla = env.ref('%s.%s' % (MODULE, xmlid), raise_if_not_found=False)
        if not regla:
            regla = Rule.search([('code', '=', code),
                                 ('struct_id', '=', base.id)], limit=1)
        if not regla:
            regla = Rule.create({
                'name': name,
                'code': code,
                'category_id': cats[tipo].id,
                'struct_id': base.id,
                'sequence': seq,
                'appears_on_payslip': True,
                'condition_select': 'none',
                'amount_select': 'code',
                'amount_python_compute': python_code,
            })
            _link(env, xmlid, 'hr.salary.rule', regla.id)
            creadas += 1

        for r in Rule.search([('code', '=', code),
                              ('struct_id', 'in', structs.ids)]):
            vals = {}
            if r.amount_select != 'code':
                vals['amount_select'] = 'code'
            if r.amount_python_compute != python_code:
                vals['amount_python_compute'] = python_code
            if tipo == 'EXE' and r.category_id != exenta:
                vals['category_id'] = exenta.id
            if vals:
                r.write(vals)
                actualizadas += 1

    # Entradas de la nómina normal en todas las estructuras.
    for it in InputType.search([('code', 'in', NOM_INPUT_CODES)]):
        faltan = structs - it.struct_ids
        if faltan:
            it.struct_ids = [(4, s.id) for s in faltan]

    for struct in structs:
        _patch_reglas_existentes(env, struct, exenta)
        _patch_isr(env, struct)
        _patch_subsidio(env, struct)
        _patch_minimos(env, struct)

    _proteger_nativas(env, structs)

    # Aviso de traslape con reglas nativas.
    for code, nativa in NATIVAS_EQUIVALENTES.items():
        if Rule.search_count([('code', '=', nativa)]):
            _logger.info(
                '%s: existe la regla nativa %s equivalente a %s. Usa una u '
                'otra: si se capturan las dos, el concepto se paga doble.',
                MODULE, nativa, code)

    _logger.info('%s: nómina normal — %s regla(s) creada(s), %s '
                 'actualizada(s) en %s estructura(s).',
                 MODULE, creadas, actualizadas, len(structs))


REGLAS_EXISTENTES = {
    # código -> expresión que devuelve la parte GRAVADA
    'FESTIVO_LABORADO': _por_dia('festivo_grav', '_dias_fest'),
    'PRIMA_DOM': ('result = pd_grav\n'
                  'result_qty = _in("DOMINGOS_PRIMA_DOM", 0.0)\n'),
    'HRS_EXTRA_DOBLE': ('result = he_doble_grav\n'
                        'result_qty = _in("HRS_EXTRA_DOBLE", 0.0)\n'),
    'HRS_EXTRA_TRIPLE': ('result = he_triple_grav\n'
                         'result_qty = _in("HRS_EXTRA_TRIPLE", 0.0)\n'),
    'VALES_DESPENSA_GRAV': 'result = vd_grav\n',
    'VALES_DESPENSA_EXENTO': 'result = vd_exe\n',
    'FONDO_AHORRO_GRAV': 'result = fa_grav\n',
    'FONDO_AHORRO_EXENTO': 'result = fa_exe\n',
}


# Reglas cuya parte va a la categoría EXENTA (suma al neto).
EXENTAS_EXISTENTES = ('VALES_DESPENSA_EXENTO', 'FONDO_AHORRO_EXENTO')


def _patch_reglas_existentes(env, struct, exenta=None):
    """Reescribe las fórmulas de las reglas de nómina que ya existían."""
    Rule = env['hr.salary.rule'].with_context(active_test=False)
    for code, expr in REGLAS_EXISTENTES.items():
        reglas = Rule.search([('code', '=', code),
                              ('struct_id', '=', struct.id)])
        nuevo = NOM_PREAMBLE + '\n' + expr
        for r in reglas:
            vals = {}
            if r.amount_select != 'code':
                vals['amount_select'] = 'code'
            if r.amount_python_compute != nuevo:
                vals['amount_python_compute'] = nuevo
            # FA y Vales dejan de depender de la entrada "Sueldo Neto (FA/VD)".
            if code.startswith(('VALES_', 'FONDO_')) and \
                    r.condition_select == 'input':
                vals['condition_select'] = 'none'
            if exenta and code in EXENTAS_EXISTENTES and \
                    r.category_id != exenta:
                vals['category_id'] = exenta.id
            if vals:
                r.write(vals)


def _patch_isr(env, struct):
    """Sustituye la fórmula de la regla ISR nativa por la mensualizada."""
    Rule = env['hr.salary.rule'].with_context(active_test=False)
    isr = Rule.search([('code', '=', 'ISR'), ('struct_id', '=', struct.id)])
    codigo = _isr_rule_code()
    for r in isr:
        vals = {}
        if r.amount_select != 'code':
            vals['amount_select'] = 'code'
        if r.condition_select != 'none':
            vals['condition_select'] = 'none'
        if r.amount_python_compute != codigo:
            vals['amount_python_compute'] = codigo
        if vals:
            r.write(vals)
            _logger.info('%s: regla ISR mensualizada en "%s".', MODULE,
                         struct.name)


# Reglas nativas de subsidio de l10n_mx. Con mx_jandea_isr_neto_subsidio = 1
# (por omisión) el subsidio ya se restó dentro de la regla de ISR, así que
# estas líneas deben quedar en cero o el recibo lo aplicaría dos veces.
SUBSIDIO_NATIVAS = ('SUBSIDY', 'SUBSIDY_CURRENT_MONTH', 'SUBSIDY_NEXT_MONTH')


def _subsidio_rule_code(principal):
    """Fórmula para las reglas nativas de subsidio.

    ``principal`` = regla que vuelve a pagar el subsidio en su propia línea
    cuando el cliente decide NO netearlo contra el ISR.
    """
    cola = '''
result = 0.0
'''
    if principal:
        cola = '''
# El subsidio solo se paga aparte si NO se netea contra el ISR.
result = 0.0
if not _p("mx_jandea_isr_neto_subsidio", 1.0) and not isr_exento_minimo:
    result = subsidio if subsidio < _isr_bruto else _isr_bruto
'''
    return (NOM_PREAMBLE + NOM_BASE_BLOCK + NOM_ISR_BLOCK + NOM_COMPAT_BLOCK
            + cola)


def _patch_subsidio(env, struct):
    """Neutraliza las reglas nativas de subsidio en la nómina normal."""
    Rule = env['hr.salary.rule'].with_context(active_test=False)
    for code in SUBSIDIO_NATIVAS:
        codigo = _subsidio_rule_code(code == 'SUBSIDY')
        for r in Rule.search([('code', '=', code),
                              ('struct_id', '=', struct.id)]):
            if r.amount_python_compute != codigo or \
                    r.condition_select != 'none':
                r.write({'amount_select': 'code',
                         'condition_select': 'none',
                         'amount_python_compute': codigo})
                _logger.info('%s: regla %s neutralizada en "%s" (el subsidio '
                             'se resta dentro del ISR).', MODULE, code,
                             struct.name)


# Reglas nativas ligadas al salario mínimo.
ISR_MINIMO_CODE = '''
# El ISR de quien gana el salario minimo ya lo decide la regla ISR segun la
# casilla de la sucursal (Retener ISR aunque gane el salario minimo). Esta
# regla nativa devolvia ese ISR y dejaba el recibo inconsistente: queda en 0.
result = 0.0
'''

IMSS_TOTAL_CODE = '''
# Cuota obrera IMSS total. Con GROSS = 0 (todas faltas) no hay base: 0.
# Si gana el salario minimo el patron absorbe la cuota (LSS art. 36): la
# linea se anula y la regla IMSS_MINIMUM_WAGE regresa el importe.
try:
    gross = categories["GROSS"] or 0.0
except Exception:
    gross = 0.0
try:
    _imss = categories["IMSS_EMPLOYEE"] or 0.0
except Exception:
    _imss = 0.0
result = -_imss
result_qty = 1.0
if gross <= 0:
    result = 0.0
    result_qty = 0.0
else:
    try:
        _sched_i = version.schedule_pay or "monthly"
    except Exception:
        _sched_i = "monthly"
    _tbl_i = payslip._rule_parameter("l10n_mx_schedule_table") or {}
    period_factor = _tbl_i.get(_sched_i, 30) or 30
    if period_factor >= 15:
        period_factor = (period_factor / 30) * (365 / 12)
    min_wage = (payslip._rule_parameter("l10n_mx_daily_min_wage") or 0.0) \\
        * period_factor
    if gross <= min_wage:
        result_qty = 0.0
'''


def _patch_minimos(env, struct):
    Rule = env['hr.salary.rule'].with_context(active_test=False)
    for code, codigo in (('ISR_MINIMUM_WAGE', ISR_MINIMO_CODE),
                         ('IMSS_EMPLOYEE_TOTAL', IMSS_TOTAL_CODE)):
        for r in Rule.search([('code', '=', code),
                              ('struct_id', '=', struct.id)]):
            if r.amount_python_compute != codigo or r.amount_select != 'code':
                r.write({'amount_select': 'code',
                         'amount_python_compute': codigo})


# Reglas NATIVAS de l10n_mx que este módulo reescribe. Al actualizar
# l10n_mx_hr_payroll, Odoo las regresaba a su fórmula original (así se perdió
# el ISR mensualizado y el subsidio volvió a salir aparte). Se marcan
# noupdate para que la actualización de la localización ya no las toque.
NATIVAS_PROTEGIDAS = ('ISR', 'SUBSIDY', 'SUBSIDY_CURRENT_MONTH',
                      'SUBSIDY_NEXT_MONTH', 'ISR_MINIMUM_WAGE',
                      'IMSS_EMPLOYEE_TOTAL')


def _proteger_nativas(env, structs):
    Rule = env['hr.salary.rule'].with_context(active_test=False)
    reglas = Rule.search([('code', 'in', NATIVAS_PROTEGIDAS),
                          ('struct_id', 'in', structs.ids)])
    if not reglas:
        return
    imd = env['ir.model.data'].search([
        ('model', '=', 'hr.salary.rule'),
        ('res_id', 'in', reglas.ids),
        ('noupdate', '=', False),
    ])
    if imd:
        imd.write({'noupdate': True})
        _logger.info('%s: %s regla(s) nativa(s) protegidas contra la '
                     'actualización de l10n_mx.', MODULE, len(imd))


# ---------------------------------------------------------------------------
# Parámetros que se crean por código (no en XML): algunos ya existían en
# bases donde se capturaron a mano, y crearlos por XML chocaría con el
# código único del parámetro.
# ---------------------------------------------------------------------------
PARAMS_CODIGO = (
    ('mx_jandea_vd_dia_desde',
     'MX Jandea · Vales · Día mínimo del date_to (16=2a quincena; 0=apagado)',
     '16.0'),
    ('mx_jandea_fa_captura_asist',
     'MX Jandea · Fondo de Ahorro · Proporcionar el importe capturado a la '
     'asistencia (1/0)', '1.0'),
    ('mx_jandea_isr_mensual_directo',
     'MX Jandea · ISR · Nómina mensual con tarifa directa (1 = sí, 0 = '
     'mensualizar a 30.4 como Aspel)', '0.0'),
)

# Valores que cambian de criterio en esta versión: (código, viejo, nuevo).
PARAMS_CORRECCION = (
    ('mx_jandea_te_pct_exento', 1.0, '0.5'),
    ('mx_jandea_festivo_mult', 3.0, '2.0'),
)


def _ensure_params(env):
    Param = env['hr.rule.parameter']
    Value = env['hr.rule.parameter.value']
    mx = env.ref('base.mx', raise_if_not_found=False)
    for code, name, valor in PARAMS_CODIGO:
        par = Param.search([('code', '=', code)], limit=1)
        if not par:
            vals = {'name': name, 'code': code}
            if mx and 'country_id' in Param._fields:
                vals['country_id'] = mx.id
            par = Param.create(vals)
        if not Value.search_count([('rule_parameter_id', '=', par.id)]):
            Value.create({'rule_parameter_id': par.id,
                          'date_from': '2020-01-01',
                          'parameter_value': valor})
    for code, viejo, nuevo in PARAMS_CORRECCION:
        par = Param.search([('code', '=', code)], limit=1)
        if not par:
            continue
        for v in Value.search([('rule_parameter_id', '=', par.id)]):
            try:
                actual = float(v.parameter_value)
            except (TypeError, ValueError):
                continue
            if abs(actual - viejo) < 1e-9:
                v.parameter_value = nuevo
                _logger.info('%s: parámetro %s %s -> %s.', MODULE, code,
                             viejo, nuevo)
