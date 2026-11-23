# -*- coding: utf-8 -*-
import base64
import uuid

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import file_open

ROWS_PER_PAGE = 16  # mismas filas de resultados que el formato en Excel
IMAGES_PER_SKETCH_PAGE = 2
# Campos binarios que no admite el tracking estándar: se registran a mano en el chatter
VT_BINARY_LOG = {
    "vt_sketch_image": "Croquis de ubicación",
    "vt_technician_signature": "Firma del técnico",
    "vt_signatory_signature": "Firma del signatario",
    "vt_customer_signature": "Firma del cliente",
}


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
    vt_issue_date = fields.Date(string="Fecha de emisión", default=fields.Date.context_today, copy=False, tracking=True)

    # ---------------- Datos del cliente ----------------
    vt_partner_id = fields.Many2one(
        "res.partner", string="Cliente (VT)",
        compute="_compute_vt_partner_id", store=True, readonly=False,
        tracking=True,
    )
    vt_client_name = fields.Char(
        string="Nombre o Razón Social",
        compute="_compute_vt_client_data", store=True, readonly=False,
        tracking=True,
    )
    vt_client_address = fields.Char(
        string="Dirección",
        compute="_compute_vt_client_data", store=True, readonly=False,
        tracking=True,
    )
    vt_client_contact = fields.Char(string="Persona de contacto", tracking=True)
    vt_client_phone = fields.Char(
        string="Teléfono",
        compute="_compute_vt_client_data", store=True, readonly=False,
        tracking=True,
    )
    vt_work_location = fields.Text(string="Obra o ubicación de servicio", tracking=True)

    # ---------------- Datos de la pieza ----------------
    vt_piece_identification = fields.Char(string="Identificación", tracking=True)
    vt_piece_dimensions = fields.Char(
        string="Dimensiones (mm)",
        help="Si se deja vacío, el PDF muestra el total de longitud inspeccionada.",
        tracking=True,
    )
    vt_piece_mark = fields.Char(
        string="Marca",
        help="Si se deja vacío, el PDF muestra la identificación de la pieza.",
        tracking=True,
    )
    vt_material_type = fields.Char(string="Tipo de material", tracking=True)
    vt_surface_finish = fields.Char(string="Acabado superficial", default="LIMPIEZA MECANICA", tracking=True)
    vt_welding_process = fields.Char(string="Proceso de soldadura", default="FCAW", tracking=True)
    vt_joint_type = fields.Char(string="Tipo de junta AWS", tracking=True)

    # ---------------- Información de inspección ----------------
    vt_procedure = fields.Char(string="Procedimiento", default="VT-JT-01", tracking=True)
    vt_reference_standard = fields.Char(string="Norma de referencia", default="AWS D1.1 ED 2025", tracking=True)
    vt_inspection_stage = fields.Selection(
        [("initial", "INICIAL"), ("in_process", "EN PROCESO"), ("final", "FINAL")],
        string="Etapa de la inspección", default="final",
        tracking=True,
    )
    vt_acceptance_criteria = fields.Char(string="Criterio de aceptación", default="TABLA 8.1", tracking=True)
    vt_inspected_zone = fields.Float(string="Zona inspeccionada", default=1.0, help="1.0 = 100%", tracking=True)
    vt_lighting = fields.Char(string="Iluminación", default="1320 LX", tracking=True)

    # ---------------- Equipo de medición ----------------
    vt_equipment_serial = fields.Char(string="Serie del equipo", tracking=True)
    vt_equipment_model = fields.Char(string="Modelo del equipo", tracking=True)

    # ---------------- Resultados ----------------
    vt_results_title = fields.Char(
        string="Título de resultados",
        help="Encabezado de la tabla de resultados (ej. COLUMNA ECM-T-1 PIEZA 5). "
             "Si se deja vacío se usa la identificación de la pieza.",
        tracking=True,
    )
    vt_line_ids = fields.One2many("project.task.vt.line", "task_id", string="Resultados por junta", copy=True)
    vt_image_ids = fields.One2many("project.task.vt.image", "task_id", string="Planos", copy=True)
    vt_joint_count = fields.Integer(string="No. de juntas", compute="_compute_vt_joint_count")
    vt_rejected_count = fields.Integer(string="Rechazadas", compute="_compute_vt_joint_count")
    vt_total_length = fields.Float(
        string="Total de longitud inspeccionada (mm)",
        compute="_compute_vt_total_length", store=True, digits=(16, 2),
    )
    vt_sketch_image = fields.Image(string="Croquis de ubicación", max_width=1920, max_height=1920)
    vt_observations = fields.Text(string="Observaciones", default="SIN OBSERVACIONES", tracking=True)

    # ---------------- Firmas ----------------
    vt_technician_name = fields.Char(string="Nombre del técnico", tracking=True)
    vt_technician_signature = fields.Binary(string="Firma del técnico", copy=False)
    vt_technician_date = fields.Date(string="Fecha (técnico)", copy=False, tracking=True)
    vt_signatory_name = fields.Char(string="Nombre del signatario", tracking=True)
    vt_signatory_signature = fields.Binary(string="Firma del signatario", copy=False)
    vt_signatory_date = fields.Date(string="Fecha (signatario)", copy=False, tracking=True)
    vt_customer_sign_name = fields.Char(
        string="Nombre (cliente)",
        compute="_compute_vt_client_data", store=True, readonly=False,
        tracking=True,
    )
    vt_customer_signature = fields.Binary(string="Firma del cliente", copy=False)
    vt_customer_date = fields.Date(string="Fecha (cliente)", copy=False, tracking=True)

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
        binary_changed = [f for f in VT_BINARY_LOG if f in vals]
        if binary_changed and not self.env.context.get("vt_no_log"):
            res = self.with_context(vt_no_log=True).write(vals)
            for task in self:
                items = Markup("").join(
                    Markup("<li>%s: %s</li>") % (VT_BINARY_LOG[f], "actualizada" if vals[f] else "eliminada")
                    for f in binary_changed)
                task.message_post(body=Markup("Inspección Visual:<ul>%s</ul>") % items)
            return res
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

    def copy(self, default=None):
        new_tasks = super().copy(default)
        for old, new in zip(self, new_tasks):
            # Conserva marcas y la relación junta ↔ plano en la copia (ej. reparaciones)
            for old_img, new_img in zip(old.vt_image_ids, new.vt_image_ids):
                new_img.with_context(vt_no_log=True).write({
                    "markers": old_img.markers or [],
                    "annotated_image": old_img.annotated_image,
                })
                for old_line, new_line in zip(old.vt_line_ids, new.vt_line_ids):
                    if old_line.image_id == old_img:
                        new_line.with_context(vt_no_log=True).write({
                            "image_id": new_img.id, "marker_uid": old_line.marker_uid})
        return new_tasks

    # ------------------------------------------------------------------
    # Marcador de juntas en plano (cliente OWL)
    # ------------------------------------------------------------------
    def action_vt_open_marker(self):
        self.ensure_one()
        if not self.vt_image_ids:
            raise UserError(_("Primero agrega al menos un plano (foto o imagen) en la sección 'Planos'."))
        return {
            "type": "ir.actions.client",
            "tag": "mx_soldic_vt_joint_marker",
            "name": _("Marcar juntas · %s", self.vt_report_number or self.name),
            "params": {"task_id": self.id},
            "context": {"active_id": self.id, "active_model": "project.task"},
        }

    def vt_get_marker_data(self):
        self.ensure_one()
        return {
            "task_id": self.id,
            "title": self.vt_report_number or self.name,
            "piece": self.vt_piece_identification or self.name,
            "images": [{
                "id": img.id,
                "name": img.name,
                "markers": img.markers or [],
                "url": "/web/image/project.task.vt.image/%s/image?unique=%s" % (
                    img.id, int(img.write_date.timestamp()) if img.write_date else 0),
            } for img in self.vt_image_ids],
        }

    @api.model
    def _vt_clean_marker(self, m):
        def num(v):
            return min(max(float(v or 0.0), -0.5), 1.5)
        return {"uid": str(m.get("uid") or uuid.uuid4().hex), "x": num(m.get("x")), "y": num(m.get("y")),
                "lx": num(m.get("lx")), "ly": num(m.get("ly"))}

    def vt_save_markers(self, payload):
        """Guarda las marcas de todas las vistas, regenera la imagen anotada y sincroniza la tabla:
        una junta por marca (J1..Jn continuo entre vistas). Las juntas conservan sus datos aunque
        cambie su número."""
        self.ensure_one()
        Line = self.env["project.task.vt.line"].with_context(vt_no_log=True)
        data = {int(p["id"]): p for p in payload or []}
        existing = {l.marker_uid: l for l in self.vt_line_ids if l.marker_uid}
        seen, to_create, added, renamed, per_view = set(), [], [], [], []
        n = 0
        for img in self.vt_image_ids:
            p = data.get(img.id)
            markers = [self._vt_clean_marker(m) for m in ((p or {}).get("markers") if p else img.markers) or []]
            for m in markers:
                n += 1
                label = "J%d" % n
                seen.add(m["uid"])
                line = existing.get(m["uid"])
                if line:
                    vals = {}
                    if line.joint != label:
                        renamed.append("%s→%s" % (line.joint, label))
                        vals["joint"] = label
                    if line.sequence != n:
                        vals["sequence"] = n
                    if line.image_id != img:
                        vals["image_id"] = img.id
                    if vals:
                        line.with_context(vt_no_log=True).write(vals)
                else:
                    added.append(label)
                    to_create.append({"task_id": self.id, "joint": label, "sequence": n, "image_id": img.id,
                                      "marker_uid": m["uid"], "indication": "-----", "result": "accepted"})
            per_view.append("%s: %s" % (img.name, len(markers)))
            if p is not None:
                annotated = p.get("annotated") or False
                if annotated and "," in annotated:
                    annotated = annotated.split(",", 1)[1]
                img.with_context(vt_no_log=True).write({"markers": markers, "annotated_image": annotated})
        removed = self.vt_line_ids.filtered(lambda l: l.marker_uid and l.marker_uid not in seen)
        removed_names = removed.mapped("joint")
        removed.with_context(vt_no_log=True).unlink()
        Line.create(to_create)
        # Juntas capturadas a mano: continúan la numeración después de las del plano
        for i, line in enumerate(self.vt_line_ids.filtered(lambda l: not l.marker_uid), start=1):
            vals = {"sequence": n + i}
            label = "J%d" % (n + i)
            if line.joint != label and (line.joint or "").upper().startswith("J"):
                renamed.append("%s→%s" % (line.joint, label))
                vals["joint"] = label
            line.with_context(vt_no_log=True).write(vals)

        items = [Markup("<li>Total de juntas marcadas: <b>%s</b> (%s)</li>") % (n, "; ".join(per_view))]
        if added:
            items.append(Markup("<li>Agregadas: %s</li>") % ", ".join(added))
        if removed_names:
            items.append(Markup("<li>Eliminadas: %s</li>") % ", ".join(removed_names))
        if renamed:
            items.append(Markup("<li>Renumeradas: %s</li>") % ", ".join(renamed))
        attachments = [("%s.jpg" % img.name, base64.b64decode(img.annotated_image))
                       for img in self.vt_image_ids if img.annotated_image and img.id in data]
        self.message_post(body=Markup("Juntas marcadas en plano:<ul>%s</ul>") % Markup("").join(items),
                          attachments=attachments)
        return {"joint_count": n}

    # ---------------- Asistentes ----------------
    def action_vt_generate_joints(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Generar juntas"),
            "res_model": "vt.generate.joints",
            "view_mode": "form",
            "target": "new",
            "context": {"default_task_id": self.id},
        }

    def action_vt_fill_joints(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Llenar varias juntas"),
            "res_model": "vt.fill.joints",
            "view_mode": "form",
            "target": "new",
            "context": {"default_task_id": self.id},
        }

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

    @api.depends("vt_line_ids.result")
    def _compute_vt_joint_count(self):
        for task in self:
            task.vt_joint_count = len(task.vt_line_ids)
            task.vt_rejected_count = len(task.vt_line_ids.filtered(lambda l: l.result == "rejected"))

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
        sketches = [{"name": img.name, "data": img._vt_report_image()} for img in self.vt_image_ids]
        if self.vt_sketch_image:
            sketches.append({"name": "", "data": self.vt_sketch_image})
        for i in range(0, len(sketches), IMAGES_PER_SKETCH_PAGE):
            pages.append({"type": "sketch", "images": sketches[i:i + IMAGES_PER_SKETCH_PAGE]})
        total = len(pages)
        for n, page in enumerate(pages, start=1):
            page["number"] = n
            page["total"] = total
        return pages

    def action_print_visual_inspection(self):
        return self.env.ref("mx_soldic_visual_inspection.action_report_visual_inspection").report_action(self)
