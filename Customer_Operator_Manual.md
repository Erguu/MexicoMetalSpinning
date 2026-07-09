# Customer Operator Manual — Metal Spinning Machine
# Manual del Operador (Cliente) — Máquina de Repujado de Metal

**Machine:** CNC Metal Spinning Lathe · Siemens S7-1214C control
**Máquina:** Torno CNC de repujado de metal · Control Siemens S7-1214C

**Audience / Destinatario:** Machine operators on the production floor / Operadores de máquina en planta
**Document type:** Day-to-day operating manual (bilingual EN / ES)

> This manual covers normal operation, sheet loading, manual mode, troubleshooting, and
> maintenance. For wiring and electrical detail see `Program/docs/Wiring_Diagram.md`.
> For programming/recipe changes contact Maintenance.
>
> Este manual cubre la operación normal, carga de lámina, modo manual, diagnóstico de fallas y
> mantenimiento. Para el cableado y detalle eléctrico consulte `Program/docs/Wiring_Diagram.md`.
> Para cambios de programa/receta contacte a Mantenimiento.

---

## Warning Conventions / Convenciones de Advertencia

| Symbol | Meaning (EN) | Significado (ES) |
|--------|--------------|------------------|
| ⛔ **DANGER** | Risk of serious injury or death | Riesgo de lesión grave o muerte |
| ⚠️ **WARNING** | Risk of injury or machine damage | Riesgo de lesión o daño a la máquina |
| 📝 **NOTE** | Important information | Información importante |

---

## 1. Introduction / Introducción

**EN:** This machine forms (spins) a flat metal blank against a rotating mandrel using
forming tools mounted on a turret. Two linear axes position the tool: **X** (radial, in/out)
and **Z** (axial, along the part). The **spindle** rotates the mandrel and blank. Pneumatic
cylinders hold the sheet, clamp the mandrel, and lock the tool head. The machine runs stored
**recipes** (programs 1–5) created from CAM software.

**ES:** Esta máquina conforma (repuja) un disco metálico plano contra un mandril giratorio usando
herramientas de conformado montadas en una torreta. Dos ejes lineales posicionan la herramienta:
**X** (radial, entrada/salida) y **Z** (axial, a lo largo de la pieza). El **husillo** hace girar el
mandril y el disco. Cilindros neumáticos sujetan la lámina, fijan el mandril y bloquean el cabezal
de herramienta. La máquina ejecuta **recetas** almacenadas (programas 1–5) creadas desde software CAM.

---

## 2. Safety First / Seguridad Primero

⛔ **DANGER — Rotating spindle / Husillo giratorio**
- **EN:** Never touch the mandrel, blank, or tool while the spindle is turning. Loose clothing,
  gloves, hair, and jewelry can be caught. Keep both hands clear before pressing Start.
- **ES:** Nunca toque el mandril, el disco o la herramienta mientras el husillo gira. La ropa
  suelta, guantes, cabello y joyería pueden quedar atrapados. Mantenga ambas manos alejadas antes
  de presionar Arranque.

⛔ **DANGER — Lockout / Tagout before service / Bloqueo y Etiquetado antes del servicio**
- **EN:** Before any cleaning, tool change by hand, or maintenance: press **E-STOP**, turn the
  main disconnect OFF, lock it with your padlock, and **bleed the pneumatic air supply**. Pneumatic
  cylinders can move even with electrical power off if air pressure remains.
- **ES:** Antes de cualquier limpieza, cambio manual de herramienta o mantenimiento: presione
  **PARO DE EMERGENCIA**, apague el interruptor principal, bloquéelo con su candado y **purgue el
  suministro de aire neumático**. Los cilindros neumáticos pueden moverse aún sin energía eléctrica
  si queda presión de aire.

⚠️ **WARNING — Two-hand start / Arranque a dos manos**
- **EN:** Sheet loading requires both Start buttons (A and B) pressed together. This is a safety
  feature — never tie down, tape, or bypass one button.
