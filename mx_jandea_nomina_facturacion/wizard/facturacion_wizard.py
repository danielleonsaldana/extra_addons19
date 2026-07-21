# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MxJandeaNominaFacturacionWizard(models.TransientModel):
    _name = 'mx.jandea.nomina.facturacion.wizard'
    _description = 'Generar facturación de nómina entre empresas'

    # ------------------------------------------------------------------ #
    #  Origen de la nómina
    # ------------------------------------------------------------------ #
    modo = fields.Selection(
        [('lote', 'Por lote de nómina'), ('mensual', 'Mensual (mes + empresa)')],
        string='Origen', required=True, default='lote',
    )
    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Lote de nómina',
        help='Lote de recibos que servirá de base.',
    )
    company_nomina_id = fields.Many2one(
        'res.company', string='Empresa de la nómina (cliente)', required=True,
        default=lambda self: self.env.company,
        help='Empresa que corrió la nómina. Será el CLIENTE/receptor de la factura.',
    )
    date_from = fields.Date('Desde')
    date_to = fields.Date('Hasta')

    # ------------------------------------------------------------------ #
    #  Emisor / cliente
    # ------------------------------------------------------------------ #
    company_emisor_id = fields.Many2one(
        'res.company', string='Empresa que factura (emisora)', required=True,
        help='Empresa que emitirá la orden de venta / factura. '
             'Se puede cambiar en cada generación.',
    )
    partner_id = fields.Many2one(
        'res.partner', string='Cliente',
        help='Por defecto el contacto de la empresa de la nómina. Editable.',
    )

    # ------------------------------------------------------------------ #
    #  Resultado del cálculo (solo lectura, informativo)
    # ------------------------------------------------------------------ #
    calculado = fields.Boolean('Calculado', default=False)
    num_empleados = fields.Integer('# Empleados (recibos)', readonly=True)
    base_gross = fields.Monetary('Percepciones (GROSS)', readonly=True)
    base_net = fields.Monetary('Neto (NET)', readonly=True)
    base_basic = fields.Monetary('Sueldo base (BASIC)', readonly=True)
    base_ded = fields.Monetary('Deducciones (DED)', readonly=True)
    currency_id = fields.Many2one(
        'res.currency', string='Moneda',
        compute='_compute_currency_id', store=False,
    )

    linea_ids = fields.One2many(
        'mx.jandea.nomina.facturacion.wizard.linea', 'wizard_id',
        string='Conceptos a facturar',
    )

    @api.depends('company_emisor_id', 'company_nomina_id')
    def _compute_currency_id(self):
        for w in self:
            company = w.company_emisor_id or w.company_nomina_id or self.env.company
            w.currency_id = company.currency_id

    # ------------------------------------------------------------------ #
    #  Onchanges de comodidad
    # ------------------------------------------------------------------ #
    @api.onchange('payslip_run_id')
    def _onchange_payslip_run_id(self):
        if self.payslip_run_id:
            self.company_nomina_id = self.payslip_run_id.company_id
            if self.payslip_run_id.date_start:
                self.date_from = self.payslip_run_id.date_start
                self.date_to = self.payslip_run_id.date_end
        self.calculado = False

    @api.onchange('company_nomina_id')
    def _onchange_company_nomina_id(self):
        if self.company_nomina_id and not self.partner_id:
            self.partner_id = self.company_nomina_id.partner_id
        self.calculado = False

    @api.onchange('modo', 'date_from', 'date_to', 'company_emisor_id')
    def _onchange_reset_calculo(self):
        self.calculado = False

    # ------------------------------------------------------------------ #
    #  Recolección de recibos y cálculo de bases
    # ------------------------------------------------------------------ #
    def _get_payslips(self):
        """Recibos base según el modo. Se usa sudo() para lecturas multiempresa."""
        self.ensure_one()
        Payslip = self.env['hr.payslip'].sudo()
        if self.modo == 'lote':
            if not self.payslip_run_id:
                raise UserError(_('Selecciona un lote de nómina.'))
            slips = self.payslip_run_id.sudo().slip_ids
        else:
            if not (self.date_from and self.date_to and self.company_nomina_id):
                raise UserError(_('Indica empresa de la nómina y el rango de fechas (Desde/Hasta).'))
            slips = Payslip.search([
                ('company_id', '=', self.company_nomina_id.id),
                ('date_from', '>=', self.date_from),
                ('date_to', '<=', self.date_to),
                ('state', 'not in', ('draft', 'cancel')),
            ])
        # Excluimos borradores/cancelados sin depender del nombre exacto del
        # estado "validado" (varía entre versiones de nómina).
        slips = slips.filtered(lambda s: s.state not in ('draft', 'cancel'))
        if not slips:
            raise UserError(_('No se encontraron recibos (validados/pagados) para el origen indicado.'))
        return slips

    @staticmethod
    def _bases_from_slips(slips):
        """Suma por categoría a partir de las líneas de los recibos."""
        lines = slips.sudo().mapped('line_ids')
        bases = {'GROSS': 0.0, 'NET': 0.0, 'BASIC': 0.0, 'DED': 0.0}
        for line in lines:
            code = line.category_id.code
            if code in bases:
                bases[code] += line.total
        # DED viene negativo en Odoo; lo devolvemos en positivo para la base
        bases['DED'] = abs(bases['DED'])
        return bases

    def _custom_base(self, slips, codes_str):
        codes = [c.strip() for c in (codes_str or '').split(',') if c.strip()]
        if not codes:
            return 0.0
        lines = slips.sudo().mapped('line_ids').filtered(lambda l: l.code in codes)
        return sum(lines.mapped('total'))

    def action_calcular(self):
        """Calcula bases y precarga las líneas desde los conceptos activos."""
        self.ensure_one()
        if not self.company_emisor_id:
            raise UserError(_('Selecciona la empresa que factura (emisora).'))
        slips = self._get_payslips()
        bases = self._bases_from_slips(slips)
        num = len(slips)

        self.num_empleados = num
        self.base_gross = bases['GROSS']
        self.base_net = bases['NET']
        self.base_basic = bases['BASIC']
        self.base_ded = bases['DED']

        conceptos = self.env['mx.jandea.nomina.concepto'].search([
            '|', ('company_id', '=', False),
            ('company_id', '=', self.company_emisor_id.id),
        ])
        if not conceptos:
            raise UserError(_(
                'No hay conceptos de facturación configurados. '
                'Ve a Nómina → Facturación → Conceptos de Facturación.'))

        lineas = [(5, 0, 0)]
        for c in conceptos:
            bases_concepto = dict(bases)
            if c.tipo_calculo == 'porcentaje' and c.base_nomina == 'CUSTOM':
                bases_concepto['__CUSTOM__'] = self._custom_base(slips, c.base_codes)
            importe = c._calcular_importe(bases_concepto, num)
            lineas.append((0, 0, {
                'concepto_id': c.id,
                'product_id': c.product_id.id,
                'name': c.descripcion or c.product_id.display_name,
                'cantidad': 1.0,
                'precio_unitario': importe,
            }))
        self.linea_ids = lineas
        self.calculado = True

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ------------------------------------------------------------------ #
    #  Generar la orden de venta en la empresa emisora
    # ------------------------------------------------------------------ #
    def action_generar_orden(self):
        self.ensure_one()
        if not self.calculado:
            raise UserError(_('Primero pulsa "Calcular / Previsualizar".'))
        if not self.linea_ids:
            raise UserError(_('No hay conceptos para facturar.'))

        partner = self.partner_id or self.company_nomina_id.partner_id
        if not partner:
            raise UserError(_('La empresa de la nómina no tiene un contacto para usar como cliente.'))

        emisor = self.company_emisor_id

        periodo = ''
        if self.modo == 'lote' and self.payslip_run_id:
            periodo = self.payslip_run_id.name
        elif self.date_from and self.date_to:
            periodo = _('%(desde)s a %(hasta)s', desde=self.date_from, hasta=self.date_to)

        order_lines = []
        for l in self.linea_ids:
            if not l.product_id:
                raise UserError(_('El concepto "%s" no tiene producto.', l.name or ''))
            order_lines.append((0, 0, {
                'product_id': l.product_id.id,
                'name': l.name or l.product_id.display_name,
                'product_uom_qty': l.cantidad or 1.0,
                'price_unit': l.precio_unitario,
            }))

        SaleOrder = self.env['sale.order'].with_company(emisor).with_context(
            mail_create_nosubscribe=True,
        )
        order = SaleOrder.create({
            'company_id': emisor.id,
            'partner_id': partner.id,
            'order_line': order_lines,
            'mx_jandea_nomina_origen': True,
            'mx_jandea_nomina_run_id': self.payslip_run_id.id if self.modo == 'lote' else False,
            'mx_jandea_nomina_company_id': self.company_nomina_id.id,
            'mx_jandea_nomina_periodo': periodo,
            'mx_jandea_nomina_num_empleados': self.num_empleados,
        })

        # Forzamos el precio calculado (evita que la lista de precios lo recalcule).
        for wline, oline in zip(self.linea_ids, order.order_line):
            oline.with_company(emisor).price_unit = wline.precio_unitario

        return {
            'type': 'ir.actions.act_window',
            'name': _('Orden de Venta generada'),
            'res_model': 'sale.order',
            'res_id': order.id,
            'view_mode': 'form',
            'target': 'current',
        }


class MxJandeaNominaFacturacionWizardLinea(models.TransientModel):
    _name = 'mx.jandea.nomina.facturacion.wizard.linea'
    _description = 'Línea de conceptos a facturar (asistente)'
    _order = 'id'

    wizard_id = fields.Many2one(
        'mx.jandea.nomina.facturacion.wizard', required=True, ondelete='cascade',
    )
    concepto_id = fields.Many2one('mx.jandea.nomina.concepto', string='Concepto')
    product_id = fields.Many2one(
        'product.product', string='Producto', required=True,
        domain="[('sale_ok', '=', True)]",
    )
    name = fields.Char('Descripción', required=True)
    cantidad = fields.Float('Cantidad', default=1.0)
    precio_unitario = fields.Monetary('Precio unitario')
    subtotal = fields.Monetary('Subtotal', compute='_compute_subtotal')
    currency_id = fields.Many2one(related='wizard_id.currency_id')

    @api.depends('cantidad', 'precio_unitario')
    def _compute_subtotal(self):
        for l in self:
            l.subtotal = (l.cantidad or 0.0) * (l.precio_unitario or 0.0)
