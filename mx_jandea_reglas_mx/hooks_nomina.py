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

_DIAS_SCHED = {"daily": 1.0, "weekly": 7.0, "bi-weekly": 14.0,
               "semi-monthly": 15.0, "monthly": 30.0}
dias_nomina = _DIAS_SCHED.get(_sched) or float(_dias_calendario or 30)

# Factor de mensualizacion: el ISR se calcula MENSUAL y despues se saca la
# parte proporcional. Quincenal = 2 quincenas por mes, semanal = 30.4/7, etc.
_FACTOR_SCHED = {"daily": 30.4, "weekly": 30.4 / 7.0, "bi-weekly": 30.4 / 14.0,
                 "semi-monthly": 2.0, "monthly": 1.0}
factor_mes = _FACTOR_SCHED.get(_sched) or (30.4 / (dias_nomina or 30.4))

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
_vd_tope_mes = UMA * _p("mx_jandea_vd_uma_pct", 0.40) * _p(
    "mx_jandea_favd_dias_mes", 30.4)
_vd_tope = _vd_tope_mes * _prorrata
_vd_calc = (sueldo_mensual * _p("mx_jandea_vd_tasa", 0.10)) * _prorrata
if _vd_calc > _vd_tope:
    _vd_calc = _vd_tope
# mx_jandea_vd_auto = 0 (por omision): los vales solo se pagan si se captura
# el importe en el recibo. = 1: se otorgan automaticamente a todo el que tenga
# contrato, calculados como el Excel (10% del sueldo topado a la exencion).
vd_imp = _in("VALES_DESPENSA", 0.0) or (
    _vd_calc if _p("mx_jandea_vd_auto", 0.0) else 0.0)
vd_exe = vd_imp if vd_imp < _vd_tope else _vd_tope
vd_grav = vd_imp - vd_exe

# --------------------------------------------------------------------------
# FONDO DE AHORRO  (columna O) - exento hasta 1.3 UMA / 13% del salario
# --------------------------------------------------------------------------
_fa_tope = (UMA * _p("mx_jandea_fa_uma_mult", 1.3)
            * _p("mx_jandea_favd_dias_mes", 30.4)) * _prorrata
_fa_calc = (sd * dias_lab) * _p("mx_jandea_fa_tasa", 0.13)
if _fa_calc > _fa_tope:
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
# Se parte del GROSS que arma Odoo y se le resta lo exento. El parametro
# mx_jandea_gross_incluye_exento existe porque, segun como l10n_mx arme la
# categoria exenta, GROSS puede o no traerla dentro:
#   1 (por omision) -> GROSS trae lo exento, hay que restarlo.
#   0               -> GROSS ya viene neto de exentos, no se resta nada.
# Se valida con un recibo de prueba y se deja fijo.
# --------------------------------------------------------------------------
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
# ISR (columna X)
# "Los calculos de impuesto (ISR) deben ser mensualizados y despues sacar la
#  parte proporcional de acuerdo a la periodicidad de la nomina."
#
# El SUBSIDIO PARA EL EMPLEO no se calcula aqui: l10n_mx ya trae sus reglas
# SUBSIDY / SUBSIDY_CURRENT_MONTH / SUBSIDY_NEXT_MONTH. La columna X del
# Excel equivale, en Odoo, a ISR + SUBSIDY.
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

_isr = 0.0
_bg_mensual = base_gravable * factor_mes
if _bg_mensual > 0:
    _low, _fix, _rate = 0.01, 0.0, 0.0192
    for _l, _h, _f, _r in _isr_tabla():
        if _bg_mensual >= _l:
            _low, _fix, _rate = _l, _f, _r
    _isr = ((_bg_mensual - _low) * _rate + _fix) / (factor_mes or 1.0)

# Si el salario diario es el minimo general no hay retencion (LISR; el Excel
# lo resuelve en H4 con IF(SD=SMG,0,...)).
if sd <= SMG + 0.01 and not _p("mx_jandea_isr_al_minimo", 0.0):
    _isr = 0.0
if _isr < 0:
    _isr = 0.0
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
         p + NOM_BASE_BLOCK + NOM_ISR_BLOCK + '\nresult = _isr\n'),
    ]


def _isr_rule_code():
    """Fórmula que sustituye a la regla ISR nativa de 'Regular Pay'."""
    return (NOM_PREAMBLE + NOM_BASE_BLOCK + NOM_ISR_BLOCK + '''
result = -_isr
if base_gravable <= 0:
    result = 0.0
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
