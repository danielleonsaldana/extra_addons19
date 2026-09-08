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
  * Festivo y descanso laborado se pagan al TRIPLE (LFT art. 73), no al 200%.
  * La exención de 5 UMA de tiempo extra es SEMANAL y COMPARTIDA entre horas
    extra, festivo laborado y descanso laborado (no independiente por concepto).

Todo lo configurable son ``hr.rule.parameter``; no hay cifras en el código.
"""
import logging

_logger = logging.getLogger(__name__)

MODULE = 'mx_jandea_reglas_mx'

# Códigos de entrada de la nómina normal.
NOM_INPUT_CODES = [
    'SALARIO_DIARIO', 'DIAS_LABORADOS', 'DIAS_DESCANSO', 'PRIMA_VAC_DIAS',
    'PRIMA_VACACIONAL', 'VALES_DESPENSA', 'FONDO_AHORRO', 'OTRAS_PERCEPCIONES',
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

# --------------------------------------------------------------------------
# PERIODICIDAD
# "Los importes y calculos deben ser aplicados de acuerdo a la periodicidad
#  de la nomina (semanal, quincenal, etc.)"
# --------------------------------------------------------------------------
_dias_calendario = (payslip.date_to - payslip.date_from).days + 1
try:
    _sched = (version and version["schedule_pay"]) or "monthly"
except Exception:
    _sched = "monthly"

# Los dias de cada periodicidad los define la PROPIA localizacion mexicana en
# el parametro l10n_mx_schedule_table. OJO: en l10n_mx "bi-weekly" es
# QUINCENAL (15 dias) y la catorcenal es "14_days". Se lee de ahi para no
# desalinearse si Odoo agrega o renombra periodicidades; el diccionario de
# abajo solo es respaldo por si el parametro no existe.
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

# Factor de mensualizacion: el ISR se calcula MENSUAL y despues se saca la
# parte proporcional. SIEMPRE es dias_mes / dias del periodo, como Aspel:
#   quincena -> 30.4 / 15 = 2.026667  (NO 2.0)
#   semana   -> 30.4 / 7  = 4.342857
_DIAS_MES = _p("mx_jandea_dias_mes_isr", 30.4)
if dias_nomina >= 30.0:
    # Mensual (o mayor): la tabla mensual se aplica tal cual, sin factor.
    factor_mes = 30.0 / dias_nomina
else:
    factor_mes = _DIAS_MES / (dias_nomina or _DIAS_MES)

# La exencion de tiempo extra es SEMANAL -> cuantas semanas trae el periodo.
semanas = dias_nomina / 7.0

# --------------------------------------------------------------------------
# SALARIO DIARIO
# En estos contratos el "wage" es el importe DEL PERIODO (la quincena), no el
# mensual; por eso se divide entre los dias de la periodicidad, no entre 30.
# --------------------------------------------------------------------------
try:
    _wage = (version and version.wage) or 0.0
except Exception:
    _wage = 0.0
sd = _in("SALARIO_DIARIO", 0.0) or (_wage / (dias_nomina or 1.0))
dias_lab = _in("DIAS_LABORADOS", 0.0) or dias_nomina
sueldo_mensual = sd * 30.0                      # columna G del Excel
_prorrata = (dias_lab / 30.0) if dias_lab else 0.0

# --------------------------------------------------------------------------
# TIEMPO EXTRA / FESTIVO / DESCANSO  (columnas L y M)
# Pago al TRIPLE (LFT art. 73: salario del dia mas doble).
# Exencion: bolsa COMUN de 5 UMA por semana repartida en este orden.
# --------------------------------------------------------------------------
try:
    _horas_dia = (version.resource_calendar_id.hours_per_day or 8.0)
except Exception:
    _horas_dia = 8.0
_sh = sd / (_horas_dia or 8.0)

_mult_fest = _p("mx_jandea_festivo_mult", 3.0)
he_doble_imp = _sh * 2.0 * _in("HRS_EXTRA_DOBLE", 0.0)
he_triple_imp = _sh * 3.0 * _in("HRS_EXTRA_TRIPLE", 0.0)
festivo_imp = sd * _mult_fest * _in("DIAS_FESTIVO", 0.0)
descanso_imp = sd * _mult_fest * _in("DIAS_DESCANSO", 0.0)

# Porcentaje exento del tiempo extra: 1.0 = 100% (criterio del Excel).
# El art. 93 fracc. I LISR exenta el 50% para quien no gana el minimo: para
# aplicarlo basta poner 0.5 en el parametro, sin tocar codigo.
_te_pct = _p("mx_jandea_te_pct_exento", 1.0)
# Semanas que se consideran para la bolsa: 0 = las semanas reales del periodo
# (una quincena trae ~2.14). Si el criterio del cliente es una sola bolsa por
# periodo (como el Excel de ejemplo), se pone 1 en mx_jandea_te_semanas.
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
# PRIMA VACACIONAL  (columna K) - exenta 15 UMA
# --------------------------------------------------------------------------
pv_imp = _in("PRIMA_VACACIONAL", 0.0) or (
    sd * _in("PRIMA_VAC_DIAS", 0.0) * _p("mx_jandea_pv_pct", 0.25))
_pv_tope = UMA * _p("mx_jandea_pv_uma", 15.0)
pv_exe = pv_imp if pv_imp < _pv_tope else _pv_tope
pv_grav = pv_imp - pv_exe

# --------------------------------------------------------------------------
# PRIMA DOMINICAL  (columna Q) - 25% del SD por domingo laborado
# Exencion: art. 93 fracc. XIV LISR = 1 UMA por domingo. Si el cliente exige
# el criterio del Excel (1 salario minimo), se pone 1 en mx_jandea_pd_base_smg.
# --------------------------------------------------------------------------
_domingos = _in("DOMINGOS_PRIMA_DOM", 0.0)
pd_imp = sd * _domingos * _p("mx_jandea_pd_pct", 0.25)
_pd_base = SMG if _p("mx_jandea_pd_base_smg", 0.0) else UMA
_pd_tope = _pd_base * _domingos
pd_exe = pd_imp if pd_imp < _pd_tope else _pd_tope
pd_grav = pd_imp - pd_exe

# --------------------------------------------------------------------------
# VALES DE DESPENSA  (columna N) - exentos 40% de la UMA al mes
# Se otorga el 10% del sueldo salvo que rebase el tope. Prorrateado a los
# dias laborados del periodo.
# --------------------------------------------------------------------------
# Dias que se usan para topar las exenciones del periodo: los dias pagados
# (una quincena completa = 15). Antes se mensualizaba a 30.4 y se prorrateaba,
# lo que daba 15.2 dias en una quincena.
_dias_exe = dias_lab or dias_nomina
# --------------------------------------------------------------------------
# VALES DE DESPENSA
# Tope de exencion = 40% de la UMA x 30.4  (mx_jandea_vd_dias_tope_base).
# Si el parametro se pone en 0, el tope se calcula con los dias del periodo.
# Lo que rebase el tope GRAVA (no se recorta el importe, salvo que
# mx_jandea_vd_topar_importe = 1).
# --------------------------------------------------------------------------
_vd_dias = _p("mx_jandea_vd_dias_tope_base", 30.4) or _dias_exe
_vd_tope = UMA * _p("mx_jandea_vd_uma_pct", 0.40) * _vd_dias
_vd_calc = (sueldo_mensual * _p("mx_jandea_vd_tasa", 0.10)) * _prorrata
if _p("mx_jandea_vd_topar_importe", 0.0) and _vd_calc > _vd_tope:
    _vd_calc = _vd_tope
# mx_jandea_vd_auto = 0 (por omision): los vales solo se pagan si se captura
# el importe en el recibo. = 1: se otorgan automaticamente a todo el que tenga
# contrato, calculados como el Excel (10% del sueldo topado a la exencion).
vd_imp = _in("VALES_DESPENSA", 0.0) or (
    _vd_calc if _p("mx_jandea_vd_auto", 0.0) else 0.0)
vd_exe = vd_imp if vd_imp < _vd_tope else _vd_tope
vd_grav = vd_imp - vd_exe

# --------------------------------------------------------------------------
# FONDO DE AHORRO  (columna O)
# Art. 93 fracc. XI LISR: exento mientras la aportacion no exceda el 13% del
# salario NI 1.3 veces la UMA elevada al periodo. En una quincena:
#     tope = UMA * 15 * 1.3
# Solo el EXCEDENTE de ese tope grava; el resto no toca la base de ISR.
# --------------------------------------------------------------------------
_fa_tope = UMA * _p("mx_jandea_fa_uma_mult", 1.3) * _dias_exe
_fa_calc = (sd * dias_lab) * _p("mx_jandea_fa_tasa", 0.13)
# Por omision NO se topa el importe: se aporta el 13% completo y lo que pase
# del tope de exencion simplemente GRAVA (que es el punto del art. 93 XI).
# Con mx_jandea_fa_topar_importe = 1 se recorta la aportacion al tope, como
# hacia el Excel.
if _p("mx_jandea_fa_topar_importe", 0.0) and _fa_calc > _fa_tope:
    _fa_calc = _fa_tope
# mx_jandea_fa_auto: mismo criterio que los vales.
fa_imp = _in("FONDO_AHORRO", 0.0) or (
    _fa_calc if _p("mx_jandea_fa_auto", 0.0) else 0.0)
fa_exe = fa_imp if fa_imp < _fa_tope else _fa_tope
fa_grav = fa_imp - fa_exe

# --------------------------------------------------------------------------
# OTRAS PERCEPCIONES  (columna R) - gravan al 100%
# --------------------------------------------------------------------------
otras_perc = _in("OTRAS_PERCEPCIONES", 0.0)

# --------------------------------------------------------------------------
# TOTAL EXENTO del periodo (para despejar la base gravable).
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

# Si el salario diario es el minimo general no hay retencion (LISR; el Excel
# lo resuelve en H4 con IF(SD=SMG,0,...)).
if sd <= SMG + 0.01 and not _p("mx_jandea_isr_al_minimo", 0.0):
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
         'FESTIVO_LABORADO_EXE', 'EXE', 85, p + '\nresult = festivo_exe\n'),

        ('rule_nom_he_doble_exe', 'Horas Extra Dobles (Exento)',
         'HRS_EXTRA_DOBLE_EXE', 'EXE', 86, p + '\nresult = he_doble_exe\n'),
        ('rule_nom_he_triple_exe', 'Horas Extra Triples (Exento)',
         'HRS_EXTRA_TRIPLE_EXE', 'EXE', 87, p + '\nresult = he_triple_exe\n'),

        ('rule_nom_descanso', 'Descanso Laborado (Gravado)',
         'DESCANSO_LABORADO', 'GRAV', 88,
         p + '\nresult = descanso_grav\nresult_qty = _in("DIAS_DESCANSO", 0.0)\n'),
        ('rule_nom_descanso_exe', 'Descanso Laborado (Exento)',
         'DESCANSO_LABORADO_EXE', 'EXE', 89, p + '\nresult = descanso_exe\n'),

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
result = -_isr
if base_gravable <= 0:
    result = 0.0
if gross <= min_wage:
    result_qty = 0.0
''')


# ---------------------------------------------------------------------------
# Construcción
# ---------------------------------------------------------------------------

def _resolve_categorias(env):
    """(gravada, exenta, deduccion, informativa) de forma robusta."""
    from odoo.addons.mx_jandea_reglas_mx.hooks import _get_category
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
        exenta = _get_category(env, 'PERCEP_EXE', 'Percepción Exenta (MX)')
        _logger.warning(
            '%s: no se encontró la categoría EXENTA de l10n_mx; se creó '
            '"PERCEP_EXE". Verifica que no entre a la base de ISR.', MODULE)

    deduccion = Cat.search([('code', '=', 'DED')], limit=1) \
        or _get_category(env, 'DED', 'Deduction')
    informativa = _get_category(env, 'PATRONAL', 'Costo Patronal (informativo)')
    return gravada, exenta, deduccion, informativa


def _build_nomina_rules(env):
    """Crea/actualiza las reglas de nómina normal sobre 'l10n_mx_regular_pay'."""
    from odoo.addons.mx_jandea_reglas_mx.hooks import _link

    struct = env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay',
                     raise_if_not_found=False)
    if not struct:
        _logger.warning('%s: no se encontró l10n_mx_regular_pay; no se crearon '
                        'las reglas de nómina normal.', MODULE)
        return

    gravada, exenta, deduccion, informativa = _resolve_categorias(env)
    cats = {'GRAV': gravada, 'EXE': exenta, 'DED': deduccion,
            'INFO': informativa}

    Rule = env['hr.salary.rule']
    InputType = env['hr.payslip.input.type']
    creadas = actualizadas = 0

    for xmlid, name, code, tipo, seq, python_code in _nomina_rules_spec():
        regla = env.ref('%s.%s' % (MODULE, xmlid), raise_if_not_found=False)
        if not regla:
            regla = Rule.search([('code', '=', code),
                                 ('struct_id', '=', struct.id)], limit=1)
        if regla:
            if regla.amount_python_compute != python_code:
                regla.amount_python_compute = python_code
                actualizadas += 1
            continue
        vals = {
            'name': name,
            'code': code,
            'category_id': cats[tipo].id,
            'struct_id': struct.id,
            'sequence': seq,
            'appears_on_payslip': True,
            'condition_select': 'none',
            'amount_select': 'code',
            'amount_python_compute': python_code,
        }
        regla = Rule.create(vals)
        _link(env, xmlid, 'hr.salary.rule', regla.id)
        creadas += 1

    # Enlazar las entradas nuevas a la estructura de nómina normal.
    for it in InputType.search([('code', 'in', NOM_INPUT_CODES)]):
        if struct not in it.struct_ids:
            it.struct_ids = [(4, struct.id)]

    # Re-aplicar el preámbulo a las reglas de nómina que ya existían en XML
    # (festivo, prima dominical, horas extra) para que usen el MISMO salario
    # diario, la misma periodicidad y devuelvan solo la parte GRAVADA.
    _patch_reglas_existentes(env, struct)

    # ISR mensualizado sobre la base gravable.
    _patch_isr(env, struct)

    # Subsidio para el empleo: se resta dentro del ISR, las reglas nativas se
    # neutralizan para no contarlo dos veces.
    _patch_subsidio(env, struct)

    # Aviso de traslape con reglas nativas.
    for code, nativa in NATIVAS_EQUIVALENTES.items():
        if Rule.search_count([('code', '=', nativa)]):
            _logger.warning(
                '%s: existe la regla nativa %s equivalente a %s. Usa una u '
                'otra: si se capturan las dos, el concepto se paga doble.',
                MODULE, nativa, code)

    _logger.info('%s: nómina normal — %s regla(s) creada(s), %s actualizada(s).',
                 MODULE, creadas, actualizadas)


REGLAS_EXISTENTES = {
    # código -> expresión que devuelve la parte GRAVADA
    'FESTIVO_LABORADO': ('result = festivo_grav\n'
                         'result_qty = _in("DIAS_FESTIVO", 0.0)\n'),
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


def _patch_reglas_existentes(env, struct):
    """Reescribe las fórmulas de las reglas de nómina que ya existían."""
    Rule = env['hr.salary.rule']
    for code, expr in REGLAS_EXISTENTES.items():
        reglas = Rule.search([('code', '=', code),
                              ('struct_id', '=', struct.id)])
        nuevo = NOM_PREAMBLE + '\n' + expr
        for r in reglas:
            if r.amount_python_compute != nuevo:
                r.amount_python_compute = nuevo
            # FA y Vales dejan de depender de la entrada "Sueldo Neto (FA/VD)":
            # ahora se calculan con el salario del contrato como el Excel.
            if code.startswith(('VALES_', 'FONDO_')) and \
                    r.condition_select == 'input':
                r.condition_select = 'none'


def _patch_isr(env, struct):
    """Sustituye la fórmula de la regla ISR nativa por la mensualizada."""
    Rule = env['hr.salary.rule']
    isr = Rule.search([('code', '=', 'ISR'), ('struct_id', '=', struct.id)],
                      limit=1)
    if not isr:
        isr = env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_isr',
                      raise_if_not_found=False)
    if not isr:
        _logger.warning('%s: no se encontró la regla ISR de nómina normal.',
                        MODULE)
        return
    codigo = _isr_rule_code()
    if isr.amount_python_compute != codigo:
        isr.amount_python_compute = codigo
        _logger.info('%s: regla ISR de nómina normal mensualizada.', MODULE)


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
if not _p("mx_jandea_isr_neto_subsidio", 1.0):
    result = subsidio if subsidio < _isr_bruto else _isr_bruto
'''
    return (NOM_PREAMBLE + NOM_BASE_BLOCK + NOM_ISR_BLOCK + NOM_COMPAT_BLOCK
            + cola)


def _patch_subsidio(env, struct):
    """Neutraliza las reglas nativas de subsidio en la nómina normal."""
    Rule = env['hr.salary.rule']
    for code in SUBSIDIO_NATIVAS:
        reglas = Rule.search([('code', '=', code),
                              ('struct_id', '=', struct.id)])
        if not reglas:
            continue
        codigo = _subsidio_rule_code(code == 'SUBSIDY')
        for r in reglas:
            if r.amount_python_compute != codigo:
                r.amount_select = 'code'
                r.condition_select = 'none'
                r.amount_python_compute = codigo
                _logger.info('%s: regla %s neutralizada (el subsidio se resta '
                             'dentro del ISR).', MODULE, code)