- **ES:** La carga de lámina requiere ambos botones de Arranque (A y B) presionados juntos. Es una
  función de seguridad — nunca amarre, encinte ni anule un botón.

⚠️ **WARNING — Safety door & air / Puerta de seguridad y aire**
- **EN:** The machine will not run in automatic mode with the safety door open or with low air
  pressure. Do not defeat the door switch.
- **ES:** La máquina no funcionará en modo automático con la puerta de seguridad abierta o con baja
  presión de aire. No anule el interruptor de la puerta.

### Always / Siempre
- **EN:** Wear safety glasses · Keep the door closed during operation · Know where the E-Stop is ·
  Keep the work area clean and dry.
- **ES:** Use lentes de seguridad · Mantenga la puerta cerrada durante la operación · Sepa dónde está
  el Paro de Emergencia · Mantenga el área de trabajo limpia y seca.

### Never / Nunca
- **EN:** Reach into a running machine · Bypass the door or E-Stop · Leave a new/unproven program
  running unattended · Wear gloves near the rotating spindle.
- **ES:** Meta las manos en una máquina en marcha · Anule la puerta o el Paro de Emergencia · Deje
  un programa nuevo/no probado funcionando sin vigilancia · Use guantes cerca del husillo giratorio.

---

## 3. Control Panel Tour / Recorrido por el Panel de Control

### Physical panel / Panel físico

| Control | EN | ES |
|---------|----|----|
| **E-STOP** (red mushroom) | Press to cut power to motion immediately. Twist to release. | Presione para cortar energía al movimiento de inmediato. Gire para liberar. |
| **START A + START B** (two green buttons) | Press **both together** to confirm sheet load and start. | Presione **ambos juntos** para confirmar carga de lámina y arrancar. |
| **Main disconnect** | Turns electrical power on/off. | Enciende/apaga la energía eléctrica. |

📝 **NOTE / NOTA:** Stop, Pause, Reset, Continue and Acknowledge are **HMI (touchscreen) buttons**,
not physical panel buttons. / Paro, Pausa, Reinicio, Continuar y Reconocer son **botones de la HMI
(pantalla táctil)**, no botones físicos del panel.

### HMI (touchscreen) buttons / Botones de la HMI (pantalla táctil)

| Button (EN) | Botón (ES) | Function / Función |
|-------------|-----------|--------------------|
| **Start** | Arranque | Begin the selected program (after sheet load) / Inicia el programa seleccionado |
| **Stop** | Paro | Controlled stop; axes return to zero / Paro controlado; ejes regresan a cero |
| **Pause** | Pausa | Feed hold; remembers position / Pausa de avance; recuerda la posición |
| **Continue** | Continuar | Resume from the paused line / Reanuda desde la línea pausada |
| **Reset** | Reinicio | Clear errors and return to a safe, ready state / Borra errores y regresa a estado seguro y listo |
| **Ack Error** | Reconocer Error | Clear the error message only (no full reset) / Borra solo el mensaje de error |
| **Restart** | Reiniciar Programa | Restart the program from the first line / Reinicia el programa desde la primera línea |

### Displays / Indicadores

| Display | Shows (EN) | Muestra (ES) |
|---------|-----------|--------------|
| Status bar | Current state: Running, Paused, Error… | Estado actual: Ejecutando, Pausado, Error… |
| X position | Radial position (mm) | Posición radial (mm) |
| Z position | Axial position (mm) | Posición axial (mm) |
| Tool | Current tool number (1–4) | Número de herramienta actual (1–4) |
| RPM | Spindle speed | Velocidad del husillo |
| Feedrate % | Speed override percentage | Porcentaje de ajuste de velocidad |
| Line x / y | Current line / total lines | Línea actual / líneas totales |

### Status lamps / Lámparas de estado

