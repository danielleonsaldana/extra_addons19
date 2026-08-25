# mx_jandea_employee_import — v19.0.1.2.0

## Carga de ajustes salariales recurrentes desde el machote
Se agregó la posibilidad de cargar, por empleado y en el mismo machote,
tres conceptos que se crean como **ajuste salarial recurrente**
(`hr.salary.attachment`, igual que los préstamos):

| Columna del machote            | Tipo de entrada (código) |
|--------------------------------|--------------------------|
| Vales de Despensa              | `VALES_DESPENSA`         |
| Fondo de Ahorro                | `FONDO_AHORRO`           |
| Ajuste Salarial                | `AJUSTE_SALARIAL`        |
| Ajuste Salarial (Concepto)     | (descripción del ajuste) |

- Columnas **opcionales**: si la celda va vacía o en 0, no se crea nada.
- El monto se toma como **importe mensual** del ajuste; el ajuste queda
  **recurrente** (sin fecha de fin). `date_start` = fecha de ingreso del
  empleado (o la fecha de hoy).
- Al **reimportar** con "actualizar existentes", reutiliza el ajuste abierto
  del mismo empleado y tipo y solo actualiza el monto (no duplica).
- Se crean 3 tipos de entrada (`hr.payslip.input.type`,
  `available_in_attachments=True`).

## Importante (para que se refleje en el recibo)
Estos ajustes crean el `hr.salary.attachment` con su código, pero **el importe
solo aparece en el recibo si existe una regla salarial que lea
`inputs['VALES_DESPENSA'].amount`** (y equivalentes). El cálculo automático de
Fondo de Ahorro / Vales por las reglas FA/VD (que leen `SUELDO_NETO_FAVD`, etc.)
es **independiente** de estos ajustes; si usas ambos, cuida no duplicar el
concepto. Si tus reglas ya leen otros códigos, cambia el `code` de los tipos de
entrada en `data/hr_payslip_input_type_data.xml` para que coincidan.

## Dependencia
Se agregó `hr_payroll` a `depends` (necesario para `hr.salary.attachment`).
