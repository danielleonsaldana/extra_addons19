# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

MODULE = 'mx_jandea_nomina_facturacion'


def _find_payroll_root(env):
    """Encuentra la raíz de la app de Nómina sin depender de un xmlid fijo.

    Busca un menú que abra un modelo típico de nómina y sube por parent_id
    hasta la raíz (el menú de la app). Robusto entre versiones/localizaciones.
    """
    Menu = env['ir.ui.menu']
    Act = env['ir.actions.act_window']
    for model in ('hr.payslip.run', 'hr.payslip', 'hr.salary.attachment'):
        actions = Act.search([('res_model', '=', model)])
        if not actions:
            continue
        refs = ['ir.actions.act_window,%d' % a.id for a in actions]
        menu = Menu.search([('action', 'in', refs)], limit=1)
        if menu:
            top = menu
            while top.parent_id:
                top = top.parent_id
            return top
    return False


def _link(env, name, menu):
    """Registra el menú en ir.model.data para que la desinstalación lo limpie."""
    env['ir.model.data'].create({
        'name': name,
        'module': MODULE,
        'model': 'ir.ui.menu',
        'res_id': menu.id,
        'noupdate': True,
    })


def post_init_hook(env):
    """Crea el menú 'Facturación de Nómina' bajo la app de Nómina.

    Si no se encuentra la app de Nómina, cae a la raíz de RR.HH.
    Se ejecuta solo al instalar; los menús quedan vinculados al módulo.
    """
    # Evitar duplicados en reinstalación.
    if env.ref('%s.menu_nomina_facturacion_root' % MODULE, raise_if_not_found=False):
        return

    parent = False
    try:
        parent = _find_payroll_root(env)
    except Exception as e:  # noqa: BLE001
        _logger.warning('%s: no se pudo detectar la app de Nómina (%s).', MODULE, e)

    if not parent:
        parent = env.ref('hr.menu_hr_root', raise_if_not_found=False)
        _logger.info('%s: menú colocado bajo RR.HH. (no se detectó app de Nómina).', MODULE)
    else:
        _logger.info('%s: menú colocado bajo la app de Nómina "%s".', MODULE, parent.name)

    Menu = env['ir.ui.menu']

    root = Menu.create({
        'name': 'Facturación de Nómina',
        'parent_id': parent.id if parent else False,
        'sequence': 90,
    })
    _link(env, 'menu_nomina_facturacion_root', root)

    act_wizard = env.ref('%s.action_facturacion_wizard' % MODULE, raise_if_not_found=False)
    if act_wizard:
        m = Menu.create({
            'name': 'Generar Facturación',
            'parent_id': root.id,
            'action': 'ir.actions.act_window,%d' % act_wizard.id,
            'sequence': 10,
        })
        _link(env, 'menu_facturacion_wizard', m)

    act_concepto = env.ref('%s.action_nomina_concepto' % MODULE, raise_if_not_found=False)
    if act_concepto:
        m = Menu.create({
            'name': 'Conceptos de Facturación',
            'parent_id': root.id,
            'action': 'ir.actions.act_window,%d' % act_concepto.id,
            'sequence': 20,
        })
        _link(env, 'menu_nomina_concepto', m)
