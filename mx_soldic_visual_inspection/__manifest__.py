# -*- coding: utf-8 -*-
{
    "name": "Proyecto - Inspección Visual (VT)",
    "version": "19.0.1.1.0",
    "summary": "Informe final de ensayo de Inspección Visual (VT) en tareas de proyecto, con PDF imprimible",
    "description": """
Agrega a las tareas de Proyecto una pestaña "Inspección Visual" con todos los
datos del formato JT-VT-01-F01 (Informe final de ensayo - Inspección visual):

* Datos del informe y del cliente
* Datos de la pieza
* Información de inspección y equipo de medición
* Resultados por junta (indicación, dimensiones, resultado)
* Croquis de ubicación
* Observaciones y firmas (técnico, signatario y cliente)

Incluye el reporte PDF con el mismo diseño del formato en Excel.
    """,
    "author": "Daniel León Saldaña",
    "category": "Services/Project",
    "license": "LGPL-3",
    "depends": ["project"],
    "data": [
        "security/ir.model.access.csv",
        "report/paperformat.xml",
        "report/visual_inspection_report.xml",
        "report/visual_inspection_templates.xml",
        "views/project_task_views.xml",
        "views/project_project_views.xml",
        "views/res_company_views.xml",
    ],
    "installable": True,
    "application": False,
}
