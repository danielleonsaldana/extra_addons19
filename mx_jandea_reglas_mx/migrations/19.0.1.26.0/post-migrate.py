# -*- coding: utf-8 -*-
"""19.0.1.26.0: base gravable aditiva, mensualización 30.4/días y subsidio.

Cambios que se reescriben en las reglas ya instaladas:

  * La base de ISR se arma sumando (sueldo + lo gravado). El fondo de ahorro
    deja de restar de la base: solo suma su excedente del tope
    ``UMA * días del periodo * 1.3`` (quincena = UMA × 15 × 1.3).
  * La mensualización pasa de 2.0 a 30.4/15 en nóminas quincenales.
  * Se calcula el subsidio para el empleo (decreto DOF 31/12/2025) y se resta
    dentro de la regla de ISR; las reglas nativas SUBSIDY se neutralizan.
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
    _logger.info('mx_jandea_reglas_mx: ISR quincenal alineado con Aspel '
                 '(v19.0.1.26.0).')
