# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

# Código del concepto / regla. Debe coincidir con el code del
# hr.payslip.input.type creado en data/hr_payslip_input_type_data.xml
RULE_CODE = 'PRESTAMO'


def post_init_attach_rule(env):
    """Crea la regla salarial de Préstamo en cada estructura de nómina existente.

    La regla solo descuenta cuando el recibo trae una entrada tipo Préstamo
    (generada por el ajuste salarial del empleado). Si no hay préstamo activo,
    devuelve 0.0, por lo que es inofensiva para las demás nóminas.

    Se ejecuta una sola vez, al instalar el módulo. Para estructuras creadas
    después de la instalación, la regla puede agregarse a mano (ver README en
    la descripción del módulo) o reinstalando el módulo.
    """
    input_type = env.ref(
        'mx_jandea_prestamos.input_type_prestamo', raise_if_not_found=False
    )
    if not input_type:
        _logger.warning(
            'mx_jandea_prestamos: no se encontró el tipo de entrada PRESTAMO; '
            'no se creó la regla salarial.'
        )
        return

    # Categoría de Deducción. Se busca por código 'DED' para no depender del
    # xmlid exacto (puede variar entre localizaciones).
    category = env['hr.salary.rule.category'].search(
        [('code', '=', 'DED')], limit=1
    )
    if not category:
        _logger.warning(
            'mx_jandea_prestamos: no se encontró la categoría de deducción '
            "(código 'DED'). Crea la regla salarial manualmente y asígnale "
            'una categoría de deducción.'
        )
        return

    Rule = env['hr.salary.rule']
    structures = env['hr.payroll.structure'].search([])

    # El signo negativo hace que el préstamo reste del neto (convención estándar
    # de deducciones en Odoo). Si en tu estructura el neto sumara las
    # deducciones con signo propio, cambia a: result = inputs.PRESTAMO.amount
    python_code = (
        "# Descuento de préstamo tomado del ajuste salarial (hr.salary.attachment)\n"
        "result = -(inputs.%s.amount) if inputs.%s else 0.0"
        % (RULE_CODE, RULE_CODE)
    )

    created = 0
    for struct in structures:
        exists = Rule.search(
            [('struct_id', '=', struct.id), ('code', '=', RULE_CODE)], limit=1
        )
        if exists:
            continue
        Rule.create({
            'name': 'Préstamo a empleado',
            'code': RULE_CODE,
            'category_id': category.id,
            'struct_id': struct.id,
            'sequence': 145,  # entre deducciones (110-150), antes del neto
            'appears_on_payslip': True,
            'condition_select': 'none',
            'amount_select': 'code',
            'amount_python_compute': python_code,
        })
        created += 1

    _logger.info(
        'mx_jandea_prestamos: regla "%s" creada en %s estructura(s) de nómina.',
        RULE_CODE, created,
    )
