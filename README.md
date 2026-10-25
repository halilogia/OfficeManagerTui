# Office Manager Tycoon TUI

Terminalde çalışan, 24-bit TrueColor, yaşayan bir **Ofis Müdürü Simülatörü**. Saf Python 3, sıfır bağımlılık.

## Çalıştırma

```
python main.py          # en az 125x38 terminal
run.bat                 # Windows Terminal'i 125x38 açar (boşluklu yollara dayanıklı)
./run.ps1               # PowerShell başlatıcı
python test_office.py   # headless testler
```

Gereksinim: Windows 10/11 + Windows Terminal (VT100 + UTF-8). Eski conhost'ta emoji bozuk görünebilir.

## Ekran düzeni (125x38)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┬────────────┐
│ ▓▒░ OFFICE MANAGER TYCOON   BÜTÇE $9,000  Gün 1  10:22 [██░░░░]  > 1x  CRUNCH                │            │
│ olay bandı / alarm / bilgi satırı                                                            │            │
├────────────────────────────────────────────────────────────┬─────────────────────────────────┤  SPRINTLER │
│  Harita 30x12 karo (her karo 3x2 karakter)                 │ ╭ SPRINTLER 1/3 ╮                │            │
│  ┌ mutfak ─────┐ ┌ toplantı (kırmızı halı) ┐ ┌ sunucu ┐   │ ╭ EKİP  moral · enerji ╮         │   EKİP     │
│  │ ☕  💧  🌿  │ │      ═══ masa ═══        │ │ ▐≡▌▐≡▌ │   │                                 │            │
│  └─────────────┘ └──────────────────────────┘ └────────┘   │                                 │            │
│   masa+monitör sıraları (12 koltuk)         dinlenme alanı  │                                 │            │
├──────────────────────────┬───────────────────────────────┬─┴─────────────────────────────────┴────────────┤
│ SEÇİLİ ÇALIŞAN           │ OLAY GÜNLÜĞÜ                  │ KOMUTLAR                                       │
└──────────────────────────┴───────────────────────────────┴────────────────────────────────────────────────┘
```

Harita: duvar/pencere (pencere gökyüzü günün saatine göre renk değiştirir), mutfak (espresso makinesi, su sebili),
kırmızı halılı toplantı masası, çelik sunucu kabinleri (LED'ler yanıp söner), 12 masa + koltuk, teal halılı
dinlenme alanı (kanepe), bitkiler. Yükseltmeler haritaya yeni eşya ekler (Arcade, ikinci kahve makinesi).

## Çalışanlar

Roller: Backend, Frontend, UI/UX, DevOps, Marketing, Intern. Her çalışanın adı, rolü, yeteneği (1-10),
günlük maaşı, morali, enerjisi ve o anki aktivitesi vardır. Yürümek için BFS yol bulma kullanılır.

```
            enerji<34              sosyal ihtiyaç
  WORKING ───────────► COFFEE_RUN        WORKING ───────► WATER_COOLER_CHAT (iki kişi = bonus moral)
     │  ▲                  (kahve makinesi bozuksa moral düşer)
     │  └── her mola sonrası masaya dönüş
     ├── enerji<24 ──► LOUNGE (kanepe, arcade ile moral)     ├── enerji<9  ──► SLEEPING (Zzz)
     ├── moral<22  ──► STRESSED/BURNOUT (hız %20, ter damlası; moral≥40 olunca düzelir)
     ├── alarm     ──► PANIC (sunucu odasına koş, arıza ilerlemesine katkı; DevOps 2x)
     ├── teslimat  ──► CELEBRATING (zıplar, ✨)
     └── toplantı  ──► MEETING (toplantı masasında toplanır, +moral)
```

Moral 25 saniye boyunca %5'in altında kalan çalışan istifa eder. Çalışanlar iş yaptıkça XP kazanıp seviye atlar.

## Tycoon mekaniği

- **Gün** = 100 sim sn (09:00-18:00). Gün sonunda maaşlar, kira, kahve çekirdeği düşer; teslim edilmiş projelerden küçük retainer gelir.
- **Sprint**: her projenin rol bazlı iş ihtiyacı vardır (ör. Mobil Uygulama v2 → Frontend %30, Backend %25...). Çalışanlar kendi rollerine uygun ihtiyaca puan yazar;
  rol işi bittiyse diğerlerine %40 verimle yardım eder. Hızlı/yorgun/stresli çalışma **bug** üretir, geliştiriciler bug temizler.
  Teslimde ödül = ödül × (0.55 + 0.45 × kalite) − bug × $60; geç teslim %40 ceza, 2 gün gecikirse iptal (-$1000).
- **Olaylar**: 🔥 Sunucu Odası Aşırı Isındı, ☕ Espresso Bozuldu, 🍩 Donut (+15 moral), 📉 Prodüksiyonda Kritik Hata,
  💡 İnovasyon Patlaması (25 sn x1.5 verim), memnun müşteri, grip. Alarm süresinde çözülmezse zarar ve bug artışı.
- **Hedef**: bütçeyi $40.000'e çıkar. $-3.000'a düşersen şirket iflas eder.

## Tuşlar

| Tuş | İşlev |
|---|---|
| `H` | İşe alım: 4 aday arasından seç (ücret = 2 günlük maaş); `R` adayları yeniler (-$150) |
| `F` | Seçili çalışanı kov (tazminat 3 günlük maaş, ekip morali -5) |
| `P` | Yeni sprint: 3 müşteri teklifinden seç (en fazla 3 aktif) |
| `B` | Prim: seçili çalışana ($300, +35) ya da tüm ekibe ($150/kişi, +20) |
| `C` | Premium kahve & atıştırmalık: herkese +35 enerji, +5 moral |
| `U` | Yükseltmeler: Ergonomik Koltuk, Çift Monitör, Langırt/Arcade, Kahve Barı, Soğutmalı Sunucu |
| `M` | Genel toplantı (9 sn iş durur; +moral, +2 kalite; 70 sn bekleme) |
| `K` | Crunch: 2x hız, ~2.4x enerji/moral kaybı, 2x bug |
| `Space` | Duraklat / devam |
| `1` `2` `3` | Hız 1x / 2x / 4x |
| `← → Tab ↑ ↓` | Çalışan seç |
| `Q` | Çıkış |

Menüler açıkken simülasyon durur.

## Dosyalar

| Dosya | Görev |
|---|---|
| `main.py` | Ana döngü (30 FPS), klavye, `Game` sınıfı |
| `office_map.py` | Karo matrisi, eşyalar, BFS, karo sprite'ları |
| `worker.py` | Roller, durum makinesi, ihtiyaçlar, yürüme |
| `simulation.py` | Bütçe, projeler, yükseltmeler, olaylar, yönetici aksiyonları |
| `renderer.py` | `ScreenBuffer` / `DiffWriter` (farksal, titreşimsiz), parçacıklar, HUD, modallar |
| `colors.py` | TrueColor ANSI, palet, Windows VT kurulumu |
| `test_office.py` | Headless testler (`unittest`) |
| `run.bat` / `run.ps1` | Windows Terminal başlatıcıları |
