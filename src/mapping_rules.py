# src/mapping_rules.py
import pandas as pd
import numpy as np
import yaml
from pathlib import Path


def _safe(val, default=0.0):
    """Заменяем NaN/inf на безопасное значение."""
    if pd.isna(val) or val is None or val == np.inf or val == -np.inf:
        return default
    return float(val)

def _approx_per_month(visits_per_week: float) -> float:
    """Грубая конверсия частоты из конфигурации (визиты/неделю) в визиты/месяц."""
    return visits_per_week * 4.345  # средняя длина месяца в неделях

def load_config(path="config/personas.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _rule_assign(row: pd.Series) -> tuple[str, str]:
    """
    Жёсткие правила первого уровня.
    Возвращает (persona, rule_tag) или (None, None), если правила не сработали.
    """
    vpm   = _safe(row.get("visits_per_month"))
    avg_l = _safe(row.get("avg_fuel_liters"))
    c_att = _safe(row.get("coffee_attach_rate"))
    wend  = _safe(row.get("weekend_share"))
    morn  = row.get("morning_share")
    morn  = 0.0 if pd.isna(morn) else float(morn)

    # 1) Commuter: много визитов, утром
    if (vpm >= 15) and (morn >= 0.60):
        return "Commuter", "rule:commuter_strict"
    # допускаем отсутствие времени -> только по частоте
    if (vpm >= 18) and pd.isna(row.get("morning_share")):
        return "Commuter", "rule:commuter_freq_only"

    # 2) Thrifty: большой средний объём, низкий кофе, редкие визиты
    if (avg_l >= 40) and (c_att <= 0.10) and (vpm <= 6):
        return "Thrifty", "rule:thrifty"

    # 3) Weekend: высокая доля выходных, нечасто, объём средне/высокий
    if (wend >= 0.60) and (vpm <= 8) and (avg_l >= 30):
        return "Weekend", "rule:weekend"

    # 4) Shopper: высокий кофе, маленький объём, средняя частота
    if (c_att >= 0.40) and (avg_l <= 25) and (8 <= vpm <= 18):
        return "Shopper", "rule:shopper"

    return None, None

def _persona_prototype(cfg: dict, name: str) -> dict:
    """
    Формирует 'эталонный' вектор признаков персоны из YAML для мягкой классификации.
    """
    p = cfg["personas"][name]
    return {
        "visits_per_month": _approx_per_month(float(p["visits_per_week"])),
        "avg_fuel_liters":  float(p["fuel_liters_mean"]),
        "coffee_attach_rate": float(p["coffee_attach_rate"]),
        "weekend_share":    float(p["weekend_share"]),
        "morning_share":    float(p["morning_share"]),
    }

def _distance(row: pd.Series, proto: dict) -> float:
    """
    Взвешенная L2-дистанция между пользователем и прототипом персоны.
    Нормализации грубые, но стабильные для эвристики.
    """
    # норм-коэффициенты (масштабы признаков)
    scales = {
        "visits_per_month": 20.0,
        "avg_fuel_liters":  50.0,
        "coffee_attach_rate": 1.0,
        "weekend_share":    1.0,
        "morning_share":    1.0,
    }
    s = 0.0
    for k, scale in scales.items():
        rv = _safe(row.get(k), default=0.0)
        pv = float(proto.get(k, 0.0))
        # если у юзера нет 'morning_share' (NaN), не штрафуем по этому признаку
        if k == "morning_share" and pd.isna(row.get("morning_share")):
            continue
        s += ((rv - pv) / scale) ** 2
    return np.sqrt(s)

def _soft_assign(row: pd.Series, cfg: dict) -> tuple[str, str]:
    """
    Мягкое присвоение: выбираем ближайший 'прототип' персоны по расстоянию.
    """
    names = list(cfg["personas"].keys())
    protos = {n: _persona_prototype(cfg, n) for n in names}
    dists = {n: _distance(row, protos[n]) for n in names}
    best = min(dists, key=dists.get)
    return best, f"soft:{best}"

def map_users_rule(features: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    """
    Rule-based маппинг с мягким фоллбэком.
    На вход: features из src/features.py
    На выход: DataFrame с колонками:
      customer_id, assigned_persona, assign_rule
    """
    if cfg is None:
        cfg = load_config()

    out = []
    for _, row in features.iterrows():
        persona, tag = _rule_assign(row)
        if persona is None:
            persona, tag = _soft_assign(row, cfg)
        out.append((int(row["customer_id"]), persona, tag))

    mapped = pd.DataFrame(out, columns=["customer_id", "assigned_persona", "assign_rule"])
    return mapped


if __name__ == "__main__":
    feats_path = Path("data/features.csv")
    if not feats_path.exists():
        print("⚠️  Не найден data/features.csv — сначала посчитайте признаки (src/features.py).")
        raise SystemExit(1)

    cfg = load_config()
    feats = pd.read_csv(feats_path)
    mapped = map_users_rule(feats, cfg)
    out_path = Path("data/mapping.csv")
    mapped.to_csv(out_path, index=False)
    print(f"Сохранено: {out_path} ({len(mapped)} строк)")
