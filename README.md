# EismoInfo Home Assistant integracija

[![Validate](https://github.com/triumfas/HAEismoInfo/actions/workflows/validate.yml/badge.svg)](https://github.com/triumfas/HAEismoInfo/actions/workflows/validate.yml)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant custom integracija, kuri naudoja viešą [eismoinfo.lt](https://eismoinfo.lt) API ir
sukuria sensorius pasirinktoms kelių orų stotelėms (KOS).

## Galimybės

- Prisijungiama prie viešo eismoinfo.lt „weather-conditions“ API (autentifikacijos nereikia).
- Galima pridėti bet kiek stotelių – kiekvienai sukuriamas atskiras įrenginys (device).
- Kiekvienai stotelei galima nustatyti **savo pavadinimą**, nebūtinai tą, kurį grąžina API.
- Pavadinimą ir atnaujinimo intervalą bet kada galima pakeisti per integracijos nustatymus
  (Options).
- Kiekvienai stotelei sukuriami sensoriai: oro temperatūra, kelio dangos temperatūra, rasos
  taškas, vėjo greitis (vidutinis/maksimalus) ir kryptis, kritulių tipas ir kiekis, matomumas,
  kelio dangos būklė, sukibimo koeficientas, įspėjimai ir paskutinio atnaujinimo laikas.
- Papildomai (išjungti pagal nutylėjimą, nes daugumoje stotelių duomenų nėra): užšalimo taškas ir
  kelio konstrukcijos temperatūros keliuose gyliuose.

## Diegimas

### Per HACS (rekomenduojama)

1. HACS → Integrations → meniu (⋮) → **Custom repositories**.
2. Įveskite `https://github.com/triumfas/HAEismoInfo`, kategorija **Integration**.
3. Susiraskite „EismoInfo“ sąraše ir įdiekite.
4. Perkraukite Home Assistant.

### Rankiniu būdu

1. Nukopijuokite `custom_components/eismoinfo` aplanką į savo HA `config/custom_components/`.
2. Perkraukite Home Assistant.

## Konfigūravimas

1. **Nustatymai → Įrenginiai ir paslaugos → Pridėti integraciją** → ieškokite „EismoInfo“.
2. Pasirinkite norimą stotelę iš sąrašo.
3. Nebūtina: įveskite savo pavadinimą stotelei (jei paliksite tuščią, bus naudojamas API
   pavadinimas).
4. Kartokite žingsnius kiekvienai norimai stotelei.

Norėdami pervadinti stotelę arba pakeisti atnaujinimo dažnį vėliau, eikite į integracijos kortelę
→ **Konfigūruoti** (Options).

## Sensoriai

| Sensorius | Vienetas | Pagal nutylėjimą |
|---|---|---|
| Oro temperatūra | °C | ✅ |
| Kelio dangos temperatūra | °C | ✅ |
| Rasos taškas | °C | ✅ |
| Vidutinis / maksimalus vėjo greitis | m/s | ✅ |
| Vėjo kryptis | – | ✅ |
| Kritulių tipas / kiekis | – / mm | ✅ |
| Matomumas | m | ✅ |
| Kelio danga | – | ✅ |
| Sukibimo koeficientas | – | ✅ |
| Įspėjimai | – | ✅ |
| Paskutinis atnaujinimas | – | ✅ |
| Užšalimo taškas | °C | ❌ |
| Konstrukcijos temperatūra (7–200 cm) | °C | ❌ |

## Duomenų šaltinis

Duomenys imami iš viešo, neautorizuoto eismoinfo.lt API. Integracija naudoja vieną bendrą
užklausą visoms stotelėms (kas ~5 min pagal nutylėjimą), nepriklausomai nuo to, kiek stotelių
pridėta Home Assistant'e.

## Licencija

[MIT](LICENSE)
