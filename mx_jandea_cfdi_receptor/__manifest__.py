# -*- coding: utf-8 -*-
{
    'name': 'MX Jandea - Validación de Receptor CFDI',
    'version': '19.0.1.0.0',
    'summary': 'Bloquea la carga de un CFDI cuyo Receptor no coincide con la '
               'empresa a la que se está subiendo',
    'description': """
Al subir un XML (CFDI) a una factura de PROVEEDOR mediante el botón "Subir",
Odoo crea la factura en la empresa activa. Este módulo valida que el RFC del
NODO RECEPTOR del CFDI coincida con el RFC (razón social) de esa empresa.

Si no coinciden, la carga se detiene con un mensaje claro indicando el RFC que
trae el XML y el de la empresa, para evitar registrar una factura en la razón
social equivocada.

Se engancha a account.move._extend_with_attachments (flujo nativo de importación
de adjuntos) y lee el árbol XML ya parseado (file_data['xml_tree']), por lo que
no vuelve a parsear el archivo ni depende del orden de los decodificadores.
    """,
    'author': 'Jandea IT',
    'category': 'Accounting/Accounting',
    'depends': [
        'account',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
