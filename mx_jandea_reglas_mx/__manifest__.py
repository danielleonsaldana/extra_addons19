# -*- coding: utf-8 -*-
{
    'name': 'MX Jandea - Reglas Salariales Complementarias',
    'version': '19.0.1.26.3',
    'summary': 'Reglas salariales mexicanas no incluidas en l10n_mx_hr_payroll + Finiquito/Liquidación + Listado de Nómina (exenciones, base gravable e ISR mensualizado)',
    'description': """
Reglas complementarias para la nómina mexicana:

* Fix de la regla ISR nativa cuando GROSS = 0 (empleado con todas faltas).
* Percepciones complementarias (horas extra, festivo, prima dominical, PTU,
  premios, compensación, habitación).
* Deducciones complementarias (anticipo, caja de ahorro, SAR e INFONAVIT
  voluntarios).
* Fondo de Ahorro y Vales de Despensa en la nómina NORMAL, con parte gravada
  (integra IMSS/ISR) y parte exenta, replicando el Excel de "Licencias
  Internacionales". Tope de Fondo de Ahorro = 1.3 x UMA; topes y tasas son
  parámetros de regla (mx_jandea_fa_uma_mult, mx_jandea_fa_tasa,
  mx_jandea_vd_tasa, mx_jandea_favd_dias_mes/_quincena). Se activan al capturar
  la entrada "Sueldo Neto (FA/VD)" en el recibo.
* Estructura "Mexico: Finiquito / Liquidación" que replica el cálculo de
  finiquito: salario pendiente, aguinaldo y vacaciones proporcionales, prima
  vacacional, indemnización 90 y 20 días, prima de antigüedad (topada a 2 SMG),
  cuota obrera IMSS, ISR con exenciones en UMA (art. 93 LISR) e ISN.

ISN (Impuesto Sobre Nóminas): es un impuesto ESTATAL a cargo del PATRÓN, no una
deducción al trabajador. Por eso se calcula en la categoría PATRONAL, fuera del
neto. Si la entrada FNQT_ISN_TASA no se captura o va en 0, el ISN no aplica.

* NÓMINA NORMAL (v1.25.0) — replica el Excel "Listado de Nómina":
  cada percepción con exención se parte en GRAVADA y EXENTA (prima vacacional
  15 UMA, tiempo extra/festivo/descanso con bolsa COMÚN de 5 UMA semanales,
  prima dominical, vales 40% UMA al mes, fondo de ahorro 1.3 UMA), se agrega la
  regla informativa BASE_GRAVABLE_ISR (columna W) y el ISR pasa a calcularse
  MENSUALIZADO sobre la base gravable y luego prorrateado a la periodicidad.
  Los vales se compensan contra el neto y llevan el descuento de $1.00.
* ISR QUINCENAL ALINEADO CON ASPEL (v1.26.0):
    1) base = sueldo + SOLO lo que grava. Se arma sumando, no restando
       exentos al GROSS: así el fondo de ahorro no resta nada de la base y
       solo suma su EXCEDENTE del tope (UMA x días del periodo x 1.3, es
       decir UMA x 15 x 1.3 en una quincena).
    2) base_mes = base x (30.4 / días del periodo)  -> quincena = 2.026667.
    3) impuesto_mes = tarifa mensual del SAT (Anexo 8 RMF).
    4) impuesto_periodo = impuesto_mes x (días del periodo / 30.4).
    5) impuesto_neto = impuesto_periodo - subsidio para el empleo.
  El subsidio se calcula con el decreto DOF 31/12/2025 (15.02% de la UMA
  mensual, 15.59% de la UMA 2025 en enero de 2026, tope de ingreso mensual
  $11,492.66, prorrateo /30.4 x días) y se resta DENTRO de la regla de ISR;
  las reglas nativas SUBSIDY / SUBSIDY_CURRENT_MONTH / SUBSIDY_NEXT_MONTH se
  neutralizan para no aplicarlo dos veces. Con mx_jandea_isr_neto_subsidio = 0
  el ISR vuelve a salir bruto y el subsidio a su propia línea.

UMA y salario mínimo se leen de parámetros de regla versionados por año
(mx_jandea_uma / mx_jandea_smg), así que no requieren cambios de código.
    """,
    'author': 'Jandea IT',
    'category': 'Human Resources/Payroll',
    'depends': [
        'l10n_mx_hr_payroll',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_rule_parameter_data.xml',
        'data/hr_rule_parameter_nomina_data.xml',
        'data/hr_payslip_input_type_data.xml',
        'data/hr_payslip_input_type_finiquito_data.xml',
        'data/hr_payslip_input_type_nomina_data.xml',
        'data/hr_salary_rule_data.xml',
        'wizards/fnqt_pct_wizard_views.xml',
        'views/hr_payslip_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
