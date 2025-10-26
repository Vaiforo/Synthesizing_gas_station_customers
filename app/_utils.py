from __future__ import annotations
from src.metrics import compute_kpis, compare_groups
from src.campaigns import apply_campaign
from src.mapping_rules import map_users_rule
from src.features import build_user_features
from src.data_gen import generate_customers, generate_transactions
import yaml
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

try:
    import streamlit as st

    cache_data = st.cache_data
except Exception:
    def _identity(x=None, **kwargs):
        def inner(func):
            return func
        return inner
    cache_data = _identity


BASE_DIR = Path(".")
CONFIG_PATH = BASE_DIR / "config" / "personas.yaml"
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"

CUSTOMERS_CSV = DATA_DIR / "customers.csv"
TRANSACTIONS_CSV = DATA_DIR / "transactions.csv"
FEATURES_CSV = DATA_DIR / "features.csv"
MAPPING_CSV = DATA_DIR / "mapping.csv"
COHORT_CSV = DATA_DIR / "cohort_ab.csv"

TX_AFTER_CSV = DATA_DIR / "transactions_after.csv"
KPI_SUMMARY_CSV = REPORTS_DIR / "kpi_summary.csv"
CAMPAIGN_RESULTS_JSON = REPORTS_DIR / "campaign_results.json"


@cache_data(show_spinner=False)
def load_config(path: Path = CONFIG_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(cfg: Dict[str, Any], path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def obj_to_json_bytes(obj: Dict[str, Any]) -> bytes:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")


@cache_data(show_spinner=False)
def cached_generate(n_users: int, days: int, cfg: Dict[str, Any], seed: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame]:
    customers = generate_customers(n_customers=n_users, cfg=cfg, seed=seed)
    transactions = generate_transactions(
        customers, cfg=cfg, days=days, seed=seed)
    return customers, transactions


@cache_data(show_spinner=False)
def cached_features(transactions: pd.DataFrame) -> pd.DataFrame:
    return build_user_features(transactions)


@cache_data(show_spinner=False)
def cached_mapping(features: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
    return map_users_rule(features, cfg)


@cache_data(show_spinner=False)
def cached_apply_campaign(
    campaign_name: str,
    transactions: pd.DataFrame,
    customers_for_segment: pd.DataFrame,
    cfg: Dict[str, Any],
    segment_col: str = "persona",
    ratio: float = 0.5,
    seed: int = 42,
):
    return apply_campaign(
        transactions=transactions,
        customers=customers_for_segment,
        campaign_name=campaign_name,
        cfg=cfg,
        segment_col=segment_col,
        ratio=ratio,
        seed=seed,
    )


@cache_data(show_spinner=False)
def cached_kpis(transactions: pd.DataFrame, cohort: pd.DataFrame) -> pd.DataFrame:
    return compute_kpis(transactions, cohort)


@cache_data(show_spinner=False)
def cached_compare(kpi_df: pd.DataFrame) -> pd.DataFrame:
    return compare_groups(kpi_df)


def run_demo_pipeline(
    n_users: int = 3000,
    days: int = 90,
    campaign_name: Optional[str] = "fuel_discount",
    use_mapped_persona: bool = False,
    seed: int = 42,
) -> Dict[str, Any]:
    ensure_dirs()
    cfg = load_config()

    customers, transactions = cached_generate(n_users, days, cfg, seed=seed)
    features = cached_features(transactions)
    mapping = cached_mapping(features, cfg)

    if use_mapped_persona:
        customers_seg = customers.merge(mapping, on="customer_id", how="left")
        seg_col = "assigned_persona"
    else:
        customers_seg = customers.copy()
        seg_col = "persona"

    if campaign_name:
        tx_after, cohort_ab, meta = cached_apply_campaign(
            campaign_name=campaign_name,
            transactions=transactions,
            customers_for_segment=customers_seg[["customer_id", seg_col]].rename(columns={
                                                                                 seg_col: "persona"}),
            cfg=cfg,
            segment_col="persona",
            ratio=0.5,
            seed=seed,
        )
        kpi = cached_kpis(tx_after, cohort_ab)
        cmp = cached_compare(kpi)
    else:
        tx_after, cohort_ab, meta = transactions, pd.DataFrame(), {}
        kpi, cmp = pd.DataFrame(), pd.DataFrame()

    return {
        "config": cfg,
        "customers": customers,
        "transactions": transactions,
        "features": features,
        "mapping": mapping,
        "transactions_after": tx_after,
        "cohort": cohort_ab,
        "kpi": kpi,
        "compare": cmp,
        "meta": meta,
    }


def persist_artifacts(art: Dict[str, Any]) -> None:
    ensure_dirs()
    if isinstance(art.get("customers"), pd.DataFrame):
        art["customers"].to_csv(CUSTOMERS_CSV, index=False)
    if isinstance(art.get("transactions"), pd.DataFrame):
        art["transactions"].to_csv(TRANSACTIONS_CSV, index=False)
    if isinstance(art.get("features"), pd.DataFrame):
        art["features"].to_csv(FEATURES_CSV, index=False)
    if isinstance(art.get("mapping"), pd.DataFrame):
        art["mapping"].to_csv(MAPPING_CSV, index=False)
    if isinstance(art.get("cohort"), pd.DataFrame) and not art["cohort"].empty:
        art["cohort"].to_csv(COHORT_CSV, index=False)
    if isinstance(art.get("transactions_after"), pd.DataFrame) and not art["transactions_after"].empty:
        art["transactions_after"].to_csv(TX_AFTER_CSV, index=False)
    if isinstance(art.get("kpi"), pd.DataFrame) and not art["kpi"].empty:
        art["kpi"].to_csv(KPI_SUMMARY_CSV, index=False)


def make_downloads(art: Dict[str, Any]) -> Dict[str, bytes]:
    out: Dict[str, bytes] = {}
    for key in ["customers", "transactions", "features", "mapping", "cohort", "transactions_after", "kpi", "compare"]:
        val = art.get(key)
        if isinstance(val, pd.DataFrame) and not val.empty:
            out[f"{key}.csv"] = df_to_csv_bytes(val)
    if isinstance(art.get("meta"), dict) and art["meta"]:
        out["campaign_results.json"] = obj_to_json_bytes(art["meta"])
    return out
