# 🧠 Knowledge (OfficeManagerTui)

Projenin oturumlar arası kalıcı mühendislik hafızası ve mimari kararları (ADR).

## 1. Kararlar ve Standartlar
* **ADR-01: Pure Python & 0 Bağımlılık:** Harici paket yükleme sorunlarını ve Windows platformu uyumsuzluklarını önlemek için yalnızca `sys`, `os`, `time`, `msvcrt`, `ctypes` kullanıldı.
* **ADR-02: Diferansiyel Render:** `clearScreen` (`\033[2J`) terminalde yoğun titreşime neden olduğu için `DiffWriter` ile yalnızca değişen koordinatlar `\033[{y};{x}H` ile üzerine yazılır.
* **ADR-03: Windows Terminal Kaçış Koruması:** `run.bat` içerisinde `%~dp0` değişkeninin ters bölü ile bitmesi Windows argüman kaçışını bozduğu için `-d "%CD%."` parametresi benimsendi.
