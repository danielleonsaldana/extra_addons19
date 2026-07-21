# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


# Bases de nómina disponibles para conceptos calculados por porcentaje.
# Se apoyan en las líneas de categoría del recibo (hr.payslip.line):
#   GROSS = percepciones gravadas, NET = neto a pagar, BASIC = sueldo base,
#   DED = total deducciones. CUSTOM = suma de códigos de regla específicos.
BASE_NOMINA_SELECTION = [
    ('GROSS', 'Percepciones gravadas (GROSS)'),
    ('NET', 'Neto a pagar (NET)'),
    ('BASIC', 'Sueldo base (BASIC)'),
    ('DED', 'Total deducciones (DED)'),
    ('CUSTOM', 'Códigos de regla específicos'),
]


class MxJandeaNominaConcepto(models.Model):
    _name = 'mx.jandea.nomina.concepto'
    _description = 'Concepto de facturación de nómina'
    _order = 'sequence, id'

    sequence = fields.Integer('Secuencia', default=10)
    name = fields.Char('Concepto', required=True, translate=False)
    active = fields.Boolean('Activo', default=True)

    product_id = fields.Many2one(
        'product.product', string='Producto/Servicio', required=True,
        domain="[('sale_ok', '=', True)]",
        help='Producto que se usará en la línea de la orden de venta. '
             'Aquí se controlan los impuestos (IVA/retenciones) y, si timbras, '
             'la clave ProdServ / unidad SAT.',
    )
    descripcion = fields.Char(
        'Descripción en la línea',
        help='Texto que aparece en la línea de la orden de venta. '
             'Si se deja vacío se usa el nombre del producto.',
    )

    tipo_calculo = fields.Selection(
        [
            ('porcentaje', 'Comisión: % sobre base de nómina'),
            ('fijo', 'Monto fijo'),
            ('manual', 'Capturar al generar'),
        ],
        string='Tipo de cálculo', required=True, default='porcentaje',
    )

    # --- Porcentaje ---
    porcentaje = fields.Float(
        'Porcentaje (%)', digits=(16, 4),
        help='Ej. 5 = 5%. Se aplica sobre la base seleccionada.',
    )
    base_nomina = fields.Selection(
        BASE_NOMINA_SELECTION, string='Base de nómina', default='GROSS',
    )
    base_codes = fields.Char(
        'Códigos de regla',
        help='Solo si la base es "Códigos de regla específicos". '
             'Códigos separados por coma, ej: GROSS,COMPENSACION',
    )

    # --- Monto fijo ---
    monto_fijo = fields.Monetary('Monto fijo')
    por_empleado = fields.Boolean(
        'Multiplicar por # de empleados',
        help='Si está activo, el monto fijo se multiplica por la cantidad de '
             'recibos incluidos en el período.',
    )

    currency_id = fields.Many2one(
        'res.currency', string='Moneda',
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        'res.company', string='Empresa emisora',
        help='Déjalo vacío para que el concepto esté disponible para todas las '
             'empresas emisoras. Si lo fijas, solo aplica cuando esa empresa factura.',
    )

    notas = fields.Char('Notas')

    def _calcular_importe(self, bases, num_empleados):
        """Devuelve el importe unitario del concepto dado un dict de bases
        {'GROSS': x, 'NET': y, ...} y el número de empleados (recibos)."""
        self.ensure_one()
        if self.tipo_calculo == 'porcentaje':
            if self.base_nomina == 'CUSTOM':
                base = bases.get('__CUSTOM__', 0.0)
            else:
                base = bases.get(self.base_nomina, 0.0)
            return round(base * (self.porcentaje / 100.0), 2)
        if self.tipo_calculo == 'fijo':
            monto = self.monto_fijo
            if self.por_empleado:
                monto *= (num_empleados or 0)
            return round(monto, 2)
        # manual
        return 0.0
