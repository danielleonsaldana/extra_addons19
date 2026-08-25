# mx_jandea_contratos — v19.0.1.1.0

## Se incluyeron 3 contratos de "Licencias Internacionales" (Stylos y Shows S.A. de C.V.)

Los tres `.docx` venían como plantillas de combinación de correspondencia de
Word (campos `MERGEFIELD`) con datos de un empleado real capturados. Se
convirtieron a plantillas `docxtpl` (`{{ placeholder }}`) para que **los datos
se traigan de la ficha del empleado al imprimir**.

### Plantillas agregadas (Configuración → Documentos → Plantillas)
1. **CIT Indeterminado con Periodo de Prueba** — indeterminado sujeto a prueba.
2. **CIT Indeterminado con Reconocimiento de Antigüedad** — agrega la fecha de
   antigüedad reconocida.
3. **Contrato por Tiempo Determinado** — estructura PATRÓN/TRABAJADOR, con
   vigencia (inicio, días, término).

Todas: `doc_type=contrato`, `gender=unisex` (una sola plantilla sirve para
hombre y mujer; el sexo y el estado civil se resuelven por texto).

### Qué es fijo y qué es variable
- **Fijo (texto del cliente):** datos de la EMPRESA (Stylos y Shows, su
  representante, RFC `SSH040329EV9`, domicilio, giro) y todo el clausulado.
- **Variable (del empleado):** nombre, nacionalidad, edad, sexo, estado civil,
  CURP, RFC, NSS, domicilio (calle/colonia/CP/municipio/estado), puesto,
  fecha de ingreso, antigüedad, término, vigencia, sueldo mensual (número y
  letra), banco, CLABE y sucursal.

## Wizard "Imprimir Documento" — prellenado desde el empleado
El asistente ahora **jala automáticamente** del `hr.employee`:
- Nombre completo y dividido en apellido paterno / materno / nombre(s).
- RFC (`mx_rfc`), CURP (`mx_curp`), NSS (`nss`/`ssnid`).
  *(Se corrigió el prellenado: antes leía `l10n_mx_rfc`/`l10n_mx_curp`, que no
  existen en esta suite, y los dejaba en blanco.)*
- Nacionalidad (MEXICANA por defecto / `country_id`), edad (de `birthday`),
  sexo (de `gender`), estado civil (de `marital`, con género).
- Domicilio por partes (`private_street`, `private_street2`, `private_zip`,
  `private_city`, `private_state_id`) y también el domicilio completo.
- Puesto (`job_id` / `job_title`).
- Fechas: ingreso (`contract_date_start`), antigüedad (`first_contract_date`),
  término (`contract_date_end`), y vigencia en días (término − ingreso).
- Sueldo **mensual** calculado desde `wage` × factor de `schedule_pay`
  (quincenal ×2, semanal ×52/12, etc.), en número y **en letra**.
- Banco y CLABE de la cuenta bancaria del empleado.

Todos los campos son **editables** en el wizard para corregir a mano antes de
generar el `.docx`.

## Conversión de número a letras
Se agregó un convertidor de importe a letras en español **sin dependencias
externas** (no requiere `num2words`). Formato: `PALABRAS NN/100`
(p. ej. `VEINTE MIL TRESCIENTOS CINCUENTA Y UNO 50/100`).

## Notas
- Las plantillas existentes (Burdina H/M, Krino H/M, Crystal) siguen
  funcionando: se conservaron todas sus claves de contexto.
- Falta confirmar en tu build si la cuenta bancaria del empleado es
  `bank_account_id` o `bank_account_ids` (el wizard soporta ambas por
  `getattr`).
- El sueldo mensual se estima con `wage` × factor de periodicidad; verifica el
  valor en el wizard antes de imprimir si tu configuración de `wage` difiere.
