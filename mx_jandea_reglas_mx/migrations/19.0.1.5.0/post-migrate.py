# -*- coding: utf-8 -*-
"""Sincroniza las reglas de Finiquito con la definición 19.0.1.5.0.

Cambios de esta versión:
  * SDI calculado con factor de integración (art. 30 LSS): la indemnización y la
    cuota IMSS ahora usan el salario diario INTEGRADO (p. ej. 428.33 -> 450.05),
    igual que el Excel, en vez del salario diario simple.
  * Indemnización por días directos: se captura FNQT_IND_DIAS (90/60/45...) y con
    días > 0 aplica, sin necesitar FNQT_IND_90=1.
  * Nuevo input FNQT_SDI_REAL (override del SDI real).

Como el PREAMBLE va embebido en TODAS las reglas, se reescribe su código para
que los cambios apliquen al ACTUALIZAR (sin desinstalar/reinstalar). También se
enlazan los inputs pendientes a la estructura.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    from odoo.addons.mx_jandea_reglas_mx.hooks import (
        _rules_spec, STRUCT_XMLID, FNQT_INPUT_CODES)

    env = api.Environment(cr, SUPERUSER_ID, {})
    Rule = env['hr.salary.rule']

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
    _logger.info('mx_jandea_reglas_mx: %s regla(s) de finiquito resincronizadas '
                 'a 19.0.1.5.0.', actualizadas)

    # Enlazar cualquier input pendiente (incluye FNQT_SDI_REAL) a la estructura.
    struct = env.ref('mx_jandea_reglas_mx.%s' % STRUCT_XMLID,
                     raise_if_not_found=False)
    if struct:
        InputType = env['hr.payslip.input.type']
        pendientes = InputType.search([('code', 'in', FNQT_INPUT_CODES)])
        for it in pendientes:
            if struct not in it.struct_ids:
                it.struct_ids = [(4, struct.id)]
        _logger.info('mx_jandea_reglas_mx: inputs de finiquito enlazados a la '
                     'estructura.')
