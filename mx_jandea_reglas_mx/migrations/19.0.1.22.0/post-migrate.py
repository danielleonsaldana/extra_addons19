# -*- coding: utf-8 -*-
"""19.0.1.22.0: corrige la base gravable y los montos de indemnizacion segun el
Excel corregido del cliente:

  * BASE GRAVABLE: ahora SUMA las 3 indemnizaciones (Ind90 + Ind20 + Prima de
    antiguedad) y les aplica UNA sola exencion = 90 UMA x años REDONDEADOS
    (>= 6 meses sube). Antes solo consideraba Ind90 y omitia Ind20 y Prima.
  * Ind20 y Prima de antiguedad: montos con años CON DECIMALES (no redondeados).
  * Ind20: se calcula sobre el SDI (salario diario integrado).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    from odoo.addons.mx_jandea_reglas_mx.hooks import (
        _rules_spec, _clean_foreign_rules, _patch_native_rules,
        STRUCT_XMLID, MODULE)

    env = api.Environment(cr, SUPERUSER_ID, {})
    Rule = env['hr.salary.rule']

    for xmlid, name, code, cat_code, seq, python_code in _rules_spec():
        regla = env.ref('%s.%s' % (MODULE, xmlid), raise_if_not_found=False)
        if not regla:
            regla = Rule.search([('code', '=', code)], limit=1)
        if regla and regla.amount_python_compute != python_code:
            regla.amount_python_compute = python_code

    struct = env.ref('%s.%s' % (MODULE, STRUCT_XMLID), raise_if_not_found=False)
    if struct:
        _clean_foreign_rules(env, struct)
    _patch_native_rules(env)

    _logger.info('mx_jandea_reglas_mx: base gravable e indemnizaciones '
                 'corregidas (v19.0.1.22.0).')
