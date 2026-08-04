# -*- coding: utf-8 -*-
"""Sincroniza el Finiquito con la definición 19.0.1.8.0.

Corrige, en las reglas YA creadas (sin desinstalar):
  * FECHA DE ALTA: se toma la MÁS ANTIGUA disponible. En Odoo 19 el "version"
    del contrato puede traer la fecha de una versión reciente, lo que dejaba la
    antigüedad, el aguinaldo y las vacaciones diminutos.
  * Lectura de entradas capturadas (FNQT_IND_DIAS, FNQT_DIAS_SAL, …): ahora se
    leen también directo de las entradas del recibo. Antes la indemnización
    capturada (p. ej. 90) salía en 0.
  * Importe × Cantidad: Salario Pendiente, Aguinaldo, Vacaciones e Indemnización
    ahora ponen el importe DIARIO y los días como cantidad, para que el Total
    (importe × cantidad) sea correcto (antes multiplicaba dos veces).
  * "Salario Pendiente" toma los días de asistencia del período si no se captura
    FNQT_DIAS_SAL.
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
        vals = {}
        if regla.amount_python_compute != python_code:
            vals['amount_python_compute'] = python_code
        if regla.name != name:
            vals['name'] = name
        if regla.sequence != seq:
            vals['sequence'] = seq
        if vals:
            regla.write(vals)
            actualizadas += 1

    struct = env.ref('%s.%s' % (MODULE, STRUCT_XMLID), raise_if_not_found=False)
    if struct:
        _clean_foreign_rules(env, struct)

    _logger.info('mx_jandea_reglas_mx: %s regla(s) resincronizadas '
                 '(v19.0.1.8.0).', actualizadas)
