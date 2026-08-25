# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

# (xmlid, nombre, código). Deben coincidir con data/hr_payslip_input_type_data.xml
INPUT_TYPES = [
    ('mx_jandea_employee_import.input_type_vales_despensa', 'Vales de Despensa', 'VALES_DESPENSA'),
    ('mx_jandea_employee_import.input_type_fondo_ahorro', 'Fondo de Ahorro', 'FONDO_AHORRO'),
    ('mx_jandea_employee_import.input_type_ajuste_salarial', 'Ajuste Salarial', 'AJUSTE_SALARIAL'),
]


def ensure_input_types(env):
    """Garantiza que los tres tipos de entrada existan y estén disponibles como
    ajuste salarial (available_in_attachments=True). Idempotente: sirve tanto en
    instalación (post_init_hook) como en actualización (post-migrate), y repara
    registros que hubieran quedado sin la bandera.
    """
    if 'hr.payslip.input.type' not in env:
        _logger.warning('mx_jandea_employee_import: hr_payroll no disponible; '
                        'no se crearon los tipos de entrada.')
        return
    InputType = env['hr.payslip.input.type']
    Data = env['ir.model.data']
    creados, reparados = 0, 0
    for xmlid, name, code in INPUT_TYPES:
        module, xid = xmlid.split('.')
        rec = env.ref(xmlid, raise_if_not_found=False)
        if not rec:
            # Puede existir por código sin el xmlid (instalación previa manual)
            rec = InputType.search([('code', '=', code)], limit=1)
        if rec:
            if not rec.available_in_attachments:
                rec.available_in_attachments = True
                reparados += 1
        else:
            rec = InputType.create({
                'name': name, 'code': code, 'available_in_attachments': True,
            })
            creados += 1
        # Asegurar el xmlid para que la desinstalación limpie el registro
        if not Data.search([('module', '=', module), ('name', '=', xid)], limit=1):
            Data.create({
                'name': xid, 'module': module,
                'model': 'hr.payslip.input.type', 'res_id': rec.id,
                'noupdate': True,
            })
    _logger.info('mx_jandea_employee_import: tipos de entrada de ajustes '
                 'verificados (Vales, Fondo de Ahorro, Ajuste Salarial). '
                 'Creados=%s, reparados=%s.', creados, reparados)


def post_init_ensure_input_types(env):
    ensure_input_types(env)
