# -*- coding: utf-8 -*-
"""19.0.1.27.0: integra al módulo las fórmulas corregidas a mano en la base.

* Un solo preámbulo para TODAS las reglas de nómina normal (antes cada regla
  traía una versión distinta y gravado/exento de un mismo concepto salían de
  fórmulas diferentes):
    - asistencia: dias pagados = dias del periodo - faltas (entrada FALTAS o
      ausencias sin goce); vales y fondo de ahorro se proporcionan;
    - festivo y descanso laborados al DOBLE, pagados como dias x importe;
    - exención de tiempo extra: 100% sin tope si gana el mínimo, 50% con
      bolsa de 5 UMA semanales si gana más;
    - vales una vez al mes (fin de mes semanal/mensual, 2a quincena);
    - fondo de ahorro con tope anual 1.3 UMA x 365.
* Se aplica a todas las estructuras MX_REGULAR (incluida "Sin fondo de ahorro
  y vales", que ya no suma FA/vales a la base del ISR).
* ISR mensualizado + subsidio de nuevo en la regla ISR (la actualización de
  l10n_mx lo había regresado a la fórmula nativa) y las reglas nativas
  reescritas quedan protegidas (noupdate).
* ISR al salario mínimo: lo decide la casilla de cada sucursal.
* Las partes EXENTAS pasan a la categoría PERCEP_EXE (hija de ALW) para que
  sumen al neto.
* Parámetros: tiempo extra exento 1.0 -> 0.5, festivo 3.0 -> 2.0 y altas de
  mx_jandea_vd_dia_desde / mx_jandea_fa_captura_asist /
  mx_jandea_isr_mensual_directo.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    from odoo.addons.mx_jandea_reglas_mx.hooks_nomina import _build_nomina_rules

    env = api.Environment(cr, SUPERUSER_ID, {})
    _build_nomina_rules(env)
    _logger.info('mx_jandea_reglas_mx: fórmulas unificadas (v19.0.1.27.0).')
