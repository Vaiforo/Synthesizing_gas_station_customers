import pandas as pd
import numpy as np
from pathlib import Path


MORNING_HOURS = (6, 11)


def _ensure_datetime_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"]).dt.date

    if "time" in out.columns:
        out["time"] = pd.to_datetime(
            out["time"].astype(str), errors="coerce").dt.time

    if "datetime" in out.columns:
        out["datetime"] = pd.to_datetime(out["datetime"], errors="coerce")

    if "datetime" not in out.columns and {"date", "time"} <= set(out.columns):
        out["datetime"] = pd.to_datetime(
            out["date"].astype(str) + " " + out["time"].astype(str), errors="coerce"
        )

    return out


def _compute_period_months(user_tx: pd.DataFrame) -> float:
    if "datetime" in user_tx.columns and user_tx["datetime"].notna().any():
        tmin = user_tx["datetime"].min()
        tmax = user_tx["datetime"].max()
    else:
        tmin = pd.to_datetime(user_tx["date"]).min()
        tmax = pd.to_datetime(user_tx["date"]).max()

    days = max(1, (tmax - tmin).days + 1)
    return days / 30.0


def _is_weekend(series_dates: pd.Series) -> pd.Series:
    d = pd.to_datetime(series_dates)
    return d.dt.weekday >= 5


def _is_morning(series_dt: pd.Series) -> pd.Series:
    if series_dt.isna().all():
        return pd.Series(np.nan, index=series_dt.index)
    hours = series_dt.dt.hour
    return (hours >= MORNING_HOURS[0]) & (hours < MORNING_HOURS[1])


def build_user_features(transactions: pd.DataFrame) -> pd.DataFrame:
    tx = _ensure_datetime_cols(transactions)

    needed_cols = {"customer_id", "amount", "fuel_liters"}
    missing = needed_cols - set(tx.columns)
    if missing:
        raise ValueError(
            f"В transactions отсутствуют обязательные колонки {missing}")

    has_datetime = "datetime" in tx.columns and tx["datetime"].notna().any()
    tx["is_weekend"] = _is_weekend(
        tx["date"]) if "date" in tx.columns else False
    tx["is_morning"] = _is_morning(tx["datetime"]) if has_datetime else np.nan
    tx["coffee"] = tx["coffee"].fillna(0).astype(
        int) if "coffee" in tx.columns else 0
    tx["carwash"] = tx["carwash"].fillna(0).astype(
        int) if "carwash" in tx.columns else 0

    grp = tx.groupby("customer_id", as_index=True)

    agg = grp.agg(
        visits_total=("amount", "count"),
        revenue_total=("amount", "sum"),
        avg_check=("amount", "mean"),
        avg_fuel_liters=("fuel_liters", "mean"),
        coffee_sum=("coffee", "sum"),
        carwash_sum=("carwash", "sum"),
        weekend_sum=("is_weekend", "sum"),
        morning_sum=(
            "is_morning", lambda s: np.nan if s.isna().all() else s.sum()),
    )

    period_months = grp.apply(_compute_period_months).rename("period_months")
    agg = agg.join(period_months)

    agg["visits_per_month"] = agg["visits_total"] / \
        agg["period_months"].replace(0, np.nan)
    agg["coffee_attach_rate"] = agg["coffee_sum"] / \
        agg["visits_total"].replace(0, np.nan)
    agg["carwash_attach_rate"] = agg["carwash_sum"] / \
        agg["visits_total"].replace(0, np.nan)
    agg["weekend_share"] = agg["weekend_sum"] / \
        agg["visits_total"].replace(0, np.nan)

    def _morning_share(row):
        if np.isnan(row["morning_sum"]):
            return np.nan
        return row["morning_sum"] / row["visits_total"] if row["visits_total"] else np.nan

    agg["morning_share"] = agg.apply(_morning_share, axis=1)

    if "persona" in tx.columns:
        persona_mode = grp["persona"].agg(
            lambda s: s.mode().iat[0] if not s.mode().empty else np.nan)
        agg["persona_mode"] = persona_mode

    agg = agg.replace([np.inf, -np.inf], np.nan).reset_index()

    features = agg[
        [
            "customer_id",
            "visits_total",
            "visits_per_month",
            "avg_check",
            "avg_fuel_liters",
            "coffee_attach_rate",
            "carwash_attach_rate",
            "morning_share",
            "weekend_share",
            "revenue_total",
        ]
        + (["persona_mode"] if "persona_mode" in agg.columns else [])
    ].copy()

    return features


if __name__ == "__main__":
    tx_path = Path("data/transactions.csv")
    if not tx_path.exists():
        print("Не найден data/transactions.csv")
        raise SystemExit(1)

    tx = pd.read_csv(tx_path)
    feats = build_user_features(tx)
    out_path = Path("data/features.csv")
    feats.to_csv(out_path, index=False)
    print(f"Сохранено {out_path} ({len(feats)} строк)")
