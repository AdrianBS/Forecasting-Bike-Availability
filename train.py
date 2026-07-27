from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import root_mean_squared_error
from sklearn.linear_model import ElasticNet
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.svm import SVR

ROOT = Path.cwd()
CSV = ROOT / "data" / "processed" / "model_ready.csv"

df = pd.read_csv(CSV, parse_dates=["time"])
LABEL = "y_t_plus_1h"

# Baseline (LOCF)
rmse_baseline = root_mean_squared_error(df[LABEL], df["free_bikes"])
print(f"Baseline RMSE (LOCF) på hele settet: {rmse_baseline:.3f}")


# features kolonner
drop_cols = ["time", LABEL]
X_df = df.drop(columns=drop_cols).copy()
y = df[LABEL].to_numpy()

X_df = pd.get_dummies(X_df, columns=["station"], dtype=int)

#Deler opp data

X_trainval, X_test, y_trainval, y_test, strat_trainval, strat_test = train_test_split(
    X_df, y, df["station"], test_size=0.15, random_state=42, shuffle=False
)
X_train, X_val, y_train, y_val = train_test_split(
    X_trainval, y_trainval, test_size=0.15/0.85, random_state=42,
    shuffle=False
)

print("Størrelser:", len(X_train), len(X_val), len(X_test))

models = {
    "ElasticNet": ElasticNet(alpha=0.1, l1_ratio=0.5, random_state=42, max_iter=5000),
    "RandomForest": RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1),
    "HistGBR": HistGradientBoostingRegressor(random_state=42),
    "SVR": SVR(kernel="rbf", C=10.0, epsilon=0.2),
}

def rmse(y_true, y_pred):
    return root_mean_squared_error(y_true, y_pred)

train_median = X_train.median(numeric_only=True)
X_train = X_train.fillna(train_median)
X_val = X_val.fillna(train_median)
X_test = X_test.fillna(train_median)

X_train_t = X_train.values
X_val_t = X_val.values
X_test_t = X_test.values


results = {}
for name, model in models.items():
    model.fit(X_train_t, y_train)
    rmse_tr = rmse(y_train, model.predict(X_train_t))
    rmse_va = rmse(y_val, model.predict(X_val_t))
    results[name] = {"rmse_train": rmse_tr, "rmse_val": rmse_va}

results_df = pd.DataFrame(results).T.sort_values("rmse_val")
print(results_df)
best_name = results_df.index[0]
print("Beste på val:", best_name)
best_model = models[best_name]

# Slår sammen train+val
X_trva = np.vstack([X_train_t, X_val_t])
y_trva = np.concatenate([y_train, y_val])

best_model.fit(X_trva, y_trva)
rmse_test = rmse(y_test, best_model.predict(X_test_t))

print(f"Baseline RMSE (LOCF): {rmse_baseline:.3f}")
print(f"{best_name} test-RMSE: {rmse_test:.3f}")

# Lagre modellen
import pickle

MODELD = ROOT / "models"
MODELD.mkdir(parents=True, exist_ok=True)

artifact = {
    "model": best_model,
    "feature_columns": list(X_df.columns),
    "train_median": train_median.to_dict(),
    "label": LABEL,
}

model_path = MODELD / f"{best_name}.pkl"
with open(model_path, "wb") as f:
    pickle.dump(artifact, f, protocol=pickle.HIGHEST_PROTOCOL)

print("Lagret med pickle:", model_path)