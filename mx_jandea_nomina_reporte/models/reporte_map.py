# -*- coding: utf-8 -*-
from odoo import fields, models


# Columnas de dinero del Listado de Nómina.
# (clave_interna, etiqueta, tipo) -> tipo: 'P' percepción, 'D' deducción.
# El orden aquí define el orden de las columnas en el Excel.
COLUMNAS_REPORTE = [
    ('sueldo', 'Sueldo', 'P'),
    ('vacaciones', 'Vacaciones', 'P'),
    ('prima_vacacional', 'Prima Vacacional', 'P'),
    ('festivo', 'Festivo Laborado', 'P'),
    ('descanso', 'Descanso Laborado', 'P'),
    ('vales_despensa', 'Vales Despensa', 'P'),
    ('fondo_ahorro', 'Fondo de Ahorro', 'P'),
    ('prima_dominical', 'Prima Dominical', 'P'),
    ('otras_percepciones', 'Otras Percepciones', 'P'),
    ('aguinaldo', 'Aguinaldo', 'P'),
    ('ptu', 'Reparto de Utilidades', 'P'),
    ('isr', 'ISR', 'D'),
    ('cuotas_imss', 'Cuotas IMSS', 'D'),
    ('anticipo_nomina', 'Anticipo de Nomina', 'D'),
    ('prestamo_personal', 'Prestamo Personal', 'D'),
    ('adeudo_empresa', 'Adeudo Empresa', 'D'),
    ('pension_alimenticia', 'Pensión Alimenticia', 'D'),
    ('caja_ahorro', 'Caja de Ahorro', 'D'),
    ('fondo_ahorro_emp', 'Fondo de Ahorro Empleado', 'D'),
    ('fondo_ahorro_pat', 'Fondo de Ahorro Patron', 'D'),
    ('otras_deducciones', 'Otras Deducciones', 'D'),
    ('descuento_vales', 'Descuento Vales Despensa', 'D'),
]

COLUMNA_SELECTION = [(k, v) for (k, v, _t) in COLUMNAS_REPORTE]


class MxJandeaNominaReporteMap(models.Model):
    _name = 'mx.jandea.nomina.reporte.map'
    _description = 'Mapeo de columna del Listado de Nómina a códigos de regla'
    _order = 'columna'
    _rec_name = 'columna'

    columna = fields.Selection(
        COLUMNA_SELECTION, string='Columna del reporte', required=True,
    )
    codes = fields.Char(
        'Códigos de regla',
        help='Códigos de reglas salariales (hr.salary.rule) cuyo importe se '
             'suma en esta columna. Separados por coma, ej: FESTIVO_LABORADO.',
    )
    company_id = fields.Many2one(
        'res.company', string='Empresa',
        help='Vacío = aplica a todas. Fija una empresa para usar códigos '
             'distintos por compañía.',
    )
    notas = fields.Char('Notas')

    _sql_constraints = [
        ('columna_company_uniq',
         'unique(columna, company_id)',
         'Ya existe un mapeo para esta columna y empresa.'),
    ]
