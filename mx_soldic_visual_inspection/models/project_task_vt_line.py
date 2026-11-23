# -*- coding: utf-8 -*-
from markupsafe import Markup, escape

from odoo import api, fields, models

LOGGED_FIELDS = ["joint", "description", "welder", "indication", "dimension", "result"]


class ProjectTaskVtLine(models.Model):
    _name = "project.task.vt.line"
    _description = "Resultado de Inspección Visual por junta"
    _order = "task_id, sequence, id"

    task_id = fields.Many2one("project.task", string="Tarea", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    joint = fields.Char(string="Junta", required=True)
    description = fields.Char(string="Descripción")
    welder = fields.Char(string="Soldador")
    indication = fields.Char(string="Indicación (mm)", default="-----")
    dimension = fields.Float(string="Dimensiones (mm)", digits=(16, 2))
    result = fields.Selection(
        [("accepted", "ACEPTADA"), ("rejected", "RECHAZADA")],
        string="Resultado",
        default="accepted",
        required=True,
    )
    image_id = fields.Many2one("project.task.vt.image", string="Plano", ondelete="set null", copy=False)
    marker_uid = fields.Char(string="Marcador", copy=False, index=True)

    # ---------------- Trazabilidad en el chatter de la tarea ----------------
    def _vt_display(self, fname):
        self.ensure_one()
        field = self._fields[fname]
        value = self[fname]
        if field.type == "selection":
            return dict(field._description_selection(self.env)).get(value, "")
        if field.type == "float":
            return "{:,.2f}".format(value or 0.0)
        return value or "—"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get("vt_no_log"):
            for task, task_lines in lines.grouped("task_id").items():
                names = ", ".join(task_lines.mapped("joint"))
                task.message_post(body=Markup("Juntas agregadas: <b>%s</b>") % names)
        return lines

    def write(self, vals):
        if self.env.context.get("vt_no_log"):
            return super().write(vals)
        tracked = [f for f in LOGGED_FIELDS if f in vals]
        before = {line.id: {f: line._vt_display(f) for f in tracked} for line in self} if tracked else {}
        res = super().write(vals)
        if tracked:
            for task, task_lines in self.grouped("task_id").items():
                rows = []
                for line in task_lines:
                    diffs = []
                    for f in tracked:
                        old, new = before[line.id][f], line._vt_display(f)
                        if old != new:
                            diffs.append(Markup("%s: %s → <b>%s</b>") % (self._fields[f].string, old, new))
                    if diffs:
                        rows.append(Markup("<li><b>%s</b> · %s</li>") % (line.joint, Markup(" · ").join(diffs)))
                if rows:
                    task.message_post(body=Markup("Cambios en juntas:<ul>%s</ul>") % Markup("").join(rows))
        return res

    def unlink(self):
        if not self.env.context.get("vt_no_log"):
            for task, task_lines in self.grouped("task_id").items():
                task.message_post(body=Markup("Juntas eliminadas: <b>%s</b>") % escape(", ".join(task_lines.mapped("joint"))))
        return super().unlink()
