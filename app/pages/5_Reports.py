import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from app._utils import (
    load_config,
    cached_kpis,
    cached_compare,
    df_to_csv_bytes,
    make_downloads,
    FEATURES_CSV,
    MAPPING_CSV,
    TRANSACTIONS_CSV,
    TX_AFTER_CSV,
    COHORT_CSV,
)
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))

try:
    from app._utils import run_demo_pipeline, persist_artifacts, make_downloads
except ModuleNotFoundError:
    from _utils import run_demo_pipeline, persist_artifacts, make_downloads


st.set_page_config(page_title="Отчёты и графики", layout="wide")

st.title("Отчёты: сегменты, визиты, KPI A/B")
st.caption("Здесь собраны основные визуализации и таблицы для питча: распределение сегментов, активность и результаты экспериментов")

st.divider()

st.subheader("Распределение присвоенных портретов (mapping)")
if Path(MAPPING_CSV).exists():
    mapping = pd.read_csv(MAPPING_CSV)
    seg_counts = mapping["assigned_persona"].value_counts(
    ).rename_axis("persona").reset_index(name="users")
    c1, c2 = st.columns([1.2, 1.8])
    with c1:
        st.dataframe(seg_counts, use_container_width=True)
    with c2:
        chart_df = seg_counts.set_index("persona")["users"]
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.bar(chart_df.index.astype(str), chart_df.values)
        ax.set_ylabel("users")
        ax.set_title("Assigned personas")
        st.pyplot(fig, clear_figure=True)
else:
    st.info("Не найден `data/mapping.csv`. Зайдите на вкладку **Mapping** и сохраните результат маппинга.")

st.divider()

st.subheader("Распределение количества визитов на клиента")
if Path(TRANSACTIONS_CSV).exists():
    tx = pd.read_csv(TRANSACTIONS_CSV)
    visits_per_user = tx.groupby("customer_id")["amount"].count()
    col1, col2 = st.columns([1.2, 1.8])
    with col1:
        st.metric("Клиентов в выборке",
                  f"{visits_per_user.shape[0]:,}".replace(",", " "))
        st.metric("Среднее визитов/клиента", f"{visits_per_user.mean():.2f}")
        st.metric("Медиана визитов/клиента", f"{visits_per_user.median():.0f}")
    with col2:
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.hist(visits_per_user.values, bins=30)
        ax.set_xlabel("Визитов за период")
        ax.set_ylabel("Число клиентов")
        ax.set_title("Гистограмма визитов на клиента")
        st.pyplot(fig, clear_figure=True)
else:
    st.info(
        "Не найден `data/transactions.csv`. Сгенерируйте данные на вкладке **Generate**.")

st.divider()

st.subheader("KPI A/B по кампании (последний запуск)")
if Path(TX_AFTER_CSV).exists() and Path(COHORT_CSV).exists():
    tx_after = pd.read_csv(TX_AFTER_CSV)
    cohort = pd.read_csv(COHORT_CSV)

    kpi = cached_kpis(tx_after, cohort)
    cmp = cached_compare(kpi)

    st.markdown("**KPI по группам**")
    st.dataframe(kpi, use_container_width=True)

    st.markdown("**Сравнение A vs B (дельты, %)**")
    st.dataframe(cmp, use_container_width=True)

    key_metrics = ["visits_per_user", "revenue_per_user"]
    cols = st.columns(len(key_metrics))
    kpi_idx = kpi.set_index("group")
    for i, m in enumerate(key_metrics):
        with cols[i]:
            fig, ax = plt.subplots(figsize=(4, 3))
            ax.bar(["A", "B"], [kpi_idx.loc["A", m], kpi_idx.loc["B", m]])
            ax.set_title(m.replace("_", " "))
            st.pyplot(fig, clear_figure=True)

    # Downloads
    st.markdown("### Скачать таблицы")
    dcols = st.columns(3)
    with dcols[0]:
        st.download_button("KPI (A/B)", data=df_to_csv_bytes(kpi),
                           file_name="kpi_summary.csv", mime="text/csv", use_container_width=True)
    with dcols[1]:
        st.download_button("Сравнение A vs B", data=df_to_csv_bytes(
            cmp), file_name="compare_ab.csv", mime="text/csv", use_container_width=True)
    with dcols[2]:
        st.download_button("Cohort A/B", data=df_to_csv_bytes(cohort),
                           file_name="cohort_ab.csv", mime="text/csv", use_container_width=True)

else:
    st.info("Не найдены `data/transactions_after.csv` и/или `data/cohort_ab.csv`. Запустите эксперимент на вкладке **Home** или **Experiments**.")

st.divider()

st.subheader("Сводка признаков (features) — опционально")
if Path(FEATURES_CSV).exists():
    feats = pd.read_csv(FEATURES_CSV)
    show_cols = [
        "customer_id",
        "visits_total",
        "visits_per_month",
        "avg_check",
        "avg_fuel_liters",
        "coffee_attach_rate",
        "carwash_attach_rate",
        "morning_share",
        "weekend_share",
    ]
    show_cols = [c for c in show_cols if c in feats.columns]
    st.dataframe(feats[show_cols].head(50), use_container_width=True)
else:
    st.caption("Сохраните features на вкладке **Mapping**, чтобы видеть превью.")
