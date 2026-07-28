# -*- coding: utf-8 -*-
"""Sincroniza las reglas de Finiquito con la definición 19.0.1.4.0.

El post_init_hook solo crea reglas/enlaces que faltan al INSTALAR; en una
actualización hay que reescribir lo ya existente. Esta migración aplica, sin
desinstalar/reinstalar:

  * Indemnización con días CONFIGURABLES (FNQT_IND_DIAS, def. 90) en lugar del
    90 fijo. La regla ahora muestra los días pagados como cantidad y se
    renombra a "Indemnización Constitucional".
  * Salario pendiente muestra los días pagados (admite más de 15).
  * Enlaza el nuevo input FNQT_IND_DIAS a la estructura de Finiquito.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    from odoo.addons.mx_jandea_reglas_mx.hooks import _rules_spec, STRUCT_XMLID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Rule = env['hr.salary.rule']

    # 1) Resincronizar código y nombre de todas las reglas del finiquito.
    actualizadas = 0
    for xmlid, name, code, cat_code, seq, python_code in _rules_spec():
        regla = env.ref('mx_jandea_reglas_mx.%s' % xmlid, raise_if_not_found=False)
        if not regla:
            regla = Rule.search([('code', '=', code)], limit=1)
        if not regla:
            continue
        vals = {}
        if regla.amount_python_compute != python_code:
            vals['amount_python_compute'] = python_code
        if regla.name != name:
            vals['name'] = name
        if vals:
            regla.write(vals)
            actualizadas += 1
    _logger.info('mx_jandea_reglas_mx: %s regla(s) de finiquito actualizadas.',
                 actualizadas)

    # 2) Enlazar el nuevo input FNQT_IND_DIAS (y cualquier otro pendiente) a la
    #    estructura de Finiquito.
    struct = env.ref('mx_jandea_reglas_mx.%s' % STRUCT_XMLID,
                     raise_if_not_found=False)
    if struct:
        InputType = env['hr.payslip.input.type']
        it = InputType.search([('code', '=', 'FNQT_IND_DIAS')], limit=1)
        if it and struct not in it.struct_ids:
            it.struct_ids = [(4, struct.id)]
            _logger.info('mx_jandea_reglas_mx: FNQT_IND_DIAS enlazado a la '
                         'estructura de Finiquito.')
