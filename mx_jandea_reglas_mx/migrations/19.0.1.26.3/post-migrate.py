# -*- coding: utf-8 -*-
"""19.0.1.26.3: cuadre exacto contra Aspel.

El tope exento de los vales pasa a ser 40% de la UMA x 30.4 (parámetro
mx_jandea_vd_dias_tope_base) en vez de calcularse con los días del periodo, y
lo que rebase ese tope GRAVA en vez de recortarse el importe.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    from odoo.addons.mx_jandea_reglas_mx.hooks_nomina import _build_nomina_rules

    env = api.Environment(cr, SUPERUSER_ID, {})
    _build_nomina_rules(env)
    _logger.info('mx_jandea_reglas_mx: tope de vales actualizado '
                 '(v19.0.1.26.3).')
