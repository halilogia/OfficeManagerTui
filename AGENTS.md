# 🤖 Agents Constitution (OfficeManagerTui)

Bu repo, Triad otonom ekibi (Antigravity & Claude Code) tarafından geliştirilmektedir.

## 1. Temel Standartlar
* **Tek Sorumluluk İlkesi (SRP):** Her modül tek bir sorumluluğa sahiptir. Modüller 300 satırı aşarsa alt modüllere bölünmelidir.
* **0 Harici Bağımlılık:** `requirements.txt` veya harici pip paketleri eklenemez.
* **Titreşimsiz Kuralı:** Render kodlarında asla tam ekran temizleme (`\033[2J`) yapılmaz; `DiffWriter` ve `ScreenBuffer` kullanılır.

## 2. Doğrulama ve Bitiş Tanımı (Definition of Done)
* Tüm değişikliklerden sonra `python test_office.py` çalıştırılmalı ve 30 testin tamamı firesiz geçmelidir.
* `python -m py_compile` ile sözdizimi doğrulanmalıdır.
* Değişiklikler commit edildikten sonra `git push` ile uzak depoya gönderilmelidir.
