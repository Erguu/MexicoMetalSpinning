# Letter for Delta — price request

**Purpose:** External correspondence — request for quotation on a CODESYS motion controller
package to replace the S7-1200 + PTO motion on the metal spinning machine.
**Written:** 2026-09-13. **Revised 2026-09-14:** model changed from AX-308E to AX-8 CNC variant.
**Background:** `CNC_Controller_Options.md` §0.8 (why CODESYS), §0.10c (why standalone),
§0.11f (why one box).

**Why the model changed (2026-09-14).** The first draft asked for the **AX-308E** with SoftMotion
CNC. Delta's own ordering code rules that out: in the CODESYS catalogue
(`DELTA_IA-Delta_Motion_Control_Solution_Based_on_CODESYS_C_EN_20210929`, p.22) the AX-3 software
digit has **one** value, `M: Motion Control`. The `C: CODESYS SoftMotion - CNC` value exists only
in the **AX-8** code, and the only orderable AX-3 part is `AX-308EA0MA1T` "Basic Motion
Controller". The AX-3 does PLCopen single/multi-axis, gearing, CAM and interpolation from ST —
**no G-code interpreter.** So the candidate is now the AX-8 "Advanced" variant:

| Code | Meaning |
|---|---|
| `AX-816EP0CE1P` | 16 axes · Celeron · **C = SoftMotion CNC** · **E = Linux** · PNP — probably cheapest (no Windows licence), unconfirmed |
| `AX-816EP0CB1P` | same, Win10 IoT |
| `AX-816EP0CC1P` | same, Win10 IoT + CODESYS TargetVisu (extra licence) |

**16 axes is the smallest AX-8** — there is no 8-axis AX-8. No price was found online for any
of the three, so the letter asks Delta to price all three.

Consequences of the change, all reflected below:

- **No local pulse outputs.** The AX-8 is EtherCAT only, so old question A2 (the AX-308E's four
  pulse axes) is dead. The way to keep the existing pulse/direction drives becomes Delta's
  **R1-EC5621D0** 1-channel EtherCAT pulse module — new question A2.
- **Only 8 DI / 8 DO built in** (vs 16/8), so the I/O expansion line is larger — quoted as R1-EC
  remote I/O, which shares the same coupler as the pulse modules.
- Delta's AX-8 catalogue carries the note *"Only certain CNC and Robot functions are supported.
  Please contact Delta for available application info before using."* — so question A now asks
  for the **specific function blocks** this design depends on, not a yes/no.
- PC-based and more expensive than the AX-308E; **no price found online** (resellers list it as
  quote-only, including Akdeniz Mekatronik in Adana).

**If Delta's CNC subset turns out too thin,** Delta's dedicated alternative is the **NC5** CNC
controller (EtherCAT, ISO G-code, lathe support). It is a closed CNC with its own PLC, so it loses
the §0.11f one-box argument — ask about it only if question A fails.

**Before sending — two things to fill in:**
1. **Servo motor sizing.** The existing drive/motor make, model and power rating is recorded
   nowhere in this project. Get the nameplate data off the X and Z motors and attach it, or the
   quote will be a guess.
2. Confirm the digital I/O count against `Wiring_Diagram.md` (currently 16 DI / 23 DO).

---

**Subject:** Request for quotation — AX-8 motion controller with SoftMotion CNC

Dear Delta team,

We build special-purpose metal spinning machines in Türkiye. We are replacing the motion control
on one machine: it currently runs on a Siemens S7-1200 with pulse/direction servo drives, and we
want to move to a CODESYS-based controller that executes G-code directly, with look-ahead and
corner blending, and runs the machine logic in the same application. The machine has two
interpolated axes (X and Z), one indexing turret axis and a spindle on a VFD.

Please quote the following:

