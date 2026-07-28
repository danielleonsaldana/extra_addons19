# -*- coding: utf-8 -*-
import logging

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _norm_rfc(value):
    """Normaliza un RFC para comparar: mayúsculas, sin espacios ni guiones."""
    return (value or '').upper().replace(' ', '').replace('-', '').strip()


def _localname(el):
    """Nombre de etiqueta sin el namespace (CFDI 3.3 o 4.0 indistinto)."""
    tag = getattr(el, 'tag', '') or ''
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Solo validamos facturas donde el RECEPTOR del CFDI debe ser la empresa
    # que registra el documento (facturas y notas de crédito de proveedor).
    _MX_RECEPTOR_MOVE_TYPES = ('in_invoice', 'in_refund')

    def _extend_with_attachments(self, files_data, new=False):
        # Ejecuta la importación nativa y después valida el receptor. Si no
        # coincide, se lanza UserError y la transacción se revierte: la factura
        # NO queda registrada en la razón social equivocada.
        res = super()._extend_with_attachments(files_data, new=new)
        try:
            self._mx_jandea_check_cfdi_receptor(files_data)
        except UserError:
            raise
        except Exception:  # noqa: BLE001 - nunca romper la carga por un fallo del check
            _logger.exception('mx_jandea_cfdi_receptor: fallo al validar receptor CFDI.')
        return res

    def _mx_jandea_check_cfdi_receptor(self, files_data):
        for move in self:
            if move.move_type not in self._MX_RECEPTOR_MOVE_TYPES:
                continue
            company_rfc = _norm_rfc(move.company_id.vat)
            if not company_rfc:
                # Sin RFC configurado en la empresa no hay contra qué comparar.
                continue

            for file_data in (files_data or []):
                tree = file_data.get('xml_tree') if isinstance(file_data, dict) else None
                if tree is None:
                    continue
                if _localname(tree) != 'Comprobante':
                    continue  # No es un CFDI.

                receptor = None
                for el in tree.iter():
                    if _localname(el) == 'Receptor':
                        receptor = el
                        break
                if receptor is None:
                    continue

                rfc_xml = _norm_rfc(receptor.get('Rfc') or receptor.get('rfc'))
                if not rfc_xml:
                    continue

                if rfc_xml != company_rfc:
                    nombre_xml = (receptor.get('Nombre')
                                  or receptor.get('nombre') or '').strip()
                    raise UserError(_(
                        "El CFDI no corresponde a esta empresa.\n\n"
                        "Receptor del XML: %(nombre_xml)s (RFC %(rfc_xml)s)\n"
                        "Empresa actual: %(empresa)s (RFC %(rfc_empresa)s)\n\n"
                        "Estás cargando el comprobante en una razón social "
                        "distinta a la del receptor. Cámbiate a la empresa "
                        "correcta o verifica el archivo.",
                        nombre_xml=nombre_xml or 'N/D',
                        rfc_xml=rfc_xml,
                        empresa=move.company_id.name,
                        rfc_empresa=company_rfc,
                    ))
