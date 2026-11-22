# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    vt_enabled = fields.Boolean(
        string="Inspección Visual",
        default=True,
        help="Muestra la pestaña 'Inspección Visual' en las tareas de este proyecto.",
    )
