# -*- coding: utf-8 -*-
"""Sincroniza el Finiquito con la definición 19.0.1.12.0.

Corrige en las reglas ya creadas (sin desinstalar):
  * FECHA DE ALTA: se busca la MAS ANTIGUA entre TODAS las versiones/contratos
    del empleado (employee.version_ids / contract_ids). Ademas, si se captura
    FNQT_DIAS_LAB, la fecha de alta se deriva de la baja (palanca manual
    infalible). Antes la antiguedad salia de ~1 dia -> aguinaldo/vacaciones
    diminutos y el ISR disparado (sin exencion de indemnizacion).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    from odoo.addons.mx_jandea_reglas_mx.hooks import (
        _rules_spec, _clean_foreign_rules, STRUCT_XMLID, MODULE)

    env = api.Environment(cr, SUPERUSER_ID, {})
    Rule = env['hr.salary.rule']

    actualizadas = 0
    for xmlid, name, code, cat_code, seq, python_code in _rules_spec():
        regla = env.ref('%s.%s' % (MODULE, xmlid), raise_if_not_found=False)
        if not regla:
            regla = Rule.search([('code', '=', code)], limit=1)
        if not regla:
            continue
        if regla.amount_python_compute != python_code:
            regla.amount_python_compute = python_code
            actualizadas += 1

    struct = env.ref('%s.%s' % (MODULE, STRUCT_XMLID), raise_if_not_found=False)
    if struct:
        _clean_foreign_rules(env, struct)

    _logger.info('mx_jandea_reglas_mx: %s regla(s) resincronizadas '
                 '(v19.0.1.12.0).', actualizadas)
