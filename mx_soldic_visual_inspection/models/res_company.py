# -*- coding: utf-8 -*-
from odoo import fields, models

DEFAULT_LEGEND = (
    "1. LOS RESULTADOS DE CONFORMIDAD O NO CONFORMIDAD SE EVALÚAN CON BASE EN EL MÉTODO Y EL "
    "CRITERIO DE ACEPTACIÓN ESTABLECIDOS EN LA COTIZACIÓN O ACUERDO CON EL CLIENTE; NO OBSTANTE, "
    "LA REGLA DE DECISIÓN APLICADA NO CONTEMPLA LA INCERTIDUMBRE DE LA MEDICIÓN, SINO ÚNICAMENTE "
    "LO ESPECIFICADO EN DICHO MÉTODO Y CRITERIO.\n"
    "2. DE SER REQUERIDO POR EL CLIENTE LA INFORMACIÓN PROPORCIONADA SERA IDENTIFICADA MEDIANTE LA "
    "SEÑALIZACIÓN CON COLOR DIFERENTE Y SE INDICA EN EL ÁREA DE OBSERVACIONES.\n"
    "3. ESTE INFORME NO DEBE REPRODUCIRSE PARCIAL O TOTALMENTE SIN AUTORIZACIÓN PREVIA DE J.T "
    "SERVICIOS, ESTE INFORME VALIDA UNICAMENTE LAS PIEZAS O PARTES INSPECCIONADAS."
)


class ResCompany(models.Model):
    _inherit = "res.company"

    vt_logo = fields.Image(
        string="Logo del informe",
        max_width=1024, max_height=1024,
        help="Logo de la esquina superior izquierda. Si se deja vacío se usa el logo J.T. Servicios incluido en el módulo.",
    )
    vt_accreditation_logo = fields.Image(
        string="Logo de acreditación",
        max_width=1024, max_height=1024,
        help="Logo de la esquina superior derecha (ej. EMA). Si se deja vacío se usa el incluido en el módulo.",
    )
    vt_report_title = fields.Char(
        string="Título del informe",
        default="INFORME FINAL DE ENSAYO\nINSPECCIÓN VISUAL",
    )
    vt_header_address = fields.Char(
        string="Dirección (encabezado)",
        default="Calle Lluvia #22, Col. Ampliación Banderas, Tuxpan Veracruz, C.P. 92773",
    )
    vt_header_contact = fields.Char(
        string="Contacto (encabezado)",
        default="JT_ASI_08@hotmail.com",
    )
    vt_format_revision = fields.Char(string="Emisión No.", default="04")
    vt_format_date = fields.Char(string="Fecha de emisión del formato", default="Mar-2026")
    vt_format_code = fields.Char(string="Codificación del formato", default="JT-VT-01-F01")
    vt_legend = fields.Text(string="Leyendas al pie", default=DEFAULT_LEGEND)
