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
    'FNQT_DIAS_SAL', 'FNQT_SD_IMSS', 'FNQT_SDI_IMSS', 'FNQT_DIAS_AGUI',
    'FNQT_DIAS_LAB', 'FNQT_ANIOS_ANTIG', 'FNQT_DIAS_VAC_BASE',
    'FNQT_VAC_PEND', 'FNQT_PV_PEND',
    'FNQT_IND_90', 'FNQT_IND_20', 'FNQT_PRIMA_ANT', 'FNQT_AGUI_PAGADO',
    'FNQT_FACTOR_LIQ', 'FNQT_FACTOR_ISR',
    'FNQT_OTRAS_PERC', 'FNQT_INFONAVIT', 'FNQT_FONACOT', 'FNQT_OTRAS_DED',
    'FNQT_ISN_TASA', 'FNQT_ISN_EXCL_SEP',
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
    try:
        v = inputs[c]
        return v.amount if v else d
    except Exception:
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
        _v = getattr(_o, _f, False)
    except Exception:
        _v = False
    if _v and payslip.date_from <= _v <= payslip.date_to:
        fecha_baja = _v
        break
fecha_alta = False
for _o, _f in ((version, 'contract_date_start'), (version, 'date_start'),
               (version, 'date_version'), (employee, 'first_contract_date')):
    try:
        _v = getattr(_o, _f, False)
    except Exception:
        _v = False
    if _v:
        fecha_alta = _v
        break
if not fecha_alta:
    fecha_alta = payslip.date_from
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
dias_vac_base = _in('FNQT_DIAS_VAC_BASE', 0.0) or ((fecha_baja - _aniv).days + 5)
anios_lab = int(round(dias_lab / 365.25))
anios_antig = _in('FNQT_ANIOS_ANTIG', 0.0) or round(dias_lab / 365.25, 2)

dias_agui = _in('FNQT_DIAS_AGUI', 15.0) or 15.0
if fecha_alta < inicio_anio:
    agui_prop = (((fecha_baja - inicio_anio).days + 1) / 365.0) * dias_agui
else:
    agui_prop = (((fecha_baja - fecha_alta).days + 1) / 365.0) * dias_agui

def _dias_vac_lft(a):
    a = int(round(a))
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

# El recibo puede no tener version/contrato asignado ("Version: False").
# En ese caso el sueldo se toma del contrato del empleado o queda en 0,
# en vez de reventar con AttributeError.
_wage = 0.0
for _o in (version, employee):
    try:
        _w = getattr(_o, 'wage', False) or getattr(_o, 'contract_wage', False)
    except Exception:
        _w = False
    if _w:
        _wage = _w
        break
sd_real = _wage / 30.0
sdi_real = sd_real
sd_imss = _in('FNQT_SD_IMSS', 0.0) or sd_real
sdi_imss = _in('FNQT_SDI_IMSS', 0.0) or sd_imss

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
    dias_sal = _wd
factor_liq = _in('FNQT_FACTOR_LIQ', 0.0) or 1.0
agui_pagado = _in('FNQT_AGUI_PAGADO', 0.0)
ind_90 = _in('FNQT_IND_90', 0.0)
ind_20 = _in('FNQT_IND_20', 0.0)
prima_ant_on = _in('FNQT_PRIMA_ANT', 0.0)

# --- Percepciones, columna REAL (lo que se paga) ---
p_salario_r = dias_sal * sd_real
p_agui_r = 0.0 if agui_pagado else sd_real * agui_prop
p_vac_r = (vac_prop + vac_pend) * sd_real
p_pv_r = ((vac_prop + pv_pend) * 0.25) * sd_real
p_ind90_r = (90.0 * sdi_real if ind_90 else 0.0) * factor_liq
p_ind20_r = ((sd_real * 20.0) * anios_lab if ind_20 else 0.0) * factor_liq
_tope_pa = SMG * 2.0
p_pant_r = 0.0
if prima_ant_on:
    _base_pa_r = _tope_pa if sd_real > _tope_pa else sd_real
    p_pant_r = (_base_pa_r * 12.0) * anios_antig * factor_liq
