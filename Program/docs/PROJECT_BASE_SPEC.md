Project Base Specification — Reusable defaults for new machine projects
=====================================================================

Purpose
-------
Provide a concise, structured, machine- and AI-friendly specification of the default, reusable parts of this PLC project
that should be reused for new projects. This excludes G-code parsing/execution specifics — focus is on infra, naming,
state machine, HMI/DB conventions, diagnostics, safety and IO handler contracts so an automated tool (or an engineer)
can derive a new project scaffold quickly and consistently.

Format & intent
---------------
- Human-readable Markdown with structured YAML examples for direct parsing by tools or ML agents.
- Keep conventions explicit: name patterns, DB schemas, state enums, error code ranges, and required FB interfaces.
- This is a "base profile" — concrete projects may add FBs/fields, but should preserve these core contracts.

Scope (what to standardize)
---------------------------
- Process state machine and lifecycle (START, PRE_SCAN, HOMING, RUNNING, PAUSED, STOPPING, ERROR, COMPLETE)
- Naming conventions for FBs, DBs, UDTs and tags
- HMI tag groups and minimal required fields
- Diagnostic and error DBs (what to always include)
- Safety handler, IO handler, error/alarm handler contracts
- FB interface contracts (inputs/outputs that other code depends on)
- Error code ranges and semantics

Conventions (naming & placement)
--------------------------------
- Files / code:
  - FB_*.scl for function blocks (FB_Process, FB_SafetyHandler, FB_IOHandler, FB_AlarmManager, etc.)
  - DB_*.scl for data blocks (DB_HMI, DB_MachineConfig, DB_Diagnostic, DB_Error)
  - UDT_*.scl for user data types (UDT_RecipeLine)
- Symbol names:
  - Global DBs: DB_<Purpose> (e.g., DB_HMI, DB_Diagnostic, DB_Error)
  - FBs: FB_<Role> (FB_Process, FB_SafetyHandler)
  - Error codes: 16#XXXX with grouped ranges (see below)
- Tag prefixes in HMI: DB_HMI.* for operator controls, DB_Diagnostic.* for developer debug readouts

State machine (canonical)
-------------------------
Use integer constants for states; preserve the following set and meanings as a baseline:

YAML example:

```yaml
STATE:
  STOPPED: 0         # Idle, drives off
  MANUAL: 5          # Manual mode active
  STARTING: 10       # Pre-run setup
  PRE_SCAN: 12       # Validate program / readiness
  HOMING: 15         # Homing sequence
  RUNNING: 20        # Main execution
  PAUSED: 25         # Paused - only Continue resumes
  STOPPING: 18       # Controlled stop preparing safe state
  ERROR: 999         # Error state - requires ack/restart
  COMPLETE: 100      # Program complete (OK)
```

State machine rules:
- Avoid long blocking operations inside a single PLC scan. Use pre-scan / batch processing for heavy tasks.
- Prefer small, deterministic state transitions with explicit "request" flags (publish/subscribe style) instead of direct calls.
- External FBs (spindle, axis, tools) should be driven through request flags and their Done/Error outputs inspected by the supervisor.

DB contracts (required fields)
----------------------------
These DBs (and key fields) form the minimal cross-module contract. Keep types stable between projects.

DB_HMI (operator <-> PLC)
YAML:
```yaml
DB_HMI:
  Btn_Start: Bool
  Btn_Stop: Bool
  Btn_Pause: Bool
  Btn_Reset: Bool
  Btn_Continue: Bool
  ActiveProgram: Int
  TotalLines: Int
  CurrentLine: Int
  ProgressPercent: Real
  Feedrate: Int
  FeedrateOverride: Real
  ErrorText: String
  ErrorDetail: String
```

DB_Diagnostic (developer focused)
```yaml
DB_Diagnostic:
  CurrentProgram: Int
  Recipe_CurrentLine: Int
  Recipe_TargetX: Real
  Recipe_TargetZ: Real
  Recipe_Velocity: Real
  MoveX_Busy: Bool
  MoveX_Done: Bool
  MoveX_Error: Bool
  MoveZ_Busy: Bool
  MoveZ_Done: Bool
  MoveZ_Error: Bool
  Error_ProcessState: Int
  Error_Line: Int
  Error_Code: Word
  Error_Text: String
```

DB_Error (centralized alarm snapshot)
```yaml
DB_Error:
  Active: Bool
  Code: Word
  Severity: Byte  # 0=info,1=warn,2=error,3=fatal
  Source: String
  Line: Int
  TimeStamp: DTL
  Details: String
  History_Code: Array[1..10] of Word
```

DB_MachineConfig (machine parameters)
```yaml
DB_MachineConfig:
  RapidVelocity: Real
  MaxVelocity: Real
  MinVelocity: Real
  SafePos_X: Real
  SafePos_Z: Real
  Bypass_SafetyChecks: Bool
  Bypass_Drives: Bool
```

