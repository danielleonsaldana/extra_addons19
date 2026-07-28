# -*- coding: utf-8 -*-
{
    'name': 'MX Jandea - Validación de Receptor CFDI',
    'version': '19.0.1.2.0',
    'summary': 'Advierte y pide confirmación cuando el Receptor de un CFDI no '
               'coincide con la empresa a la que se sube',
    'description': """
Al subir un XML (CFDI) a una factura de PROVEEDOR (botón "Subir", arrastrar o
por correo), Odoo crea la factura en la empresa activa. Este módulo compara el
RFC del NODO RECEPTOR del CFDI contra el RFC de esa empresa.

Si NO coinciden:
  * La factura se crea, pero muestra una advertencia visible con el receptor del
    XML (nombre y RFC) frente a la empresa actual.
  * NO se puede Registrar/Confirmar la factura hasta marcar la casilla
    "Cargar de todos modos", de modo que el usuario decide explícitamente si la
    registra o la elimina. Así se evita cargar una factura en la razón social
    equivocada por error.

Se engancha a account.move._extend_with_attachments (flujo nativo de importación
de adjuntos) y lee el árbol XML ya parseado (file_data['xml_tree']), por lo que
no vuelve a parsear el archivo ni depende del orden de los decodificadores. El
bloqueo de registro vive en account.move._post.
    """,
    'author': 'Jandea IT',
    'category': 'Accounting/Accounting',
    'depends': [
        'account',
    ],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
