from app._utils import CONFIG_PATH, load_config, save_config
import yaml
import streamlit as st
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))        # чтобы 'app' был виден как пакет
    sys.path.insert(0, str(ROOT / "src"))  # чтобы 'src' тоже был импортируем

try:
    from app._utils import run_demo_pipeline, persist_artifacts, make_downloads
except ModuleNotFoundError:
    from _utils import run_demo_pipeline, persist_artifacts, make_downloads


st.set_page_config(page_title="⚙️ Конфигурация портретов",
                   page_icon="⚙️", layout="wide")

st.title("⚙️ Конфигурация портретов и кампаний")
st.markdown(
    """
Здесь вы можете просмотреть и при необходимости подредактировать параметры синтетических клиентов и кампаний.
Файл хранится по пути `config/personas.yaml`.  
После сохранения изменения автоматически вступают в силу при следующем запуске симуляции.
"""
)
st.divider()

try:
    cfg = load_config()
except FileNotFoundError:
    st.error("❌ Не найден config/personas.yaml. Сначала создайте файл конфигурации.")
    st.stop()

personas = cfg.get("personas", {})
campaigns = cfg.get("campaigns", {})

st.subheader("👥 Портреты клиентов")
st.caption("Основные параметры, влияющие на поведение и генерацию транзакций.")

cols = st.columns([1, 1, 1, 1])
for idx, (name, p) in enumerate(personas.items()):
    with cols[idx % 4]:
        with st.expander(f"🧩 {name}", expanded=(idx == 0)):
            st.text_area("Описание", value=p.get(
                "description", ""), key=f"{name}_desc")
            p["visits_per_week"] = st.number_input(
                "Визитов в неделю", min_value=0.1, max_value=14.0,
                value=float(p.get("visits_per_week", 3)), step=0.1, key=f"{name}_visits"
            )
            p["avg_check"] = st.number_input(
                "Средний чек (₽)", min_value=100.0, max_value=5000.0,
                value=float(p.get("avg_check", 1500)), step=50.0, key=f"{name}_check"
            )
            p["coffee_attach_rate"] = st.slider(
                "Attach-rate кофе", 0.0, 1.0, float(p.get("coffee_attach_rate", 0.5)), key=f"{name}_coffee"
            )
            p["carwash_attach_rate"] = st.slider(
                "Attach-rate мойки", 0.0, 1.0, float(p.get("carwash_attach_rate", 0.1)), key=f"{name}_carwash"
            )
            p["morning_share"] = st.slider(
                "Доля утренних визитов", 0.0, 1.0, float(p.get("morning_share", 0.3)), key=f"{name}_morning"
            )
            p["weekend_share"] = st.slider(
                "Доля визитов в выходные", 0.0, 1.0, float(p.get("weekend_share", 0.3)), key=f"{name}_weekend"
            )
            personas[name] = p

st.divider()

st.subheader("🎯 Кампании")
st.caption("Настройки uplift-эффектов для экспериментов.")

for idx, (name, c) in enumerate(campaigns.items()):
    with st.expander(f"📢 {name}", expanded=(idx == 0)):
        st.text_area("Описание", value=c.get(
            "description", ""), key=f"{name}_desc")
        st.write("**Целевые портреты:**",
                 ", ".join(c.get("target_personas", [])))
        c["uplift_visits_pct"] = st.slider(
            "Рост визитов (%)", 0.0, 1.0, float(c.get("uplift_visits_pct", 0.1)), 0.01, key=f"{name}_visits"
        )
        c["uplift_avg_check_pct"] = st.slider(
            "Рост среднего чека (%)", 0.0, 1.0, float(c.get("uplift_avg_check_pct", 0.05)), 0.01, key=f"{name}_check"
        )
        c["uplift_coffee_attach"] = st.slider(
            "Рост attach кофе (абс. п.п.)", 0.0, 1.0, float(c.get("uplift_coffee_attach", 0.1)), 0.01, key=f"{name}_coffee"
        )
        campaigns[name] = c

st.divider()

if st.button("💾 Сохранить изменения", use_container_width=True):
    cfg["personas"] = personas
    cfg["campaigns"] = campaigns
    save_config(cfg, CONFIG_PATH)
    st.success(f"✅ Конфигурация сохранена в {CONFIG_PATH}")
    st.toast("Изменения вступят в силу при следующей генерации данных.")
else:
    st.info("Измените параметры и нажмите **Сохранить изменения**, чтобы обновить конфигурацию.")
