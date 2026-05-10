"""Страница истории сессий."""
import json
from datetime import datetime
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Тарих · История сессий",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

HISTORY_PATH = Path(__file__).parent.parent / "history.json"

THEME_RU = {
    7:  "Здоровье",
    8:  "Казахстан",
    9:  "Космос",
    10: "Компьютер",
    11: "Народы",
    12: "Природа",
    13: "Герои",
}

ANSWER_MODE_LABEL = {
    "type":   "✍️ ввод",
    "choice": "🔘 варианты",
    "mixed":  "🔀 смешанный",
}

TYPE_SHORT = {
    "word_kk_ru": "kk→ru",
    "word_ru_kk": "ru→kk",
    "phrase":     "фразы",
    "fill":       "пропуски",
}


def load_history():
    if not HISTORY_PATH.exists():
        return []
    try:
        with open(HISTORY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(records):
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def fmt_ts(ts):
    try:
        return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts


# ---------------- UI ----------------
st.title("📊 Тарих · История сессий")
st.caption("Все завершённые тесты сохраняются автоматически в файл `history.json`.")

history = load_history()

if not history:
    st.info(
        "🪧 История пока пуста. Пройди хотя бы один тест — "
        "и его результаты появятся здесь."
    )
    st.page_link("app.py", label="← Перейти к тесту", icon="📚")
    st.stop()

# ---------------- Сводные метрики ----------------
total_sessions = len(history)
total_questions = sum(r["total"] for r in history)
total_correct = sum(r["correct"] for r in history)
avg_pct = round(total_correct / total_questions * 100) if total_questions else 0
best_pct = max(r["percent"] for r in history)

cols = st.columns(4)
cols[0].metric("Сессий", total_sessions)
cols[1].metric("Всего вопросов", total_questions)
cols[2].metric("Средний %", f"{avg_pct}%")
cols[3].metric("Лучший %", f"{best_pct}%")

st.markdown("---")

# ---------------- График по времени ----------------
if total_sessions >= 2:
    st.subheader("Динамика по времени")
    chart_data = {
        "ts": [fmt_ts(r["ts"]) for r in history],
        "Процент правильных": [r["percent"] for r in history],
    }
    try:
        import pandas as pd
        df = pd.DataFrame(chart_data).set_index("ts")
        st.line_chart(df, height=220)
    except Exception:
        # fallback без pandas (на всякий случай)
        st.line_chart({"%": [r["percent"] for r in history]}, height=220)

# ---------------- Слабые темы ----------------
st.subheader("Темы, где чаще всего ошибки")
theme_errors = {}
theme_total = {}
for r in history:
    for tid_str, n in r.get("errors_by_theme", {}).items():
        tid = int(tid_str)
        theme_errors[tid] = theme_errors.get(tid, 0) + n
    for tid in r.get("themes", []):
        theme_total[tid] = theme_total.get(tid, 0) + 1

if theme_errors:
    rows = []
    for tid, errors in sorted(theme_errors.items(), key=lambda x: -x[1]):
        rows.append({
            "Тема": f"{tid}. {THEME_RU.get(tid, '?')}",
            "Ошибок всего": errors,
            "Сессий с этой темой": theme_total.get(tid, 0),
        })
    st.table(rows)
else:
    st.success("Нет ошибок по темам — отлично!")

st.markdown("---")

# ---------------- Таблица всех сессий ----------------
st.subheader("Все сессии")

# Фильтры
filter_cols = st.columns([1, 1, 1, 1])
mode_filter = filter_cols[0].selectbox(
    "Режим ответа",
    options=["все", "type", "choice", "mixed"],
    format_func=lambda x: "все" if x == "все" else ANSWER_MODE_LABEL[x],
)
status_filter = filter_cols[1].selectbox(
    "Статус",
    options=["все", "completed", "aborted"],
    format_func=lambda x: {"все": "все", "completed": "✓ только пройденные", "aborted": "⊘ только прерванные"}[x],
)
min_pct = filter_cols[2].slider("Минимальный %", 0, 100, 0, step=10)
filter_cols[3].caption(" ")  # выравниваем

# Применяем фильтры
filtered = history
if mode_filter != "все":
    filtered = [r for r in filtered if r.get("answer_mode") == mode_filter]
if status_filter == "completed":
    filtered = [r for r in filtered if r.get("completed", True)]
elif status_filter == "aborted":
    filtered = [r for r in filtered if not r.get("completed", True)]
filtered = [r for r in filtered if r["percent"] >= min_pct]

# Показываем в обратном порядке — новые сверху
filtered = list(reversed(filtered))

if not filtered:
    st.info("Под фильтр ничего не попало.")
else:
    rows = []
    for r in filtered:
        types_short = ", ".join(TYPE_SHORT.get(t, t) for t in r.get("types", []))
        themes_short = ", ".join(str(t) for t in r.get("themes", []))
        completed = r.get("completed", True)
        answered = r.get("answered", r["total"])
        rows.append({
            "Когда": fmt_ts(r["ts"]),
            "✓": "✓" if completed else "⊘",
            "Темы": themes_short,
            "Типы": types_short,
            "Режим": ANSWER_MODE_LABEL.get(r.get("answer_mode", "type"), r.get("answer_mode", "?")),
            "Прошёл": f"{answered} / {r['total']}",
            "Дұрыс": r["correct"],
            "%": r["percent"],
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption("✓ — тест пройден до конца · ⊘ — прерван кнопкой «Шығу»")

st.markdown("---")

# ---------------- Управление ----------------
ctrl = st.columns(3)

# Скачать как JSON
ctrl[0].download_button(
    "⬇️ Скачать history.json",
    data=json.dumps(history, ensure_ascii=False, indent=2),
    file_name="history.json",
    mime="application/json",
    use_container_width=True,
)

# Удалить последнюю запись
if ctrl[1].button("🗑️ Удалить последнюю", use_container_width=True):
    history.pop()
    save_history(history)
    st.success("Последняя запись удалена.")
    st.rerun()

# Очистить всё (с подтверждением)
if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False

if not st.session_state.confirm_clear:
    if ctrl[2].button("🧹 Очистить всю историю", type="secondary", use_container_width=True):
        st.session_state.confirm_clear = True
        st.rerun()
else:
    ctrl[2].warning("Точно? Это нельзя отменить.")
    yn = st.columns(2)
    if yn[0].button("✓ Да, очистить", type="primary", use_container_width=True):
        save_history([])
        st.session_state.confirm_clear = False
        st.success("История очищена.")
        st.rerun()
    if yn[1].button("✗ Отмена", use_container_width=True):
        st.session_state.confirm_clear = False
        st.rerun()
