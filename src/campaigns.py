# src/campaigns.py
import pandas as pd
import numpy as np
import yaml
from datetime import timedelta
from pathlib import Path
from typing import Tuple, Dict, Optional

def load_config(path: str = "config/personas.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _user_baseline_stats(tx_user: pd.DataFrame) -> dict:
    """Быстрые базовые метрики пользователя: для синтеза доп. визитов."""
    if tx_user.empty:
        return {"avg_amount": 1500.0, "avg_fuel": 25.0, "coffee_rate": 0.1, "carwash_rate": 0.05}
    avg_amount = float(tx_user["amount"].mean())
    avg_fuel = float(tx_user["fuel_liters"].mean()) if "fuel_liters" in tx_user else 25.0
    coffee_rate = float((tx_user.get("coffee", 0).mean() if "coffee" in tx_user else 0.0))
    carwash_rate = float((tx_user.get("carwash", 0).mean() if "carwash" in tx_user else 0.0))
    return {
        "avg_amount": max(200.0, avg_amount),
        "avg_fuel": max(5.0, avg_fuel),
        "coffee_rate": np.clip(coffee_rate, 0.0, 1.0),
        "carwash_rate": np.clip(carwash_rate, 0.0, 1.0),
    }

def _sample_dt_like(tx: pd.DataFrame, n: int) -> pd.Series:
    """Сэмплим новые timestamps рядом с концом периода (±7 дней от максимальной даты)."""
    if "datetime" in tx.columns and tx["datetime"].notna().any():
        tmax = pd.to_datetime(tx["datetime"]).max()
    else:
        tmax = pd.to_datetime(tx["date"]).max() if "date" in tx.columns else pd.Timestamp.utcnow()

    # равномерно в последние 7 дней + время 06:00..22:00
    deltas = pd.to_timedelta(np.random.randint(0, 7, size=n), unit="D")
    times = pd.to_timedelta(np.random.randint(6 * 3600, 22 * 3600, size=n), unit="s")

    dt_idx = (tmax - deltas) + times  # DatetimeIndex
    return pd.Series(dt_idx).reset_index(drop=True)  # <-- теперь есть .iloc


def _ensure_cols(tx: pd.DataFrame) -> pd.DataFrame:
    """Гарантируем наличие базовых колонок для кампаний."""
    out = tx.copy()
    if "coffee" not in out:
        out["coffee"] = 0
    if "carwash" not in out:
        out["carwash"] = 0
    if "datetime" not in out and {"date", "time"} <= set(out.columns):
        out["datetime"] = pd.to_datetime(out["date"].astype(str) + " " + out["time"].astype(str), errors="coerce")
    if "date" not in out:
        out["date"] = pd.to_datetime(out["datetime"]).dt.date
    if "time" not in out:
        out["time"] = pd.to_datetime(out["datetime"]).dt.strftime("%H:%M:%S")
    return out

def split_cohort(
    customers: pd.DataFrame,
    target_personas: list[str],
    segment_col: str = "persona",
    ratio: float = 0.5,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Делим целевую аудиторию (по портретам) на группы A/B.
    Возврат: DataFrame[customer_id, group] только по таргету.
    """
    rng = np.random.default_rng(seed)
    cohort = customers[customers[segment_col].isin(target_personas)][["customer_id"]].copy()
    n = len(cohort)
    if n == 0:
        return pd.DataFrame(columns=["customer_id", "group"])
    mask = rng.random(n) < ratio
    cohort["group"] = np.where(mask, "B", "A")
    return cohort

def _apply_fuel_discount(
    tx: pd.DataFrame,
    customers: pd.DataFrame,
    cohort_ab: pd.DataFrame,
    campaign_cfg: dict,
    seed: int = 42,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Логика кампании 'fuel_discount':
      - Для B: добавляем доп. визиты ~ Binomial(visits, uplift_visits_pct)
      - Для новых визитов: amount *= (1 + uplift_avg_check_pct)
      - Вероятность кофе чуть растёт на uplift_coffee_attach (абс. п.п., клип 0..1)
    """
    rng = np.random.default_rng(seed)
    uplift_v = float(campaign_cfg.get("uplift_visits_pct", 0.0))
    uplift_amount = float(campaign_cfg.get("uplift_avg_check_pct", 0.0))
    uplift_coffee = float(campaign_cfg.get("uplift_coffee_attach", 0.0))

    tx = _ensure_cols(tx)
    tx_extra = []

    b_ids = set(cohort_ab.loc[cohort_ab["group"] == "B", "customer_id"].astype(int))
    tx_by_user = {cid: df for cid, df in tx.groupby("customer_id")}
    persona_map = customers.set_index("customer_id")["persona"].to_dict()

    added_count = 0
    for cid in b_ids:
        base = tx_by_user.get(cid, pd.DataFrame(columns=tx.columns))
        stats = _user_baseline_stats(base)

        baseline_visits = len(base) if len(base) > 0 else 4
        add_n = rng.binomial(baseline_visits, np.clip(uplift_v, 0.0, 1.0))
        if add_n <= 0:
            continue

        new_dt = _sample_dt_like(tx, add_n)

        for i in range(add_n):
            dt = new_dt.iloc[i]
            amt = float(stats["avg_amount"]) * (1.0 + float(rng.normal(0.0, 0.05)))
            amt *= (1.0 + uplift_amount)
            fuel = max(5.0, float(stats["avg_fuel"]) * (1.0 + float(rng.normal(0.0, 0.05))))
            coffee_p = float(np.clip(stats["coffee_rate"] + uplift_coffee, 0.0, 1.0))
            carwash_p = float(np.clip(stats["carwash_rate"], 0.0, 1.0))
            c = int(rng.random() < coffee_p)
            w = int(rng.random() < carwash_p)

            tx_extra.append(
                [
                    cid,
                    persona_map.get(cid, base["persona"].iloc[0] if not base.empty else "Unknown"),
                    dt,
                    dt.date().isoformat(),
                    dt.strftime("%H:%M:%S"),
                    round(max(200.0, amt), 2),
                    round(fuel, 1),
                    c,
                    w,
                ]
            )
            added_count += 1

    if tx_extra:
        add_df = pd.DataFrame(
            tx_extra,
            columns=["customer_id", "persona", "datetime", "date", "time", "amount", "fuel_liters", "coffee", "carwash"],
        )
        tx_after = pd.concat([tx, add_df], ignore_index=True)
    else:
        tx_after = tx.copy()

    meta = {"added_visits": int(added_count)}
    return tx_after.sort_values(["datetime", "customer_id"]).reset_index(drop=True), meta



def _apply_coffee_coupon(
    tx: pd.DataFrame,
    customers: pd.DataFrame,
    cohort_ab: pd.DataFrame,
    campaign_cfg: dict,
    seed: int = 42,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Логика кампании 'coffee_coupon':
      - Для B: повышаем attach кофе в УТРО (6-11) на uplift_coffee_attach (абс. п.п., клип 0..1)
      - Также добавляем доп. визиты ~ Binomial(visits, uplift_visits_pct) (с высоким шансом кофе утром)
      - Небольшой рост среднего чека (uplift_avg_check_pct)
    """
    rng = np.random.default_rng(seed)
    uplift_v = float(campaign_cfg.get("uplift_visits_pct", 0.0))
    uplift_amount = float(campaign_cfg.get("uplift_avg_check_pct", 0.0))
    uplift_coffee = float(campaign_cfg.get("uplift_coffee_attach", 0.0))

    tx = _ensure_cols(tx).copy()
    b_ids = set(cohort_ab.loc[cohort_ab["group"] == "B", "customer_id"].astype(int))
    persona_map = customers.set_index("customer_id")["persona"].to_dict()

    # 1) Повышаем кофе в уже существующих УТРО-визитах для B
    mask_b = tx["customer_id"].isin(b_ids)
    dt_series = pd.to_datetime(tx["datetime"])
    morning_mask = (dt_series.dt.hour >= 6) & (dt_series.dt.hour < 11)
    # вероятность переключения 0->1
    switch_prob = np.clip(uplift_coffee, 0.0, 1.0)
    idx_to_flip = tx.index[mask_b & morning_mask & (tx["coffee"] == 0)]
    flips = rng.random(len(idx_to_flip)) < switch_prob
    tx.loc[idx_to_flip[flips], "coffee"] = 1

    # 2) Добавляем доп. визиты
    tx_extra = []
    tx_by_user = {cid: df for cid, df in tx.groupby("customer_id")}
    total_added = 0
    for cid in b_ids:
        base = tx_by_user.get(cid, pd.DataFrame(columns=tx.columns))
        stats = _user_baseline_stats(base)
        baseline_visits = len(base) if len(base) > 0 else 4
        add_n = rng.binomial(baseline_visits, np.clip(uplift_v, 0.0, 1.0))
        if add_n <= 0:
            continue
        new_dt = _sample_dt_like(tx, add_n)
        for i in range(add_n):
            dt = new_dt.iloc[i]
            # Для купона стараемся назначить утром => если выпало не утро, сместим
            hour = dt.hour
            if not (6 <= hour < 11):
                dt = dt.normalize() + pd.to_timedelta(np.random.randint(6, 11), unit="h") + pd.to_timedelta(
                    np.random.randint(0, 59), unit="m"
                )

            amt = stats["avg_amount"] * (1.0 + rng.normal(0.0, 0.05))
            amt *= (1.0 + uplift_amount)
            fuel = max(5.0, stats["avg_fuel"] * (1.0 + rng.normal(0.0, 0.05)))
            # Утренний кофе вероятен:
            coffee_p = np.clip(stats["coffee_rate"] + uplift_coffee, 0.0, 1.0)
            c = int(rng.random() < coffee_p)
            w = int(rng.random() < stats["carwash_rate"])
            tx_extra.append(
                [
                    cid,
                    persona_map.get(cid, base["persona"].iloc[0] if not base.empty else "Unknown"),
                    dt,
                    dt.date().isoformat(),
                    dt.strftime("%H:%M:%S"),
                    round(max(200.0, amt), 2),
                    round(fuel, 1),
                    c,
                    w,
                ]
            )
            total_added += 1

    if tx_extra:
        add_df = pd.DataFrame(
            tx_extra,
            columns=["customer_id", "persona", "datetime", "date", "time", "amount", "fuel_liters", "coffee", "carwash"],
        )
        tx_after = pd.concat([tx, add_df], ignore_index=True)
    else:
        tx_after = tx

    meta = {"added_visits": int(total_added), "coffee_flipped": int(flips.sum() if len(idx_to_flip) else 0)}
    return tx_after.sort_values(["datetime", "customer_id"]).reset_index(drop=True), meta

def apply_campaign(
    transactions: pd.DataFrame,
    customers: pd.DataFrame,
    campaign_name: str,
    cfg: Optional[dict] = None,
    segment_col: str = "persona",     # или "assigned_persona" после маппинга
    ratio: float = 0.5,
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    """
    Применяет кампанию к целевому сегменту и возвращает:
      - tx_after: модифицированный датафрейм транзакций
      - cohort_ab: DataFrame[customer_id, group] по таргету (A/B)
      - meta: словарь с тех. статистикой (сколько добавили визитов и т.д.)
    """
    if cfg is None:
        cfg = load_config()

    camp = cfg["campaigns"].get(campaign_name)
    if camp is None:
        raise ValueError(f"Не найдена кампания '{campaign_name}' в конфиге.")

    targets = list(camp.get("target_personas", []))
    cohort_ab = split_cohort(customers, target_personas=targets, segment_col=segment_col, ratio=ratio, seed=seed)

    if campaign_name == "fuel_discount":
        tx_after, meta = _apply_fuel_discount(transactions, customers, cohort_ab, camp, seed=seed)
    elif campaign_name == "coffee_coupon":
        tx_after, meta = _apply_coffee_coupon(transactions, customers, cohort_ab, camp, seed=seed)
    else:
        raise NotImplementedError(f"Кампания '{campaign_name}' не реализована.")

    return tx_after, cohort_ab, {"campaign": campaign_name, **meta}


if __name__ == "__main__":
    cfg = load_config()
    tx_path = Path("data/transactions.csv")
    cust_path = Path("data/customers.csv")

    if not (tx_path.exists() and cust_path.exists()):
        print("⚠️  Нужны data/transactions.csv и data/customers.csv — сначала сгенерируйте данные.")
        raise SystemExit(1)

    tx = pd.read_csv(tx_path, parse_dates=["datetime"])
    customers = pd.read_csv(cust_path)

    # Пример: применим скидку на топливо к таргету
    tx_after, cohort, meta = apply_campaign(tx, customers, "fuel_discount", cfg=cfg, segment_col="persona", ratio=0.5, seed=42)
    out_path = Path("data/transactions_after.csv")
    tx_after.to_csv(out_path, index=False)

    cohort.to_csv("data/cohort_ab.csv", index=False)
    print(f"✅ Кампания: {meta['campaign']}. Добавлено визитов: {meta.get('added_visits', 0)}.")
