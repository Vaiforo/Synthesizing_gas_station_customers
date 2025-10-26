import pandas as pd
import numpy as np
import yaml
from datetime import datetime, timedelta, time
import random
from pathlib import Path


def load_config(path: str = "config/personas.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _rand_between(a: int, b: int) -> int:
    return random.randint(a, b)


def _biased_hour(persona: str, p: dict, is_weekend: bool) -> int:
    # Если данных недостаточно - берем данные с прортрета
    if persona.lower().startswith("commuter"):
        if random.random() < p.get("morning_share", 0.6):
            return _rand_between(6, 10)
        return _rand_between(17, 20)

    if persona.lower().startswith("weekend"):
        return _rand_between(10, 18)

    if persona.lower().startswith("shopper"):
        return _rand_between(12, 21)

    if persona.lower().startswith("thrifty"):
        return _rand_between(20, 23)

    return _rand_between(8, 20)


def _pick_datetime(start_date: datetime, days: int, persona: str, p: dict) -> datetime:
    d = start_date + timedelta(days=_rand_between(0, days - 1))
    is_weekend = d.weekday() >= 5
    hour = _biased_hour(persona, p, is_weekend)
    minute = _rand_between(0, 59)
    second = _rand_between(0, 59)
    return datetime(d.year, d.month, d.day, hour, minute, second)


def generate_customers(n_customers: int = 1000, cfg: dict | None = None, seed: int = 42) -> pd.DataFrame:
    if cfg is None:
        cfg = load_config()
    random.seed(seed)
    np.random.seed(seed)

    personas_cfg = cfg["personas"]
    personas = list(personas_cfg.keys())
    shares = np.array([personas_cfg[p]["share"]
                      for p in personas], dtype=float)
    shares = shares / shares.sum()

    assigned = np.random.choice(personas, size=n_customers, p=shares)
    df = pd.DataFrame(
        {
            "customer_id": np.arange(1, n_customers + 1, dtype=int),
            "persona": assigned,
        }
    )
    return df


def generate_transactions(
    customers: pd.DataFrame,
    cfg: dict | None = None,
    days: int = 90,
    end_date: datetime | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    if cfg is None:
        cfg = load_config()
    random.seed(seed)
    np.random.seed(seed)

    personas_cfg = cfg["personas"]
    if end_date is None:
        end_date = datetime.today()
    start_date = end_date - timedelta(days=days)

    rows = []
    for _, row in customers.iterrows():
        persona = str(row["persona"])
        p = personas_cfg[persona]
        exp_visits = float(p.get("visits_per_week", 1.0)) * (days / 7.0)
        n_visits = np.random.poisson(max(0.1, exp_visits))

        for _ in range(n_visits):
            dt = _pick_datetime(start_date, days, persona, p)
            fuel = max(5.0, np.random.normal(
                p["fuel_liters_mean"], p["fuel_liters_sd"]))
            coffee = int(random.random() < p["coffee_attach_rate"])
            carwash = int(random.random() < p["carwash_attach_rate"])
            amount = float(p["avg_check"]) * \
                (1.0 + np.random.normal(0.0, 0.10))
            amount = round(max(200.0, amount), 2)

            rows.append(
                [
                    int(row["customer_id"]),
                    persona,
                    dt,
                    dt.date().isoformat(),
                    dt.strftime("%H:%M:%S"),
                    amount,
                    round(fuel, 1),
                    coffee,
                    carwash,
                ]
            )

    tx = pd.DataFrame(
        rows,
        columns=[
            "customer_id",
            "persona",
            "datetime",
            "date",
            "time",
            "amount",
            "fuel_liters",
            "coffee",
            "carwash",
        ],
    )

    tx.sort_values(["datetime", "customer_id"],
                   inplace=True, ignore_index=True)
    return tx


if __name__ == "__main__":
    cfg = load_config()
    Path("data").mkdir(parents=True, exist_ok=True)

    customers = generate_customers(n_customers=5000, cfg=cfg, seed=42)
    tx = generate_transactions(customers, cfg=cfg, days=60, seed=42)

    customers.to_csv("data/customers.csv", index=False)
    tx.to_csv("data/transactions.csv", index=False)
    print(f"Синтезировано {len(customers)} клиентов и {len(tx)} транзакций")
