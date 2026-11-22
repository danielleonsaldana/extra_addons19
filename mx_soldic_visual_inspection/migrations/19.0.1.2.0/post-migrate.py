# -*- coding: utf-8 -*-
# Cambia el separador del folio de "_" a "-" en los informes ya existentes.
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    tasks = env["project.task"].with_context(active_test=False).search(
        [("vt_plan_number", "!=", False), ("vt_sequence_number", ">", 0)])
    old_numbers = {t.id: t.vt_report_number for t in tasks}
    tasks._compute_vt_report_number()
    tasks.flush_recordset(["vt_report_number"])
    # Si el nombre de la tarea contenía el folio viejo, se actualiza también
    for task in tasks:
        old = old_numbers.get(task.id)
        if old and task.name and old in task.name and old != task.vt_report_number:
            task.name = task.name.replace(old, task.vt_report_number)
    # Reparaciones creadas con el nombre anterior "... (Reparación)": se renombran con el folio
    for task in tasks.filtered(lambda t: t.vt_is_repair and "(Reparación)" in (t.name or "")):
        base = task._vt_base_name()
        task.name = "%s - %s" % (task.vt_report_number, base) if base else task.vt_report_number