| # | Item | Qty | Note |
|---|---|---|---|
| 1 | AX-8 motion controller, 16 axes, **SoftMotion CNC**, PNP — please price all three variants: **AX-816EP0CE1P** (Linux), **AX-816EP0CB1P** (Windows), **AX-816EP0CC1P** (Windows + TargetVisu) | 1 | see question A. We intend to buy the lowest-cost variant that meets question A |
| 2 | **ASDA-B3-E** EtherCAT servo drive + motor | 3 | X, Z, turret — sizing per the attached motor data |
| 3 | Digital I/O expansion (**R1-EC** remote I/O + coupler) | — | to reach approx. **16 inputs / 24 outputs** total, **PNP / sourcing** |
| 4 | Operator display | 1 | a touch monitor for TargetVisu, or a panel running WebVisu — please advise which you recommend and quote it |
| 5 | Software licences | — | anything needed for SoftMotion CNC and visualisation that is **not** already included in item 1 |
| 6 | VFD option | 1 | we have an existing spindle inverter; please also quote an **MS300** or **MH300** with EtherCAT so we can compare keeping ours against a fully EtherCAT machine |
| 7 | Alternative to item 2 | 3 | **R1-EC5621D0** pulse module — see question A2 |

Three questions before we finalise the model choice:

**A.** Your AX-8 catalogue notes that *only certain CNC functions are supported*. Please confirm
that the CNC variant supports the following, as used from our own Structured Text program:
- loading a **DIN 66025 G-code file at runtime** (`SMC_ReadNCFile` or equivalent) — our programs
  are generated by CAM software and change per part, so they cannot be compiled into the project;
- `SMC_NCDecoder`, `SMC_SmoothPath` (corner blending) and `SMC_LimitDynamics` / look-ahead;
- `SMC_Interpolator` with **M functions**, including `SMC_PreAcknowledgeMFunction`;
- **G2/G3 arcs** in the X/Z plane.

If any of these is missing or needs an additional licence, please say which. We need **one**
interpolator — two axes (X/Z) contouring as a single path; the turret is point-to-point.

**A2.** **We already have pulse/direction servo drives and motors on this machine.** Can the
**R1-EC5621D0** pulse module be used from CODESYS on the AX-8 as a **SoftMotion axis inside a CNC
path group** — i.e. can X and Z run an interpolated G-code path through two R1-EC5621D0 modules —
or is it limited to point-to-point positioning? If the answer is yes, please quote that variant as
well: controller + licences + I/O + 3 pulse modules, no servos.

**B.** The machine will be **exported to Mexico**. Does Delta have service and spare-part support
in Mexico, and can firmware and software be supported remotely from Türkiye?

Please also advise **lead time** for the above.

We would be glad to arrange a technical call.

Best regards,

**Çağdaş Ergüvan**
[Company]
[Phone] · [E-mail]

---

## Turkish version — for the Türkiye distributor

**Language note:** the body below is in Turkish because the recipient is the local distributor.
External correspondence, not project documentation — the English-only rule in `CLAUDE.md` applies
to code and project docs. Same convention as `letterforsyntec.md`.

---

**Konu:** Teklif talebi — SoftMotion CNC özellikli AX-8 hareket kontrolörü

Sayın Delta Yetkilisi,

Firmamız Türkiye'de özel amaçlı metal sıvama tezgâhları üretmektedir. Bir tezgâhımızın hareket
kontrolünü değiştiriyoruz: sistem şu anda Siemens S7-1200 ve puls/yön arayüzlü servo sürücülerle
çalışmaktadır. Bunun yerine, G kodunu doğrudan çalıştıran, ileri bakış (look-ahead) ve köşe
yumuşatma özelliklerine sahip, makine mantığını da aynı uygulamada çalıştıran **CODESYS tabanlı**
bir kontrolöre geçmek istiyoruz. Tezgâhta enterpolasyon yapan **iki eksen (X ve Z)**, bir adet
indeksleme yapan **taret ekseni** ve invertörle sürülen bir **iş mili** bulunmaktadır.

Aşağıdaki kalemler için fiyat teklifi rica ederiz:

