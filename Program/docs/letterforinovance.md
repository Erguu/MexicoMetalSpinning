# Letter for Inovance — price request

**Purpose:** External correspondence — request for quotation on a CODESYS motion controller
package to replace the S7-1200 + PTO motion on the metal spinning machine.
**Written:** 2026-09-13
**Background:** `CNC_Controller_Options.md` §0.8 (why CODESYS), §0.10c (why standalone).
**Companion:** `letterfordelta.md` — **deliberately the same six line items** so the two quotations
can be compared directly. Do not renumber them.

**Possible Türkiye route:** EMEA Technology (emea.com.tr) lists Inovance alongside CODESYS in its
product range and is worth trying before going to Inovance Europe directly.

**Before sending — same two gaps as the Delta letter:**
1. **Servo motor sizing.** The existing drive/motor make, model and power rating is recorded
   nowhere in this project. Attach the X and Z motor nameplate data or the quote is a guess.
2. Confirm the digital I/O count against `Wiring_Diagram.md` (currently 16 DI / 23 DO).

**Question A is the one that decides the model** and is weaker evidence here than with Delta:
Delta publishes that the AX-8 carries a DIN 66025 interpreter, whereas Inovance's marketing says
only that the AM400/AM600 "come with CNC" functions. Whether that means the full CODESYS
SoftMotion CNC G-code interpreter or something narrower is **unverified** — get it in writing.
Question C (English documentation) is specific to this vendor and is a real commissioning risk.

**Model changed to AM522 (2026-09-14)** — it is the model the vendor suggested earlier. From
Inovance Europe's own brochure (`AM320_522_Br_Sreads_Web_v16.pdf`):

| | AM522 |
|---|---|
| Axes | **16 EtherCAT + 4 pulse**, plus 4 encoder inputs (200 kHz); AM521 = 8 EtherCAT + 4 pulse |
| Motion | *"Axis group for lineal and circular interpolation"*, *"Support CAM and interpolation motion"* |
| Built-in I/O | 8 DI (sink/source) / 8 DO. **`AM522-0808TP` = source (PNP) outputs** — order this one; `…TN` is sink |
| Price seen | ~$1,100 (`AM522-0808TN`, single eBay listing — not a quote) |

**What it does not say:** nothing in the AM522 brochure, the Inovance EU product page or the
AM500 product summaries mentions **G-code, DIN 66025 or a CNC interpreter.** Interpolation from ST
is not G-code. Inovance's actual CNC product in Europe is the **PA9000** (a dedicated PC-based
CNC from their European CNC centre, which ships with its own standard PLC program) — a different
architecture, and not what this letter is asking about. So for the AM522, question A is the whole
decision, and A2 (can the 4 pulse axes join the path) matters because it would keep the existing
drives.

---

**Subject:** Request for quotation — AM-series motion controller with CNC / G-code execution

Dear Inovance team,

We build special-purpose metal spinning machines in Türkiye. We are replacing the motion control
on one machine: it currently runs on a Siemens S7-1200 with pulse/direction servo drives, and we
want to move to a CODESYS-based controller that executes G-code directly, with look-ahead and
corner blending. The machine has two interpolated axes (X and Z), one indexing turret axis and a
spindle on a VFD.

Please quote the following:

| # | Item | Qty | Note |
|---|---|---|---|
| 1 | **AM522-0808TP** motion controller (PNP outputs) | 1 | with **CNC / G-code execution** — see question A. Please also quote **AM521-0808TP** if you consider 8 EtherCAT axes sufficient |
| 2 | **SV660N** EtherCAT servo drive + motor | 3 | X, Z, turret — sizing per the attached motor data |
| 3 | Digital I/O expansion | — | to reach approx. **16 inputs / 24 outputs** total |
| 4 | Operator interface | 1 | an **IT7000** series HMI, or a panel running CODESYS WebVisu — please advise which you recommend and quote it |
| 5 | Software licences | — | CNC and visualisation licences, if not included with the hardware |
| 6 | VFD option | 1 | we have an existing spindle inverter; please also quote an **MD500** series drive with EtherCAT so we can compare keeping ours against a fully EtherCAT machine |

Four questions before we finalise the model choice:

**A.** Does the AM522 execute a **standard G-code program (DIN 66025) through the CODESYS
SoftMotion CNC interpreter**, with look-ahead and corner blending across consecutive short
segments? We mean a G-code **file loaded at runtime** and executed by the controller — not axis
group interpolation commanded from our own PLC code, which we understand the AM522 supports. Our programs are several thousand `G1` segments of about 1 mm at feedrates below
300 mm/min, and continuous motion without stopping between segments is the reason for this
project. If the CNC function is a separate licence, please include it in the quotation. **This
determines which controller we buy.** If it is licensed per interpolator, **we need only one** —
the machine contours two axes (X/Z) as a single path; the turret is point-to-point.

**A2.** The AM522 also provides **4 local pulse axes.** Can those pulse-train axes be
used as **interpolated CNC path-group axes** — i.e. can X and Z run a contouring G-code path on the
local pulse outputs — or are they limited to point-to-point positioning? **We already have
pulse/direction servo drives and motors on this machine, so if the answer is yes we would keep
them and buy the controller alone.** Please quote that variant as well (controller + licences +
I/O, no servos).

**B.** The machine will be **exported to Mexico**. Does Inovance have service and spare-part
support in Mexico, and can firmware and software be supported remotely from Türkiye?

