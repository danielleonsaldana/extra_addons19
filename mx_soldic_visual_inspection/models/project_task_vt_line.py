# -*- coding: utf-8 -*-
from odoo import fields, models


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