p_otras = _in('FNQT_OTRAS_PERC', 0.0)

# --- Percepciones, columna IMSS (base reportada) ---
p_salario_i = dias_sal * sd_imss
p_agui_i = 0.0 if agui_pagado else sd_imss * agui_prop
p_vac_i = (vac_prop + vac_pend) * sd_imss
p_pv_i = pv_prop * sd_imss
p_ind90_i = (90.0 * sdi_imss if ind_90 else 0.0) * factor_liq
p_ind20_i = ((sdi_imss * 20.0) * anios_lab if ind_20 else 0.0) * factor_liq
p_pant_i = 0.0
if prima_ant_on:
    _base_pa_i = _tope_pa if sd_imss > _tope_pa else sd_imss
    p_pant_i = (_base_pa_i * 12.0) * anios_antig * factor_liq

total_perc_real = (p_salario_r + p_agui_r + p_vac_r + p_pv_r
                   + p_ind90_r + p_ind20_r + p_pant_r + p_otras)
total_perc_imss = (p_salario_i + p_agui_i + p_vac_i + p_pv_i
                   + p_ind90_i + p_ind20_i + p_pant_i + p_otras)

# --- Base gravable ISR (art. 93 LISR: exenciones en UMA) ---
_ex_agui = UMA * 30.0
_ex_pv = UMA * 15.0
_ex_sep = (UMA * 90.0) * anios_lab
base_gravable = (
    p_salario_i
    + (0.0 if p_agui_i < _ex_agui else p_agui_i - _ex_agui)
    + p_vac_i
    + (p_pv_i - _ex_pv if p_pv_i > _ex_pv else 0.0)
    + (p_ind90_i - _ex_sep if p_ind90_i > _ex_sep else 0.0)
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

factor_isr = _in('FNQT_FACTOR_ISR', 0.0) or 4.3429
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
'''


def _rules_spec():
    """Definición de las reglas: (xmlid, nombre, código, categoría, seq, code)."""
    p = PREAMBLE
    return [
        # ---------------- PERCEPCIONES ----------------
        (
            'rule_fnqt_salario', 'Salario Pendiente', 'FNQT_SALARIO',
            'BASIC', 10, p + '\nresult = p_salario_r\n'
        ),
        (
            'rule_fnqt_aguinaldo', 'Aguinaldo Proporcional', 'FNQT_AGUINALDO',
            'ALW', 20, p + '\nresult = p_agui_r\nresult_qty = agui_prop\n'
        ),
        (
            'rule_fnqt_vacaciones', 'Vacaciones', 'FNQT_VACACIONES',
            'ALW', 30, p + '\nresult = p_vac_r\nresult_qty = vac_prop + vac_pend\n'
        ),
        (
            'rule_fnqt_prima_vac', 'Prima Vacacional', 'FNQT_PRIMA_VAC',
            'ALW', 40, p + '\nresult = p_pv_r\n'
        ),
        (
            'rule_fnqt_ind90', 'Indemnización 90 Días', 'FNQT_IND90',
            'ALW', 50, p + '\nresult = p_ind90_r\n'
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
        (
            # ISN: impuesto estatal A CARGO DEL PATRÓN. No se descuenta al
            # trabajador, por eso vive en la categoría PATRONAL y no en DED.
            # Si FNQT_ISN_TASA no se captura o va en 0, el resultado es 0.
            'rule_fnqt_isn', 'ISN (Impuesto Sobre Nóminas) · costo patronal',
            'FNQT_ISN', 'PATRONAL', 230,
            p + '''
_isn_tasa = _in('FNQT_ISN_TASA', 0.0)
_isn_base = total_perc_real
if _in('FNQT_ISN_EXCL_SEP', 0.0):
    _isn_base = _isn_base - p_ind90_r - p_ind20_r - p_pant_r
if _isn_base < 0:
    _isn_base = 0.0
result = _isn_base * (_isn_tasa / 100.0)
'''
        ),
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

    _logger.info('%s: %s regla(s) de finiquito creadas.', MODULE, created)
