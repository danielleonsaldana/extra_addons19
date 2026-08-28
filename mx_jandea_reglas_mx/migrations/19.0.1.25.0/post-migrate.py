# -*- coding: utf-8 -*-
"""19.0.1.25.0: nómina NORMAL — Listado de Nómina.

Crea/actualiza las reglas que replican "Jandea_Ejemplo_Listado_de_Nomina.xlsx":

  * percepciones partidas en GRAVADA / EXENTA (prima vacacional, tiempo extra,
    festivo, descanso laborado, prima dominical, vales, fondo de ahorro),
  * regla informativa BASE_GRAVABLE_ISR (columna W),
  * ISR mensualizado sobre la base gravable y prorrateado a la periodicidad,
  * compensación y descuento de vales de despensa.

No toca NADA de la estructura de Finiquito.

En un upgrade el post_init_hook no corre, por eso se invoca aquí. Es
idempotente: si las reglas ya existen solo se les reescribe la fórmula.
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
    _logger.info('mx_jandea_reglas_mx: Listado de Nómina aplicado '
                 '(v19.0.1.25.0).')
