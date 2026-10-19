# Hex2Vec embedding model (trained by the ETL job)

_Captured 2026-10-19 17:00:15 UTC by `scripts/capture_evidence.py`._

Model artifacts in UC Volume `/Volumes/geo_sme_emea_catalog/site_selection/models/hex2vec`:

| file | bytes | modified |
|---|---|---|
| config.json | 2,810 | 2026-10-19 16:57:51 UTC |
| hex2vec_metadata.json | 2,827 | 2026-10-19 16:57:51 UTC |
| model.pt | 24,957 | 2026-10-19 16:57:51 UTC |

## Training metadata (`hex2vec_metadata.json`)

- **Cities:** 37 — Москва (RU), London (GB), Roma (IT), New York (US), Berlin (DE), Helsinki (FI), Oslo (NO), Chicago (US), Warszawa (PL), Madrid (ES), Praha (CZ), Vilnius (LT), Астана (KZ), Wien (AT), Мінск (BY), Rīga (LV), Београд (RS), Bratislava (SK), San Francisco (US), Kraków (PL), Gdańsk (PL), Wrocław (PL), Łódź (PL), Zagreb (HR), Stockholm (SE), Poznań (PL), Reykjavík (IS), Ljubljana (SI), Amsterdam (NL), Tallinn (EE), София (BG), Dublin (IE), Paris (FR), Lisboa (PT), Luxembourg (LU), Bern (CH), Bruxelles - Brussel (BE)
- **H3 resolution:** 9
- **Regions (H3 cells with ≥1 feature):** 106,365 of 196,022 cells covering the training cities
- **Features (POIs + buildings):** 5,004,905
- **Feature categories:** 43
- **Encoder sizes:** [48, 24, 12] · **max epochs:** 10 · **batch size:** 256
- **Saved at:** 2026-10-19T16:57:49.890641+00:00
