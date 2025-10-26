import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path


def compute_kpis(transactions: pd.DataFrame, cohort: pd.DataFrame) -> pd.DataFrame:
    tx = transactions.copy()
    df = tx.merge(cohort, on="customer_id", how="inner")
    if "group" not in df.columns:
        raise ValueError("cohort должен содержать колонку 'group' (A/B)")

    group_stats = []
    for g, sub in df.groupby("group"):
        users = sub["customer_id"].nunique()
        visits = len(sub)
        visits_per_user = visits / users if users else 0
        revenue_per_user = sub["amount"].sum() / users if users else 0
        coffee_attach = sub["coffee"].mean(
        ) if "coffee" in sub.columns else np.nan
        carwash_attach = sub["carwash"].mean(
        ) if "carwash" in sub.columns else np.nan
        group_stats.append(
            {
                "group": g,
                "users": users,
                "visits_per_user": visits_per_user,
                "revenue_per_user": revenue_per_user,
                "coffee_attach_rate": coffee_attach,
                "carwash_attach_rate": carwash_attach,
            }
        )
    return pd.DataFrame(group_stats)


def compare_groups(kpi_df: pd.DataFrame) -> pd.DataFrame:
    if set(kpi_df["group"]) != {"A", "B"}:
        raise ValueError("Ожидаются группы A и B в kpi_df.")

    kpi_df = kpi_df.set_index("group")
    metrics = [c for c in kpi_df.columns if c != "users"]
    res = []

    for m in metrics:
        a_val = kpi_df.loc["A", m]
        b_val = kpi_df.loc["B", m]
        delta = (b_val - a_val) / a_val * 100 if a_val else np.nan
        res.append({"metric": m, "A": a_val, "B": b_val,
                   "delta_%": delta, "p_value": np.nan})

    return pd.DataFrame(res)


if __name__ == "__main__":
    tx_path = Path("data/transactions_after.csv")
    cohort_path = Path("data/cohort_ab.csv")

    if not (tx_path.exists() and cohort_path.exists()):
        print("Не найдены входные файлы data/transactions_after.csv и data/cohort_ab.csv")
        raise SystemExit(1)

    tx = pd.read_csv(tx_path)
    cohort = pd.read_csv(cohort_path)

    kpi = compute_kpis(tx, cohort)
    print("KPI по группам")
    print(kpi)

    cmp = compare_groups(kpi)
    print("\nСравнение A vs B")
    print(cmp)
