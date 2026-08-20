# -*- coding: utf-8 -*-
"""19.0.1.24.0: nómina NORMAL — Fondo de Ahorro y Vales de Despensa.

Agrega a la estructura nativa 'l10n_mx_regular_pay' cuatro reglas de percepción
(FA gravado/exento, Vales gravado/exento) que replican el Excel
"LicenciasInternacionales (FA y VD)". Se disparan solo cuando en el recibo se
captura la entrada "Sueldo Neto (FA/VD)".

En un upgrade el post_init_hook NO se ejecuta, por eso aquí:
  * se crean las reglas si aún no existen, y
  * si ya existen, se re-aplica su fórmula Python (por si cambió el preámbulo).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    from odoo.addons.mx_jandea_reglas_mx.hooks import (
        _favd_rules_spec, _build_favd_rules, MODULE)

    env = api.Environment(cr, SUPERUSER_ID, {})
    Rule = env['hr.salary.rule']

    # 1) Crear las reglas que falten (idempotente).
    _build_favd_rules(env)

    # 2) Re-aplicar la fórmula Python en las reglas ya existentes.
    for xmlid, name, code, tipo, seq, python_code in _favd_rules_spec():
        regla = env.ref('%s.%s' % (MODULE, xmlid), raise_if_not_found=False)
        if not regla:
            regla = Rule.search([('code', '=', code)], limit=1)
        if regla and regla.amount_python_compute != python_code:
            regla.amount_python_compute = python_code

    _logger.info('mx_jandea_reglas_mx: reglas de Fondo de Ahorro / Vales de '
                 'Despensa aplicadas (v19.0.1.24.0).')
