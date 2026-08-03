# Letter for Syntec Türkiye

**Purpose:** External correspondence — inquiry about a pulse (step/dir) type CNC controller to take over
X/Z contouring while the S7-1200 remains master.
**Written:** 2026-08-01 · **Revised:** 2026-08-02 after reviewing the 2019 Syntec HSHP catalog.
**Language note:** The letter body is in Turkish because the recipient is Syntec Türkiye. This is external
correspondence, not project documentation — the English-only rule in `CLAUDE.md` applies to code and
project docs.

**Background:** See `MotionSmoothing.md` for the underlying motion problem and the alternatives considered.

**Deciding questions: 2, 3, 4 and 6.** A "no" on 2 or 6 kills the whole approach. Push on all four before
discussing price.

**What the catalog already tells us** (`2019_EN_SYNTEC-High-Speed-High-Precision-Controller.pdf`):

- Only the **6-series (6TA/6TB)** and 11-series lathe controllers have general-purpose pulse output.
  Everything else (6TA-E, 21x, 22x, 200/210/220) is Mechatrolink / EtherCAT / RTEX — would require
  replacing our servo drives. **6TB** is the target model (4 axes, 512 MB vs 3 axes, 256 MB on 6TA).
- **11TA is marked "Only sell in Taiwan"** (p.16 remark) — dropped from the inquiry; 11TB availability
  is now asked instead.
- Pulse output is listed only as **A/B phase** and **CW/CCW** — not pulse+direction. Hence question 2.
- The *Dipole foreground/background* row shows `--` for the 6-series, so the PC-side API is not
  available on this model. Program selection would have to go through the built-in PLC. Hence question 4.
- The p.15–16 feature table did not extract legibly (the "optional" glyph is missing), so we cannot tell
  whether constant jerk / cross-segment S-curve / corner deceleration are standard or optional on the
  6-series. Hence question 3.
- No Mexico office is listed. Nearest is USA (Walnut, CA). Hence question 9.

**Syntec Türkiye contact:** Küçükbakkalköy Mah., Vedat Günyol Cd., Defne Sok. No:1 D:1502,
Flora Residence, 34750 Ataşehir/İstanbul · +90-216-2662475 · daisy.cheng@syntecclub.com.tw

---

**Konu:** Puls (step/dir) tipi CNC kontrol ünitesi — bilgi ve teklif talebi

Sayın Syntec Türkiye Yetkilisi,

Firmamız özel amaçlı metal sıvama (metal spinning) tezgâhı üretmektedir. Mevcut tezgâhımızda kontrol
Siemens S7-1200 PLC ile yapılmakta, X ve Z eksenleri **puls + yön (step/dir)** arayüzlü servo sürücülerle
sürülmektedir.

PLC'nin hareket kontrolü noktadan noktaya çalıştığı için CAM'den gelen kısa segmentlerin sonunda eksenler
duruyor. Bu nedenle, **mevcut servo sürücülerimizi değiştirmeden** X ve Z eksenlerinin kontrolünü ileri
bakışlı (look-ahead) ve köşe yumuşatmalı bir CNC ünitesine devretmek istiyoruz. **S7-1200 PLC ana
kontrolör olarak kalacak**; proses sırası, silindirler, emniyet ve operatör HMI'ı PLC tarafında kalmaya
devam edecek. CNC ünitesi yalnızca eksen hareketinden sorumlu olacak ve PLC ile birlikte çalışacaktır.

Çalışma koşullarımız: 2 eksen (X/Z), ilerleme genellikle **300 mm/dak altında**, CAM'den gelen segment
boyu **1 mm civarında**. Yüksek hız gerektiren bir uygulama değiliz; ihtiyacımız segmentler arasında
durmadan, sürekli ve düzgün bir hareket elde etmektir.

2019 tarihli "High-Speed High-Precision Controller" kataloğunuzu inceledik. Buna göre puls çıkışlı torna
ürünleriniz **6 serisi (6TA / 6TB)** ve **11 serisi** olarak görünüyor. Sorularımız şunlardır:

**Ürün seçimi**

