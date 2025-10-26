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
    cached_features,
    cached_mapping,
    df_to_csv_bytes,
    TRANSACTIONS_CSV,
    FEATURES_CSV,
    MAPPING_CSV,
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


st.set_page_config(page_title="Маппинг персон", layout="wide")

st.title("Rule-based маппинг пользователей к портретам")
st.markdown(
    """
Тут считаются агрегаты поведения по транзакциям и **присваивает каждому клиенту портрет** (Commuter / Thrifty / Weekend / Shopper)
на основе простых правил и мягкого фоллбэка к ближайшему прототипу персоны
"""
)
st.divider()

cfg = load_config()
ensure_dirs()

st.subheader("Источник транзакций")
src_choice = st.radio(
    "Выберите источник данных:",
    ["Загрузить transactions.csv", "Взять из папки /data/transactions.csv"],
    index=1,
    horizontal=True,
)

transactions: pd.DataFrame | None = None
if src_choice == "Загрузить transactions.csv":
    up = st.file_uploader("Загрузите файл transactions.csv", type=["csv"])
    if up is not None:
        transactions = pd.read_csv(up)
        st.success(
            f"Файл загружен: {up.name}  ·  строк: {len(transactions):,}".replace(",", " "))
else:
    if Path(TRANSACTIONS_CSV).exists():
        transactions = pd.read_csv(TRANSACTIONS_CSV)
        st.info(
            f"Используем файл: `{TRANSACTIONS_CSV}`  ·  строк: {len(transactions):,}".replace(",", " "))
    else:
        st.error(
            "Не найден data/transactions.csv. Сначала сгенерируйте данные на вкладке **Generate**.")

st.divider()

if transactions is not None:
    c1, c2 = st.columns(2)
    do_feats = c1.button("Посчитать признаки (features)")
    do_map = c2.button("Применить маппинг персон")

    features = None
    mapping = None

    if do_feats or do_map:
        with st.spinner("Считаем агрегаты поведения..."):
            features = cached_features(transactions)
        st.success(f"Признаки посчитаны ({len(features)} пользователей)")
        st.dataframe(features.head(20), use_container_width=True)

        # сохранить по желанию
        s1, s2 = st.columns(2)
        with s1:
            if st.button("Сохранить features.csv в /data", use_container_width=True):
                features.to_csv(FEATURES_CSV, index=False)
                st.toast(f"Сохранено: {FEATURES_CSV}")
        with s2:
            st.download_button(
                "Скачать features.csv",
                data=df_to_csv_bytes(features),
                file_name="features.csv",
                mime="text/csv",
                use_container_width=True,
            )

    if do_map:
        with st.spinner("Маппим пользователей к портретам (rule-based + soft fallback)..."):
            if features is None:
                features = cached_features(transactions)
            mapping = cached_mapping(features, cfg)

        st.subheader("Результат маппинга")
        st.dataframe(mapping.head(30), use_container_width=True)

        # сводка по сегментам
        st.markdown("**Сводка по присвоенным портретам**")
        seg = mapping["assigned_persona"].value_counts().rename_axis(
            "persona").reset_index(name="users")
        st.dataframe(seg, use_container_width=True)

        # сохранить / скачать
        s3, s4 = st.columns(2)
        with s3:
            if st.button("Сохранить mapping.csv в /data", use_container_width=True):
                mapping.to_csv(MAPPING_CSV, index=False)
                st.toast(f"Сохранено: {MAPPING_CSV}")
        with s4:
            st.download_button(
                "Скачать mapping.csv",
                data=df_to_csv_bytes(mapping),
                file_name="mapping.csv",
                mime="text/csv",
                use_container_width=True,
            )

else:
    st.info("Загрузите или выберите transactions.csv и нажмите кнопки расчёта выше")