| Lamp | Color | Meaning (EN) | Significado (ES) |
|------|-------|--------------|------------------|
| Running | Green / Verde | Program executing | Programa en ejecución |
| Paused | Yellow / Amarillo | Feed hold active | Pausa de avance activa |
| Error | Red / Rojo | Fault — see error text | Falla — ver texto de error |

---

## 4. Daily Startup & Shutdown / Arranque y Apagado Diario

### Startup / Arranque
1. **EN:** Turn the main disconnect ON. Wait for the HMI to boot.
   **ES:** Encienda el interruptor principal. Espere a que arranque la HMI.
2. **EN:** Release the E-Stop (twist). Confirm the safety screen shows **E-Stop OK**, **Door Closed**,
   and **Air OK** (green).
   **ES:** Libere el Paro de Emergencia (gire). Confirme que la pantalla de seguridad muestre
   **Paro OK**, **Puerta Cerrada** y **Aire OK** (verde).
3. **EN:** Confirm the drives/contactors are enabled (Drives Enabled indicator green).
   **ES:** Confirme que los drives/contactores estén habilitados (indicador Drives Habilitados verde).
4. **EN:** Home the machine if not already homed (the machine will home automatically at the start of
   a run; you can also use **Home All** in Manual mode).
   **ES:** Referencie la máquina si no está referenciada (la máquina se referencia automáticamente al
   inicio de un ciclo; también puede usar **Referenciar Todo** en modo Manual).

### Pre-flight checklist / Lista de verificación previa
- [ ] **EN:** Material blank ready · Correct tools in the turret · Door closed · Air ≥ 6 bar ·
      No error message · Correct recipe selected.
- [ ] **ES:** Disco de material listo · Herramientas correctas en la torreta · Puerta cerrada ·
      Aire ≥ 6 bar · Sin mensaje de error · Receta correcta seleccionada.

### Shutdown / Apagado
1. **EN:** Let the current part finish or press **Stop** and wait for the machine to return to zero.
   **ES:** Deje terminar la pieza actual o presione **Paro** y espere a que la máquina regrese a cero.
2. **EN:** Clean the work area, remove the finished part.
   **ES:** Limpie el área de trabajo, retire la pieza terminada.
3. **EN:** Turn the main disconnect OFF. Report any issues.
   **ES:** Apague el interruptor principal. Reporte cualquier problema.

---

## 5. Loading a Sheet / Carga de la Lámina

**EN:** When the status shows **"Waiting for sheet…"** the machine runs a guided three-phase
sequence. Follow each step exactly.

**ES:** Cuando el estado muestre **"Esperando lámina…"** la máquina ejecuta una secuencia guiada de
tres fases. Siga cada paso exactamente.

| Phase | What the machine does (EN) | Lo que hace la máquina (ES) | What you do / Qué hace usted |
|-------|----------------------------|------------------------------|------------------------------|
| 1 | Sheet holder cylinder **extends** to hold position | El cilindro sujeta-lámina **extiende** a la posición de sujeción | **EN:** Place the blank onto the mandrel. **ES:** Coloque el disco sobre el mandril. |
| 2 | HMI prompts: *"Insert sheet, then press both start buttons"* | La HMI indica: *"Inserte lámina, luego presione ambos botones de arranque"* | **EN:** Press and **hold both** Start buttons together. **ES:** Presione y **mantenga ambos** botones de Arranque juntos. |
| 3 | Mandrel lock **clamps** (≈5 s), then sheet holder **retracts** (≈5 s) | El bloqueo de mandril **fija** (≈5 s), luego el sujeta-lámina **retrae** (≈5 s) | **EN:** Stay clear — do not touch. **ES:** Manténgase alejado — no toque. |

**EN:** After phase 3, the tool head locks and the machine automatically enters **Running**.

**ES:** Después de la fase 3, el cabezal de herramienta se bloquea y la máquina entra automáticamente
en **Ejecutando**.

⚠️ **WARNING:** If you press only one Start button, the machine will not proceed — both must be held
together. / Si presiona solo un botón de Arranque, la máquina no avanzará — ambos deben mantenerse juntos.

