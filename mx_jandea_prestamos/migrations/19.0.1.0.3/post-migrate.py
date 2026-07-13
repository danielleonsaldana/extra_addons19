# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Puebla company_id en las líneas de calendario ya existentes.

    El campo company_id de mx.jandea.prestamo.linea es nuevo en 19.0.1.0.3
    (related store). Para las líneas creadas con versiones anteriores, la
    columna queda en NULL y la regla multiempresa las ocultaría. Aquí se
    copia la compañía desde el préstamo padre en una sola sentencia SQL.
    """
    cr.execute("""
        UPDATE mx_jandea_prestamo_linea l
           SET company_id = p.company_id
          FROM mx_jandea_prestamo p
         WHERE l.prestamo_id = p.id
           AND l.company_id IS DISTINCT FROM p.company_id
    """)
    _logger.info(
        'mx_jandea_prestamos: company_id poblado en %s línea(s) de calendario.',
        cr.rowcount,
    )
