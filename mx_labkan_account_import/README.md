# mx_labkan_account_import

**Alta Masiva de Cuentas Contables + Descarga TXT Bancaria**  
Módulo Odoo 17 para Labkan / BHAANG

---

## Funcionalidades

### 1. Alta Masiva de Cuentas Contables (`account.account`)

Permite importar cuentas contables desde un archivo **Excel (.xlsx)** o **CSV**.

**Acceso:**  
`Contabilidad → Configuración → Alta Masiva de Cuentas Contables`

También disponible como **Acción** desde la vista lista del Plan Contable.

**Columnas del archivo:**

| Columna | Requerido | Descripción |
|---|---|---|
| Código | ✅ | Código de cuenta (ej: `101.01.001`) |
| Nombre | ✅ | Nombre de la cuenta |
| Tipo de cuenta | ✅ | Ver hoja "Tipos de cuenta" en plantilla |
| Reconciliable | ❌ | Sí / No (default: No) |
| Moneda | ❌ | Código ISO, ej: MXN |
| Etiquetas | ❌ | Separadas por `\|` |
| Notas | ❌ | Notas internas |
| Activo | ❌ | Sí / No (default: Sí) |

**Opciones:**
- Selección de hoja y fila de encabezados (flexible)
- Opción de actualizar cuentas existentes
- Descarga de plantilla Excel con hoja de referencia de tipos

---

### 2. Descarga Masiva TXT Cuentas Bancarias

Exporta cuentas bancarias de beneficiarios (`res.partner.bank`) en formato TXT
compatible con los portales bancarios mexicanos.

**Acceso:**  
`Contabilidad → Configuración → Descarga Masiva TXT (Bancos)`

**Formatos soportados:**

#### Inbursa
```
NoCuenta|UsoDestino
```
- No. Cuenta / Tarjeta / CLABE (11, 16 o 18 posiciones)
- Uso: Nómina / Proveedores / Honorarios / Arrendamiento / Otros

#### Otros Bancos
```
Celular/Tarjeta/CLABE|NombreBeneficiario|RFC|Banco
```

**Filtros disponibles:**
- Por compañía
- Por contacto(s) específico(s)
- Por banco
- Solo cuentas activas

---

## Instalación

1. Copiar la carpeta `mx_labkan_account_import` al directorio de addons
2. Actualizar lista de aplicaciones
3. Instalar el módulo

**Dependencias:** `account`, `base_setup`  
**Dependencia Python:** `openpyxl` (ya incluido en Odoo 17)

---

## Estructura del módulo

```
mx_labkan_account_import/
├── __manifest__.py
├── __init__.py
├── security/
│   └── ir.model.access.csv
├── views/
│   └── account_menu_extend.xml
└── wizard/
    ├── __init__.py
    ├── account_import_wizard.py          # Alta masiva cuentas contables
    ├── account_import_wizard_views.xml
    ├── bank_account_export_wizard.py     # Descarga TXT bancaria
    └── bank_account_export_wizard_views.xml
```

---

*Desarrollado por Labkan IT — Daniel León Saldaña*
