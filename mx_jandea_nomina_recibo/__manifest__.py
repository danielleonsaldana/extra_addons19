# -*- coding: utf-8 -*-
{
    'name': 'MX Jandea - Recibo de Nómina (PDF)',
    'version': '19.0.1.2.0',
    'summary': 'Recibo de nómina mexicano en español, con días completos del período',
    'description': """
Reporte PDF de recibo de nómina con formato mexicano, en español.

Diferencias contra el reporte nativo (hr_payroll.report_payslip + la extensión
de l10n_mx_hr_payroll):

* Conceptos traducidos al español en el PDF (no se tocan las reglas nativas).
* Los DÍAS DEL PERÍODO se muestran completos según la periodicidad de la
  nómina (15 quincenal, 7 semanal, 14 catorcenal, 30 mensual), no solo los
  días efectivamente laborados.
* No se imprimen: sueldo mensual, correo electrónico, estado civil, fecha de
  cálculo, tipo de contrato, horario laboral, factor de integración ni
  dirección.
* No se imprime el ISN: es un impuesto estatal a cargo del patrón y no un
  concepto aplicable al colaborador. En general se excluye del recibo toda la
  categoría PATRONAL (costo patronal informativo).
* Formato de dos columnas Percepciones / Deducciones, con neto a pagar,
  importe con letra y espacio de firma.
* RENGLONES FIJOS (v1.2.0). Nómina: Salario básico titular, Prima
  vacacional, Prima dominical, Festivo laborado, Descanso laborado, Fondo de
  ahorro, Vales de despensa, Otras percepciones | FONACOT, INFONAVIT, ISR,
  IMSS, Otras deducciones, Préstamos personales | Salario neto.
  Finiquito: Salario, Aguinaldo, Vacaciones, Prima vacacional,
  Indemnizaciones (solo las que se generen), Prima de antigüedad, Otras
  percepciones | Préstamos, IMSS, ISR, INFONAVIT, FONACOT, Otras deducciones
  | Neto a pagar. Cada renglón suma gravado + exento; lo que no cae en un
  renglón va a "Otras", así el total siempre cuadra con la línea NET.
* Días del período: quincenal = 15 (en l10n_mx "bi-weekly" es quincenal).

Es un reporte independiente: el nativo sigue disponible por si se necesita.
    """,
    'author': 'Jandea IT',
    'category': 'Human Resources/Payroll',
    'depends': [
        'hr_payroll',
    ],
    'data': [
        'report/recibo_nomina_templates.xml',
        'report/recibo_nomina_report.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
