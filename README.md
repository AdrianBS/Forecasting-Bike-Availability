# Forecasting Bike Availability - Bergen Bysykkel

Predicts how many bikes will be available at 9 key Bergen bike-share stations **one hour from now**, using historical station status, trip logs, and weather data.

**[▶ View the full interactive EDA notebook](https://adrianbs.github.io/Forecasting-Bike-Availability/EDA_rendered.html)** · **[📄 Read the full report (PDF)](Project_Report.pdf)**

_Note: This project is written in **Norwegian**._

---

## Results

| Model | Val RMSE | Test RMSE |
|---|---|---|
| Baseline (LOCF) | – | 1.505 |
| ElasticNet | 1.063 | – |
| HistGradientBoosting | 1.098 | – |
| RandomForest | 1.121 | – |
| **SVR (selected)** | **1.061** | **1.461** |

The best model (SVR) beats a last-observation-carried-forward baseline by ~3% RMSE on a chronological hold-out test set. This is modest but consistent, since bike counts change slowly hour to hour and the baseline is already strong outside rush hours.

Trained on **52,622 rows** spanning **2024-04-10 to 2025-05-02** (5,847 hourly time steps × 9 stations), split chronologically 70/15/15 (36,834 / 7,894 / 7,894) to avoid leaking future information into training.

## A few things the data showed

<table>
<tr>
<td width="33%">
<img src="images/observed_vs_locf.png" width="100%"><br>
<sub><b>LOCF tracks well but lags</b> - it over/under-predicts exactly when availability is changing fastest, which is why time and traffic features matter.</sub>
</td>
<td width="33%">
<img src="images/departures_heatmap.png" width="100%"><br>
<sub><b>Clear commute peaks</b> around 06:00 and 14:00 on weekdays, justifying <code>hour_of_day</code> / <code>day_of_week</code> as features.</sub>
</td>
<td width="33%">
<img src="images/free_bikes_per_station.png" width="100%"><br>
<sub><b>Each station has its own rhythm</b> - some drain in the morning, others in the afternoon, so per-station patterns matter more than a global average.</sub>
</td>
</tr>
</table>

## How it works

*(data flow - `pipeline.py`'s output is already committed, so day-to-day you only run `train.py` → `predict.py`; see [Running it yourself](#running-it-yourself))*

```mermaid
flowchart LR
    A[stations.csv<br>trips.csv<br>weather.csv] --> B[pipeline.py<br>hourly grid · LOCF · lags ·<br>rolling windows · weather]
    B --> C[data/processed/<br>model_ready.csv]
    C --> D[train.py<br>chronological 70/15/15 split<br>ElasticNet · RF · HistGBR · SVR]
    D --> E[models/best_model.pkl]
    E --> F[predict.py<br>rebuilds features at t · fills<br>NAs with train medians]
    F --> G[Prediction for t+1h<br>per station, in Europe/Oslo time]
```

1. **`pipeline.py`** - builds an hourly grid per station, forward-fills bike counts (LOCF), joins weather (resampled hourly) and trip-derived features (departures/arrivals, 3h rolling windows, net flow), adds calendar features, and writes `model_ready.csv`. The April–August 2024 window is dropped due to very sparse station coverage.
2. **`train.py`** - chronological 70/15/15 train/val/test split (no shuffling, to avoid leakage), compares ElasticNet, RandomForest, HistGradientBoosting and SVR against the LOCF baseline, and saves the best model + feature schema + training medians with `pickle`.
3. **`predict.py`** - reads the latest raw data, finds the most recent timestamp, rounds up to the next full hour, rebuilds the exact same features used in training, and outputs an integer prediction (≥0) for each station one hour ahead, printed in local Bergen time.

## Repo structure

```
├── raw_data/                 # stations.csv, trips.csv, weather.csv + README.md (field docs)
├── data/processed/           # model_ready.csv (prebuilt output of pipeline.py)
├── EDA.ipynb                 # exploratory data analysis (interactive Plotly charts)
├── pipeline.py                # raw data → model_ready.csv (already run; rerun to refresh)
├── train.py                    # trains + selects + saves the model
├── predict.py                  # loads latest raw data → next-hour prediction
├── requirements.txt           # pinned dependencies
├── Project_Report.pdf       # full written report (Norwegian)
└── hvordan_bruke.txt           # usage notes (Norwegian)
```

## Running it yourself

Raw data is included in [`raw_data/`](raw_data), and `data/processed/model_ready.csv` (the output of `pipeline.py`) is already built and committed, so you can go straight to training and predicting:

```bash
git clone https://github.com/YOUR-USERNAME/YOUR-REPO.git
cd YOUR-REPO
pip install -r requirements.txt

python train.py    # trains models on model_ready.csv, saves the best one to models/
python predict.py  # loads the saved model + latest raw data, prints a next-hour prediction
```

No API keys or extra setup needed - see [`hvordan_bruke.txt`](hvordan_bruke.txt) for troubleshooting notes (e.g. `predict.py` expects the `.pkl` from `train.py` directly under `models/`).

`pipeline.py` is the script that turned raw data into `model_ready.csv` in the first place. You only need to rerun it - before `train.py` - if you've updated `raw_data/` and want to regenerate the processed dataset:

```bash
python pipeline.py  # rebuilds data/processed/model_ready.csv from raw_data/
```

**Example `predict.py` output:**

```
Siste tidsstempel i data: 2025-05-02 17:49:25+0200
Neste hele klokketime: 2025-05-02 18:00:00+0200
Predikerer for: 2025-05-02 19:00:00+0200

                Stasjon  Nåværende sykler  Predikerte sykler
       Florida Bybanestopp                21                 18
          Møllendalsplass                 4                  7
                     ...                ...                ...
```

## Data

Raw data lives in [`raw_data/`](raw_data) - see [`raw_data/README.md`](raw_data/README.md) for full field-level documentation (columns, types, sampling frequency, known quirks like station-name mismatches between files).

Sources:
- [Bergen Bysykkel open data](https://bergenbysykkel.no/en/open-data) - station status & trips
- [Open-Meteo](https://open-meteo.com/) - weather
- [MaxHalford/bike-sharing-history](https://github.com/MaxHalford/bike-sharing-history) - historical station snapshots

## What I'd improve

- **Label naming** - `y_t_plus_1h` is precise but clunky; something shorter would read better throughout the code.
- **Model coverage** - only 4 model types were compared (ElasticNet, RandomForest, HistGradientBoosting, SVR). A gradient-boosted model with more thorough hyperparameter tuning is the most likely next step to push RMSE lower.

## Stack

Python · pandas · scikit-learn · Plotly

---
*Course project, INF161 - University of Bergen, Autumn 2025.*

---
*Course project, INF161 - University of Bergen, Autumn 2025.*