| # | Ürün | Adet | Açıklama |
|---|---|---|---|
| 1 | AX-8 hareket kontrolörü, 16 eksen, **SoftMotion CNC**, PNP — lütfen üç versiyonu da fiyatlandırınız: **AX-816EP0CE1P** (Linux), **AX-816EP0CB1P** (Windows), **AX-816EP0CC1P** (Windows + TargetVisu) | 1 | A sorusuna bakınız. A sorusunu karşılayan en düşük maliyetli versiyonu almayı planlıyoruz |
| 2 | **ASDA-B3-E** EtherCAT servo sürücü + motor | 3 | X, Z, taret — ekteki motor etiket bilgilerine göre boyutlandırma |
| 3 | Dijital G/Ç genişletme (**R1-EC** uzak G/Ç + kuplör) | — | toplamda yaklaşık **16 giriş / 24 çıkış**, **PNP** |
| 4 | Operatör ekranı | 1 | TargetVisu için dokunmatik monitör veya WebVisu çalıştıran bir panel — hangisini önerdiğinizi belirtip fiyatlandırınız |
| 5 | Yazılım lisansları | — | SoftMotion CNC ve görselleştirme için 1. kaleme dahil **olmayan** lisanslar |
| 6 | İnvertör opsiyonu | 1 | Mevcut bir iş mili invertörümüz var; kendi invertörümüzü kullanmak ile tamamen EtherCAT bir tezgâh arasında karşılaştırma yapabilmemiz için **EtherCAT'li MS300 veya MH300** fiyatını da veriniz |
| 7 | 2. kaleme alternatif | 3 | **R1-EC5621D0** puls modülü — A2 sorusuna bakınız |

Model seçimini belirleyecek üç sorumuz var:

**A.** AX-8 kataloğunuzda *yalnızca belirli CNC fonksiyonlarının desteklendiği* belirtiliyor.
CNC versiyonunun, kendi Structured Text programımızdan kullanılmak üzere aşağıdakileri
desteklediğini teyit eder misiniz:
- **DIN 66025 G kodu dosyasının çalışma anında yüklenmesi** (`SMC_ReadNCFile` veya eşdeğeri) —
  programlarımız CAM yazılımıyla üretiliyor ve parçaya göre değişiyor, projeye derlenemez;
- `SMC_NCDecoder`, `SMC_SmoothPath` (köşe yumuşatma) ve `SMC_LimitDynamics` / ileri bakış;
- **M fonksiyonları** ile `SMC_Interpolator`, `SMC_PreAcknowledgeMFunction` dahil;
- X/Z düzleminde **G2/G3 dairesel interpolasyon**.

Bunlardan eksik olan veya ek lisans gerektiren varsa lütfen belirtiniz. Bize **tek bir**
interpolatör yeterli — iki eksen (X/Z) tek bir yol olarak kontur çiziyor, taret ise noktadan
noktaya hareket ediyor.

**A2.** **Tezgâhta hâlihazırda puls/yön arayüzlü servo sürücü ve motorlar mevcut.**
**R1-EC5621D0** puls modülü, AX-8 üzerinde CODESYS'ten **CNC yol grubu içinde bir SoftMotion
ekseni** olarak kullanılabiliyor mu — yani X ve Z, iki adet R1-EC5621D0 üzerinden enterpolasyonlu
G kodu yolu çalıştırabilir mi — yoksa yalnızca noktadan noktaya konumlandırma ile mi sınırlı?
Cevap olumluysa lütfen bu seçeneği de fiyatlandırınız: kontrolör + lisanslar + G/Ç + 3 puls
modülü, servo hariç.

**B.** Tezgâh **Meksika'ya ihraç edilecektir.** Delta'nın Meksika'da servis ve yedek parça
desteği bulunuyor mu? Yazılım ve firmware desteği Türkiye'den uzaktan sağlanabilir mi?

Ayrıca **teslim süresini** de belirtmenizi rica ederiz.

Konuyu bir teknik görüşmede detaylandırmaktan memnuniyet duyarız. İlginiz için şimdiden teşekkür
ederim.

Saygılarımla,

**Çağdaş Ergüvan**
[Firma adı]
[Telefon] · [E-posta]
