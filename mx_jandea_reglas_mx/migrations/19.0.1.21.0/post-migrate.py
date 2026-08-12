# -*- coding: utf-8 -*-
"""19.0.1.21.0: alinea centavos con el Excel del cliente.

Redondea el factor de integracion a 4 decimales (1.0507) y el SDI a 2 decimales
(450.05), igual que el Excel. Antes Odoo usaba precision completa (SDI 450.04) y
salia ~$0.90 de diferencia en indemnizacion / base gravable / ISR.
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

    _logger.info('mx_jandea_reglas_mx: centavos alineados (v19.0.1.21.0).')
