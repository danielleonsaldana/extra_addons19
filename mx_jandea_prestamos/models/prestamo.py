# -*- coding: utf-8 -*-
from math import ceil

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MxJandeaPrestamo(models.Model):
    _name = 'mx.jandea.prestamo'
    _description = 'Préstamo a empleado'
    _inherit = ['mail.thread']
    _order = 'fecha_inicio desc, id desc'
    _rec_name = 'name'

    name = fields.Char('Referencia', compute='_compute_name', store=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', required=True, tracking=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company,
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
        for r in self:
            descontado = r.attachment_id.paid_amount if r.attachment_id else 0.0
            r.descontado = descontado
            r.restante = max(0.0, r.monto_total - descontado)

    @api.depends('monto_total', 'monto_periodo')
    def _compute_num_periodos(self):
        for r in self:
            r.num_periodos = ceil(r.monto_total / r.monto_periodo) if r.monto_periodo else 0

    @api.depends('payslip_ids')
    def _compute_payslip_count(self):
        for r in self:
            r.payslip_count = len(r.payslip_ids)

    def _delta(self):
        self.ensure_one()
        if self.periodicidad == 'semanal':
            return relativedelta(weeks=1)
        if self.periodicidad == 'mensual':
            return relativedelta(months=1)
        return relativedelta(weeks=2)  # quincenal

    def action_confirmar(self):
        for r in self:
            if r.state != 'borrador':
                continue
            if r.monto_total <= 0 or r.monto_periodo <= 0:
                raise UserError(_('El monto total y el monto por período deben ser mayores a cero.'))
            if r.monto_periodo > r.monto_total:
                raise UserError(_('El monto por período no puede ser mayor que el monto total.'))

            input_type = self.env.ref('mx_jandea_prestamos.input_type_prestamo')
            attachment = self.env['hr.salary.attachment'].create({
                'employee_ids': [(6, 0, [r.employee_id.id])],
                'company_id': r.company_id.id,
                'description': _('Préstamo'),
                'other_input_type_id': input_type.id,
                'duration_type': 'limited',
                'monthly_amount': r.monto_periodo,
                'total_amount': r.monto_total,
                'date_start': r.fecha_inicio,
                'state': 'open',
            })
            # Refuerzo defensivo: asegurar duración Limitada y total correcto.
            if attachment.duration_type != 'limited':
                attachment.write({'duration_type': 'limited', 'total_amount': r.monto_total})

            r.attachment_id = attachment.id
            r._generar_calendario()
            r.state = 'confirmado'
        return True

    def _generar_calendario(self):
        self.ensure_one()
        self.linea_ids.unlink()
        lineas = []
        restante = self.monto_total
        acumulado = 0.0
        fecha = self.fecha_inicio
        delta = self._delta()
        secuencia = 1
        # tope de seguridad para evitar bucles infinitos
        while restante > 0.0001 and secuencia <= 600:
            monto = min(self.monto_periodo, restante)
            restante = round(restante - monto, 2)
            acumulado = round(acumulado + monto, 2)
            lineas.append((0, 0, {
                'secuencia': secuencia,
                'fecha': fecha,
                'monto': monto,
                'saldo_restante': restante,
                'monto_acumulado': acumulado,
            }))
            fecha = fecha + delta
            secuencia += 1
        self.linea_ids = lineas

    def action_ver_recibos(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Recibos'),
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.payslip_ids.ids)],
        }


class MxJandeaPrestamoLinea(models.Model):
    _name = 'mx.jandea.prestamo.linea'
    _description = 'Línea de calendario de préstamo'
    _order = 'prestamo_id, secuencia'

    prestamo_id = fields.Many2one(
        'mx.jandea.prestamo', string='Préstamo', required=True, ondelete='cascade',
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
