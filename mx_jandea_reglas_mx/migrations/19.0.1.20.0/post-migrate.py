# -*- coding: utf-8 -*-
"""19.0.1.20.0: blinda en el modulo dos parches sobre reglas NATIVAS de
l10n_mx (para que sobrevivan a futuras actualizaciones de la localizacion):

  1) Aguinaldo con dias CAPTURABLES (entrada DIAS_AGUINALDO) en las estructuras
     'Christmas Bonus'. Si no se captura, usa el parametro (15).
  2) Fix getattr -> obj['campo'] en reglas nativas (p. ej. ISR de 'Regular Pay'
     que revienta con TODAS las faltas).

Ambos se reaplican de forma idempotente via _patch_native_rules.
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

    # Resync reglas del finiquito (por si se saltaron migraciones).
    for xmlid, name, code, cat_code, seq, python_code in _rules_spec():
        regla = env.ref('%s.%s' % (MODULE, xmlid), raise_if_not_found=False)
        if not regla:
            regla = Rule.search([('code', '=', code)], limit=1)
        if regla and regla.amount_python_compute != python_code:
            regla.amount_python_compute = python_code

    struct = env.ref('%s.%s' % (MODULE, STRUCT_XMLID), raise_if_not_found=False)
    if struct:
        _clean_foreign_rules(env, struct)

    # Reaplicar parches nativos (aguinaldo capturable + getattr).
    _patch_native_rules(env)

    _logger.info('mx_jandea_reglas_mx: parches nativos blindados (v19.0.1.20.0).')
