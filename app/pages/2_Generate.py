import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))        # чтобы 'app' был виден как пакет
    sys.path.insert(0, str(ROOT / "src")) # чтобы 'src' тоже был импортируем

try:
    from app._utils import run_demo_pipeline, persist_artifacts, make_downloads  # и т.д.
except ModuleNotFoundError:
    from _utils import run_demo_pipeline, persist_artifacts, make_downloads


import streamlit as st
import pandas as pd

from app._utils import (
    load_config,
    ensure_dirs,
    cached_generate,
    df_to_csv_bytes,
    CUSTOMERS_CSV,
    TRANSACTIONS_CSV,
)

st.set_page_config(page_title="🧪 Генерация данных", page_icon="🧪", layout="wide")

st.title("🧪 Генерация синтетических клиентов и транзакций")
st.markdown(
    """
На этом шаге создаются:
- **customers.csv** — таблица клиентов с назначенными портретами;
- **transactions.csv** — история визитов за выбранный период.

Параметры генерации берутся из `config/personas.yaml`.
"""
)
st.divider()

# --- Параметры генерации ------------------------------------------------------------
cfg = load_config()
col1, col2, col3 = st.columns(3)
n_users = col1.number_input("Количество клиентов", min_value=100, max_value=100_000, value=3000, step=100)
days = col2.number_input("Период (дней)", min_value=30, max_value=365, value=90, step=10)
seed = col3.number_input("Seed (для воспроизводимости)", min_value=0, max_value=1_000_000, value=42, step=1)

# Покажем сводку по долям персон для понимания
with st.expander("👥 Доли портретов из конфигурации"):
    personas = cfg.get("personas", {})
    if personas:
        pr = pd.DataFrame(
            [{"persona": k, "share": v.get("share", None)} for k, v in personas.items()]
        ).assign(share=lambda d: d["share"] / d["share"].sum() if d["share"].notna().any() else d["share"])
        st.dataframe(pr, use_container_width=True)
    else:
        st.info("В конфиге пока нет секции personas.")

st.divider()

# --- Кнопка генерации ---------------------------------------------------------------
if st.button("🚀 Сгенерировать данные", use_container_width=True):
    with st.spinner("Генерируем synthetic customers & transactions..."):
        ensure_dirs()
        customers, transactions = cached_generate(int(n_users), int(days), cfg, seed=int(seed))

    st.success(f"✅ Готово! Клиенты: {len(customers):,} | Транзакций: {len(transactions):,}".replace(",", " "))
    st.caption(f"Файлы будут сохранены по запросу в: `{CUSTOMERS_CSV}` и `{TRANSACTIONS_CSV}`")

    st.subheader("🔎 Превью данных")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**customers (head)**")
        st.dataframe(customers.head(20), use_container_width=True)
    with c2:
        st.markdown("**transactions (head)**")
        st.dataframe(transactions.head(20), use_container_width=True)

    st.divider()

    # --- Download & Save ------------------------------------------------------------
    st.subheader("⬇️ Скачать / 💾 Сохранить")
    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button(
            "💾 Скачать customers.csv",
            data=df_to_csv_bytes(customers),
            file_name="customers.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with d2:
        st.download_button(
            "💾 Скачать transactions.csv",
            data=df_to_csv_bytes(transactions),
            file_name="transactions.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with d3:
        if st.button("📁 Сохранить в папку /data", use_container_width=True):
            customers.to_csv(CUSTOMERS_CSV, index=False)
            transactions.to_csv(TRANSACTIONS_CSV, index=False)
            st.success(f"Сохранено: {CUSTOMERS_CSV} и {TRANSACTIONS_CSV}")

else:
    st.info("Нажмите **Сгенерировать данные**, чтобы создать synthetic customers и transactions.")
