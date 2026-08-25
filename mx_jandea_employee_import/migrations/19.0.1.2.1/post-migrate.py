# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID

from odoo.addons.mx_jandea_employee_import.hooks import ensure_input_types

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Al actualizar a 19.0.1.2.1 garantiza que los tipos de entrada de los
    ajustes (Vales de Despensa, Fondo de Ahorro, Ajuste Salarial) existan y
    estén disponibles en el diálogo de ajuste salarial."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    ensure_input_types(env)
    _logger.info('mx_jandea_employee_import 19.0.1.2.1: tipos de entrada de '
                 'ajustes verificados en actualización.')