---

## 6. Running a Program / Ejecución de un Programa

1. **Select recipe / Seleccione la receta:** choose program **1–5** in the Recipe Selector.
2. **Set speed / Ajuste la velocidad:** set Feedrate Override to **100%** for normal speed.
   - **EN:** Lower % = slower and safer. Higher % only for proven programs.
   - **ES:** Menor % = más lento y seguro. Mayor % solo para programas comprobados.
3. **Start / Arranque:** complete the sheet-loading sequence (Section 5), then the machine runs.
4. **During the run / Durante el ciclo:** watch the X/Z positions, line counter, and RPM.

### Speed control / Control de velocidad
- **EN:** **Feedrate Override** affects cutting/forming moves (50–200%). **Rapid Override** affects
  fast positioning moves. Adjust on the fly; the change takes effect immediately.
- **ES:** **Ajuste de Avance** afecta los movimientos de conformado (50–200%). **Ajuste Rápido**
  afecta los movimientos rápidos de posicionamiento. Ajuste sobre la marcha; el cambio aplica de inmediato.

### Pause / Resume / Pausa / Reanudar
1. **EN:** Press **Pause** to hold. The machine remembers its position.
   **ES:** Presione **Pausa** para detener. La máquina recuerda su posición.
2. **EN:** Press **Continue** (not Pause again) to resume from the same line.
   **ES:** Presione **Continuar** (no Pausa otra vez) para reanudar desde la misma línea.

### Normal stop / Paro normal
- **EN:** Press **Stop**. The spindle decelerates while X and Z return to zero together; the mandrel
  unclamps. The machine ends in **Stopped**.
- **ES:** Presione **Paro**. El husillo desacelera mientras X y Z regresan a cero juntos; el mandril
  se libera. La máquina termina en **Detenido**.

### Completion / Finalización
- **EN:** At program end the status shows **Program Complete**. Remove the part, then load the next
  sheet to run again.
- **ES:** Al terminar el programa el estado muestra **Programa Completado**. Retire la pieza, luego
  cargue la siguiente lámina para ejecutar de nuevo.

---

## 7. Manual Mode / Modo Manual

**EN:** Manual mode lets you jog axes, home, move to preset positions, and run the spindle by hand —
for setup, tool changes, and recovery. Enable it from the Manual screen (**Enable Manual**). Manual
mode is only available from a stopped/safe state.

**ES:** El modo manual permite mover los ejes (jog), referenciar, ir a posiciones predefinidas y
operar el husillo a mano — para preparación, cambios de herramienta y recuperación. Actívelo en la
pantalla Manual (**Habilitar Manual**). El modo manual solo está disponible desde un estado
detenido/seguro.

### Selecting an axis / Selección de eje
- **EN:** Use the Axis Selector: **0 = X, 1 = Z, 2 = Tool, 3 = Spindle**. The screen shows the
  selected axis name, position, and whether it is homed/ready.
- **ES:** Use el Selector de Eje: **0 = X, 1 = Z, 2 = Torreta, 3 = Husillo**. La pantalla muestra el
  nombre del eje seleccionado, su posición y si está referenciado/listo.

### Jogging / Movimiento manual (jog)
| Control | EN | ES |
|---------|----|----|
| **Jog + / Jog −** | Hold to move the axis continuously at Jog Speed | Mantenga para mover el eje continuamente a la Velocidad de Jog |
| **Jog Speed** | Continuous jog velocity (mm/min) | Velocidad de jog continuo (mm/min) |
| **Step + / Step −** | Move one increment (Step Size) per press | Mueve un incremento (Tamaño de Paso) por pulsación |
| **Step Size** | Size of each incremental step (mm) | Tamaño de cada paso incremental (mm) |
| **Target + Move** | Type a target, press Move for an absolute move | Escriba un objetivo, presione Mover para un movimiento absoluto |

