# -*- coding: utf-8 -*-
from odoo import models, fields

# (codigo de regla, etiqueta, afectado por defecto)
CONCEPTOS = [
    ('FNQT_IND90', 'Indemnización 90 días', True),
    ('FNQT_IND20', 'Indemnización 20 días por año', True),
    ('FNQT_PRIMA_ANT', 'Prima de Antigüedad', True),
    ('FNQT_SALARIO', 'Salario Pendiente', False),
    ('FNQT_AGUINALDO', 'Aguinaldo', False),
    ('FNQT_VACACIONES', 'Vacaciones', False),
    ('FNQT_PRIMA_VAC', 'Prima Vacacional', False),
    ('FNQT_OTRAS_PERC', 'Otras Percepciones', False),
]


class FnqtPctWizard(models.TransientModel):
    _name = 'fnqt.pct.wizard'
    _description = 'Aplicar porcentaje a conceptos del finiquito'

    payslip_id = fields.Many2one(
        'hr.payslip', string='Recibo', required=True,
        default=lambda self: self.env.context.get(
            'default_payslip_id') or self.env.context.get('active_id'))
    pct = fields.Float(string='% a aplicar (100 = completo)', default=100.0,
                       required=True)

    afecta_ind90 = fields.Boolean('Indemnización 90 días', default=True)
    afecta_ind20 = fields.Boolean('Indemnización 20 días por año', default=True)
    afecta_prima_ant = fields.Boolean('Prima de Antigüedad', default=True)
    afecta_salario = fields.Boolean('Salario Pendiente', default=False)
    afecta_aguinaldo = fields.Boolean('Aguinaldo', default=False)
    afecta_vacaciones = fields.Boolean('Vacaciones', default=False)
    afecta_prima_vac = fields.Boolean('Prima Vacacional', default=False)
    afecta_otras = fields.Boolean('Otras Percepciones', default=False)

    def _codigos(self):
        m = [
            ('FNQT_IND90', self.afecta_ind90),
            ('FNQT_IND20', self.afecta_ind20),
            ('FNQT_PRIMA_ANT', self.afecta_prima_ant),
            ('FNQT_SALARIO', self.afecta_salario),
            ('FNQT_AGUINALDO', self.afecta_aguinaldo),
            ('FNQT_VACACIONES', self.afecta_vacaciones),
            ('FNQT_PRIMA_VAC', self.afecta_prima_vac),
            ('FNQT_OTRAS_PERC', self.afecta_otras),
        ]
        return [c for c, on in m if on]

    def action_apply(self):
        self.ensure_one()
        codes = self._codigos()
        pct = self.pct or 100.0
        ps = self.payslip_id
        ps.write({
            'x_fnqt_pct': pct,
            'x_fnqt_pct_codes': ','.join(codes),
        })
        etiquetas = {c: n for c, n, _d in CONCEPTOS}
        nombres = ', '.join(etiquetas.get(c, c) for c in codes) or '(ninguno)'
        try:
            ps.message_post(body='Se aplicó %.2f%% a: %s' % (pct, nombres))
        except Exception:
            pass
        # Recalcular la hoja para reflejar el ajuste.
        try:
            ps.compute_sheet()
        except Exception:
            try:
                ps.action_payslip_compute_sheet()
            except Exception:
                pass
        return {'type': 'ir.actions.act_window_close'}

    def action_quitar(self):
        """Regresa todos los conceptos a 100% (quita el ajuste)."""
        self.ensure_one()
        ps = self.payslip_id
        ps.write({'x_fnqt_pct': 100.0, 'x_fnqt_pct_codes': ''})
        try:
            ps.message_post(body='Se quitó el ajuste de porcentaje (100%).')
        except Exception:
            pass
        try:
            ps.compute_sheet()
        except Exception:
            try:
                ps.action_payslip_compute_sheet()
            except Exception:
                pass
        return {'type': 'ir.actions.act_window_close'}
