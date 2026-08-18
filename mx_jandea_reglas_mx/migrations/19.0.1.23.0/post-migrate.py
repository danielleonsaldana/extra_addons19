# -*- coding: utf-8 -*-
"""19.0.1.23.0: la tabla de dias de vacaciones (LFT) usa los años SIN redondear
(se trunca al rango inferior, igual que el VLOOKUP aproximado del Excel).
Antes redondeaba (4.82 -> 5 -> 20 dias); ahora trunca (4.82 -> 4 -> 18 dias), lo
que corrige Vacaciones, Prima Vacacional y el SDI (via factor de integracion).
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

    _logger.info('mx_jandea_reglas_mx: vacaciones sin redondear años '
                 '(v19.0.1.23.0).')