### Homing & presets / Referenciado y posiciones predefinidas
| Button | EN | ES |
|--------|----|----|
| **Home Axis** | Home the selected axis | Referencia el eje seleccionado |
| **Home All** | Home X and Z | Referencia X y Z |
| **Go Safe** | Move to the safe position | Va a la posición segura |
| **Go Zero** | Move to machine zero | Va al cero de máquina |

### Manual spindle / Husillo manual
- **EN:** Set **Spindle Speed** (RPM) and **Direction** (1 = CW). Hold **Spindle Start** to run,
  **Spindle Stop** to stop. Watch **Actual RPM** and the **At Speed** indicator.
- **ES:** Ajuste **Velocidad del Husillo** (RPM) y **Dirección** (1 = horario). Mantenga **Arranque
  Husillo** para girar, **Paro Husillo** para detener. Observe **RPM Real** y el indicador **A Velocidad**.

⚠️ **WARNING:** The spindle rotates the mandrel — keep clear and never run the spindle by hand with a
loose blank. / El husillo hace girar el mandril — manténgase alejado y nunca opere el husillo a mano
con un disco suelto.

---

## 8. Tool Setup / Configuración de Herramientas

**EN:** The turret has up to 4 slots. The recipe asks for a tool by **code** (e.g., 101), not by
slot. You tell the PLC which code is in which slot on the **Tool Setup** screen.

**ES:** La torreta tiene hasta 4 posiciones (slots). La receta pide una herramienta por **código**
(p. ej., 101), no por posición. Usted le indica al PLC qué código está en qué posición en la pantalla
**Configuración de Herramientas**.

**Default mapping / Mapeo por defecto:** Slot 1 → 101, Slot 2 → 102, Slot 3 → 103, Slot 4 → 104.

### Procedure / Procedimiento
1. **EN:** Open the **Tool Setup** screen.
   **ES:** Abra la pantalla **Configuración de Herramientas**.
2. **EN:** For each slot (1–4), enter the code of the tool physically installed there.
   **ES:** Para cada slot (1–4), ingrese el código de la herramienta instalada físicamente ahí.
3. **EN:** Press **Apply Tool Config** (a single press — press and release).
   **ES:** Presione **Aplicar Config. Herramientas** (una sola pulsación — presione y suelte).

📝 **NOTE:** If the recipe asks for a code that is not mapped, you get error **0x0308 / 0x0309 — Tool
code not mapped**. Enter the code in the correct slot and press Apply. / Si la receta pide un código
no mapeado, obtiene el error **0x0308 / 0x0309 — Código de herramienta no mapeado**. Ingrese el código
en el slot correcto y presione Aplicar.

---

## 9. Batch Production / Producción por Lotes

**EN:** To run several identical parts:
1. Keep the same recipe selected.
2. After each **Program Complete**, remove the finished part.
3. Load the next blank (Section 5) and start again.
4. The **Cycle Count** display increments with each completed program — use it to track quantity.

**ES:** Para producir varias piezas idénticas:
1. Mantenga la misma receta seleccionada.
2. Después de cada **Programa Completado**, retire la pieza terminada.
3. Cargue el siguiente disco (Sección 5) y arranque de nuevo.
4. El indicador **Conteo de Ciclos** aumenta con cada programa completado — úselo para controlar la cantidad.

---

## 10. Troubleshooting / Diagnóstico de Fallas

### "Machine won't start" decision flow / Flujo "La máquina no arranca"

```
Machine will not start / La máquina no arranca
        │
        ├─ Status shows ERROR? ───────────────► Read error text → fix cause → press Reset
        │  ¿Estado muestra ERROR?               Lea texto de error → corrija → presione Reinicio
        │
        ├─ Safety not green? ─────────────────► Check: E-Stop released? Door closed? Air ≥ 6 bar?
        │  ¿Seguridad no en verde?              Revise: ¿Paro liberado? ¿Puerta cerrada? ¿Aire ≥ 6 bar?
        │
        ├─ Drives not enabled? ───────────────► Enable drives/contactors on the HMI
        │  ¿Drives no habilitados?              Habilite drives/contactores en la HMI
        │
        └─ Waiting for sheet? ────────────────► Complete the two-hand sheet load (Section 5)
           ¿Esperando lámina?                   Complete la carga a dos manos (Sección 5)
```

