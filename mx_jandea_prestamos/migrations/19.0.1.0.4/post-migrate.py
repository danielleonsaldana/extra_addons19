# -*- coding: utf-8 -*-
"""Repara el código de la regla PRESTAMO ya creada en la base.

En Odoo 19 ``inputs`` es un diccionario, por lo que el acceso por atributo
(``inputs.PRESTAMO``) lanza:

    AttributeError: 'dict' object has no attribute 'PRESTAMO'

Las reglas creadas por versiones anteriores del módulo quedaron con ese código.
Esta migración las reescribe, sin necesidad de desinstalar/reinstalar.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    from odoo.addons.mx_jandea_prestamos.hooks import RULE_CODE, build_rule_code

    env = api.Environment(cr, SUPERUSER_ID, {})
    nuevo = build_rule_code()
    reglas = env['hr.salary.rule'].search([('code', '=', RULE_CODE)])
    actualizadas = 0
    for regla in reglas:
        if regla.amount_python_compute != nuevo:
            regla.amount_python_compute = nuevo
            actualizadas += 1
    _logger.info(
        'mx_jandea_prestamos: %s regla(s) "%s" actualizadas al acceso por '
        'clave de inputs.', actualizadas, RULE_CODE)
