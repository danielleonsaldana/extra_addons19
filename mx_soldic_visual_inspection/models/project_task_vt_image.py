# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import api, fields, models


class ProjectTaskVtImage(models.Model):
    _name = "project.task.vt.image"
    _description = "Plano / imagen de Inspección Visual"
    _order = "task_id, sequence, id"

    task_id = fields.Many2one("project.task", string="Tarea", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Vista", required=True, default="Vista")
    image = fields.Image(string="Plano", required=True, max_width=1920, max_height=1920)
    annotated_image = fields.Image(
        string="Plano con juntas", max_width=1920, max_height=1920, copy=False, readonly=True,
        help="Se genera al guardar las juntas marcadas. Es la imagen que sale en el croquis del PDF.",
    )
    markers = fields.Json(string="Marcadores", copy=False, default=list)
    marker_count = fields.Integer(string="Juntas", compute="_compute_marker_count")
    line_ids = fields.One2many("project.task.vt.line", "image_id", string="Juntas de esta vista")

    @api.depends("markers")
    def _compute_marker_count(self):
        for rec in self:
            rec.marker_count = len(rec.markers or [])

    def _vt_report_image(self):
        self.ensure_one()
        return self.annotated_image or self.image

    # ---------------- Trazabilidad en el chatter de la tarea ----------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.task_id.message_post(body=Markup("Plano agregado: <b>%s</b>") % rec.name)
        return records

    def write(self, vals):
        if "image" in vals:
            # Si cambia la imagen base, las marcas anteriores ya no corresponden
            vals.setdefault("annotated_image", False)
        res = super().write(vals)
        if not self.env.context.get("vt_no_log"):
            for rec in self:
                changes = []
                if "image" in vals:
                    changes.append("se reemplazó la imagen")
                if "name" in vals:
                    changes.append("nombre: %s" % rec.name)
                if changes:
                    rec.task_id.message_post(body=Markup("Plano <b>%s</b>: %s") % (rec.name, ", ".join(changes)))
        return res

    def unlink(self):
        for rec in self:
            rec.task_id.message_post(
                body=Markup("Plano eliminado: <b>%s</b> (%s juntas marcadas)") % (rec.name, rec.marker_count))
        return super().unlink()
