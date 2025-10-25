import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))        # чтобы 'app' был виден как пакет
    sys.path.insert(0, str(ROOT / "src")) # чтобы 'src' тоже был импортируем

try:
    from app._utils import run_demo_pipeline, persist_artifacts, make_downloads  # и т.д.
except ModuleNotFoundError:
    # на случай, если запускали из app/ и относительный импорт уместнее
    from _utils import run_demo_pipeline, persist_artifacts, make_downloads


import streamlit as st
from app._utils import (
    run_demo_pipeline,
    persist_artifacts,
    make_downloads,
    df_to_csv_bytes,
    obj_to_json_bytes,
)

st.set_page_config(
    page_title="Синтезация клиентов АЗС",
    page_icon="⛽",
    layout="wide",
)

# --- Заголовок и описание -----------------------------------------------------------
st.title("⛽ Синтезация клиентов АЗС для проверки гипотез")
st.markdown(
    """
Этот прототип демонстрирует, как можно **генерировать синтетических клиентов АЗС**, 
назначать им портреты и моделировать отклик на маркетинговые кампании (A/B-тесты) 
без использования реальных персональных данных.

**Что делает приложение:**
1. Создаёт синтетических клиентов по 4 портретам (Commuter, Thrifty, Weekend, Shopper);  
2. Генерирует их транзакции за период (60–90 дней);  
3. Считает агрегаты поведения и маппит к портретам;  
4. Применяет кампанию (`fuel_discount` или `coffee_coupon`) к выбранным сегментам;  
5. Показывает KPI «до/после» и позволяет скачать результаты.
"""
)

st.divider()

# --- Настройки демо -----------------------------------------------------------------
col1, col2, col3 = st.columns(3)
n_users = col1.number_input("Количество клиентов", min_value=100, max_value=10000, value=3000, step=100)
days = col2.number_input("Период генерации (дней)", min_value=30, max_value=180, value=90, step=10)
campaign_name = col3.selectbox("Кампания для симуляции", ["fuel_discount", "coffee_coupon", "без кампании"])

use_mapped = st.checkbox("Использовать маппинг персон (после анализа фичей)", value=False)

st.divider()

# --- Запуск пайплайна ---------------------------------------------------------------
if st.button("🚀 Запустить полную симуляцию", use_container_width=True):
    with st.spinner("Генерация данных и расчёт метрик..."):
        art = run_demo_pipeline(
            n_users=int(n_users),
            days=int(days),
            campaign_name=None if campaign_name == "без кампании" else campaign_name,
            use_mapped_persona=use_mapped,
        )
        persist_artifacts(art)

    st.success("✅ Симуляция завершена!")
    st.markdown(f"**Кампания:** `{art['meta'].get('campaign', 'нет')}`  |  "
                f"Добавлено визитов: {art['meta'].get('added_visits', 0)}")

    st.divider()

    # --- Отображение KPI ------------------------------------------------------------
    if not art["kpi"].empty:
        st.subheader("📊 KPI по группам A/B")
        st.dataframe(art["kpi"], use_container_width=True)

    if not art["compare"].empty:
        st.subheader("📈 Сравнение A vs B")
        st.dataframe(art["compare"], use_container_width=True)

    st.divider()

    # --- Скачивание результатов -----------------------------------------------------
    st.subheader("⬇️ Скачать результаты")
    downloads = make_downloads(art)
    cols = st.columns(4)
    for i, (fname, data) in enumerate(downloads.items()):
        with cols[i % 4]:
            st.download_button(
                label=f"💾 {fname}",
                data=data,
                file_name=fname,
                mime="text/csv" if fname.endswith(".csv") else "application/json",
            )

else:
    st.info("Нажмите **🚀 Запустить полную симуляцию**, чтобы сгенерировать и проанализировать данные.")
    st.caption("Вы можете перейти на вкладки 'Config', 'Generate', 'Mapping', 'Experiments' и 'Reports' для работы по шагам.")
