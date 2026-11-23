# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class VtGenerateJoints(models.TransientModel):
    _name = "vt.generate.joints"
    _description = "Generar juntas de Inspección Visual"

    task_id = fields.Many2one("project.task", required=True, ondelete="cascade")
    quantity = fields.Integer(string="¿Cuántas juntas?", default=1, required=True)
    description = fields.Char(string="Descripción")
    dimension = fields.Float(string="Dimensiones (mm)", digits=(16, 2))
    indication = fields.Char(string="Indicación (mm)", default="-----")
    next_joint = fields.Char(string="Iniciará en", compute="_compute_next_joint")

    @api.depends("task_id")
    def _compute_next_joint(self):
        for wiz in self:
            wiz.next_joint = "J%d" % (len(wiz.task_id.vt_line_ids) + 1)

    def action_generate(self):
        self.ensure_one()
        if self.quantity < 1 or self.quantity > 500:
            raise UserError(_("Indica una cantidad entre 1 y 500."))
        start = len(self.task_id.vt_line_ids)
        last_seq = max(self.task_id.vt_line_ids.mapped("sequence") or [0])
        self.env["project.task.vt.line"].create([{
            "task_id": self.task_id.id,
            "joint": "J%d" % (start + i),
            "sequence": last_seq + i,
            "description": self.description,
            "dimension": self.dimension,
            "indication": self.indication or "-----",
            "result": "accepted",
        } for i in range(1, self.quantity + 1)])
        return {"type": "ir.actions.act_window_close"}


class VtFillJoints(models.TransientModel):
    _name = "vt.fill.joints"
    _description = "Llenar varias juntas de Inspección Visual"

    task_id = fields.Many2one("project.task", required=True, ondelete="cascade")
    line_ids = fields.Many2many(
        "project.task.vt.line", string="Juntas",
        domain="[('task_id', '=', task_id)]",
        help="Elige las juntas a las que se les copiarán los datos (ej. J1, J4, J7, J10).",
    )
    description = fields.Char(string="Descripción")
    dimension = fields.Float(string="Dimensiones (mm)", digits=(16, 2))
    indication = fields.Char(string="Indicación (mm)")
    welder = fields.Char(string="Soldador")
    result = fields.Selection([("accepted", "ACEPTADA"), ("rejected", "RECHAZADA")], string="Resultado")

    def action_apply(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Selecciona al menos una junta."))
        vals = {}
        if self.description:
            vals["description"] = self.description
        if self.dimension:
            vals["dimension"] = self.dimension
        if self.indication:
            vals["indication"] = self.indication
        if self.welder:
            vals["welder"] = self.welder
        if self.result:
            vals["result"] = self.result
        if not vals:
            raise UserError(_("Captura al menos un dato para copiar."))
        self.line_ids.write(vals)
        return {"type": "ir.actions.act_window_close"}
