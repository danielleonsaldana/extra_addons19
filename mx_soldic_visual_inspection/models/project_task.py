# -*- coding: utf-8 -*-
import base64

from odoo import api, fields, models
from odoo.tools import file_open

ROWS_PER_PAGE = 16  # mismas filas de resultados que el formato en Excel


class ProjectTask(models.Model):
    _inherit = "project.task"

    vt_enabled = fields.Boolean(related="project_id.vt_enabled", string="Usa Inspección Visual")

    # ---------------- Datos del informe ----------------
    vt_plan_number = fields.Char(
        string="No. de plano", tracking=True, copy=True,
        help="Número de plano del cliente (ej. ECM-T-25). Se captura manualmente.",
    )
    vt_is_repair = fields.Boolean(
        string="Reparación", tracking=True, copy=False,
        help="Marca el informe como reparación: agrega una 'R' al final del folio.",
    )
    vt_sequence_number = fields.Integer(
        string="Consecutivo", copy=False, readonly=True,
        help="Consecutivo del informe por número de plano dentro de la empresa.",
    )
    vt_report_number = fields.Char(
        string="Informe No.", tracking=True, copy=False,
        compute="_compute_vt_report_number", store=True, readonly=True,
    )
    vt_issue_date = fields.Date(string="Fecha de emisión", default=fields.Date.context_today, copy=False)

    # ---------------- Datos del cliente ----------------
    vt_partner_id = fields.Many2one(
        "res.partner", string="Cliente (VT)",
        compute="_compute_vt_partner_id", store=True, readonly=False,
    )
    vt_client_name = fields.Char(
        string="Nombre o Razón Social",
        compute="_compute_vt_client_data", store=True, readonly=False,
    )
    vt_client_address = fields.Char(
        string="Dirección",
        compute="_compute_vt_client_data", store=True, readonly=False,
    )
    vt_client_contact = fields.Char(string="Persona de contacto")
    vt_client_phone = fields.Char(
        string="Teléfono",
        compute="_compute_vt_client_data", store=True, readonly=False,
    )
    vt_work_location = fields.Text(string="Obra o ubicación de servicio")

    # ---------------- Datos de la pieza ----------------
    vt_piece_identification = fields.Char(string="Identificación")
    vt_piece_dimensions = fields.Char(
        string="Dimensiones (mm)",
        help="Si se deja vacío, el PDF muestra el total de longitud inspeccionada.",
    )
    vt_piece_mark = fields.Char(
        string="Marca",
        help="Si se deja vacío, el PDF muestra la identificación de la pieza.",
    )
    vt_material_type = fields.Char(string="Tipo de material")
    vt_surface_finish = fields.Char(string="Acabado superficial", default="LIMPIEZA MECANICA")
    vt_welding_process = fields.Char(string="Proceso de soldadura", default="FCAW")
    vt_joint_type = fields.Char(string="Tipo de junta AWS")

    # ---------------- Información de inspección ----------------
    vt_procedure = fields.Char(string="Procedimiento", default="VT-JT-01")
    vt_reference_standard = fields.Char(string="Norma de referencia", default="AWS D1.1 ED 2025")
    vt_inspection_stage = fields.Selection(
        [("initial", "INICIAL"), ("in_process", "EN PROCESO"), ("final", "FINAL")],
        string="Etapa de la inspección", default="final",
    )
    vt_acceptance_criteria = fields.Char(string="Criterio de aceptación", default="TABLA 8.1")
    vt_inspected_zone = fields.Float(string="Zona inspeccionada", default=1.0, help="1.0 = 100%")
    vt_lighting = fields.Char(string="Iluminación", default="1320 LX")

    # ---------------- Equipo de medición ----------------
    vt_equipment_serial = fields.Char(string="Serie del equipo")
    vt_equipment_model = fields.Char(string="Modelo del equipo")

    # ---------------- Resultados ----------------
    vt_results_title = fields.Char(
        string="Título de resultados",
        help="Encabezado de la tabla de resultados (ej. COLUMNA ECM-T-1 PIEZA 5). "
             "Si se deja vacío se usa la identificación de la pieza.",
    )
    vt_line_ids = fields.One2many("project.task.vt.line", "task_id", string="Resultados por junta", copy=True)
    vt_total_length = fields.Float(
        string="Total de longitud inspeccionada (mm)",
        compute="_compute_vt_total_length", store=True, digits=(16, 2),
    )
    vt_sketch_image = fields.Image(string="Croquis de ubicación", max_width=1920, max_height=1920)
    vt_observations = fields.Text(string="Observaciones", default="SIN OBSERVACIONES")

    # ---------------- Firmas ----------------
    vt_technician_name = fields.Char(string="Nombre del técnico")
    vt_technician_signature = fields.Binary(string="Firma del técnico", copy=False)
    vt_technician_date = fields.Date(string="Fecha (técnico)", copy=False)
    vt_signatory_name = fields.Char(string="Nombre del signatario")
    vt_signatory_signature = fields.Binary(string="Firma del signatario", copy=False)
    vt_signatory_date = fields.Date(string="Fecha (signatario)", copy=False)
    vt_customer_sign_name = fields.Char(
        string="Nombre (cliente)",
        compute="_compute_vt_client_data", store=True, readonly=False,
    )
    vt_customer_signature = fields.Binary(string="Firma del cliente", copy=False)
    vt_customer_date = fields.Date(string="Fecha (cliente)", copy=False)

    # ------------------------------------------------------------------
    @api.depends("partner_id", "project_id.partner_id")
    def _compute_vt_partner_id(self):
        for task in self:
            task.vt_partner_id = task.vt_partner_id or task.partner_id or task.project_id.partner_id

    @api.depends("vt_partner_id")
    def _compute_vt_client_data(self):
        for task in self:
            partner = task.vt_partner_id
            if not partner:
                task.vt_client_name = task.vt_client_name
                task.vt_customer_sign_name = task.vt_customer_sign_name
                task.vt_client_address = task.vt_client_address
                task.vt_client_phone = task.vt_client_phone
                continue
            commercial = partner.commercial_partner_id
            task.vt_client_name = commercial.name
            task.vt_customer_sign_name = commercial.name
            task.vt_client_address = ", ".join(
                p for p in [
                    commercial.street, commercial.street2,
                    commercial.zip and "C.P. %s" % commercial.zip,
                    commercial.city, commercial.state_id.name,
                ] if p
            )
            task.vt_client_phone = partner.phone or commercial.phone or False

    @api.depends("vt_plan_number", "vt_sequence_number", "vt_is_repair")
    def _compute_vt_report_number(self):
        for task in self:
            if not task.vt_plan_number or not task.vt_sequence_number:
                # sin plano no hay folio automático: se conserva lo que tuviera
                task.vt_report_number = task.vt_report_number
                continue
            company = task.company_id or self.env.company
            code = company._vt_get_company_code()
            parts = ["VT"] + ([code] if code else []) + ["%02d" % task.vt_sequence_number]
            task.vt_report_number = "%s-%s%s" % (
                "-".join(parts), task.vt_plan_number, "R" if task.vt_is_repair else "")

    # ---------------- Consecutivo por plano ----------------
    @api.model
    def _vt_normalize_plan(self, plan):
        return (plan or "").strip().upper() or False

    def _vt_assign_sequence(self):
        """Asigna el siguiente consecutivo para el número de plano en la empresa."""
        Task = self.sudo().with_context(active_test=False)
        for task in self:
            if not task.vt_plan_number:
                task.with_context(vt_skip_sequence=True).vt_sequence_number = 0
                continue
            others = Task.search([
                ("id", "!=", task.id),
                ("company_id", "=", task.company_id.id),
                ("vt_plan_number", "=", task.vt_plan_number),
                ("vt_sequence_number", ">", 0),
            ])
            last = max(others.mapped("vt_sequence_number") or [0])
            task.with_context(vt_skip_sequence=True).vt_sequence_number = last + 1

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("vt_plan_number"):
                vals["vt_plan_number"] = self._vt_normalize_plan(vals["vt_plan_number"])
        tasks = super().create(vals_list)
        tasks.filtered(lambda t: t.vt_plan_number and not t.vt_sequence_number)._vt_assign_sequence()
        return tasks

    def write(self, vals):
        if "vt_plan_number" in vals:
            vals["vt_plan_number"] = self._vt_normalize_plan(vals["vt_plan_number"])
        if self.env.context.get("vt_skip_sequence") or not ({"vt_plan_number", "company_id"} & set(vals)):
            return super().write(vals)
        old = {t.id: (t.vt_plan_number, t.company_id.id) for t in self}
        res = super().write(vals)
        changed = self.filtered(
            lambda t: (t.vt_plan_number, t.company_id.id) != old[t.id] or (t.vt_plan_number and not t.vt_sequence_number))
        changed._vt_assign_sequence()
        return res

    def _vt_base_name(self):
        """Nombre de la pieza sin folio ni sufijos de reparación previos."""
        self.ensure_one()
        name = self.name or ""
        if self.vt_report_number and name.startswith(self.vt_report_number):
            name = name[len(self.vt_report_number):].lstrip(" -·")
        while name.endswith("(Reparación)"):
            name = name[: -len("(Reparación)")].rstrip()
        return name.strip()

    def action_vt_create_repair(self):
        """Duplica la tarea como reparación: mismo plano, siguiente consecutivo y 'R' al final.
        El nombre de la nueva tarea lleva el folio para encontrarla fácilmente."""
        self.ensure_one()
        base = self._vt_base_name()
        repair = self.copy({"vt_is_repair": True})
        repair.name = "%s - %s" % (repair.vt_report_number, base) if base else repair.vt_report_number
        repair.vt_line_ids.write({"result": "accepted"})
        return {
            "type": "ir.actions.act_window",
            "res_model": "project.task",
            "res_id": repair.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.depends("vt_line_ids.dimension")
    def _compute_vt_total_length(self):
        for task in self:
            task.vt_total_length = sum(task.vt_line_ids.mapped("dimension"))

    # ------------------------------------------------------------------
    # Ayudantes para el reporte
    # ------------------------------------------------------------------
    def _vt_static_image(self, path):
        with file_open(path, "rb") as f:
            return base64.b64encode(f.read())

    def _vt_report_logo(self):
        company = self.company_id or self.env.company
        return company.vt_logo or self._vt_static_image("mx_soldic_visual_inspection/static/img/logo_company.jpg")

    def _vt_report_accreditation_logo(self):
        company = self.company_id or self.env.company
        return company.vt_accreditation_logo or self._vt_static_image(
            "mx_soldic_visual_inspection/static/img/logo_accreditation.png")

    def _vt_fmt_date(self, value):
        return value.strftime("%d/%m/%Y") if value else ""

    def _vt_fmt_number(self, value):
        return "{:,.2f}".format(value or 0.0)

    def _vt_report_pages(self):
        """Divide los resultados en páginas de ROWS_PER_PAGE filas (rellenando con filas
        vacías como el formato de Excel) y agrega la página de croquis si existe."""
        self.ensure_one()
        lines = list(self.vt_line_ids)
        pages = []
        chunks = [lines[i:i + ROWS_PER_PAGE] for i in range(0, len(lines), ROWS_PER_PAGE)] or [[]]
        for idx, chunk in enumerate(chunks):
            pages.append({
                "type": "results",
                "lines": chunk,
                "blank_rows": ROWS_PER_PAGE - len(chunk),
                "is_last_results": idx == len(chunks) - 1,
            })
        if self.vt_sketch_image:
            pages.append({"type": "sketch"})
        total = len(pages)
        for n, page in enumerate(pages, start=1):
            page["number"] = n
            page["total"] = total
        return pages

    def action_print_visual_inspection(self):
        return self.env.ref("mx_soldic_visual_inspection.action_report_visual_inspection").report_action(self)
