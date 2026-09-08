# -*- coding: utf-8 -*-
"""19.0.1.26.1: los días del periodo se leen de l10n_mx_schedule_table.

En la localización mexicana ``bi-weekly`` es QUINCENAL (15 días) y la
catorcenal es ``14_days``; además no existe ``semi-monthly``. El diccionario
propio de la v26.0 daba 14 días a las nóminas quincenales, así que el ISR se
mensualizaba con 30.4/14 (base mensual inflada) y el subsidio se apagaba por
rebasar el límite de ingreso. Ahora los días salen del propio parámetro de
l10n_mx y el diccionario queda solo como respaldo.
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
    _logger.info('mx_jandea_reglas_mx: días del periodo tomados de '
                 'l10n_mx_schedule_table (v19.0.1.26.1).')
