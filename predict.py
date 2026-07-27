from pathlib import Path
import pickle
import pandas as pd
import numpy as np

TARGETS = [
    "Møllendalsplass","Torgallmenningen","Grieghallen","Høyteknologisenteret",
    "Studentboligene","Akvariet","Damsgårdsveien 71","Dreggsallmenningen Sør",
    "Florida Bybanestopp"
]

def parse_ts(s: pd.Series) -> pd.Series:
    """Parser timestamps med to ulike formater"""
    x = pd.to_datetime(s, format="%Y-%m-%d %H:%M:%S.%f%z", utc=True, errors="coerce")
    m = x.isna()
    if m.any():
        x.loc[m] = pd.to_datetime(s[m], format="%Y-%m-%d %H:%M:%S%z", utc=True, errors="coerce")
    return x

def load_raw_data():
    """Laster inn rådata"""
    ROOT = Path.cwd()
    RAW = ROOT / "raw_data"
    
    stations = pd.read_csv(RAW / "stations.csv")
    stations["timestamp"] = pd.to_datetime(stations["timestamp"], utc=True)
    
    trips = pd.read_csv(RAW / "trips.zip")
    trips["started_at"] = parse_ts(trips["started_at"])
    trips["ended_at"] = parse_ts(trips["ended_at"])
    
    weather = pd.read_csv(RAW / "weather.csv")
    weather["timestamp"] = pd.to_datetime(weather["timestamp"], utc=True)
    
    return stations, trips, weather

# Vi trenger egentlig ikke hele denne da siste tidsstempel som vi er ute etter er bare for stations
# men det kan fortsatt være greit å ha den hvis man vil se på siste tidsstempel i alle datasett
# Grunnen til at jeg skriver dette er fordi oppgaven ber om å ta inn alle tre datasettene, men
# etter å ha spurt foreleser så skal vi bare se på siste tidsstempel i stations for prediksjonen.
def get_latest_timestamps(stations):
    """Finner siste tidsstempel og neste hele klokketime"""
    s_max = stations["timestamp"].max()
    # tr_max = pd.concat([trips["started_at"], trips["ended_at"]]).max()
    # w_max = weather["timestamp"].max()
    
    # Kan legge inn / bytte ut s_max med tr_max og w_max i last_ts, eller ta max mellom de for å sammenligne
    last_ts = s_max
    next_hour = last_ts.ceil("h")
    pred_time = next_hour + pd.Timedelta(hours=1)
    
    return last_ts, next_hour, pred_time

