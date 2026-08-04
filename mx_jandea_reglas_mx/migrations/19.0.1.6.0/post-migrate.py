# -*- coding: utf-8 -*-
"""Sincroniza las reglas de Finiquito con la definición 19.0.1.6.0.

Como el código Python va embebido en las reglas ya creadas, el post_init_hook
NO las reescribe al actualizar; por eso esta migración las resincroniza sin
desinstalar/reinstalar.

Cambios de esta versión:
  * Vacaciones / prima vacacional: días base = (BAJA - fecha vacaciones) + 1
    (antes +5), igual que el Excel. Corrige montos de vacaciones y P.V.
  * ISR: el factor de proporción mensual se toma de la periodicidad de pago
    (quincenal 2.0267, catorcenal 2.1714, semanal 4.3429, mensual 1.0) en vez
    del 4.3429 fijo. Sigue siendo capturable con FNQT_FACTOR_ISR.
  * Cuota obrera IMSS = 0 cuando el salario diario es el mínimo (LSS art. 36),
    igual que el Excel (IF(SD=SMG,0,...)).
  * ISN eliminado del recibo del empleado (era costo patronal): se borra la
    regla FNQT_ISN y sus entradas FNQT_ISN_TASA / FNQT_ISN_EXCL_SEP.
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

    # 1) Resincronizar código/nombre/secuencia de las reglas del finiquito.
    actualizadas = 0
    for xmlid, name, code, cat_code, seq, python_code in _rules_spec():
        regla = env.ref('mx_jandea_reglas_mx.%s' % xmlid,
                        raise_if_not_found=False)
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

    # 2) Borrar la regla ISN del recibo del empleado.
    isn = env.ref('mx_jandea_reglas_mx.rule_fnqt_isn',
                  raise_if_not_found=False)
    if not isn:
        isn = Rule.search([('code', '=', 'FNQT_ISN')], limit=1)
    if isn:
        try:
            isn.unlink()
            _logger.info('mx_jandea_reglas_mx: regla ISN eliminada.')
        except Exception:
            # Si hay recibos históricos que la referencian, al menos ocultarla.
            isn.write({'appears_on_payslip': False, 'active': False})
            _logger.info('mx_jandea_reglas_mx: regla ISN desactivada '
                         '(tenía líneas históricas).')

    # 3) Borrar las entradas de ISN.
    InType = env['hr.payslip.input.type']
    isn_inputs = InType.search(
        [('code', 'in', ['FNQT_ISN_TASA', 'FNQT_ISN_EXCL_SEP'])])
    if isn_inputs:
        try:
            isn_inputs.unlink()
        except Exception:
            pass

    _logger.info('mx_jandea_reglas_mx: %s regla(s) de finiquito '
                 'resincronizadas (v19.0.1.6.0).', actualizadas)
