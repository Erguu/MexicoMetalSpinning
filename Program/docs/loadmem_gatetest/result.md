BEFORE ONLY IN MEMORY LOAD

Cmd_Load	Bool	false	FALSE
Cmd_Reset	Bool	false	FALSE
SelectRecipe	Int	1	1
TestMode	Int	1	1
State	Int	0	50
Busy	Bool	false	FALSE
Done	Bool	false	TRUE
ErrorFlag	Bool	false	FALSE
RetVal	Int	0	0
LoadedRecipe	Int	0	1
Elapsed	Time	T#0ms	T#1MS
ScanCount	Int	0	2
Result	String[70]	''	'PASS - recipe +1 every line (header not copied in mode 1)'
TestPassed	Bool	false	TRUE
Chk_FirstLine	Bool	false	TRUE
Chk_LastLine	Bool	false	TRUE
Chk_AllLines	Bool	false	TRUE
Chk_Header	Bool	false	TRUE
Checksum	Real	0.0	635.0
Checksum_Expected	Real	0.0	635.0

------------

Cmd_Load	Bool	false	FALSE
Cmd_Reset	Bool	false	FALSE
SelectRecipe	Int	1	2
TestMode	Int	1	1
State	Int	0	50
Busy	Bool	false	FALSE
Done	Bool	false	TRUE
ErrorFlag	Bool	false	FALSE
RetVal	Int	0	0
LoadedRecipe	Int	0	2
Elapsed	Time	T#0ms	T#2MS
ScanCount	Int	0	2
Result	String[70]	''	'PASS - recipe +2 every line (header not copied in mode 1)'
TestPassed	Bool	false	TRUE
Chk_FirstLine	Bool	false	TRUE
Chk_LastLine	Bool	false	TRUE
Chk_AllLines	Bool	false	TRUE
Chk_Header	Bool	false	TRUE
Checksum	Real	0.0	1722.0
Checksum_Expected	Real	0.0	1722.0

-----------------

Cmd_Load	Bool	false	FALSE
Cmd_Reset	Bool	false	FALSE
SelectRecipe	Int	1	3
TestMode	Int	1	1
State	Int	0	50
Busy	Bool	false	FALSE
Done	Bool	false	TRUE
ErrorFlag	Bool	false	FALSE
RetVal	Int	0	0
LoadedRecipe	Int	0	3
Elapsed	Time	T#0ms	T#62MS
ScanCount	Int	0	2
Result	String[70]	''	'PASS - recipe +3 every line (header not copied in mode 1)'
TestPassed	Bool	false	TRUE
Chk_FirstLine	Bool	false	TRUE
Chk_LastLine	Bool	false	TRUE
Chk_AllLines	Bool	false	TRUE
Chk_Header	Bool	false	TRUE
Checksum	Real	0.0	666.5
Checksum_Expected	Real	0.0	666.5

------------------

Cmd_Load	Bool	false	FALSE
Cmd_Reset	Bool	false	FALSE
SelectRecipe	Int	1	1
TestMode	Int	1	2
State	Int	0	50
Busy	Bool	false	FALSE
Done	Bool	false	TRUE
ErrorFlag	Bool	false	FALSE
RetVal	Int	0	0
LoadedRecipe	Int	0	1
Elapsed	Time	T#0ms	T#0MS
ScanCount	Int	0	2
Result	String[70]	''	'PASS - recipe +1 whole DB: header + every line'
TestPassed	Bool	false	TRUE
Chk_FirstLine	Bool	false	TRUE
Chk_LastLine	Bool	false	TRUE
Chk_AllLines	Bool	false	TRUE
Chk_Header	Bool	false	TRUE
Checksum	Real	0.0	635.0
Checksum_Expected	Real	0.0	635.0


-----------------------

Cmd_Load	Bool	false	FALSE
Cmd_Reset	Bool	false	FALSE
SelectRecipe	Int	1	1
TestMode	Int	1	3
State	Int	0	50
Busy	Bool	false	FALSE
Done	Bool	false	TRUE
ErrorFlag	Bool	false	FALSE
RetVal	Int	0	0
LoadedRecipe	Int	0	1
Elapsed	Time	T#0ms	T#0MS
ScanCount	Int	0	2
Result	String[70]	''	'PASS - recipe +1 header only (lines not part of this mode)'
TestPassed	Bool	false	TRUE
Chk_FirstLine	Bool	false	TRUE
Chk_LastLine	Bool	false	TRUE
Chk_AllLines	Bool	false	TRUE
Chk_Header	Bool	false	TRUE
Checksum	Real	0.0	0.0
Checksum_Expected	Real	0.0	635.0


