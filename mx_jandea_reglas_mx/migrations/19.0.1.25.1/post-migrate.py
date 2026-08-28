# -*- coding: utf-8 -*-
"""19.0.1.25.1: fix NameError 'gross' en las reglas nativas posteriores al ISR.

Odoo evalúa todas las reglas de un recibo sobre el mismo diccionario, así que
la fórmula del ISR tiene que publicar las variables que consumen las reglas de
l10n_mx que van después (ISR_MINIMUM_WAGE usa "gross <= min_wage"). La v25.0
las dejaba de publicar y el recibo tronaba. Se reescribe la fórmula.
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
    _logger.info('mx_jandea_reglas_mx: fórmula de ISR republicada '
                 '(v19.0.1.25.1).')
