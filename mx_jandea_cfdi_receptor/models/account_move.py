# -*- coding: utf-8 -*-
import logging
import unicodedata

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from lxml import etree
except Exception:  # pragma: no cover
    etree = None


def _norm_rfc(value):
    """RFC comparable: mayúsculas, sin espacios ni guiones."""
    return (value or '').upper().replace(' ', '').replace('-', '').strip()


def _norm_name(value):
    """Razón social comparable: mayúsculas, sin acentos, sin puntuación ni
    sufijos societarios comunes (SA DE CV, S DE RL, etc.)."""
    if not value:
        return ''
    s = unicodedata.normalize('NFKD', str(value))
    s = ''.join(c for c in s if not unicodedata.combining(c)).upper()
    for junk in ('.', ',', ';', '"', "'", '/'):
        s = s.replace(junk, '')
    for suf in (' SAPI DE CV', ' S DE RL DE CV', ' SA DE CV', ' SADECV',
                ' S DE RL', ' SRL', ' SAS', ' SA', ' SC'):
        s = s.replace(suf, '')
    return ' '.join(s.split())


def _localname(el):
    tag = getattr(el, 'tag', '') or ''
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _find_local(root, name):
    try:
        for el in root.iter():
            if _localname(el) == name:
                return el
    except Exception:
        pass
    return None


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Documentos donde el RECEPTOR del CFDI debe ser la empresa que lo registra.
    _MX_RECEPTOR_MOVE_TYPES = ('in_invoice', 'in_refund')

    mx_cfdi_receptor_rfc = fields.Char(
        'RFC receptor del CFDI', copy=False, readonly=True)
    mx_cfdi_receptor_nombre = fields.Char(
        'Nombre receptor del CFDI', copy=False, readonly=True)
    mx_cfdi_folio_fiscal = fields.Char(
        'Folio fiscal (UUID) del CFDI', copy=False, readonly=True)
    mx_cfdi_receptor_mismatch = fields.Boolean(
        'Receptor CFDI no coincide', copy=False, readonly=True)
    mx_cfdi_folio_duplicado = fields.Boolean(
        'Folio fiscal duplicado', copy=False, readonly=True)
    mx_cfdi_receptor_ok = fields.Boolean(
        'Cargar de todos modos', copy=False,
        help='Marca para registrar la factura aunque el receptor no coincida '
             'o el folio fiscal esté duplicado.')

    # ------------------------------------------------------------------ #
    #  Al importar el XML (botón "Subir", arrastrar, correo...)
    # ------------------------------------------------------------------ #
    def _extend_with_attachments(self, files_data, new=False):
        res = super()._extend_with_attachments(files_data, new=new)
        try:
            self._mx_jandea_flag_cfdi(files_data)
        except Exception:  # noqa: BLE001 - nunca romper la carga por el chequeo
            _logger.exception('mx_jandea_cfdi_receptor: fallo al evaluar CFDI.')
        return res

    def _mx_jandea_flag_cfdi(self, files_data):
        for move in self:
            if move.move_type not in self._MX_RECEPTOR_MOVE_TYPES:
                continue
            datos = self._mx_read_cfdi(files_data)
            if not datos:
                _logger.info('mx_jandea_cfdi_receptor: no se encontró CFDI en '
                             'los adjuntos de la factura %s.', move.id)
                continue
            rfc_xml, nombre_xml, uuid_xml = datos

            company_rfc = _norm_rfc(move.company_id.vat)
            company_name = move.company_id.name

            # Receptor: RFC manda; si no hay RFC comparable, se usa el nombre.
            rfc_mismatch = bool(company_rfc and rfc_xml) and rfc_xml != company_rfc
            if company_rfc and rfc_xml and rfc_xml == company_rfc:
                name_mismatch = False  # RFC coincide: es la empresa correcta.
            else:
                name_mismatch = bool(nombre_xml and company_name) and \
                    _norm_name(nombre_xml) != _norm_name(company_name)
            mismatch = bool(rfc_mismatch or name_mismatch)

            duplicado = bool(uuid_xml) and move._mx_folio_duplicado(uuid_xml)

            move.write({
                'mx_cfdi_receptor_rfc': rfc_xml,
                'mx_cfdi_receptor_nombre': nombre_xml,
                'mx_cfdi_folio_fiscal': uuid_xml,
                'mx_cfdi_receptor_mismatch': mismatch,
                'mx_cfdi_folio_duplicado': duplicado,
            })
            _logger.info(
                'mx_jandea_cfdi_receptor: factura %s | receptor=%s (%s) uuid=%s '
                '| empresa=%s (%s) | no_coincide=%s duplicado=%s',
                move.id, nombre_xml, rfc_xml, uuid_xml, company_name,
                company_rfc, mismatch, duplicado)

    def _mx_folio_duplicado(self, uuid_xml):
        self.ensure_one()
        uuid_xml = (uuid_xml or '').strip().upper()
        if not uuid_xml:
            return False
        base = [
            ('id', '!=', self.id),
            ('company_id', '=', self.company_id.id),
            ('move_type', 'in', self._MX_RECEPTOR_MOVE_TYPES),
            ('state', '!=', 'cancel'),
        ]
        campos = ['mx_cfdi_folio_fiscal']
        if 'l10n_mx_edi_cfdi_uuid' in self._fields:
            campos.append('l10n_mx_edi_cfdi_uuid')
        for campo in campos:
            if self.sudo().search_count([(campo, '=ilike', uuid_xml)] + base):
                return True
        return False

    def _mx_read_cfdi(self, files_data):
        """(rfc, nombre, uuid) del primer CFDI en files_data. Usa xml_tree si
        está disponible; si no, parsea los bytes del adjunto."""
        for file_data in (files_data or []):
            if not isinstance(file_data, dict):
                continue
            tree = file_data.get('xml_tree')
            if tree is None:
                tree = self._mx_parse_attachment(file_data.get('attachment'))
            if tree is None or _localname(tree) != 'Comprobante':
                continue
            receptor = _find_local(tree, 'Receptor')
            if receptor is None:
                continue
            rfc = _norm_rfc(receptor.get('Rfc') or receptor.get('rfc'))
            nombre = (receptor.get('Nombre') or receptor.get('nombre') or '').strip()
            uuid = ''
            tfd = _find_local(tree, 'TimbreFiscalDigital')
            if tfd is not None:
                uuid = (tfd.get('UUID') or tfd.get('uuid') or '').strip().upper()
            if rfc or nombre:
                return rfc, nombre, uuid
        return None

    @staticmethod
    def _mx_parse_attachment(attachment):
        if etree is None or not attachment:
            return None
        raw = None
        for attr in ('raw', 'datas'):
            try:
                raw = getattr(attachment, attr, None)
            except Exception:
                raw = None
            if raw:
                break
        if not raw:
            return None
        try:
            if isinstance(raw, str):
                raw = raw.encode()
            return etree.fromstring(raw)
        except Exception:
            try:
                import base64
                return etree.fromstring(base64.b64decode(raw))
            except Exception:
                return None

    # ------------------------------------------------------------------ #
    #  Bloqueo al registrar si no se confirmó la carga
    # ------------------------------------------------------------------ #
    def _post(self, soft=True):
        for move in self:
            if move.move_type not in self._MX_RECEPTOR_MOVE_TYPES:
                continue
            if move.mx_cfdi_receptor_ok:
                continue
            problemas = []
            if move.mx_cfdi_receptor_mismatch:
                problemas.append(_(
                    "El receptor del CFDI (%(n)s, RFC %(r)s) no corresponde a "
                    "esta empresa (%(e)s, RFC %(er)s).",
                    n=move.mx_cfdi_receptor_nombre or 'N/D',
                    r=move.mx_cfdi_receptor_rfc or 'N/D',
                    e=move.company_id.name,
                    er=_norm_rfc(move.company_id.vat) or 'N/D'))
            if move.mx_cfdi_folio_duplicado:
                problemas.append(_(
                    "El folio fiscal (UUID %(u)s) ya está registrado en otra "
                    "factura de esta empresa.",
                    u=move.mx_cfdi_folio_fiscal or 'N/D'))
            if problemas:
                raise UserError('\n\n'.join(problemas) + '\n\n' + _(
                    "Si aun así quieres registrarla, marca \"Cargar de todos "
                    "modos\" en la advertencia. Si no, cancela o elimina la "
                    "factura."))
        return super()._post(soft=soft)