FB interface contracts (recommended)
-----------------------------------
- FB_Process (supervisor)
  - Inputs: Panel/HMI buttons, safety signals, IO handler, Axis TOs
  - Outputs: Running, IsPaused, Error, StatusID
  - Responsibilities: orchestrate lifecycle (pre-scan/homing/run/stop), coordinate FBs, copy HMI one-shot values to stable DBs, set diagnostic context

- FB_SafetyHandler
  - Inputs: EStop_OK, Door_Closed, AirPressure_OK, DriveReady signals, optional bypass flags
  - Outputs: SafeToRun, SafeToJog, ErrorCode
  - Responsibilities: centralize safety checks, return first-failure quickly, produce machine-level safety error codes

- FB_IOHandler (I/O abstraction)
  - Inputs/Outputs: grouped physical IO mapped into structured tags (digital_in[], digital_out[], analog_in[], analog_out[])
  - Responsibilities: provide a stable API for reading/writing IO, debounce/edge-detect inputs, expose status bits (DriveReady, HW limits)

- FB_AlarmManager / FB_ErrorManager
  - Inputs: NewError (edge), NewErrorCode, AcknowledgeError
  - Outputs: HasActiveError, ActiveErrorCode, ActiveErrorText, ActiveSeverity, ActiveSource, ActiveTime
  - Responsibilities: translate numeric codes to human text, keep history ring buffer, expose snapshot for HMI

- FB_RecipeHandler (executor) — domain-specific (can be swapped)
  - Inputs: Start, Stop, Pause, Reset, LineCount, Lines[] (UDT), Axis TO references
  - Outputs: Busy, Done, Error, ErrorID, CurrentLine, Request flags (ToolChangeReq, SpindleReq*, MoveReq*)
  - Important: should request external ops by flags; avoid driving hardware directly

- FB_SpindleControl
  - Inputs: Start, Stop, SetSpeed, Direction, Reset
  - Outputs: IsRunning, AtSpeed, ActualSpeed, Error, ErrorID

Error code ranges and mapping
-----------------------------
- Use grouped hex ranges so downstream systems and UIs can categorize easily:
  - Axis / Motion: 16#0001..16#00FF
  - Limits / Hardware: 16#0101..16#01FF
  - Tool / Peripherals: 16#0200..16#02FF
  - Recipe / Program logic: 16#0300..16#03FF
  - Safety: 16#0400..16#04FF
  - Spindle / Drive: 16#0500..16#05FF

Guidelines for HMI & operator flows
-----------------------------------
- Keep operator screens minimal: Program select, Start/Stop/Pause/Reset, Status (CurrentLine, Progress, ErrorText).
- Use a clear "Apply" pattern for engineer-level settings: HMI edits should be copied into stable DBs by FB_Process on operator request, not written directly to runtime DBs.
- Do not auto-guess or silently map critical missing items; show a clear instruction in DB_HMI.ErrorDetail and require operator action.

Diagnostic & telemetry best-practices
------------------------------------
- Always populate DB_Diagnostic with process context (CurrentProgram, CurrentLine, target positions, velocity).
- When raising an error, include the ProcessState and Line in DB_Diagnostic and make DB_Error snapshot contain human-friendly text.
- Keep an Error history ring buffer for post-mortem. Emit minimal telemetry for remote monitoring (states, active error codes, cycle counters).

Extension points (where to modify for new machines)
---------------------------------------------------
- Axis count: keep axis-agnostic FB interfaces (use TO/Axis objects) and parameterize axis lists in FB_Process.
- Peripherals: keep peripheral adapters (tool changer, custom turret, vacuum, sensors) behind a small FB adapter layer with the same contract.
- Spindle and motion drivers: keep a thin hardware adapter layer beneath the FB_SpindleControl / axis FBs.
- Recipe parser: keep recipe parsing and recipe execution separate. RecipeHandler should operate on UDTs, not text.

AI/Automation consumption hints
------------------------------
- The YAML examples above are intentionally structured. An AI can:
  - Read DB schemas and generate HMI tag lists.
  - Scaffold FB interfaces with given inputs/outputs.
  - Enforce naming and error-code constraints when generating new projects.
- When deriving new machine profiles, the AI should ask these minimal questions:
  1. Which axes and their names? (e.g., X,Z,Tool,Spindle)
  2. What safety signals are mandatory (EStop, Door, AirPressure, DrivesReady)?
  3. Which IO groups are required (digital_in/out, analog_in/out)?
  4. HMI display constraints (which fields to show)

Maintenance checklist (for new projects)
---------------------------------------
1. Copy this file into the new project root.
2. Populate DB_MachineConfig with machine-specific limits and bypass flags.
3. Define DB_HMI and DB_Diagnostic schemas and expose minimal operator tags.
4. Ensure FB_Process, FB_SafetyHandler and FB_IOHandler implement the state constants and DB names from this spec.
5. Implement hardware adapter FBs (spindle/axis/peripherals) that conform to the contracts above.

Versioning & traceability
-------------------------
- When deriving a new project, add a ProjectBaseVersion tag in top-level README and record the base commit/id used.
- Keep docs/*.md under source control with the code so generated manuals can be auto-updated.

End of specification.

