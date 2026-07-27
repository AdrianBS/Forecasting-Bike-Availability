# Bergen Bysykkel & Værdata

Dette datasettet inneholder prosesserte bysykkel- og værdata fra Bergen.

## 📁 Datasett-oversikt

| Fil | Beskrivelse |
|-----|-------------|
| `stations.csv` | Sanntidsdata for bysykkelstasjoner |
| `trips.csv` | Individuelle sykkelturer |
| `weather.csv` | Værmålinger |


## 🚲 stations.csv

**Beskrivelse:** Status for bysykkelstasjoner hentet ca. hvert 15. minutt via bysykkel-API.

### Felter

| Field | Type | Beskrivelse |
|-------|------|-------------|
| `station` | `object` | Navn på bysykkelstasjonen |
| `longitude` | `float64` | Lengdegrad for stasjonen |
| `latitude` | `float64` | Breddegrad for stasjonen |
| `timestamp` | `datetime64[ns, UTC]` | Tidsstempel for registrering i UTC |
| `skipped_updates` | `int64` | Antall påfølgende uendrede målinger |
| `free_bikes` | `int64` | Tilgjengelige sykler på stasjonen |
| `free_spots` | `int64` | Tilgjengelige dokking-plasser på stasjonen |


### Merknader

- **Samplingsfrekvens:** ~15 minutter
- **Datakomprimering:** Registrerer kun endringer i stasjonsstatus. Når ingen endring oppdages, økes `skipped_updates` uten å legge til ny rad. Ved statusendring tilbakestilles `skipped_updates` til 0 og ny rad legges til.

---

## 🚴 trips.csv

**Beskrivelse:** Individuelle sykkelturer med start-/slutt-tidspunkt og lokasjoner.

### Felter

| Field | Type | Beskrivelse |
|-------|------|-------------|
| `started_at` | `datetime64[ns, UTC]` | Starttidspunkt for turen i UTC |
| `ended_at` | `datetime64[ns, UTC]` | Sluttidspunkt for turen i UTC |
| `start_station_name` | `object` | Navn på startstasjon |
| `end_station_name` | `object` | Navn på sluttstasjon |
| `start_station_latitude` | `float64` | Breddegrad for startstasjon |
| `start_station_longitude` | `float64` | Lengdegrad for startstasjon |
| `end_station_latitude` | `float64` | Breddegrad for sluttstasjon |
| `end_station_longitude` | `float64` | Lengdegrad for sluttstasjon |


### Merknader

- **Konsistens i stasjonsnavn:** Stasjonsnavn stemmer ikke nødvendigvis overens med de i `stations.csv`

---

## 🌤️ weather.csv

**Beskrivelse:** Værmålinger for Bergen-området.

### Felter

| Field | Type | Enhet | Beskrivelse |
|-------|------|-------|-------------|
| `timestamp` | `datetime64[ns, UTC]` | - | Måletidspunkt konvertert fra Bergen lokal tid til UTC |
| `temperature` | `float64` | °C | Lufttemperatur |
| `precipitation` | `float64` | mm | Nedbør (regn + smeltet snø) |
| `wind_speed` | `float64` | m/s | Vindhastighet |



**Datakilder:**
- https://open-meteo.com/
- https://bergenbysykkel.no/en/open-data
- https://github.com/MaxHalford/bike-sharing-history

