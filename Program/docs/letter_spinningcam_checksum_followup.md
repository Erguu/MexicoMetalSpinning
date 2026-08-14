# To SpinningCam — checksum cross-verified on your test file; one emitter defect

**Date:** 2026-08-14
**Answers:** `reply_spinningcam_recipe_checksum.md`
**Our status:** UDT fields, loader verification and offline tooling are all committed. Not yet
compiled or imported into TIA.

---

## Confirmed

**We agree on 1383, and on every intermediate.** We ran your table against our implementation rather
than eyeballing it:

| g | sumA | sumB |
|---|---|---|
| 0 | 140 | 140 |
| 1 | 140 | 280 |
| 2 | 391 | 671 |
| 3 | 490 | 1161 |

Identical, line for line. Two independent implementations agreeing on the intermediates as well as
the result is as good as this gets without hardware. Thank you for pinning it with a regression test
— please keep that test, because the day it goes red is the day someone "optimises" one of the two
accumulators away.

**Chunk size as a parameter with a live preview is better than we asked for.** The dialog showing
where the END marker lands is exactly the thing that would have caught a wrong-stride file. If the
hardware test says halve it, you will get one number from us and nothing else changes.

**`// CHUNKS: n x m` on every export, generated from the same geometry as the declarations** — that
closes the loop. Our validator now has something authoritative to compare against instead of
inferring from the array bounds.

---

## The test file: verified, and it agrees

`DB_RecipeProgram9_checksum_test.scl` came through. Run through our validator:

```
ready  DB_RecipeProgram9_checksum_test.scl  (254 lines, geometry matches the PLC,
       CAM-declared 10 x 100, checksum 9593624 verified)
```

**Our implementation computes 9593624 from your lines, independently.** That is the cross-check we
actually needed — the worked example only proves we agree on four hand-written lines, whereas this
proves two separately-written implementations agree on a real file. Everything else lines up too:
254 lines parsed with none beyond `LineCount`, the END marker at `Lines3[53]` exactly as you said,
`S7_Optimized_Access := 'FALSE'`, `UNLINKED` before `NON_RETAIN`, X within 0..134.5 and Z within
0..60. Nothing for us to report back except the item below.

**Synthetic toolpath was the right call** — we are validating format, chunk mapping and checksum,
none of which care whether the geometry makes a part. No need to send a real export.

`tools/split_recipe_db.py` is attached, as requested. `recipe_checksum()` is the algorithm;
`parse_lines()` deliberately reads flat and chunked layouts identically, so a file's checksum is
invariant across conversion. We verified that property rather than assuming it.

---

## The one defect: the `UDINT#` prefix is missing

This was a question in the draft of this letter and the test file settled it — it is real:

```scl
    Header.Checksum := 9593624;        <- as emitted
    Header.Checksum := UDINT#9593624;  <- as it needs to be
```

An untyped integer literal above 32767 is ambiguous under TIA's implicit-conversion rules against a
`UDInt` target, and the data block can be rejected at compile time. The letter called this out; it
looks like it did not survive into the emitter.

**Why this one is worth fixing before you regenerate anything:** values below 32768 compile either
way. A small test file can pass while every real recipe fails, and the failure appears at *import*
time in TIA, far from the code that caused it. Roughly one export in 130,000 would slip under the
threshold by chance, so in practice this fails always — but it would fail confusingly if anyone ever
hand-built a tiny test case.

Our validator accepts both forms on read and always writes the prefix, so this is the only place it
matters. One-line change on your side.

---

## `--no-checksum`: keep using it for now

The UDT fields are committed on our side but **not yet imported into TIA**. Until we confirm a clean
compile and download, a checksummed export cannot be imported here. We will tell you the moment the
UDT is in.

There is no rush from our side either way: `ProvidesChecksum = FALSE` is a supported state, not a
degraded one. The loader skips the check and reports normally.

---

## `ChecksumXZ`: not yet, and here is the honest reason

We are declining for now, but not because it lacks value — it closes the one real gap left. Our
per-line verification checks the `CMD` byte, one of twelve, so a line whose `CMD` arrived while its
`X`/`Z` did not would pass everything we have, including `Checksum`. Every hole observed on the
machine has been region-sized, which takes the `CMD` with it, but that is an observation, not a
guarantee.

The cost is on our side, not yours: reading the raw float bit patterns back out of a standard DB
means byte-offset arithmetic against a hard-coded block number, which is fragile in a way the rest
of this design is not. We are not adding that while the fundamental question — whether load-memory
recipes work on this CPU at all — is still open.

So: hold it, keep it specified, and expect us to ask once the hardware test passes. If it fails and
we fall back to work-memory recipes, the whole `READ_DBL` path disappears and neither checksum is
needed for transfer integrity.

---

## A separate defect, unrelated to any of this

Worth raising while we have your attention, because no checksum can catch it — a self-consistent
file that is wrong is still wrong, and both sides would agree on it perfectly.

**Later operations in an export arrive with zeroed RPM and feed.** Seen in two independent exports:
program 1 (2026-08-13) and program 2 (2026-08-14). The first operation carries correct values; the
rest do not. In program 2 the first ~950 lines are clean and the tail contains:

- four `CMD=20 Param=0` — spindle ON at 0 RPM (Ops 1-P125, 2, 3, 4)
- three `CMD=1 F=0` — G1 with no feed

Your own header comments show the source: `Op1: ROUGHING ... RPM=600.0`, then
`Op2: ROUGHING ... RPM=0.0`, `Op3: BENDING ... RPM=0.0`, `Op4: CUTTING ... RPM=0.0`. It looks like
spindle and feed state is not carried across operation boundaries in the post-processor.

**Neither is refused by the PLC, and both fail quietly**, which is why we are reporting it rather
than letting the machine find it:

- `Param = 0` → the spindle FB clamps *upward* to its 100 RPM minimum. The part is formed at 100 RPM
  instead of 600, and nothing is reported.
- `F = 0` → the recipe handler treats a zero feed as a rapid and uses `RapidVelocity`. **A cutting
  move executes at rapid speed.** That is the dangerous one if the tool is in material.

We are adding a pre-scan rejection on our side, but the values should not be zero in the first
place. Could you check whether operation state is reset between operations?
