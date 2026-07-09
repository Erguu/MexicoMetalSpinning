> can you check if tool head lock cylinder might have a problem after stopping and starting again a recipe. it retracted itself after extended it once. just check

● Let me read the relevant code to trace the lock state during stop/restart.

● Searched for 1 pattern, read 1 file (ctrl+o to expand)

● Now let me check what state STOP_GOHOME exits to, and the STARTING state homing check:

● Read 1 file (ctrl+o to expand)

● Let me check the RUNNING state for any unexpected transitions that could cause the lock to retract:

● Searched for 2 patterns, read 1 file (ctrl+o to expand)

● Let me check how AtSetpoint is generated in FB_CylinderControl without a physical sensor:

● Searched for 1 pattern, read 1 file (ctrl+o to expand)

● Let me also check the STOPPED state and how bStartSeq is managed on restart:

● Searched for 2 patterns, read 1 file (ctrl+o to expand)

● Let me check the OB1 call order and also look at the COMPLETE state restart path:

● Searched for 1 pattern, read 1 file (ctrl+o to expand)

● Let me check the COMPLETE state restart path:

● Read 1 file (ctrl+o to expand)

● Now I have a complete picture. Here's what I found:

  ---
  ToolHeadLock Analysis: Stop → Restart Sequence                                                                                                                                                                                             
  What the code does on stop/restart                                                                                                                                                                                                         
  The logic is correct in principle but has a specific vulnerability:

  Stop: State 20 → 18 (STOPPING) → Cmd_Extend = FALSE immediately → spring retracts → State 29 (5s wait) → State 19 (home) → State 0 (STOPPED).

  Restart: State 0 → 10 → 17 (LOCK_EXTEND_WAIT) → 1s pre-delay → Cmd_Extend = TRUE → cylinder extends → AtSetpoint = TRUE → State 20 (RUNNING). Cmd_Extend = TRUE stays throughout.

  This is correct when the sensor works.

  ---
  The actual problem: state 17 has no timeout fallback

  State 17 only exits one way:
  17:
      IF "DB_Cylinder_ToolHeadLock".AtSetpoint THEN
          #State := STATE_RUNNING;
      END_IF;

  If AtSetpoint never becomes TRUE (sensor miss, alignment issue), the machine is stuck in state 17 forever. The lock physically extends (Cmd_Extend = TRUE, Sol_A = TRUE), but the main state machine never reaches RUNNING.

  Meanwhile, FB_CylinderControl (Mode 1, Timeout_Extend = T#3S) loops every 3s:
  - State 1 (EXTENDING) → timeout 3s → State 10 (ERROR, Sol_A = FALSE for ~1 scan) → auto-clears because Cmd_Extend = TRUE → State 0 → State 1 → repeat

  The cylinder stays physically extended (one-scan gap is too short for spring to move), but AtSetpoint is never TRUE → state 17 never exits.

  When the operator presses Stop (thinking the machine hung), state goes to 18 → Cmd_Extend = FALSE → lock retracts. The operator sees: "it extended, then retracted."

  ---
  Documentation inconsistency (misleading)

  Two comments claim a timer fallback exists for state 17 that does not exist in the code:

  ┌───────────────────────┬───────────────────────────────┬───────────────────────────────────┐
  │       Location        │         Comment says          │             Code has              │
  ├───────────────────────┼───────────────────────────────┼───────────────────────────────────┤
  │ 08_Main_OB1.scl:267   │ "or after 2s timer fallback"  │ no fallback in state 17           │
  ├───────────────────────┼───────────────────────────────┼───────────────────────────────────┤
  │ 02_DataBlocks.scl:765 │ "tonLockWait.Q (5s fallback)" │ tonLockWait only runs in state 29 │
  └───────────────────────┴───────────────────────────────┴───────────────────────────────────┘

  ---
  Secondary issue: lock retracts before axes stop

  In state 18 (STOPPING), Cmd_Extend = FALSE (spring retracts) happens the same scan the stop is received. fbRecipeHandler.Busy may still be TRUE — axes still moving. The lock releases while motion is in progress.

  ---
  Recommended fix

  State 17 needs an error timeout. If AtSetpoint is not received within ~5s of Cmd_Extend going TRUE, go to STATE_ERROR with a clear message rather than hanging:

  17: // LOCK_EXTEND_WAIT
      #StatusID := 17;
      IF "DB_Cylinder_ToolHeadLock".AtSetpoint THEN
          #State := STATE_RUNNING;
      ELSIF "DB_Cylinder_ToolHeadLock".Error THEN
          // Sensor did not confirm within Timeout_Extend (T#3S) — abort
          #newErrorFlag := TRUE;
          #newErrorCode := 16#0012;
          "DB_HMI".ErrorText   := 'ToolHeadLock: extend timeout';
          "DB_HMI".ErrorDetail := 'Lock sensor (AtSetpoint) not confirmed - check cylinder/sensor';
          #State := STATE_ERROR;
      END_IF;

  This uses the FB's own Timeout_Extend = T#3S as the fallback instead of a duplicate timer. The machine fails safely with a clear error rather than hanging silently.

  Also fix the stale comments in 02_DataBlocks.scl:765 and 08_Main_OB1.scl:267.

  Want me to implement this fix?