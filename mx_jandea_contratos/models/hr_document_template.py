# -*- coding: utf-8 -*-
import base64
import io

from odoo import api, fields, models
from odoo.exceptions import UserError


class HrDocumentTemplate(models.Model):
    _name = 'hr.document.template'
    _description = 'Plantilla de documento (Contrato / Alta / Baja)'
    _order = 'doc_type, sequence, name'

    name = fields.Char('Nombre', required=True)
    sequence = fields.Integer('Secuencia', default=10)
    active = fields.Boolean(default=True)

    doc_type = fields.Selection([
        ('contrato', 'Contrato Individual de Trabajo'),
        ('alta', 'Formato de Alta'),
        ('baja', 'Formato de Baja'),
    ], string='Tipo de documento', required=True)

    gender = fields.Selection([
        ('hombre', 'Hombre'),
        ('mujer', 'Mujer'),
        ('unisex', 'Unisex / No aplica'),
    ], string='Género de la plantilla', default='unisex', required=True)

    empresa_referencia = fields.Char(
        'Empresa / Cliente',
        help='Identifica a qué razón social o cliente de maquila pertenece '
             '(ej. Burdina, Krino, Crystal, o el nombre del cliente que '
             'proporciona su propio formato).',
    )

    file = fields.Binary('Archivo .docx (con placeholders {{ }})', required=True, attachment=True)
    filename = fields.Char('Nombre de archivo')

    note = fields.Text('Notas / placeholders disponibles')

    def _render(self, render_context):
        """Renderiza la plantilla docx con docxtpl y devuelve los bytes resultantes."""
        self.ensure_one()
        try:
            from docxtpl import DocxTemplate
        except ImportError:
            raise UserError(self.env._(
                "Falta instalar la librería Python 'docxtpl' en el servidor "
                "(pip install docxtpl --break-system-packages)."
            ))

        if not self.file:
            raise UserError(self.env._("La plantilla %s no tiene archivo cargado.", self.name))

        buffer_in = io.BytesIO(base64.b64decode(self.file))
        doc = DocxTemplate(buffer_in)
        try:
            doc.render(render_context)
        except Exception as e:
            raise UserError(self.env._(
                "Error al renderizar la plantilla '%(name)s'. Verifica que los "
                "placeholders {{ }} usados en el .docx coincidan con los campos "
                "del formulario.\n\nDetalle: %(error)s",
                name=self.name, error=str(e),
            ))

        buffer_out = io.BytesIO()
        doc.save(buffer_out)
        return buffer_out.getvalue()
