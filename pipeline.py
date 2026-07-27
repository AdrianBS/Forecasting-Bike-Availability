from pathlib import Path
import argparse
import pandas as pd
import numpy as np

BAD_START = pd.Timestamp("2024-04-01 00:00:00", tz="UTC")
BAD_END   = pd.Timestamp("2024-08-31 23:59:59", tz="UTC")

TARGETS = [
    "Møllendalsplass","Torgallmenningen","Grieghallen","Høyteknologisenteret",
    "Studentboligene","Akvariet","Damsgårdsveien 71","Dreggsallmenningen Sør",
    "Florida Bybanestopp"
]

def project_root() -> Path:
    p = Path(__file__).resolve().parent
    while p != p.parent and not (p / "raw_data").exists():
        p = p.parent
    return p

def parse_ts(s: pd.Series) -> pd.Series:
    x = pd.to_datetime(s, format="%Y-%m-%d %H:%M:%S.%f%z", utc=True, errors="coerce")
    m = x.isna()
    if m.any():
        x.loc[m] = pd.to_datetime(s[m], format="%Y-%m-%d %H:%M:%S%z", utc=True, errors="coerce")
    return x

def load_data(raw: Path):
    stations = pd.read_csv(raw / "stations.csv")
    stations["timestamp"] = pd.to_datetime(stations["timestamp"], utc=True)

    trips = pd.read_csv(raw / "trips.zip")
    trips["started_at"] = parse_ts(trips["started_at"])
    trips["ended_at"]   = parse_ts(trips["ended_at"])

    weather = pd.read_csv(raw / "weather.csv")
    weather["timestamp"] = pd.to_datetime(weather["timestamp"], utc=True)
    return stations, trips, weather

def hourly_free_bikes(stations: pd.DataFrame, targets: list[str]) -> pd.DataFrame:
    parts = []
    for name in targets:
        g = stations.loc[stations["station"] == name, ["timestamp","free_bikes"]].sort_values("timestamp")
        if g.empty:
            continue
        hours = pd.DataFrame({"time": pd.date_range(g["timestamp"].min().floor("h"),
                                                   g["timestamp"].max().ceil("h"),
                                                   freq="h", tz="UTC")})
        merged = pd.merge_asof(hours, g.rename(columns={"timestamp":"time"}),
                               on="time", direction="backward")
        merged["station"] = name
        parts.append(merged[["station","time","free_bikes"]])
    fb = pd.concat(parts, ignore_index=True).sort_values(["station","time"]).reset_index(drop=True)
    fb["y_t_plus_1h"] = fb.groupby("station")["free_bikes"].shift(-1)
    fb = fb.dropna(subset=["free_bikes","y_t_plus_1h"]).reset_index(drop=True)
    return fb

def weather_hourly(weather: pd.DataFrame) -> pd.DataFrame:
    return (weather.sort_values("timestamp")
            .set_index("timestamp")
            .resample("h")
            .agg({"temperature":"mean","precipitation":"sum","wind_speed":"mean"})
            .reset_index()
            .rename(columns={"timestamp":"time"}))

def trips_features(trips: pd.DataFrame, targets: list[str]) -> pd.DataFrame:
    trips = trips.copy()
    trips["hour"] = trips["started_at"].dt.floor("h")
    dep = (trips[trips["start_station_name"].isin(targets)]
           .groupby(["start_station_name","hour"]).size()
           .rename("departures").reset_index()
           .rename(columns={"start_station_name":"station","hour":"time"}))
    arr = (trips[trips["end_station_name"].isin(targets)]
           .groupby(["end_station_name","hour"]).size()
           .rename("arrivals").reset_index()
           .rename(columns={"end_station_name":"station","hour":"time"}))
    feats = dep.merge(arr, on=["station","time"], how="outer")
    feats[["departures","arrivals"]] = feats[["departures","arrivals"]].fillna(0).astype(int)
    return feats

def build_dataset(stations, trips, weather, targets):
    fb = hourly_free_bikes(stations, targets)
    w  = weather_hourly(weather)
    tf = trips_features(trips, targets)

    df = (fb.merge(w, on="time", how="left")
            .merge(tf, on=["station","time"], how="left"))

    # Fjerner perioden vi vil ekskludere
    df = df.loc[~((df["time"] >= BAD_START) & (df["time"] <= BAD_END))].copy()

    # Fyll manglende departures og arrivals med 0
    for c in ["departures","arrivals"]:
        if c in df:
            df[c] = df[c].fillna(0).astype(int)

    # Tidsfeatures
    df = df.sort_values(["station","time"]).reset_index(drop=True)
    df["hour_of_day"] = df["time"].dt.hour
    df["day_of_week"] = df["time"].dt.dayofweek
    df["is_weekend"]  = df["day_of_week"] >= 5

    # omberegner y_t_plus_1h
    t_next = df.groupby("station")["time"].shift(-1)
    y_next = df.groupby("station")["free_bikes"].shift(-1)
    mask   = (t_next - df["time"] == pd.Timedelta(hours=1))
    df["y_t_plus_1h"] = y_next.where(mask)

    # Rolling trafikk
    for c in ["departures","arrivals"]:
        df[f"{c}_3h"] = (df.groupby("station")[c]
                           .rolling(3, min_periods=1).sum()
                           .reset_index(level=0, drop=True))

    # Net flow
    df["net_flow"]    = df["arrivals"]    - df["departures"]
    df["net_flow_3h"] = df["arrivals_3h"] - df["departures_3h"]

    # Lagg/MA av free_bikes
    df["free_bikes_lag1"] = df.groupby("station")["free_bikes"].shift(1)
    df["free_bikes_ma3"]  = (df.groupby("station")["free_bikes"]
                               .rolling(3, min_periods=1).mean()
                               .reset_index(level=0, drop=True))

    # drop rader uten label eller lag1
    df = df.dropna(subset=["y_t_plus_1h","free_bikes_lag1"]).reset_index(drop=True)
    return df

def sanity(df: pd.DataFrame):
    # sorter og sjekk nøkkelting
    df = df.sort_values(["station","time"]).reset_index(drop=True)
    assert df.duplicated(["station","time"]).sum() == 0, "Duplikater i (station,time)"
    assert df["y_t_plus_1h"].notna().all(), "Label har NaN"
    next_time = df.groupby("station")["time"].shift(-1)
    chk = df.groupby("station")["free_bikes"].shift(-1)
    mask = next_time.notna()
    assert (df.loc[mask,"y_t_plus_1h"].values == chk.loc[mask].values).all(), "Label feiljustert"
    assert (df["free_bikes"] >= 0).all(), "free_bikes < 0"
    return df

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=str, default=None, help="Path til output CSV")
    args = parser.parse_args()

    ROOT = project_root()
    RAW  = ROOT / "raw_data"
    OUTD = ROOT / "data" / "processed"
    OUTD.mkdir(parents=True, exist_ok=True)

    stations, trips, weather = load_data(RAW)
    df = build_dataset(stations, trips, weather, TARGETS)
    df = sanity(df)

    out_path = Path(args.out) if args.out else (OUTD / "model_ready.csv")
    df.to_csv(out_path, index=False)
    print(f"Skrevet {len(df)} rader til {out_path}")
    print("Kolonner:", ", ".join(df.columns[:14]), "...")

if __name__ == "__main__":
    main()
