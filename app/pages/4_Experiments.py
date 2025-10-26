import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from app._utils import (
    load_config,
    ensure_dirs,
    cached_apply_campaign,
    cached_kpis,
    cached_compare,
    df_to_csv_bytes,
    TRANSACTIONS_CSV,
    CUSTOMERS_CSV,
    TX_AFTER_CSV,
    COHORT_CSV,
)
import pandas as pd
import streamlit as st
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))

try:
    # и т.д.
    from app._utils import run_demo_pipeline, persist_artifacts, make_downloads
except ModuleNotFoundError:
    from _utils import run_demo_pipeline, persist_artifacts, make_downloads


st.set_page_config(page_title="Эксперименты A/B", layout="wide")

st.title("Проведение экспериментов (A/B-тестов)")
st.markdown(
    """
На этой вкладке можно выбрать маркетинговую кампанию и запустить симуляцию её влияния 
на поведение клиентов в формате **A/B-теста**.  
Группа A — контроль, группа B — тест (с активной кампанией).
"""
)
st.divider()

cfg = load_config()
ensure_dirs()

if not (Path(TRANSACTIONS_CSV).exists() and Path(CUSTOMERS_CSV).exists()):
    st.error("Не найдены исходные файлы: `data/transactions.csv` и/или `data/customers.csv`. "
             "Сначала сгенерируйте данные на вкладке **2_Generate**.")
    st.stop()

st.subheader("Параметры эксперимента")
col1, col2, col3 = st.columns(3)
campaign_name = col1.selectbox(
    "Кампания", list(cfg.get("campaigns", {}).keys()))
ratio = col2.slider("Доля тестовой группы (B)", 0.1, 0.9, 0.5, 0.05)
seed = col3.number_input(
    "Seed", min_value=0, max_value=999999, value=42, step=1)

campaign_cfg = cfg["campaigns"][campaign_name]
targets = campaign_cfg.get("target_personas", [])

st.markdown(f"**Целевая аудитория:** {', '.join(targets)}")

st.divider()

if st.button("Запустить эксперимент", use_container_width=True):
    transactions = pd.read_csv(TRANSACTIONS_CSV, parse_dates=["datetime"])
    customers = pd.read_csv(CUSTOMERS_CSV)

    with st.spinner("Применяем кампанию и формируем группы A/B..."):
        tx_after, cohort, meta = cached_apply_campaign(
            campaign_name=campaign_name,
            transactions=transactions,
            customers_for_segment=customers,
            cfg=cfg,
            segment_col="persona",
            ratio=float(ratio),
            seed=int(seed),
        )

    st.success(f"Кампания '{campaign_name}' завершена. "
               f"Добавлено визитов: {meta.get('added_visits', 0)}")

    tx_after.to_csv(TX_AFTER_CSV, index=False)
    cohort.to_csv(COHORT_CSV, index=False)

    st.divider()
    st.subheader("KPI по группам A/B")

    kpi = cached_kpis(tx_after, cohort)
    cmp = cached_compare(kpi)

    st.dataframe(kpi, use_container_width=True)
    st.markdown("**Сравнение A vs B (дельты, %)**")
    st.dataframe(cmp, use_container_width=True)

    st.divider()
    st.subheader("Скачать результаты")
    cols = st.columns(3)
    with cols[0]:
        st.download_button(
            "transactions_after.csv",
            data=df_to_csv_bytes(tx_after),
            file_name="transactions_after.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with cols[1]:
        st.download_button(
            "cohort_ab.csv",
            data=df_to_csv_bytes(cohort),
            file_name="cohort_ab.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with cols[2]:
        st.download_button(
            "kpi_summary.csv",
            data=df_to_csv_bytes(kpi),
            file_name="kpi_summary.csv",
            mime="text/csv",
            use_container_width=True,
        )

else:
    st.info(
        "Выберите кампанию и нажмите **Запустить эксперимент**, чтобы увидеть эффект A/B.")