**C.** Is **InoProShop** and its documentation fully available in **English**, including the
motion and CNC libraries and the drive commissioning software? Our engineering is done in
Türkiye and English documentation is a requirement for us.

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
to code and project docs. Same convention as `letterforsyntec.md` and `letterfordelta.md`.

---

**Konu:** Teklif talebi — CNC / G kodu çalıştırma özellikli AM serisi hareket kontrolörü

Sayın Inovance Yetkilisi,

Firmamız Türkiye'de özel amaçlı metal sıvama tezgâhları üretmektedir. Bir tezgâhımızın hareket
kontrolünü değiştiriyoruz: sistem şu anda Siemens S7-1200 ve puls/yön arayüzlü servo sürücülerle
çalışmaktadır. Bunun yerine, G kodunu doğrudan çalıştıran, ileri bakış (look-ahead) ve köşe
yumuşatma özelliklerine sahip **CODESYS tabanlı** bir kontrolöre geçmek istiyoruz. Tezgâhta
enterpolasyon yapan **iki eksen (X ve Z)**, bir adet indeksleme yapan **taret ekseni** ve
invertörle sürülen bir **iş mili** bulunmaktadır.

Aşağıdaki kalemler için fiyat teklifi rica ederiz:

| # | Ürün | Adet | Açıklama |
|---|---|---|---|
| 1 | **AM522-0808TP** hareket kontrolörü (PNP çıkışlı) | 1 | **CNC / G kodu çalıştırma** özelliği ile — A sorusuna bakınız. 8 EtherCAT ekseni yeterli görüyorsanız lütfen **AM521-0808TP** fiyatını da veriniz |
| 2 | **SV660N** EtherCAT servo sürücü + motor | 3 | X, Z, taret — ekteki motor etiket bilgilerine göre boyutlandırma |
| 3 | Dijital G/Ç genişletme | — | toplamda yaklaşık **16 giriş / 24 çıkış** olacak şekilde |
| 4 | Operatör arayüzü | 1 | **IT7000** serisi HMI veya CODESYS WebVisu çalıştıran bir panel — hangisini önerdiğinizi belirtip fiyatlandırınız |
| 5 | Yazılım lisansları | — | CNC ve görselleştirme lisansları, donanıma dahil değilse |
| 6 | İnvertör opsiyonu | 1 | Mevcut bir iş mili invertörümüz var; kendi invertörümüzü kullanmak ile tamamen EtherCAT bir tezgâh arasında karşılaştırma yapabilmemiz için **EtherCAT'li MD500** serisi fiyatını da veriniz |

Model seçimini belirleyecek dört sorumuz var:

**A.** AM522, **CODESYS SoftMotion CNC yorumlayıcısı üzerinden standart bir G kodu programını
(DIN 66025)** çalıştırabiliyor mu? Ardışık kısa segmentler arasında ileri bakış ve köşe yumuşatma
yapabiliyor mu? Burada kastettiğimiz, **çalışma anında yüklenen** ve kontrolör tarafından
yürütülen bir G kodu dosyasıdır — kendi PLC kodumuzdan komut verilen eksen grubu enterpolasyonu
değil (AM522'nin bunu desteklediğini biliyoruz). Programlarımız 300 mm/dak altındaki ilerleme hızlarında, yaklaşık 1 mm'lik
binlerce `G1` segmentinden oluşmaktadır ve bu projenin sebebi **segmentler arasında durmadan,
sürekli hareket** elde etmektir. CNC fonksiyonu ayrı bir lisans ise lütfen teklife dahil ediniz.
**Hangi kontrolörü alacağımızı bu belirleyecektir.** Lisans interpolatör başına veriliyorsa **bize
yalnızca bir adet gerekiyor** — tezgâhta iki eksen (X/Z) tek bir yol olarak enterpolasyon yapıyor,
taret ise noktadan noktaya hareket ediyor.

**A2.** AM522 ayrıca **4 adet yerel puls ekseni** sunuyor. Bu puls trenli eksenler,
**enterpolasyon yapan CNC yol grubu ekseni** olarak kullanılabiliyor mu — yani X ve Z, yerel puls
çıkışları üzerinden kontur G kodu çalıştırabilir mi — yoksa yalnızca noktadan noktaya
konumlandırma ile mi sınırlı? **Tezgâhta hâlihazırda puls/yön arayüzlü servo sürücü ve motorlar
mevcut; cevap olumluysa bunları koruyup yalnızca kontrolörü almak isteriz.** Lütfen bu seçeneği de
fiyatlandırınız (kontrolör + lisanslar + G/Ç, servo hariç).

**B.** Tezgâh **Meksika'ya ihraç edilecektir.** Inovance'ın Meksika'da servis ve yedek parça
desteği bulunuyor mu? Yazılım ve firmware desteği Türkiye'den uzaktan sağlanabilir mi?

**C.** **InoProShop** ve dokümantasyonu — hareket ve CNC kütüphaneleri ile sürücü devreye alma
yazılımı dahil olmak üzere — **İngilizce** olarak tam anlamıyla mevcut mu? Mühendislik
çalışmalarımız Türkiye'de yürütülmektedir ve İngilizce dokümantasyon bizim için bir gerekliliktir.

Ayrıca **teslim süresini** de belirtmenizi rica ederiz.

Konuyu bir teknik görüşmede detaylandırmaktan memnuniyet duyarız. İlginiz için şimdiden teşekkür
ederim.

Saygılarımla,

**Çağdaş Ergüvan**
[Firma adı]
[Telefon] · [E-posta]
