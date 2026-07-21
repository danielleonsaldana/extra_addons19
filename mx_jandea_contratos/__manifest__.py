# -*- coding: utf-8 -*-
{
    'name': 'MX Jandea - Documentos e Impresión de Contratos',
    'version': '19.0.1.0.0',
    'summary': 'Selecciona e imprime contratos, altas y bajas desde la ficha del empleado',
    'description': """
        Motor genérico de plantillas (.docx con placeholders {{ }}) impreso
        desde la ficha del Empleado.

        - Catálogo de plantillas (Configuración → Documentos → Plantillas):
          tipo (Contrato / Alta / Baja), subtipo (Burdina Indeterminado,
          Burdina Determinado, Krino, Crystal, Cliente Maquila...), género
          (Hombre/Mujer/Unisex) y el archivo .docx con placeholders.
        - Botón "Imprimir Documento" en el Empleado → wizard para elegir
          tipo + plantilla → genera el .docx con los datos del empleado ya
          rellenados y lo deja como adjunto descargable.
        - Trae precargadas las 5 plantillas ya proporcionadas: CIDT
          Indeterminado Burdina (H/M), CPSP Crystal, CPSP Krino (H/M).
        - Para Determinado Burdina, Altas (sistema/IMSS/cuenta
          bancaria/valores agregados) y Bajas (sistema-VA/IMSS): solo hay
          que subir el .docx con sus placeholders en el catálogo, no se
          requiere programar nada nuevo.
    """,
    'author': 'Jandea IT',
    'category': 'Human Resources',
    'depends': [
        'hr_payroll',
        'hr_work_entry_enterprise',
        'l10n_mx_hr_payroll',
    ],
    'external_dependencies': {
        'python': ['docxtpl'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/hr_document_template_data.xml',
        'views/hr_document_template_views.xml',
        'views/hr_employee_views.xml',
        'wizard/hr_document_print_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
