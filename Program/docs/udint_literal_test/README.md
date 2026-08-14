# UDInt literal gate test — procedure

**Question:** does TIA accept a bare integer literal **above `DInt` max (2,147,483,647)** when the
target is a `UDInt`, and does it store the right value?

**Why it matters:** `RecipeHeader.Checksum` is a `UDInt` and SpinningCam writes it as a bare
literal. Everything imported so far (`340461202`, `9593624`) sits *below* that line. A checksum is
effectively a uniform 32-bit number, so **about half of all future exports land above it.** If bare
literals fail there, half your recipes fail to import, apparently at random.

**Cost:** one import. No download required. Nothing in the running project is touched — the test
block is standalone and shares no name with anything.

---

## Steps

1. **Import.** TIA project tree → *External source files* → *Add new external file* → select
   `Test_UDInt_Literal.scl`. Right-click it → **Generate blocks from source**.

2. **Record what TIA says.** Either it generates `DB_UDIntLiteralTest` cleanly, or it reports errors.
   If there are errors, **note which line numbers** — that is the whole result. Screenshot it.

3. **Compile** the generated block (right-click → Compile). An import can succeed where a compile
   fails; both have to pass.

4. **Read the values back — do not skip this.** Open `DB_UDIntLiteralTest` and look at the
   **Start value** column for all five tags. This is the step that catches the dangerous outcome:
   TIA accepting the literal and silently storing something else.

5. **Fill this in:**

   | Tag | Expected start value | What TIA shows |
   |---|---|---|
   | `A_Low` | 340461202 | |
   | `B_DIntMax` | 2147483647 | |
   | `C_OverBy1` | 2147483648 | |
   | `D_UDIntMax` | 4294967295 | |
   | `E_Prefixed` | 4294967295 | |

6. **Clean up.** Delete `DB_UDIntLiteralTest` and remove the external source file. It serves no
   purpose in the project once read.

---

## What each outcome means

| Result | Meaning | Action |
|---|---|---|
| All five import, compile, and show the expected values | Bare literals are safe at any magnitude | Tell SpinningCam to ignore the `UDINT#` request; drop the `--check` warning |
| `C`/`D` rejected, `E` accepted | The prefix is **mandatory** above `DInt` max | SpinningCam must emit `UDINT#`; run `--stamp` on any export until they do |
| `C`/`D` accepted but show a **wrong value** (negative, 0, or wrapped) | Worst case — silent corruption | Same action as above, and treat it as urgent: a wrong checksum in the DB means `16#0316` on a good recipe, with nothing pointing at the cause |
| Everything is rejected | The test itself is wrong, not TIA | Send me the error text |

---

## While you are in there

`E_Prefixed` is the control. If `D` fails and `E` passes, that is a clean, unambiguous result and
the answer is simply "always emit the prefix" — which costs SpinningCam one string concatenation
and closes the question permanently.

Report back with step 5's table filled in and I will update the tooling, the letter to SpinningCam,
and `CLAUDE.md` to match whatever it says.
