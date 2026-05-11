# -*- coding: utf-8 -*-
import base64
import io
import logging
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BankAccountExportWizard(models.TransientModel):
    _name = 'mx.bank.account.export.wizard'
    _description = 'Descarga Masiva TXT de Cuentas Bancarias (Inbursa / Otros Bancos)'

    # ── Opciones ─────────────────────────────────
    bank_type = fields.Selection([
        ('inbursa', 'Inbursa'),
        ('otros', 'Otros Bancos'),
    ], string='Formato banco', required=True, default='inbursa')

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )

    # Filtros
    partner_ids = fields.Many2many(
        'res.partner',
        string='Filtrar por contactos',
        help='Si no seleccionas ninguno, se exportan todas las cuentas de la compañía.',
    )
    bank_id = fields.Many2one(
        'res.bank',
        string='Filtrar por banco',
        help='Opcional: filtra sólo cuentas de este banco.',
    )
    only_active = fields.Boolean(string='Solo cuentas activas', default=True)
    uso_cuenta = fields.Selection([
        ('N', 'Nómina'),
        ('P', 'Proveedores'),
        ('H', 'Honorarios'),
        ('A', 'Arrendamiento'),
        ('O', 'Otros'),
    ], string='Uso de cuenta (Inbursa)', default='P',
        help='Campo requerido por el layout Inbursa.')

    # ── Resultado ────────────────────────────────
    state = fields.Selection([
        ('draft', 'Pendiente'),
        ('done', 'Generado'),
    ], default='draft')
    result_file = fields.Binary(string='Archivo TXT', readonly=True, attachment=False)
    result_filename = fields.Char(string='Nombre archivo', readonly=True)
    records_exported = fields.Integer(string='Registros exportados', readonly=True)

    # ── Generar TXT ──────────────────────────────
    def action_generate_txt(self):
        self.ensure_one()

        domain = self._build_domain()
        bank_accounts = self.env['res.partner.bank'].search(domain)

        if not bank_accounts:
            raise UserError(_('No se encontraron cuentas bancarias con los filtros seleccionados.'))

        if self.bank_type == 'inbursa':
            content = self._generate_inbursa(bank_accounts)
            suffix = 'inbursa'
        else:
            content = self._generate_otros(bank_accounts)
            suffix = 'otros_bancos'

        filename = f'alta_cuentas_{suffix}_{date.today().strftime("%Y%m%d")}.txt'
        file_data = base64.b64encode(content.encode('latin-1', errors='replace'))

        self.write({
            'state': 'done',
            'result_file': file_data,
            'result_filename': filename,
            'records_exported': len(bank_accounts),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_download(self):
        """Descarga directa del archivo generado."""
        self.ensure_one()
        if not self.result_file:
            raise UserError(_('Primero genera el archivo TXT.'))

        attachment = self.env['ir.attachment'].create({
            'name': self.result_filename,
            'datas': self.result_file,
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'mimetype': 'text/plain',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    # ── Domain ───────────────────────────────────
    def _build_domain(self):
        domain = [('company_id', '=', self.company_id.id)]
        if self.only_active:
            domain += [('active', '=', True)]
        if self.partner_ids:
            domain += [('partner_id', 'in', self.partner_ids.ids)]
        if self.bank_id:
            domain += [('bank_id', '=', self.bank_id.id)]
        return domain

    # ── Generadores de formato ────────────────────

    def _generate_inbursa(self, bank_accounts):
        """
        Layout Inbursa:
        Col C: No. Cuenta | No. Tarjeta | CLABE (11, 16 o 18 posiciones)
        Col D: Uso de cuenta (hasta 35 posiciones)
        Separado por pipe |
        """
        lines = []
        uso = self.uso_cuenta or 'P'

        for ba in bank_accounts:
            acc_number = (ba.acc_number or '').strip().replace(' ', '')
            if not acc_number:
                continue
            # Validar longitud según tipo
            lon = len(acc_number)
            if lon not in (11, 16, 18):
                _logger.warning(
                    'Cuenta %s (partner: %s) tiene %s dígitos — se incluye de todas formas.',
                    acc_number, ba.partner_id.name, lon,
                )
            uso_label = dict(self._fields['uso_cuenta'].selection).get(uso, 'PROVEEDORES')
            line = f'{acc_number}|{uso_label[:35]}'
            lines.append(line)

        return '\n'.join(lines)

    def _generate_otros(self, bank_accounts):
        """
        Layout Otros Bancos:
        Col B: Celular/Tarjeta/CLABE (10/16/18 posiciones)
        Col C: Nombre beneficiario (hasta 35 pos)
        Col D: RFC (hasta 13 pos)
        Col E: Banco (hasta 20 pos)
        Separado por pipe |
        """
        lines = []

        for ba in bank_accounts:
            acc_number = (ba.acc_number or '').strip().replace(' ', '')
            if not acc_number:
                continue

            partner = ba.partner_id
            nombre = (partner.name or '')[:35]
            rfc = (partner.vat or '')[:13]
            banco = ''
            if ba.bank_id:
                banco = (ba.bank_id.name or ba.bank_id.bic or '')[:20]
            elif ba.bank_name:
                banco = ba.bank_name[:20]

            line = f'{acc_number}|{nombre}|{rfc}|{banco}'
            lines.append(line)

        return '\n'.join(lines)
