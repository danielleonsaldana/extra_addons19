# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Al actualizar, escribe el context correcto en la acción "Préstamos"
    con el id real del concepto, reparando el valor roto que pudo quedar
    guardado de una instalación anterior (sustitución %(...)d no resuelta).
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    action = env.ref(
        'mx_jandea_prestamos.action_mx_jandea_prestamos',
        raise_if_not_found=False,
    )
    input_type = env.ref(
        'mx_jandea_prestamos.input_type_prestamo',
        raise_if_not_found=False,
    )
    if action and input_type and action.res_model == 'hr.salary.attachment':
        action.write({
            'context': "{'default_other_input_type_id': %d}" % input_type.id,
        })
        _logger.info(
            'mx_jandea_prestamos: context de la acción reparado (default_other_input_type_id=%d).',
            input_type.id,
        )
    else:
        _logger.warning(
            'mx_jandea_prestamos: no se pudo reparar el context (acción o '
            'concepto no encontrados).'
        )