### Common errors / Errores comunes

| Error (EN) | Error (ES) | Cause / Causa | Operator action / Acción del operador |
|------------|-----------|---------------|----------------------------------------|
| EMERGENCY STOP (0x0401) | PARO DE EMERGENCIA | E-Stop pressed / Paro presionado | Release E-Stop, press Reset / Libere el Paro, presione Reinicio |
| Safety Door Open (0x0402) | Puerta Abierta | Door open / Puerta abierta | Close door, Reset / Cierre la puerta, Reinicio |
| Air Pressure Low (0x0404) | Baja Presión de Aire | No/low air / Sin aire o bajo | Check air supply ≥ 6 bar / Revise suministro de aire ≥ 6 bar |
| Drives Not Ready (0x0403) | Drives No Listos | Drives off/fault / Drives apagados o falla | Enable drives; if it persists call Maintenance / Habilite drives; si persiste llame a Mantenimiento |
| X/Z Move Failed (0x0001/0x0002) | Fallo Movimiento X/Z | Obstruction / drive fault | Check for obstruction, Reset / Revise obstrucción, Reinicio |
| Hit Limit Switch (0x0111–0x0114) | Tocó Fin de Carrera | Axis at hard limit | Use Manual jog to move away, Reset / Use jog Manual para alejarse, Reinicio |
| Soft Limit (0x0101–0x0104) | Límite de Software | Move beyond travel | Reset; if recurring, call Maintenance / Reinicio; si reincide, llame a Mantenimiento |
| Motion Timeout (0x0307) | Tiempo Excedido de Movimiento | Axis stuck/binding | Check binding, Reset / Revise atascamiento, Reinicio |
| Tool not mapped (0x0308/0x0309) | Herramienta No Mapeada | Tool code not in table | Map code in Tool Setup (Section 8) / Mapee el código en Config. Herramientas (Sección 8) |
| Tool Rotation Timeout (0x0203) | Tiempo Excedido Torreta | Turret stuck | Check turret, Reset; if it persists call Maintenance / Revise torreta, Reinicio; si persiste llame a Mantenimiento |
| Spindle fault (0x0501–0x0503) | Falla de Husillo | VFD/spindle fault | Reset; if it persists call Maintenance / Reinicio; si persiste llame a Mantenimiento |

### Resume after pause vs. warm restart after error / Reanudar tras pausa vs. reinicio tras error

| Situation | EN | ES |
|-----------|----|----|
| After **Pause** | Press **Continue** to resume from the same line. Position is kept. | Presione **Continuar** para reanudar desde la misma línea. La posición se conserva. |
| After **Error** | Fix the cause → press **Reset**. The machine returns to a safe state; you then re-home (automatic at next start) and **reload the sheet** before running again. | Corrija la causa → presione **Reinicio**. La máquina regresa a estado seguro; luego se re-referencia (automático al siguiente arranque) y **recargue la lámina** antes de ejecutar de nuevo. |
| Power lost mid-cycle | The part in progress is scrapped. After power returns, Reset, re-home, and start a fresh sheet. | La pieza en proceso se descarta. Al regresar la energía, Reinicio, re-referencie e inicie una lámina nueva. |

📝 **NOTE:** **Reset** always returns the machine to a clean, safe, runnable state from anywhere it
stopped or faulted. / **Reinicio** siempre regresa la máquina a un estado limpio, seguro y operable
desde donde se detuvo o falló.

---

## 11. Preventive Maintenance / Mantenimiento Preventivo