def build_features_for_time(stations, trips, weather, target_time):
    """Bygger features for en spesifikk time (target_time)"""
    rows = []
    
    for station_name in TARGETS:
        # Free bikes features (siste 3 timer)
        st_data = stations[stations["station"] == station_name].copy()
        st_data = st_data.sort_values("timestamp")
        
        # Lager tidsvindu: [target_time - 2h, target_time - 1h, target_time]
        time_window = pd.date_range(
            target_time - pd.Timedelta(hours=2), 
            target_time, 
            freq="h", 
            tz="UTC"
        )
        
        # Merge asof for å få free_bikes for hver time
        grid = pd.DataFrame({"time": time_window})
        merged = pd.merge_asof(
            grid, 
            st_data.rename(columns={"timestamp": "time"})[["time", "free_bikes"]],
            on="time", 
            direction="backward"
        )
        
        # Beregner features
        free_bikes = merged.loc[merged["time"] == target_time, "free_bikes"].values[0] if len(merged) > 0 else np.nan
        free_bikes_lag1 = merged.loc[merged["time"] == target_time - pd.Timedelta(hours=1), "free_bikes"].values[0] if len(merged) > 1 else np.nan
        free_bikes_ma3 = merged["free_bikes"].mean()
        
        rows.append({
            "station": station_name,
            "time": target_time,
            "free_bikes": free_bikes,
            "free_bikes_lag1": free_bikes_lag1,
            "free_bikes_ma3": free_bikes_ma3
        })
    
    df = pd.DataFrame(rows)
    
    # Weather features (aggregert for target_time)
    w = weather.copy()
    w = w.sort_values("timestamp").set_index("timestamp")
    w_hourly = w.resample("h").agg({
        "temperature": "mean",
        "precipitation": "sum",
        "wind_speed": "mean"
    }).reset_index().rename(columns={"timestamp": "time"})
    
    df = df.merge(w_hourly[w_hourly["time"] == target_time], on="time", how="left")
    
    # Trips features
    trips_copy = trips.copy()
    trips_copy["hour"] = trips_copy["started_at"].dt.floor("h")
    
    # Departures og arrivals for siste 3 timer
    time_window_3h = pd.date_range(
        target_time - pd.Timedelta(hours=2), 
        target_time, 
        freq="h", 
        tz="UTC"
    )
    
    # Departures
    dep = (trips_copy[trips_copy["start_station_name"].isin(TARGETS)]
           .groupby(["start_station_name", "hour"]).size()
           .reset_index(name="departures")
           .rename(columns={"start_station_name": "station", "hour": "time"}))
    
    # Arrivals
    arr = (trips_copy[trips_copy["end_station_name"].isin(TARGETS)]
           .groupby(["end_station_name", "hour"]).size()
           .reset_index(name="arrivals")
           .rename(columns={"end_station_name": "station", "hour": "time"}))
    
    trips_features = []
    for station_name in TARGETS:
        dep_station = dep[dep["station"] == station_name]
        arr_station = arr[arr["station"] == station_name]
        
        # Current hour
        dep_t = dep_station[dep_station["time"] == target_time]["departures"].sum()
        arr_t = arr_station[arr_station["time"] == target_time]["arrivals"].sum()
        
        # 3-hour rolling
        dep_3h = dep_station[dep_station["time"].isin(time_window_3h)]["departures"].sum()
        arr_3h = arr_station[arr_station["time"].isin(time_window_3h)]["arrivals"].sum()
        
        trips_features.append({
            "station": station_name,
            "departures": int(dep_t),
            "arrivals": int(arr_t),
            "departures_3h": int(dep_3h),
            "arrivals_3h": int(arr_3h)
        })
    
    trips_df = pd.DataFrame(trips_features)
    df = df.merge(trips_df, on="station", how="left")
    
    # Net flow
    df["net_flow"] = df["arrivals"] - df["departures"]
    df["net_flow_3h"] = df["arrivals_3h"] - df["departures_3h"]
    
    # Tidsfeatures
    df["hour_of_day"] = df["time"].dt.hour
    df["day_of_week"] = df["time"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"] >= 5
    
    return df

def main():
    ROOT = Path.cwd()
    MODELD = ROOT / "models"
    
    # Last modellen
    pkl_path = max(MODELD.glob("*.pkl"), key=lambda p: p.stat().st_mtime)
    with open(pkl_path, "rb") as f:
        artifact = pickle.load(f)
    
    model = artifact["model"]
    feature_columns = artifact["feature_columns"]
    train_median = artifact["train_median"]
    label_name = artifact.get("label", "y_t_plus_1h")
    
    # Last rådata
    stations, trips, weather = load_raw_data()
    
    # Finn tidspunkter
    last_ts, next_hour, pred_time = get_latest_timestamps(stations)
    
    # Bygg features for neste hele klokketime
    df = build_features_for_time(stations, trips, weather, next_hour)
    
    # Preprosesser som i train.py
    X_df = df.drop(columns=["time", label_name], errors="ignore").copy()
    X_df = pd.get_dummies(X_df, columns=["station"], dtype=int)
    
    # Legg til manglende kolonner og sorter
    for col in feature_columns:
        if col not in X_df.columns:
            X_df[col] = 0
    X_df = X_df[feature_columns]
    
    # Fyll inn manglende verdier
    X_df = X_df.fillna(pd.Series(train_median))
    
    # Prediker
    y_pred = model.predict(X_df.values)
    y_pred_int = np.clip(np.rint(y_pred).astype(int), 0, None)
    
    # Lag output
    out = df[["station", "free_bikes"]].copy()
    out["Predikerte sykler"] = y_pred_int
    
    # Sorter i TARGETS-rekkefølge
    out["station"] = pd.Categorical(out["station"], categories=TARGETS, ordered=True)
    out = out.sort_values("station").reset_index(drop=True)
    
    # Konverter til lokal Bergen-tid
    oslo_tz = "Europe/Oslo"
    last_local = last_ts.tz_convert(oslo_tz)
    next_local = next_hour.tz_convert(oslo_tz)
    pred_local = pred_time.tz_convert(oslo_tz)
    
    # Print resultater
    print(f"Siste tidsstempel i data: {last_local.strftime('%Y-%m-%d %H:%M:%S%z')}")
    print(f"Neste hele klokketime: {next_local.strftime('%Y-%m-%d %H:%M:%S%z')}")
    print(f"Predikerer for: {pred_local.strftime('%Y-%m-%d %H:%M:%S%z')}")
    print()
    print(out.rename(columns={
        "station": "Stasjon",
        "free_bikes": "Nåværende sykler"
    }).to_string(index=False))

if __name__ == "__main__":
    main()