# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _norm_rfc(value):
    """Normaliza un RFC para comparar: mayúsculas, sin espacios ni guiones."""
    return (value or '').upper().replace(' ', '').replace('-', '').strip()


def _localname(el):
    """Nombre de etiqueta sin namespace (CFDI 3.3 o 4.0 indistinto)."""
    tag = getattr(el, 'tag', '') or ''
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Solo aplica a documentos donde el RECEPTOR del CFDI debe ser la empresa
    # que registra el documento (facturas y notas de crédito de proveedor).
    _MX_RECEPTOR_MOVE_TYPES = ('in_invoice', 'in_refund')

    mx_cfdi_receptor_rfc = fields.Char(
        string='RFC receptor del CFDI', copy=False, readonly=True,
        help='RFC del nodo Receptor del XML que originó esta factura.',
    )
    mx_cfdi_receptor_nombre = fields.Char(
        string='Nombre receptor del CFDI', copy=False, readonly=True,
    )
    mx_cfdi_receptor_mismatch = fields.Boolean(
        string='Receptor CFDI no coincide', copy=False, readonly=True,
        help='El RFC del receptor del XML no coincide con el RFC de la empresa '
             'en la que se está registrando la factura.',
    )
    mx_cfdi_receptor_ok = fields.Boolean(
        string='Cargar de todos modos', copy=False,
        help='Marca esta casilla para registrar la factura aunque el receptor '
             'del CFDI no corresponda a esta empresa.',
    )

    # ------------------------------------------------------------------ #
    #  Detección al importar el XML (botón "Subir", arrastrar, correo...)
    # ------------------------------------------------------------------ #
    def _extend_with_attachments(self, files_data, new=False):
        res = super()._extend_with_attachments(files_data, new=new)
        try:
            self._mx_jandea_flag_cfdi_receptor(files_data)
        except Exception:  # noqa: BLE001 - nunca romper la carga por el chequeo
            _logger.exception('mx_jandea_cfdi_receptor: fallo al evaluar receptor.')
        return res

    def _mx_jandea_flag_cfdi_receptor(self, files_data):
        for move in self:
            if move.move_type not in self._MX_RECEPTOR_MOVE_TYPES:
                continue
            datos = self._mx_read_receptor(files_data)
            if not datos:
                continue
            rfc_xml, nombre_xml = datos
            company_rfc = _norm_rfc(move.company_id.vat)
            mismatch = bool(company_rfc) and rfc_xml != company_rfc
            move.write({
                'mx_cfdi_receptor_rfc': rfc_xml,
                'mx_cfdi_receptor_nombre': nombre_xml,
                'mx_cfdi_receptor_mismatch': mismatch,
            })

    @staticmethod
    def _mx_read_receptor(files_data):
        """Devuelve (rfc_normalizado, nombre) del primer CFDI en files_data."""
        for file_data in (files_data or []):
            tree = file_data.get('xml_tree') if isinstance(file_data, dict) else None
            if tree is None or _localname(tree) != 'Comprobante':
                continue
            for el in tree.iter():
                if _localname(el) == 'Receptor':
                    rfc = _norm_rfc(el.get('Rfc') or el.get('rfc'))
                    nombre = (el.get('Nombre') or el.get('nombre') or '').strip()
                    if rfc:
                        return rfc, nombre
        return None

    # ------------------------------------------------------------------ #
    #  Bloqueo al registrar si no se ha confirmado la carga
    # ------------------------------------------------------------------ #
    def _post(self, soft=True):
        for move in self:
            if (move.move_type in self._MX_RECEPTOR_MOVE_TYPES
                    and move.mx_cfdi_receptor_mismatch
                    and not move.mx_cfdi_receptor_ok):
                raise UserError(_(
                    "El receptor del CFDI no corresponde a esta empresa.\n\n"
                    "Receptor del XML: %(nombre)s (RFC %(rfc)s)\n"
                    "Empresa actual: %(empresa)s (RFC %(rfc_emp)s)\n\n"
                    "Si de verdad quieres registrar esta factura aquí, marca la "
                    "casilla \"Cargar de todos modos\" en la advertencia de "
                    "arriba. Si no, cancela o elimina la factura.",
                    nombre=move.mx_cfdi_receptor_nombre or 'N/D',
                    rfc=move.mx_cfdi_receptor_rfc or 'N/D',
                    empresa=move.company_id.name,
                    rfc_emp=_norm_rfc(move.company_id.vat) or 'N/D',
                ))
        return super()._post(soft=soft)