1. **6TA ve 6TB** hâlen üretimde mi? İki eksenli (X/Z) kullanımımız için hangisini önerirsiniz?
   Katalogda **11TA "yalnızca Tayvan'da satılır"** olarak işaretlenmiş — **11TB** Türkiye'de temin
   edilebiliyor mu, ve bizim uygulamamız için 6 serisine göre bir avantajı olur mu?

2. **(Belirleyici)** Katalogda genel amaçlı eksen çıkışı olarak yalnızca **A/B faz** ve **CW/CCW**
   belirtilmiş. Sürücülerimiz hâlen **puls + yön (step/dir)** modunda çalışıyor. Kontrol ünitesi
   doğrudan puls+yön çıkışı verebiliyor mu? Veremiyorsa, sürücü tarafında giriş tipini CW/CCW veya
   A/B faza çevirmemiz yeterli olur mu?

**Hareket kalitesi**

3. **(Belirleyici)** 6 serisinde aşağıdaki fonksiyonlar **standart mı, opsiyonel mi**?
   - Sabit jerk kontrolü (constant jerk control)
   - Bloklar arası S-eğrisi ivmelenme/yavaşlama (cross-segment S-curve acc/dec)
   - Köşede otomatik yavaşlama (auto deceleration at corner)
   - Köşe yarıçapı hız sınırı (corner radius speed limit)

   Ayrıca 6 serisinde **ileri okuma (look-ahead) blok sayısı** ve **blok işleme hızı (blok/saniye)**
   nedir? (1 mm'lik segmentlerle çalıştığımız için bu iki değer bizim için belirleyicidir.)

**PLC ile entegrasyon**

4. **(Belirleyici)** **Çalıştırılacak programı harici PLC seçebilir mi?** Operatörün Syntec ekranından
   program seçmesine gerek kalmadan, tüm seçim bizim HMI'ımızdan yapılabilmelidir. Katalogda 6 serisi
   için "dipole ön/arka sistem" desteklenmiyor görünüyor; bu durumda program seçimi ünitenin **dahili
   PLC'si (ladder)** üzerinden register / BCD girişleriyle yapılabilir mi?

5. **Başlat, duraklat, devam, reset** ve **referans alma (homing)** komutları harici PLC'den verilebilir
   mi? Eksen referans (home) ve limit anahtarlarının doğrudan Syntec ünitesine bağlanması gerekiyor mu?

6. **(Belirleyici)** **CNC ünitesi PLC'ye sinyal gönderip PLC'den onay bekleyebilir mi?** Yani M-kodu ile
   silindir tetikleyip, işlem tamamlanana kadar PLC'den geri onay (FIN) bekleyebilir mi? Ayrıca **anlık
   X/Z konum bilgisi** PLC tarafından okunabilir mi, ve hangi arayüz üzerinden (Ethernet / RS-485)?

7. Tezgâhın **iş mili PLC tarafında kalacak** ve Syntec ünitesine bağlanmayacaktır. Ünite, tanımlı bir
   iş mili olmadan G-kodu programı çalıştırabilir mi? (G95/G96 kullanmıyoruz; ilerleme mm/dak olarak
   verilmektedir.)

**Program aktarımı ve ticari koşullar**

8. G-kodu programları üniteye nasıl yüklenir? USB, Ethernet paylaşımı veya ağ üzerinden uzaktan yükleme
   mümkün mü? (Tezgâh Meksika'ya sevk edileceği için Türkiye'den uzaktan program gönderebilmek bizim için
   önemlidir.)

9. Uygun modelin fiyatı ve teslim süresi nedir? Türkiye'de devreye alma desteği sağlanmakta mıdır?
   **Meksika'da servis** konusunda: katalogda Meksika'da bir ofis görünmüyor — **ABD (Walnut, CA) ofisiniz
   Meksika'yı kapsıyor mu**, yoksa bölgede yetkili bir servis ortağınız var mı?

Konuyu bir teknik görüşmede detaylandırmaktan memnuniyet duyarız. İlginiz için şimdiden teşekkür ederim.

Saygılarımla,

**Çağdaş Ergüvan**
[Firma adı]
[Telefon] · [E-posta]
