# -*- coding: utf-8 -*-
from math import ceil
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MxJandeaPrestamo(models.Model):
    _name = 'mx.jandea.prestamo'
    _description = 'Préstamo a empleado'
    _inherit = ['mail.thread']
    _order = 'fecha_inicio desc, id desc'
    _rec_name = 'name'
    _check_company_auto = True

    name = fields.Char('Referencia', compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company,
    )
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', required=True, tracking=True,
        check_company=True, domain="[('company_id', '=', company_id)]",
    )
    currency_id = fields.Many2one(related='company_id.currency_id')

    monto_total = fields.Monetary('Monto total', required=True, tracking=True)
    periodicidad = fields.Selection(
        [('semanal', 'Semanal'), ('quincenal', 'Quincenal'), ('mensual', 'Mensual')],
        string='Periodicidad', required=True, default='quincenal',
    )
    monto_periodo = fields.Monetary('Monto por período', required=True, tracking=True)
    fecha_inicio = fields.Date('Inicio', required=True, default=fields.Date.context_today)

    attachment_id = fields.Many2one(
        'hr.salary.attachment', string='Ajuste salarial', readonly=True, copy=False,
        check_company=True,
    )
    state = fields.Selection(
        [('borrador', 'Borrador'), ('confirmado', 'Confirmado'), ('cerrado', 'Cerrado')],
        string='Estado', default='borrador', required=True, copy=False, tracking=True,
    )

    linea_ids = fields.One2many(
        'mx.jandea.prestamo.linea', 'prestamo_id', string='Calendario de pagos', copy=False,
    )

    descontado = fields.Monetary('Descontado', compute='_compute_balance')
    restante = fields.Monetary('Restante', compute='_compute_balance')
    num_periodos = fields.Integer('Períodos', compute='_compute_num_periodos')

    payslip_ids = fields.Many2many(
        'hr.payslip', related='attachment_id.payslip_ids', string='Recibos',
    )
    payslip_count = fields.Integer('# Recibos', compute='_compute_payslip_count')

    @api.depends('employee_id')
    def _compute_name(self):
        for r in self:
            r.name = _('Préstamo - %s', r.employee_id.name or _('Nuevo'))

    @api.depends('attachment_id.paid_amount', 'monto_total')
    def _compute_balance(self):
        # sudo(): el ajuste salarial trae regla multiempresa nativa. Leerlo con
        # el usuario provoca "Error de acceso" cuando la compañía del préstamo
        # no está activada en el selector. La regla del préstamo ya garantiza
        # que el usuario solo ve registros de sus compañías activas.
        for r in self:
            attachment = r.attachment_id.sudo()
            descontado = attachment.paid_amount if attachment else 0.0
            r.descontado = descontado
            r.restante = max(0.0, r.monto_total - descontado)

    @api.depends('monto_total', 'monto_periodo')
    def _compute_num_periodos(self):
        for r in self:
            r.num_periodos = ceil(r.monto_total / r.monto_periodo) if r.monto_periodo else 0

    @api.depends('payslip_ids')
    def _compute_payslip_count(self):
        for r in self:
            r.payslip_count = len(r.attachment_id.sudo().payslip_ids)

    # ── Fechas alineadas a los periodos de nómina ─────────────────────────
    # Convención acordada:
    #   • Mensual   → último día de cada mes.
    #   • Quincenal → día 15 y último día de cada mes.
    #   • Semanal   → cada 7 días a partir de la fecha de inicio.
    @staticmethod
    def _ultimo_dia_mes(d):
        import calendar
        return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])

    @classmethod
    def _next_quincena(cls, d):
        """Primer corte quincenal (día 15 o último día) en o después de d."""
        dia15 = date(d.year, d.month, 15)
        ultimo = cls._ultimo_dia_mes(d)
        if d <= dia15:
            return dia15
        if d <= ultimo:
            return ultimo
        nm = d + relativedelta(months=1)
        return date(nm.year, nm.month, 15)

    @classmethod
    def _advance_quincena(cls, corte):
        """Del día 15 pasa al último día del mes; del último día pasa al 15 del mes siguiente."""
        if corte.day == 15:
            return cls._ultimo_dia_mes(corte)
        nm = corte + relativedelta(days=1)  # primero del mes siguiente
        return date(nm.year, nm.month, 15)

    def _fechas_calendario(self, n):
        """Lista de n fechas de descuento alineadas al periodo de nómina."""
        self.ensure_one()
        start = self.fecha_inicio
        fechas = []
        if self.periodicidad == 'mensual':
            f = self._ultimo_dia_mes(start)
            for _i in range(n):
                fechas.append(f)
                f = self._ultimo_dia_mes(f + relativedelta(days=1))
        elif self.periodicidad == 'quincenal':
            f = self._next_quincena(start)
            for _i in range(n):
                fechas.append(f)
                f = self._advance_quincena(f)
        else:  # semanal u otro
            f = start
            for _i in range(n):
                fechas.append(f)
                f = f + relativedelta(weeks=1)
        return fechas

    def _primera_fecha(self):
        """Primera fecha de descuento alineada (para arrancar el ajuste salarial)."""
        self.ensure_one()
        fechas = self._fechas_calendario(1)
        return fechas[0] if fechas else self.fecha_inicio

    def action_confirmar(self):
        for r in self:
            if r.state != 'borrador':
                continue
            if r.monto_total <= 0 or r.monto_periodo <= 0:
                raise UserError(_('El monto total y el monto por período deben ser mayores a cero.'))
            if r.monto_periodo > r.monto_total:
                raise UserError(_('El monto por período no puede ser mayor que el monto total.'))

            input_type = self.env.ref('mx_jandea_prestamos.input_type_prestamo')
            # El descuento arranca en la primera fecha alineada al periodo de
            # nómina (día 15 / último día / etc.), no en la fecha capturada.
            primera_fecha = r._primera_fecha()
            # with_company: fuerza el contexto de compañía del préstamo para que
            # la regla nativa de hr.salary.attachment no bloquee la creación.
            attachment = self.env['hr.salary.attachment'].with_company(r.company_id).create({
                'employee_ids': [(6, 0, [r.employee_id.id])],
                'company_id': r.company_id.id,
                'description': _('Préstamo'),
                'other_input_type_id': input_type.id,
                'duration_type': 'limited',
                'monthly_amount': r.monto_periodo,
                'total_amount': r.monto_total,
                'date_start': primera_fecha,
                'state': 'open',
            })
            if attachment.duration_type != 'limited':
                attachment.write({'duration_type': 'limited', 'total_amount': r.monto_total})

            r.attachment_id = attachment.id
            r._generar_calendario()
            r.state = 'confirmado'
        return True

    def _generar_calendario(self):
        self.ensure_one()
        self.linea_ids.unlink()

        # 1) Montos por periodo (el último ajusta el residuo).
        montos = []
        restante = self.monto_total
        while restante > 0.0001 and len(montos) < 600:
            monto = min(self.monto_periodo, restante)
            restante = round(restante - monto, 2)
            montos.append(monto)

        # 2) Fechas alineadas al periodo de nómina (15 / último día / etc.).
        fechas = self._fechas_calendario(len(montos))

        # 3) Construir líneas.
        lineas = []
        acumulado = 0.0
        saldo = self.monto_total
        for i, monto in enumerate(montos):
            saldo = round(saldo - monto, 2)
            acumulado = round(acumulado + monto, 2)
            lineas.append((0, 0, {
                'secuencia': i + 1,
                'fecha': fechas[i],
                'monto': monto,
                'saldo_restante': saldo,
                'monto_acumulado': acumulado,
            }))
        self.linea_ids = lineas

    def action_ver_recibos(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Recibos'),
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.attachment_id.sudo().payslip_ids.ids)],
        }


class MxJandeaPrestamoLinea(models.Model):
    _name = 'mx.jandea.prestamo.linea'
    _description = 'Línea de calendario de préstamo'
    _order = 'prestamo_id, secuencia'

    prestamo_id = fields.Many2one(
        'mx.jandea.prestamo', string='Préstamo', required=True, ondelete='cascade',
    )
    # Almacenado + indexado: lo necesita la ir.rule multiempresa de la línea.
    company_id = fields.Many2one(
        related='prestamo_id.company_id', string='Compañía',
        store=True, index=True, readonly=True,
    )
    currency_id = fields.Many2one(related='prestamo_id.currency_id')
    secuencia = fields.Integer('No.')
    fecha = fields.Date('Fecha')
    monto = fields.Monetary('Descuento')
    saldo_restante = fields.Monetary('Saldo restante')
    monto_acumulado = fields.Monetary('Acumulado')
    pagado = fields.Boolean('Pagado', compute='_compute_pagado')

    @api.depends('monto_acumulado', 'prestamo_id.descontado')
    def _compute_pagado(self):
        for line in self:
            line.pagado = (
                line.monto_acumulado > 0
                and line.prestamo_id.descontado + 0.01 >= line.monto_acumulado
            )