⛔ **DANGER:** Apply lockout/tagout (Section 2) before any maintenance task. / Aplique bloqueo y
etiquetado (Sección 2) antes de cualquier tarea de mantenimiento.

### Daily / Diario
- [ ] **EN:** Air pressure ≥ 6 bar · Inspect tools for wear/damage · Clear chips and debris ·
      Test E-Stop · Check for air leaks.
- [ ] **ES:** Presión de aire ≥ 6 bar · Inspeccione herramientas por desgaste/daño · Retire viruta y
      residuos · Pruebe el Paro de Emergencia · Revise fugas de aire.

### Weekly / Semanal
- [ ] **EN:** Lubricate axis guides/ball screws per the lubrication chart · Check that limit and
      proximity sensors are clean and secure · Inspect cylinder mounts and air hoses.
- [ ] **ES:** Lubrique guías/husillos de bolas según la carta de lubricación · Verifique que los
      sensores de fin de carrera y proximidad estén limpios y firmes · Inspeccione montajes de
      cilindros y mangueras de aire.

### Periodic (per cycle count) / Periódico (según conteo de ciclos)
- [ ] **EN:** Inspect tool heads and replace worn tools (signs: poor surface finish, increased
      forming force, visible wear/galling) · Verify mandrel clamp holds firmly · Check turret
      indexing accuracy.
- [ ] **ES:** Inspeccione cabezales y reemplace herramientas desgastadas (señales: mal acabado
      superficial, mayor fuerza de conformado, desgaste/rayado visible) · Verifique que el bloqueo de
      mandril sujete firmemente · Revise la precisión del indexado de la torreta.

📝 **NOTE:** Set the cycle interval with Maintenance based on material and tooling. The HMI **Cycle
Count** helps schedule these checks. / Defina el intervalo de ciclos con Mantenimiento según el
material y herramental. El **Conteo de Ciclos** de la HMI ayuda a programar estas revisiones.

---

## 12. Status & Message Glossary / Glosario de Estados y Mensajes

| Status (EN) | Estado (ES) | Meaning / Significado |
|-------------|-------------|------------------------|
| Stopped | Detenido | Idle, ready to start / Inactivo, listo para arrancar |
| Manual Mode | Modo Manual | Manual jog/home active / Jog/referenciado manual activo |
| Starting… | Arrancando… | Enabling drives, pre-checks / Habilitando drives, verificaciones |
| Pre-scanning… | Pre-verificando… | Validating recipe / Validando receta |
| Homing… | Referenciando… | Finding home position / Buscando posición de referencia |
| Waiting for sheet… | Esperando lámina… | Sheet loading sequence (Section 5) / Secuencia de carga (Sección 5) |
| Running | Ejecutando | Program executing / Programa en ejecución |
| Paused | Pausado | Feed hold, awaiting Continue / Pausa, esperando Continuar |
| Tool Change | Cambio de Herramienta | Changing tool / Cambiando herramienta |
| Program Complete | Programa Completado | Finished OK / Terminado correctamente |
| ERROR | ERROR | Fault — read error text / Falla — lea el texto de error |

📝 **NOTE:** The HMI shows English and Spanish text simultaneously (`StatusMsg` / `StatusMsg_ES`,
`ErrorText` / `ErrorText_ES`). / La HMI muestra texto en inglés y español simultáneamente.

---

## 13. Need Help? / ¿Necesita Ayuda?

| Issue / Asunto | Contact / Contacto |
|----------------|--------------------|
| Programming / recipe changes — Cambios de programa/receta | Maintenance / Mantenimiento |
| Mechanical / electrical issues — Problemas mecánicos/eléctricos | Maintenance / Mantenimiento |
| Safety concerns — Asuntos de seguridad | Supervisor |

---

*Bilingual operator manual (EN/ES). For electrical/wiring detail see `Program/docs/Wiring_Diagram.md`.
Terminology matches the HMI tags in `HMI_Tag_Guide.md`.*
