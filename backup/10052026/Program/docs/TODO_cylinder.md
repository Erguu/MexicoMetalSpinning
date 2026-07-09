TIA Portal SCL - Evrensel Silindir Bloğu Clean Code Özeti
1. Durumları (State) Netleştir (İç Bayraklardan Kurtul)

Kural: Her State'in (durumun) sadece tek bir amacı olmalıdır.

Uygulama: State 1 içinde hem sensörü bekleme hem de tam strok gitme işlemlerini extendFull gibi bir boolean bayrak (flag) ile ayırmak yerine, bunları tamamen ayrı durumlara böl. (Örn: State 1: Sensöre_Git, State 11: Tam_Strok_Git).

2. "Sihirli Numaralar" Yerine Sabitler (Constants) Kullan

Kural: Kod okunabilir olmalı, sayılar ne anlama geldiğini kendi kendine anlatmalıdır.

Uygulama: CASE #State OF 5: yerine VAR CONSTANT bloğunda tanımladığın isimleri kullan. (Örn: CASE #State OF #STATE_RULER_EXTEND:).

3. Parametre Kalabalığını UDT (User Data Type) ile Gizle

Kural: Bir fonksiyon bloğunun çağrıldığı yerdeki giriş/çıkış bacakları (interface) olabildiğince sade olmalıdır.

Uygulama: Analog pozisyonlama için gereken Tolerans, Offset, Çarpan gibi tüm ince ayar parametrelerini UDT_CylinderTuning adında tek bir veri tipinde topla ve FB'ye tek bir parametre olarak bağla.

4. Kodu REGION Komutu ile Mantıksal Parçalara Böl

Kural: Matematiksel hesaplamalar ile karar mekanizmaları (State Machine) iç içe geçmemelidir.

Uygulama: Matematik, hata veya darbe süresi hesaplamalarını ayrı bir REGION içine, durum makinesini ayrı bir REGION içine alarak bloğun içini daraltılabilir (katlanabilir) hale getir.

5. Analog Kontrolde Kestirim Yerine "Oransal Adımlama" Kullan

Kural: Devreye alması (commissioning) zor olan karmaşık hız/zaman algoritmalarından kaçın.

Uygulama: Hız filtresi ve valf reaksiyon süresi hesaplamak yerine; hedef uzakken valfi uzun açan, hedefe yaklaştıkça valfi daha kısa açıp duruma bakan basit ama kararlı "Oransal Adımlama" (Proportional Pulsing) mantığını tercih et.

-------------------------
Kademeli (Multi-Zone) Adımlama Kontrolü
Bu yöntem, hedefe olan uzaklığı (hata payını) belirli bölgelere ayırarak, her bölge için önceden tanımlanmış sabit bir valf açma süresi (darbe/pulse) uygulama prensibine dayanır. Oransal (matematiksel) hesaplamalar yerine, tamamen mantıksal (IF-ELSIF) koşullarla çalışır.

Devreye alma mühendisi veya operatör için son derece şeffaftır çünkü makinenin hangi hata aralığında tam olarak ne kadar süre valfi açacağı bellidir. Eylemsizliği yüksek, pnömatik silindirli pozisyonlama sistemlerinde "sürünerek yaklaşma" (inching) için en güvenilir yöntemlerden biridir.

Devreye Alma (HMI) Parametreleri
Bu yapıyı kurduğunda HMI ekranında sadece aşağıdaki parametrelere ihtiyaç duyarsın (Bu değişkenleri bir UDT içinde toplayabilirsin):

Tolerans (Tolerance): Silindirin duracağı hedef hassasiyeti (Örn: 2.0 mm).

Bölge 1 Süresi (Pulse_Short): 0 - 100 mm arası hatalarda uygulanacak kısa darbe (Örn: 50 ms).

Bölge 2 Süresi (Pulse_Medium): 100 - 200 mm arası hatalarda uygulanacak orta darbe (Örn: 150 ms).

Bölge 3 Süresi (Pulse_Long): 200 - 300 mm arası hatalarda uygulanacak uzun darbe (Örn: 300 ms).

Sürekli Açık Süresi (Pulse_Max): 300 mm'den uzak mesafeler için uygulanacak maksimum darbe veya sürekli açık kalma süresi (Örn: 1000 ms).

Oturma Süresi (SettleTime): Her darbeden sonra valfin kapalı kalacağı ve havanın tahliye edilip mekaniğin durulması için beklenecek sabit süre (Örn: 200 ms).

SCL Kod Şablonu
Kodu TIA Portal'da REGION yapısı kullanarak, mevcut State Machine (Durum Makinesi) bloğunun hemen üstüne yerleştirebilirsin. Bu blok her taramada çalışarak o anki hataya göre sıradaki darbenin süresini hesaplar.


REGION ZONE_PULSE_CALCULATION
    // 1. Mutlak pozisyon hatasını hesapla
    #PosError := #TargetPos - #RulerValue;
    #AbsError := ABS(#PosError);

    // 2. Hata aralıklarına (bölgelere) göre darbe süresini seç
    IF #AbsError <= #Tolerance THEN
        // Hedefteyiz, darbe atmaya gerek yok
        #CalculatedPulse_ms := 0.0;
        
    ELSIF #AbsError <= 100.0 THEN
        // Bölge 1: Hedefe çok yakın (En kısa darbe)
        #CalculatedPulse_ms := #Pulse_Short;
        
    ELSIF #AbsError <= 200.0 THEN
        // Bölge 2: Orta mesafe
        #CalculatedPulse_ms := #Pulse_Medium;
        
    ELSIF #AbsError <= 300.0 THEN
        // Bölge 3: Uzak mesafe
        #CalculatedPulse_ms := #Pulse_Long;
        
    ELSE
        // 300mm'den daha uzak: Maksimum uzunlukta darbe
        // Not: Mesafe çok uzunsa buradaki süreyi büyük vererek 
        // valfin kesintisiz açık kalmasını sağlayabilirsin.
        #CalculatedPulse_ms := #Pulse_Max; 
        
    END_IF;

    // 3. Hesaplanan REAL/INT süreyi TIA Portal TIMER formatına (TIME) çevir
    #PulseTimeOn := DINT_TO_TIME(REAL_TO_DINT(#CalculatedPulse_ms));
END_REGION


Durum Makinesine Entegrasyonu:
Bu hesaplamayı yaptıktan sonra, silindiri hareket ettirdiğin adımda (senin kodundaki State 5 veya State 6 analog hareket adımlarında) ilgili valfi açıp, #PulseTimeOn değerini bir TON (On-Delay Timer) veya TP (Pulse Timer) fonksiyonunun PT bacağına bağlarsın. Süre dolduğunda valfi kapatır ve #SettleTime kadar bekleyeceğin diğer State'e (bekleme durumuna) geçersin. Bekleme bitince başa döner ve ZONE_PULSE_CALCULATION bloğunun hesapladığı yeni süre ile tekrar darbe vurursun.