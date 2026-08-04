# -*- coding: utf-8 -*-
"""Sincroniza el Finiquito con la definición 19.0.1.7.0.

Cambio de esta versión:
  * Se elimina de la estructura de Finiquito la regla NATIVA de Odoo
    ``Basic Salary`` (código BASIC). Odoo la agrega a toda estructura nueva y
    PRORRATEA el sueldo por los días trabajados del período, duplicando el
    salario del finiquito. El salario del finiquito debe ir SOLO en
    ``Salario Pendiente`` (FNQT_SALARIO), controlado por FNQT_DIAS_SAL.
    Se respetan las reglas propias y las agregadas por el usuario (p. ej.
    ``Préstamo a empleado``).

También resincroniza el código Python de las reglas por si se actualiza desde
una versión previa sin pasar por su migración.
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

    # 1) Resincronizar código/nombre/secuencia de las reglas del finiquito.
    for xmlid, name, code, cat_code, seq, python_code in _rules_spec():
        regla = env.ref('%s.%s' % (MODULE, xmlid), raise_if_not_found=False)
        if not regla:
            regla = Rule.search([('code', '=', code)], limit=1)
        if not regla:
            continue
        vals = {}
        if regla.amount_python_compute != python_code:
            vals['amount_python_compute'] = python_code
        if regla.name != name:
            vals['name'] = name
        if regla.sequence != seq:
            vals['sequence'] = seq
        if vals:
            regla.write(vals)

    # 2) Quitar la regla nativa "Basic Salary" (y GROSS/NET nativas si las hay)
    #    de la estructura de Finiquito.
    struct = env.ref('%s.%s' % (MODULE, STRUCT_XMLID), raise_if_not_found=False)
    if struct:
        _clean_foreign_rules(env, struct)

    _logger.info('mx_jandea_reglas_mx: Finiquito depurado (v19.0.1.7.0).')
