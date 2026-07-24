# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

# Código del concepto / regla. Debe coincidir con el code del
# hr.payslip.input.type creado en data/hr_payslip_input_type_data.xml
RULE_CODE = 'PRESTAMO'


def build_rule_code():
    """Código Python de la regla de descuento de préstamo.

    En Odoo 19 ``inputs`` es un diccionario, por lo que el acceso por atributo
    (``inputs.PRESTAMO``) lanza AttributeError. Se accede por clave y se
    protege el caso de que la entrada no exista en el recibo.

    El signo negativo hace que el préstamo reste del neto (convención estándar
    de deducciones en Odoo).
    """
    return (
        "# Descuento de prestamo tomado del ajuste salarial (hr.salary.attachment)\n"
        "# Odoo 19: 'inputs' es un dict. El acceso por atributo\n"
        "# (inputs.%(c)s) lanza AttributeError, por eso se accede por clave.\n"
        "try:\n"
        "    _entrada = inputs['%(c)s']\n"
        "except Exception:\n"
        "    _entrada = None\n"
        "result = -(_entrada.amount) if _entrada else 0.0"
    ) % {'c': RULE_CODE}


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

    python_code = build_rule_code()

    created = 0
    for struct in structures:
        exists = Rule.search(
            [('struct_id', '=', struct.id), ('code', '=', RULE_CODE)], limit=1
        )
        if exists:
            continue
        rule = Rule.create({
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
        # Vincular la regla al módulo para que la desinstalación la elimine
        # y no queden reglas huérfanas en las estructuras.
        env['ir.model.data'].create({
            'name': 'salary_rule_prestamo_struct_%d' % struct.id,
            'module': 'mx_jandea_prestamos',
            'model': 'hr.salary.rule',
            'res_id': rule.id,
            'noupdate': True,
        })
        created += 1

    _logger.info(
        'mx_jandea_prestamos: regla "%s" creada en %s estructura(s) de nómina.',
        RULE_CODE, created,
    )

    _create_menu(env)


def _create_menu(env):
    """Configura el context de la acción (concepto por default) y crea el menú
    "Préstamos" colgándolo del menú nativo de Ajustes Salariales
    (hr.salary.attachment), sin depender de un xmlid de menú fijo.

    Se registra en ir.model.data para que la desinstalación lo elimine.
    """
    action = env.ref(
        'mx_jandea_prestamos.action_mx_jandea_prestamos',
        raise_if_not_found=False,
    )
    if not action:
        _logger.warning('mx_jandea_prestamos: no se encontró la acción; '
                        'no se configuró el menú.')
        return

    # Si el menú ya existe (reinstalación), no duplicar.
    if env.ref('mx_jandea_prestamos.menu_mx_jandea_prestamos',
               raise_if_not_found=False):
        return

    # Buscar el menú nativo que abre los Ajustes Salariales y usar su padre,
    # para que "Préstamos" aparezca al lado, dentro de Nómina.
    parent = False
    sa_actions = env['ir.actions.act_window'].search(
        [('res_model', '=', 'hr.salary.attachment')]
    )
    if sa_actions:
        refs = ['ir.actions.act_window,%d' % a.id for a in sa_actions]
        native_menu = env['ir.ui.menu'].search(
            [('action', 'in', refs)], limit=1
        )
        if native_menu:
            parent = native_menu.parent_id

    # Respaldo: raíz de RR.HH. (existe siempre).
    if not parent:
        parent = env.ref('hr.menu_hr_root', raise_if_not_found=False)

    menu = env['ir.ui.menu'].create({
        'name': 'Préstamos',
        'parent_id': parent.id if parent else False,
        'action': 'ir.actions.act_window,%d' % action.id,
        'sequence': 90,
    })

    # Vincular al módulo para que la desinstalación limpie el menú.
    env['ir.model.data'].create({
        'name': 'menu_mx_jandea_prestamos',
        'module': 'mx_jandea_prestamos',
        'model': 'ir.ui.menu',
        'res_id': menu.id,
        'noupdate': True,
    })
    _logger.info(
        'mx_jandea_prestamos: menú "Préstamos" creado bajo "%s".',
        parent.name if parent else 'raíz',
    )
