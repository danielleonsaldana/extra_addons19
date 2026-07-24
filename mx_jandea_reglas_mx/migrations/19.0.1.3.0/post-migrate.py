# -*- coding: utf-8 -*-
"""Actualiza el código Python de las reglas de Finiquito ya creadas.

El post_init_hook solo crea las reglas que faltan; no reescribe las existentes.
Esta migración sincroniza el código de todas las reglas del finiquito con la
definición actual del módulo, para no tener que desinstalar/reinstalar.

Cambios que aplica:
  * Días de salario pendiente = días efectivamente trabajados (pagados) del
    período, no el período completo de la quincena.
  * Corte de conceptos proporcionales en la fecha real de baja.
  * Tolerancia a recibos sin versión/contrato asignado.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    from odoo.addons.mx_jandea_reglas_mx.hooks import _rules_spec

    env = api.Environment(cr, SUPERUSER_ID, {})
    Rule = env['hr.salary.rule']
    actualizadas = 0
    for xmlid, name, code, cat_code, seq, python_code in _rules_spec():
        regla = env.ref('mx_jandea_reglas_mx.%s' % xmlid, raise_if_not_found=False)
        if not regla:
            # Respaldo: buscar por código si el XML-ID se perdió.
            regla = Rule.search([('code', '=', code)], limit=1)
        if not regla:
            continue
        if regla.amount_python_compute != python_code:
            regla.amount_python_compute = python_code
            actualizadas += 1
    _logger.info('mx_jandea_reglas_mx: %s regla(s) de finiquito actualizadas.',
                 actualizadas)
