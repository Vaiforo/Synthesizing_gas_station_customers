from app._utils import default_persona, normalize_persona_shares, validate_persona
from app._utils import CONFIG_PATH, load_config, save_config
import streamlit as st


st.set_page_config(page_title="Конфигурация портретов", layout="wide")

st.title("Конфигурация портретов и кампаний")
st.markdown(
    """
Здесь можно просмотреть и при необходимости подредактировать параметры синтетических клиентов и кампаний.
Файл хранится по пути config/personas.yaml.  
После сохранения изменения автоматически вступают в силу при следующем запуске симуляции.
"""
)
st.divider()

try:
    cfg = load_config()
except FileNotFoundError:
    st.error("Не найден config/personas.yaml. Сначала создайте файл конфигурации.")
    st.stop()

personas = cfg.get("personas", {})
campaigns = cfg.get("campaigns", {})

st.subheader("Создать новую персону")
with st.form("create_persona_form", clear_on_submit=True):
    new_name = st.text_input(
        "Имя персоны (латиницей/слитно)", value="NewPersona")
    col_a, col_b = st.columns(2)
    with col_a:
        share = st.number_input(
            "Доля сегмента (0..1)", min_value=0.0, max_value=1.0, value=0.10, step=0.01)
        visits = st.number_input(
            "Визитов/нед", min_value=0.1, max_value=14.0, value=2.0, step=0.1)
        avg_check = st.number_input(
            "Средний чек (₽)", min_value=100.0, max_value=10000.0, value=1500.0, step=50.0)
        fuel_mean = st.number_input(
            "Средний объём топлива (л)", min_value=5.0, max_value=120.0, value=25.0, step=1.0)
        fuel_sd = st.number_input(
            "Ст.откл. объёма топлива", min_value=0.1, max_value=40.0, value=6.0, step=0.1)
    with col_b:
        coffee = st.slider("Attach-rate кофе", 0.0, 1.0, 0.3, 0.01)
        carwash = st.slider("Attach-rate мойки", 0.0, 1.0, 0.1, 0.01)
        morning = st.slider("Доля утренних визитов", 0.0, 1.0, 0.3, 0.01)
        weekend = st.slider("Доля визитов в выходные", 0.0, 1.0, 0.3, 0.01)
    desc = st.text_area("Описание", value="Новый портрет клиента")

    submitted = st.form_submit_button("Добавить персону")
    if submitted:
        if not new_name or new_name in personas:
            st.error("Имя пустое или такая персона уже существует.")
        else:
            p = {
                "description": desc,
                "share": share,
                "visits_per_week": visits,
                "avg_check": avg_check,
                "fuel_liters_mean": fuel_mean,
                "fuel_liters_sd": fuel_sd,
                "coffee_attach_rate": coffee,
                "carwash_attach_rate": carwash,
                "morning_share": morning,
                "weekend_share": weekend,
            }
            errs = validate_persona(p)
            if errs:
                st.error("Ошибки: " + "; ".join(errs))
            else:
                personas[new_name] = p
                cfg["personas"] = personas
                cfg = normalize_persona_shares(cfg)
                save_config(cfg, CONFIG_PATH)
                st.rerun()

st.subheader("Портреты клиентов")
st.caption("Основные параметры, влияющие на поведение и генерацию транзакций.")

cols = st.columns([1, 1, 1, 1])
for idx, (name, p) in enumerate(personas.items()):
    with cols[idx % 4]:
        with st.expander(f"{name}", expanded=(idx == 0)):
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

st.subheader("Удалить персону")
del_name = st.selectbox("Выберите персону для удаления",
                        list(personas.keys()) if personas else [])
if st.button("Удалить выбранную персону", disabled=not del_name):
    personas.pop(del_name, None)
    cfg["personas"] = personas
    cfg = normalize_persona_shares(cfg)
    save_config(cfg, CONFIG_PATH)
    st.rerun()

st.divider()

st.subheader("Кампании")
st.caption("Настройки uplift-эффектов для экспериментов.")

for idx, (name, c) in enumerate(campaigns.items()):
    with st.expander(f"{name}", expanded=(idx == 0)):
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

if st.button("Сохранить изменения", use_container_width=True):
    cfg["personas"] = personas
    cfg["campaigns"] = campaigns
    save_config(cfg, CONFIG_PATH)
    st.success(f"Конфигурация сохранена в {CONFIG_PATH}")
    st.toast("Изменения вступят в силу при следующей генерации данных.")
