# master-translate — Hy-MT2 Game Localization

Tek bir kalıcı GitHub reposundan farklı oyunların farklı kaynak dillerdeki dosyalarını Türkçeye çevirmek için Hy-MT2 + GitHub Actions altyapısı.

## Temel ilke
- Her oyun için yeni repository oluşturulmaz.
- Hy-MT2 modeli aynı repository'nin GitHub Actions cache'inde tutulur.
- Model ilk cache oluşturulurken Hugging Face'ten indirilir; sonraki işler aynı cache'i geri yükler.
- Haftada iki kez çalışan `model-cache-keepalive.yml`, GitHub'ın erişilmeyen cache'leri silmesini önlemek için cache'e erişir.
- Yeni çeviri işi için yalnız `config/job.json`, `config/context.md`, `config/glossary.json` ve `input/` içeriği değişir.

## Desteklenen kaynaklar
Kaynak dil iş bazında belirlenir: İngilizce, Almanca veya Hy-MT2'nin desteklediği başka bir dil olabilir.

Format adaptörleri: CSV, TSV, XLSX/XLSM, JSON, TXT/LOCRES text export, PO, INI/CFG ve XML.

## Model cache notu
GitHub-hosted runner'lar geçicidir. Bu nedenle model her runner'ın yerel diskinde kalıcı değildir; ancak aynı repo içindeki `actions/cache` sayesinde modelin Hugging Face'ten yeniden indirilmesi gerekmez. Her runner cache'ten kopyayı geri yükler.
