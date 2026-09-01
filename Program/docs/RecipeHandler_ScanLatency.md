# FB_RecipeHandler — Inter-Segment Scan Latency

**Status:** Proposal / analysis only — **no program files changed.**
**Date:** 2026-09-02
**Scope:** `Program/05_RecipeHandler.scl` only. No DB, no HMI tag, no FB_Process change.
**Related:** `MotionSmoothing.md` (this supersedes its §2 "scan dead time" paragraph and its item #4)

---

## 1. Summary

Between the completion of one recipe move and the start of the next, `FB_RecipeHandler`
burns **4 PLC scans** doing nothing mechanically useful. Two of them are pure state-machine
bookkeeping and can be removed by fusing state transitions.

| | Dead scans | Change |
|---|---|---|
| Today | 4 | — |
| Proposed | **2** | ~12 added lines + one block relocated |
| Theoretical floor | 2 | limited by the `MC_MoveAbsolute` Execute edge, see §4 |

The two remaining scans are **not** removable without redesigning `FB_Axis_AbsPos`, which is
shared with `FB_ManualMode`. §4 shows why, with a scan-by-scan trace. That analysis is the
main reason this document exists — the "obvious" 4→1 version is not merely risky, it is
**functionally broken**, and it fails in a way that mimics a known past fault.

**Honest sizing before you read further:** at an assumed 10 ms OB1 cycle this saves ~20 ms per
recipe line, against roughly 400 ms of accel+decel ramp per segment caused by the TO jerk
limiter (`MotionSmoothing.md` §2). That is about a 5 % gain. **OB1 max cycle time has never
been measured on this machine** — that number should be recorded before deciding whether this
is worth doing at all. If the scan is 30 ms, the saving is 60 ms/line and the case is much
stronger.

---

## 2. How the 4 scans arise

### Execution context

- `OB1` calls `fbProcess` once per scan (`08_Main_OB1.scl:231`).
- `FB_Process` calls `#fbRecipeHandler` once, unconditionally (`06_MainProcess.scl:3863`).
- `FB_RecipeHandler` runs `CASE #state OF` (`05:1187`), which executes **exactly one state
  per scan**, and then calls the motion FBs **after** the CASE (`05:1831-1832`).

Because the motion FBs are called *after* the state machine, an output they produce at the end
of scan *k* is first visible to the state machine in scan *k+1*.

### Trace

Let **scan A** be the scan in which `MC_MoveAbsolute.Done` first goes TRUE — i.e. the axis has
finished decelerating and is at target.

| Scan | State executed | What happens | Necessary? |
|---|---|---|---|
| A | 30 `STATE_WAIT` | reads *stale* `Done`=FALSE; the FB call at `:1831` then sets `Done` | — (motion ends here) |
| A+1 | 30 `STATE_WAIT` | sees `Done`, `currX:=targX`, → `STATE_NEXT` (`:1396-1399`) | sampling latency — irreducible |
| A+2 | 60 `STATE_NEXT` | `lineIndex+1`, `SingleStepMode` test, → `STATE_READ` (`:1637-1644`) | **removable** |
| A+3 | 10 `STATE_READ` | `targX`/`targZ` from the line, `CASE CMD` → `STATE_EXEC` (`:1215-1216`, `:1302-1303`) | **removable** on the motion path |
| A+4 | 20 `STATE_EXEC` | velocity calc, `bTrigMove:=TRUE` (`:1371`); FB call at `:1831` issues the new `MC_MoveAbsolute` | needed |

The new pulse train therefore begins at the *end* of scan A+4 — **4 scans** after the previous
one ended.

### Correction to `MotionSmoothing.md`

That document (`:63-66`) states **3** extra scans, listing
`STATE_WAIT → STATE_NEXT → STATE_READ → STATE_EXEC`. That counts the three *transitions* and
omits scan A+1 — the WAIT scan that *detects* `Done` — which is itself entirely dead. The
correct figure is **4**. Its line references (`:613`, `:1084`, `:529-541`, `:625`, `:435`) are
also stale against the current file.

### Was the 4-scan structure deliberate?

Partly. There is **no comment anywhere claiming it is intentional**, and `MotionSmoothing.md`
item #4 already lists it as removable waste, so at least two of the scans are an artifact of
the conventional one-state-per-scan SCL idiom.

But one scan of it is **load-bearing and was never documented as such**: `MC_MoveAbsolute`
requires a rising edge on `Execute`, so at least one scan with `Execute` low must separate two
consecutive moves. The present structure supplies three such scans, so nobody ever had to think
about it. Any change here must preserve exactly that property. See §4.

---

## 3. Proposed change

Two independent edits. Each removes one scan; they stack.

| Applied | A+1 | A+2 | A+3 | A+4 | Dead scans |
|---|---|---|---|---|---|
| Neither (today) | WAIT detects → 60 | NEXT → 10 | READ → 20 | EXEC **launch** | 4 |
| Edit 1 only | WAIT+NEXT → 10 | READ → 20 | EXEC **launch** | — | 3 |
| Edit 2 only | WAIT → 60 | NEXT → 10 | READ+EXEC **launch** | — | 3 |
| **Both** | **WAIT+NEXT → 10** | **READ+EXEC launch** | — | — | **2** |

### Edit 1 — fold `STATE_NEXT` into `STATE_WAIT`

Append to the end of state 30's `ELSE` branch, **after** the Error / `tonMoveTimeout.Q` block
at `:1418-1441`. No existing line is modified.

```scl
// --- STATE_NEXT folded into this scan (saves one scan per line) ---
// Guarded on #state = STATE_NEXT so the Error / tonMoveTimeout branches above,
// which write STATE_ERROR, always win. Body is identical to state 60, which
// stays in place for every other caller (spindle, dwell, tool, ATMO, cylinder).
IF #state = STATE_NEXT THEN
    #lineIndex := #lineIndex + 1;
    IF "DB_HMI".SingleStepMode THEN
        #state := STATE_STEP_WAIT;
    ELSE
        #state := STATE_READ;
    END_IF;
END_IF;
```

Why the guard rather than editing the three completion branches: it avoids triplicating the
body, and it makes the precedence explicit — if anything earlier in the scan wrote
`STATE_ERROR`, `#state` is no longer 60 and the advance is skipped. The Pause path at `:1383`
returns via its own `IF` and never reaches this code.

State 60 is **not** deleted. Roughly a dozen other sites still transition to it
(`:1232`, `:1264`, `:1300`, `:1307`, `:1368`, `:1484`, `:1519`, `:1553`, `:1570`, `:1620`, …).

### Edit 2 — hoist `STATE_EXEC` out of the `CASE`

Pure relocation. Remove the `20:` branch from the `CASE` and place its body verbatim after
`END_CASE;` (`:1824`) and **before** the `fbMoveX`/`fbMoveZ` calls (`:1831`):

```scl
END_CASE;

// -------------------------------------------------------------------------
// STATE_EXEC (20) -- deliberately OUTSIDE the CASE above.
// A motion line selected by STATE_READ in this scan also launches in this
// scan, saving one scan per line. Must stay AFTER the CASE and BEFORE the
// fbMove calls below, or the Execute edge described in ScanLatency §4 is lost.
// Only CMD_RAPID / CMD_LINEAR reach state 20, so every non-motion CMD still
// gets its own scan -- required, because STATE_READ writes the BackSupport
// solenoid flags directly for CMD_ATMO (:1290-1299) and two lines sharing a
// scan would collide.
// -------------------------------------------------------------------------
IF #state = STATE_EXEC THEN
    ... existing body, :1318-1374, unchanged ...
END_IF;
```

No logic inside the body changes — including `#tonMoveTimeout(IN := FALSE, …)` at `:1372` and
the `IF NOT #bMoveX AND NOT #bMoveZ THEN #state := STATE_NEXT` skip branch at `:1367-1368`.

The `CMD_ATMO` collision constraint is satisfied structurally rather than by a guard: only the
`CMD_RAPID, CMD_LINEAR:` branch (`:1302-1303`) sets `STATE_EXEC`, so no other command can
reach the hoisted block in READ's scan.

### Edit 3 — `pauseReturnState` default hygiene (recommended, same commit as Edit 2)

`:1023` declares `pauseReturnState : Int := 20;  // 20 = STATE_EXEC (safe default)` and `:1135`
resets it to `STATE_EXEC`. Change both to `STATE_READ`. Rationale in §5.2.

---

## 4. Why the floor is 2, not 1 — the rejected 4→1 variant

The natural next step is to fuse all four scans: on `Done`, advance `lineIndex`, peek the next
line, and if it is `CMD_RAPID`/`CMD_LINEAR` do the whole read+compute+launch in scan A+1. That
gives 1 dead scan. **It does not work.** This section is the evidence.

### The mechanism

`MC_MoveAbsolute` starts a job on a **rising edge** of `Execute`. `FB_Axis_AbsPos`
(`03_AxisControl.scl:55-93`) manages that edge with `execLatch`. Its per-call order is:

1. `:57-59` — rising edge on the FB's `Execute` input → `doneLatch := FALSE`
2. `:60` — `prevExecute := Execute`
3. `:63-65` — `IF Execute AND NOT execLatch AND NOT doneLatch THEN execLatch := TRUE`
4. `:68-77` — **`MC_MoveAbsolute(Execute := execLatch, …)`** ← the value MC actually samples
5. `:80-89` — `IF MC.Done THEN execLatch := FALSE; doneLatch := TRUE; ELSIF MC.Error OR MC.CommandAborted THEN execLatch := FALSE`
6. `:92` — `Done := doneLatch OR MC.Done`

Note that step 4 reads `execLatch` **before** step 5 clears it. So in the scan where MC first
reports `Done`, MC was still called with `Execute = TRUE`.

### Trace: what MC samples

`E` = the FB's `Execute` input, i.e. `#bTrigMove AND #bMoveX`.

| Scan | Variant | `E` in | `execLatch` at step 4 | MC sees | Edge? |
|---|---|---|---|---|---|
| A | both | FALSE | TRUE | TRUE | — (`Done` set, step 5 clears `execLatch`) |
| A+1 | **4→1 (fused)** | **TRUE** | step 1 clears `doneLatch`, step 3 re-arms → **TRUE** | **TRUE** | ❌ **none — TRUE→TRUE** |
| A+1 | **4→2 (proposed)** | FALSE | FALSE | **FALSE** | — (this is the required low) |
| A+2 | **4→2 (proposed)** | TRUE | TRUE | TRUE | ✅ **rising** |

In the 4→1 variant MC's `Execute` input is never sampled low between the two moves, so the new
`Position` is **not latched and no move starts**.

### Why it then fails loudly and misleadingly

With `Execute` held TRUE on a completed job, `MC_MoveAbsolute.Done` stays TRUE. Step 6 therefore
reports `Done = TRUE` again in scan A+2, the fused WAIT sees it, advances `lineIndex`, and
repeats — **the recipe races to the END marker at roughly one line per scan with the axes
stationary.**

That symptom is close to indistinguishable from the recipe-load partial-copy fault already in
this project's history ("a 999-line recipe … ran ~900 zero-length moves with the HMI counting
up", CLAUDE.md, 2026-08-13). An engineer seeing it on the machine would very plausibly go
looking at `FB_RecipeLoader` first.

### Could 4→1 be rescued?

Only by changing `FB_Axis_AbsPos` — e.g. adding an input that forces `execLatch := FALSE` for
one call, or calling the MC instance twice in a scan to manufacture a low. That FB is shared
with `FB_ManualMode` (`03_AxisControl.scl:29`), so manual jog, MDI moves and the homing paths
would all enter the blast radius to buy one further scan (~10 ms). **Not recommended.**

### Second, independent reason to reject 4→1

The fused version peeks `Lines[#lineIndex]` *before* `STATE_READ`'s bound check
`IF #lineIndex >= #LineCount` (`:1211`). On the last line that is an out-of-range access on an
`Array[0..999]`.

**This project contains only two organization blocks** — `OB100 "Startup"`
(`00_Configuration.scl:493`) and `OB1 "Main"` (`08_Main_OB1.scl:198`). There is **no OB121**,
so a programming error is not caught: the CPU goes to STOP. On a machine with a part in the
chuck and the spindle turning, that is a materially worse failure than the 20 ms it was trying
to save.

The proposed 4→2 change never bypasses that guard, because `STATE_READ` still runs normally.

---

## 5. Correctness analysis of the proposed change

### 5.1 The `Execute`-low scan is preserved

The single required low scan is A+1. `STATE_WAIT` sets `#bTrigMove := FALSE` at `:1380` on
entry to every WAIT scan, and Edit 1 does not touch `#bTrigMove`. So in scan A+1, `E` is FALSE
and `execLatch` was cleared at step 5 of scan A — MC samples FALSE. Verified in the §4 table.

**This is the invariant a reviewer should check first on any future change to this path:**
*at least one scan in which `#bTrigMove AND #bMove*` is FALSE must separate two moves on the
same axis.*

### 5.2 The hoisted `STATE_EXEC` has a second entry point

`#state := #pauseReturnState` (`:1787`, in `STATE_PAUSE_RETURN` / 803) can in principle deliver
control to state 20. If it ever did, the hoisted block would run in the *same* scan in which
803 set `#bTrigMove := FALSE` (`:1780`), overwrite it to TRUE, and — because 803 held
`#bTrigMove := TRUE` throughout (`:1763`) — destroy the falling edge. That is precisely the
§4 failure, reintroduced on the pause-resume path.

All five pause entry points were checked. **Every one writes `pauseReturnState` explicitly, and
none writes `STATE_EXEC`:**

| Site | Paused from | `pauseReturnState` |
|---|---|---|
| `:1391` | `STATE_WAIT` (motion) | `STATE_READ` |
| `:1533` | `STATE_SPINDLE_WAIT` | `STATE_SPINDLE_WAIT` |
| `:1547` | `STATE_DWELL` | `STATE_DWELL` |
| `:1584` | `STATE_SPINDLE_STOP_WAIT` | `STATE_SPINDLE_STOP_WAIT` |
| `:1616` | `STATE_CYL_GOTO_WAIT` | `STATE_CYL_GOTO` |

So the hoist is safe **today** — but safe by accident. `STATE_EXEC` survives only as the
declaration default (`:1023`) and the Reset clear (`:1135`), both commented "safe default".
That comment went stale on 2026-07-09, when resuming a motion pause via `STATE_EXEC` was found
to silently skip the remainder of the interrupted line and was changed to `STATE_READ`
(see the comment block at `:1385-1391`).

Hence **Edit 3**: set both defaults to `STATE_READ`. It is independently more correct, and it
removes the trap for whoever adds a sixth pause entry point and forgets the assignment.

### 5.3 `tonMoveTimeout` still resets between lines

`:1179` drives it with `IN := #state = STATE_WAIT`, evaluated at the top of the scan using the
state left at the end of the previous scan. After Edit 1, scan A+1 ends with `#state = 10`, so
in scan A+2 the timer is called with `IN := FALSE` and `ET` resets. `STATE_EXEC`'s explicit
`#tonMoveTimeout(IN := FALSE, …)` at `:1372` also still runs. No risk of a spurious `16#0008`
(`:1441`).

*(This was a real hazard in the rejected 4→1 variant, where `#state` never leaves 30 and `ET`
would accumulate across the whole program.)*

### 5.4 Other behaviours checked

| Concern | Result |
|---|---|
| `SingleStepMode` | Edit 1 replicates the `:1640-1644` test exactly; `STATE_STEP_WAIT` still reached |
| Stop | Global handler at `:1157` runs **before** the CASE, covers all states, sets `bTrigMove := FALSE` at `:1166`. Unchanged |
| Pause | Checked at the top of WAIT (`:1383`) before the completion check, so a Pause in A+1 wins and the fold does not run. Pause is not tested in READ or EXEC — same as today. Response latency **improves** (WAIT is revisited more often) |
| Sub-0.01 mm line | `:1367-1368` still sends it to `STATE_NEXT`, which still exists in the CASE. `currX/currZ` not updated in that branch — pre-existing, unchanged |
| Per-axis `doneLatch` staleness | `STATE_EXEC` re-triggers every axis that `bMove*` marks active in the same scan the FB is called, clearing its `doneLatch`. Invariant preserved: `bMove*` and the Execute edge are always computed in one scan |
| Error precedence in WAIT | Edit 1's guard is `#state = STATE_NEXT`; the Error / timeout branches write `STATE_ERROR` first and therefore win |
| Array bounds | `STATE_READ`'s `:1211` guard is untouched and still executes before any `Lines[]` access |
| External dependencies on `#state` | None. `#state` is a `VAR`, not `VAR_OUTPUT`. `FB_Process` reads only `.CurrentLine`, `.Progress`, `.ActiveFeedrate`, `.Busy`, `.Done`, `.Error`, `.ErrorID`, `.SpindleReq*`, `.ToolChangeReq`, `.ToolReqNumber` |
| Reset paths (CLAUDE.md 4 checkpoints) | No new FB var, no new timer, no new actuator command, no new HMI field → nothing new to clear |
| Download impact | No DB interface change → no instance-DB re-initialisation, no Retain implications |

### 5.5 Known regressions

1. **Online diagnostics.** After both edits, `#state` never rests at 20 or 60 during a motion
   run — an online watch of the instance DB will alternate 30 / 10 only. Nothing in the program
   depends on this, but anyone used to watching the state machine step through READ→EXEC→NEXT
   should know it changed.
2. **Scan-time distribution.** Work previously spread over three scans now lands in two. The
   fused READ+EXEC scan adds one `SQRT`, two REAL divisions and several clamps — order tens of
   microseconds on an S7-1214C, negligible against a millisecond-scale scan, but it does push
   OB1 *max* cycle time slightly upward. Record max cycle time before and after.

---

## 6. Test plan

The state space here is small and enumerable, and every case below is deterministic — not a
race — so PLCSIM is genuinely sufficient for the logic. Only the last item needs the machine.

### PLCSIM

| # | Case | Expected |
|---|---|---|
| 1 | Two consecutive `CMD=1` lines | Both moves execute; watch `#lineIndex` advance and both axes reach target |
| 2 | Long program, run to END | Completes with correct final position; **`16#0008` must not fire** (§5.3) |
| 3 | Last line / END marker | `STATE_DONE` reached; no array access beyond `LineCount-1` |
| 4 | Motion line followed by `CMD_ATMO` (`CMD=41 P1/P2/P3`) | Solenoid flags correct; ATMO line still occupies its own scan |
| 5 | Motion → `CMD=20/21` spindle, `CMD=4` dwell, `CMD=10` tool | Each still routed via `STATE_NEXT`/`STATE_READ` normally |
| 6 | Sub-0.01 mm line between two real moves | Skipped via `:1367`, no stall |
| 7 | `SingleStepMode` ON before start, and toggled mid-run | `STATE_STEP_WAIT` entered; `StepNext` advances one line |
| 8 | Pause during a move, then Continue | Retract → hold → return → resumes the *remainder* of the interrupted line, not the next line |
| 9 | Pause during dwell / spindle wait / `CMD=40`, then Continue | Resumes the same non-motion state (regression guard for Edit 3) |
| 10 | Stop mid-move | `STATE_STOPPING` → `STATE_DONE`, axes halt |
| 11 | Reset mid-run, then Start | Clean restart from line 0, first move executes (guards the edge logic after `:1135`) |
| 12 | Warm restart from `savedLineIndex` | First move after restart executes |

Case 11 and the first move of case 1 are the ones that would catch an `Execute`-edge mistake:
the failure signature is **axes stationary while `CurrentLine` counts up**.

### Machine

| # | Case | Expected |
|---|---|---|
| 13 | Record OB1 **max** cycle time before and after | Small increase at most; gives the real value of the saving |
| 14 | Time one full pass of a known program, before and after | ~2 scans × cycle time saved per motion line |
| 15 | Inspect surface finish against a baseline part | No new chatter. Restarting ~20 ms earlier means the drive may still be settling its following error at the corner — this is the one thing PLCSIM cannot answer |

---

## 7. Recommendation and sequencing

- **Do the 4→2 change. Do not attempt 4→1** unless someone is willing to redesign
  `FB_Axis_AbsPos` and re-validate manual jog and homing with it.
- **Two commits**: (1) Edit 1, (2) Edit 2 + Edit 3. They are independent and each removes one
  scan, so a bisect point between them is free.
- **Measure OB1 max cycle time first.** It decides whether this is a 5 % gain or a 15 % one,
  and it is item 0 of `MotionSmoothing.md` §4 anyway.
- **Sequencing caveat, non-technical:** this change lands in `FB_RecipeHandler`, which also
  carries the unmerged chunked-recipe work on `feat/recipe-slots-and-batching` — approved for
  three of four work groups, with the recipe transfer still gated on a hardware test. Landing a
  motion-path change alongside it means the two get validated in the same download. Worth
  deciding deliberately rather than by default.
- **Context:** at current TO settings the jerk limiter costs ~400 ms per segment
  (`MotionSmoothing.md` §2) against the ~20 ms this recovers. If both are on the table, the
  smoothing-time change is roughly 20× the gain for less code risk. This change is worth doing
  on its own merits — it is small, contained and removes real waste — but it should not be
  presented as the fix for the machine's motion quality.

---

## 8. Claim provenance

For the reviewer's benefit — what was verified against the code versus inferred.

| Claim | Basis |
|---|---|
| One handler state per scan | `08:231`, `06:3863`, `05:1187` — read directly |
| 4 dead scans, not 3 | Derived from FB call order (`05:1831` after `:1187`); `MotionSmoothing.md:63` disagrees and is wrong |
| `MC_MoveAbsolute` needs a rising edge | Siemens/PLCopen semantics, corroborated by the existence and comment of `execLatch` (`03:51`) |
| 4→1 loses the edge | Step-by-step trace of `03:55-93`, §4 table |
| No OB121 exists | `grep ORGANIZATION_BLOCK Program/*.scl` — only `Startup` and `Main` |
| No external reader of `#state` | `grep fbRecipeHandler` across `06_MainProcess.scl` |
| All 5 pause sites set `pauseReturnState` | `grep pauseReturnState` — table in §5.2 |
| Drive settling behaviour at the corner | **Not verified** — machine test 15 |
| OB1 cycle time ≈ 10 ms | **Assumption inherited from `MotionSmoothing.md`, never measured** |