----------------------

AFTER ONLY IN MEMORY LOAD

Cmd_Load	Bool	false	FALSE
Cmd_Reset	Bool	false	FALSE
SelectRecipe	Int	1	1
TestMode	Int	1	1
State	Int	0	50
Busy	Bool	false	FALSE
Done	Bool	false	TRUE
ErrorFlag	Bool	false	FALSE
RetVal	Int	0	0
LoadedRecipe	Int	0	1
Elapsed	Time	T#0ms	T#0MS
ScanCount	Int	0	2
Result	String[70]	''	'PASS - recipe +1 every line (header not copied in mode 1)'
TestPassed	Bool	false	TRUE
Chk_FirstLine	Bool	false	TRUE
Chk_LastLine	Bool	false	TRUE
Chk_AllLines	Bool	false	TRUE
Chk_Header	Bool	false	TRUE
Checksum	Real	0.0	635.0
Checksum_Expected	Real	0.0	635.0

------

Cmd_Load	Bool	false	FALSE
Cmd_Reset	Bool	false	FALSE
SelectRecipe	Int	1	2
TestMode	Int	1	1
State	Int	0	50
Busy	Bool	false	FALSE
Done	Bool	false	TRUE
ErrorFlag	Bool	false	FALSE
RetVal	Int	0	0
LoadedRecipe	Int	0	2
Elapsed	Time	T#0ms	T#1MS
ScanCount	Int	0	2
Result	String[70]	''	'PASS - recipe +2 every line (header not copied in mode 1)'
TestPassed	Bool	false	TRUE
Chk_FirstLine	Bool	false	TRUE
Chk_LastLine	Bool	false	TRUE
Chk_AllLines	Bool	false	TRUE
Chk_Header	Bool	false	TRUE
Checksum	Real	0.0	1722.0
Checksum_Expected	Real	0.0	1722.0


------

Cmd_Load	Bool	false	FALSE
Cmd_Reset	Bool	false	FALSE
SelectRecipe	Int	1	3
TestMode	Int	1	1
State	Int	0	50
Busy	Bool	false	FALSE
Done	Bool	false	TRUE
ErrorFlag	Bool	false	FALSE
RetVal	Int	0	0
LoadedRecipe	Int	0	3
Elapsed	Time	T#0ms	T#0MS
ScanCount	Int	0	2
Result	String[70]	''	'PASS - recipe +3 every line (header not copied in mode 1)'
TestPassed	Bool	false	TRUE
Chk_FirstLine	Bool	false	TRUE
Chk_LastLine	Bool	false	TRUE
Chk_AllLines	Bool	false	TRUE
Chk_Header	Bool	false	TRUE
Checksum	Real	0.0	666.5
Checksum_Expected	Real	0.0	666.5


-------


Cmd_Load	Bool	false	FALSE
Cmd_Reset	Bool	false	FALSE
SelectRecipe	Int	1	1
TestMode	Int	1	2
State	Int	0	50
Busy	Bool	false	FALSE
Done	Bool	false	TRUE
ErrorFlag	Bool	false	FALSE
RetVal	Int	0	0
LoadedRecipe	Int	0	1
Elapsed	Time	T#0ms	T#1MS
ScanCount	Int	0	2
Result	String[70]	''	'PASS - recipe +1 whole DB: header + every line'
TestPassed	Bool	false	TRUE
Chk_FirstLine	Bool	false	TRUE
Chk_LastLine	Bool	false	TRUE
Chk_AllLines	Bool	false	TRUE
Chk_Header	Bool	false	TRUE
Checksum	Real	0.0	635.0
Checksum_Expected	Real	0.0	635.0

------


Cmd_Load	Bool	false	FALSE
Cmd_Reset	Bool	false	FALSE
SelectRecipe	Int	1	1
TestMode	Int	1	3
State	Int	0	50
Busy	Bool	false	FALSE
Done	Bool	false	TRUE
ErrorFlag	Bool	false	FALSE
RetVal	Int	0	0
LoadedRecipe	Int	0	1
Elapsed	Time	T#0ms	T#15MS
ScanCount	Int	0	2
Result	String[70]	''	'PASS - recipe +1 header only (lines not part of this mode)'
TestPassed	Bool	false	TRUE
Chk_FirstLine	Bool	false	TRUE
Chk_LastLine	Bool	false	TRUE
Chk_AllLines	Bool	false	TRUE
Chk_Header	Bool	false	TRUE
Checksum	Real	0.0	0.0
Checksum_Expected	Real	0.0	635.0
