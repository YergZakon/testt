"""
Бәйшешек — тест на знание казахского языка.
Источник: учебник «Бәйшешек», 5-сынып, 2-бөлім (темы 7-13).

Запуск:
    python3 -m streamlit run app.py
"""
import json
import random
import re
from pathlib import Path

import streamlit as st

# ---------------- Конфигурация ----------------
st.set_page_config(
    page_title="Бәйшешек — қазақ тілі тесті",
    page_icon="📚",
    layout="centered",
)

DATA_PATH = Path(__file__).parent / "data.json"
KAZ_KEYS = ["ә", "ө", "ұ", "ү", "ң", "қ", "ғ", "і", "һ"]

THEMES = [
    {"id": 7,  "name": "Денсаулық — зор байлық",        "ru": "Здоровье"},
    {"id": 8,  "name": "Менің тәуелсіз Қазақстаным",    "ru": "Казахстан"},
    {"id": 9,  "name": "Аспан әлемінің құпиясы",        "ru": "Космос"},
    {"id": 10, "name": "Компьютердің тілін табу",       "ru": "Компьютер"},
    {"id": 11, "name": "Қазақстандағы ұлттар достастығы", "ru": "Народы"},
    {"id": 12, "name": "Ұлы дала табиғаты",             "ru": "Природа"},
    {"id": 13, "name": "Ер есімі — ел есінде",          "ru": "Герои"},
]

TYPE_LABELS = {
    "word_kk_ru": "Сөз kk → ru",
    "word_ru_kk": "Сөз ru → kk",
    "phrase":     "Сөйлем (фразы)",
    "fill":       "Бос орынды толтыру",
}


# ---------------- Загрузка базы ----------------
@st.cache_data
def load_questions():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


QUESTIONS = load_questions()


# ---------------- Утилиты ----------------
def normalize(s: str) -> str:
    """Регистронезависимое сравнение, обрезка пробелов и пунктуации."""
    s = (s or "").strip().lower()
    s = s.replace("ё", "е")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[.!?,;:\"'«»()]", "", s)
    return s


def check_answer(user_input: str, expected) -> bool:
    norm = normalize(user_input)
    if not norm:
        return False
    if not isinstance(expected, list):
        expected = [expected]
    return any(normalize(e) == norm for e in expected)


def make_distractors(item, target_kind, n=3):
    """Берёт n случайных «неправильных» вариантов того же типа и темы.

    target_kind: 'ru' (нужен русский эквивалент) или 'kk' (казахский).
    """
    correct = item["ru"] if target_kind == "ru" else item["kk"]
    correct_norms = set(normalize(c) for c in (correct if isinstance(correct, list) else [correct]))

    candidates = []
    for q in QUESTIONS:
        if q is item:
            continue
        if q["type"] != item["type"]:
            continue
        if q["theme"] != item["theme"]:
            continue
        val = q.get(target_kind)
        if val is None:
            continue
        choice = val[0] if isinstance(val, list) else val
        if normalize(choice) in correct_norms:
            continue
        candidates.append(choice)

    # запасной план — расширяем поиск на другие темы того же типа
    if len(candidates) < n:
        for q in QUESTIONS:
            if q is item or q["type"] != item["type"]:
                continue
            val = q.get(target_kind)
            if val is None:
                continue
            choice = val[0] if isinstance(val, list) else val
            if normalize(choice) in correct_norms or choice in candidates:
                continue
            candidates.append(choice)
            if len(candidates) >= n * 4:
                break

    if not candidates:
        return []

    # убираем дубли с сохранением порядка
    seen, uniq = set(), []
    for c in candidates:
        key = normalize(c)
        if key not in seen:
            seen.add(key)
            uniq.append(c)

    random.shuffle(uniq)
    return uniq[:n]


def make_choice_question(item, direction):
    """word/phrase в режиме «варианты на выбор» (kk→ru или ru→kk)."""
    is_phrase = item["type"] == "phrase"
    if direction == "kk_ru":
        prompt = item["kk"]
        correct = item["ru"][0] if isinstance(item["ru"], list) else item["ru"]
        target_kind = "ru"
        direction_label = ("фраза kk → ru" if is_phrase else "kk → ru") + " · таңдау"
        hint = "выберите правильный перевод"
    else:
        prompt = item["ru"][0] if isinstance(item["ru"], list) else item["ru"]
        correct = item["kk"]
        target_kind = "kk"
        direction_label = ("фраза ru → kk" if is_phrase else "ru → kk") + " · таңдау"
        hint = "выберите правильный перевод"

    distractors = make_distractors(item, target_kind, n=3)
    if not distractors:
        # без отвлекающих — режим выбора не имеет смысла, скажет вызывающий
        return None

    options = [correct] + distractors
    random.shuffle(options)
    return {
        "mode": "options",
        "direction": direction_label,
        "prompt": prompt,
        "hint": hint,
        "expected": correct,
        "options": options,
        "show_kaz_keyboard": False,
        "theme": item["theme"],
    }


def build_question(item, allowed_types, answer_mode="type"):
    """Из элемента базы делает конкретный вопрос.

    answer_mode: 'type' — текстовый ввод; 'choice' — варианты; 'mixed' — случайно.
    """
    # Для word/phrase решаем — ввод или варианты
    use_choice_for_word_phrase = (
        answer_mode == "choice"
        or (answer_mode == "mixed" and random.random() < 0.5)
    )

    if item["type"] == "word":
        variants = []
        if "word_kk_ru" in allowed_types:
            variants.append("kk_ru")
        if "word_ru_kk" in allowed_types:
            variants.append("ru_kk")
        if not variants:
            return None
        direction = random.choice(variants)

        if use_choice_for_word_phrase:
            q = make_choice_question(item, direction)
            if q:
                return q
            # если не получилось набрать distractors — fallback к вводу

        if direction == "kk_ru":
            return {
                "mode": "text",
                "direction": "kk → ru",
                "prompt": item["kk"],
                "hint": "переведите на русский",
                "expected": item["ru"],
                "show_kaz_keyboard": False,
                "theme": item["theme"],
            }
        ru_prompt = item["ru"][0] if isinstance(item["ru"], list) else item["ru"]
        return {
            "mode": "text",
            "direction": "ru → kk",
            "prompt": ru_prompt,
            "hint": "переведите на казахский",
            "expected": item["kk"],
            "show_kaz_keyboard": True,
            "theme": item["theme"],
        }

    if item["type"] == "phrase":
        if "phrase" not in allowed_types:
            return None
        direction = item.get("dir") or random.choice(["kk_ru", "ru_kk"])

        if use_choice_for_word_phrase:
            q = make_choice_question(item, direction)
            if q:
                return q

        if direction == "kk_ru":
            return {
                "mode": "text",
                "direction": "фраза kk → ru",
                "prompt": item["kk"],
                "hint": "переведите фразу на русский",
                "expected": item["ru"],
                "show_kaz_keyboard": False,
                "theme": item["theme"],
            }
        ru_prompt = item["ru"][0] if isinstance(item["ru"], list) else item["ru"]
        return {
            "mode": "text",
            "direction": "фраза ru → kk",
            "prompt": ru_prompt,
            "hint": "переведите фразу на казахский",
            "expected": item["kk"],
            "show_kaz_keyboard": True,
            "theme": item["theme"],
        }

    if item["type"] == "fill":
        if "fill" not in allowed_types:
            return None
        options = list(item.get("options", []))
        random.shuffle(options)
        return {
            "mode": "options",
            "direction": "бос орын",
            "prompt": item["template"],
            "hint": item.get("hint", "выберите подходящее слово"),
            "expected": item["answer"],
            "options": options,
            "show_kaz_keyboard": False,
            "theme": item["theme"],
        }

    return None


# ---------------- Состояние ----------------
def init_state():
    defaults = {
        "screen": "start",            # start | quiz | result
        "queue": [],                  # список (item, allowed_types)
        "index": 0,
        "correct": 0,
        "errors_by_theme": {},        # для подсказок в конце
        "current_q": None,
        "user_answer": "",
        "feedback": None,             # None | True | False
        "selected_option": None,      # для fill — какую кнопку выбрал
        "answer_mode": "type",        # type | choice | mixed
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def start_quiz(theme_ids, types, count, answer_mode):
    pool = [q for q in QUESTIONS if q["theme"] in theme_ids]
    pool = [
        q for q in pool
        if (q["type"] == "word"   and ("word_kk_ru" in types or "word_ru_kk" in types))
        or (q["type"] == "phrase" and "phrase" in types)
        or (q["type"] == "fill"   and "fill"   in types)
    ]
    if not pool:
        st.warning("Таңдалған параметрлерге сәйкес сұрақтар жоқ / Нет вопросов под выбранные параметры")
        return
    random.shuffle(pool)
    if count != "all":
        pool = pool[: int(count)]
    st.session_state.answer_mode = answer_mode
    st.session_state.queue = [(item, set(types)) for item in pool]
    st.session_state.index = 0
    st.session_state.correct = 0
    st.session_state.errors_by_theme = {}
    st.session_state.current_q = build_question(pool[0], set(types), answer_mode)
    st.session_state.user_answer = ""
    st.session_state.feedback = None
    st.session_state.selected_option = None
    st.session_state.screen = "quiz"


def next_question():
    st.session_state.index += 1
    if st.session_state.index >= len(st.session_state.queue):
        st.session_state.screen = "result"
        return
    item, allowed = st.session_state.queue[st.session_state.index]
    st.session_state.current_q = build_question(item, allowed, st.session_state.answer_mode)
    st.session_state.user_answer = ""
    st.session_state.feedback = None
    st.session_state.selected_option = None


def submit_text_answer():
    q = st.session_state.current_q
    correct = check_answer(st.session_state.user_answer, q["expected"])
    st.session_state.feedback = correct
    if correct:
        st.session_state.correct += 1
    else:
        t = q["theme"]
        st.session_state.errors_by_theme[t] = st.session_state.errors_by_theme.get(t, 0) + 1


def submit_option(option: str):
    q = st.session_state.current_q
    correct = check_answer(option, q["expected"])
    st.session_state.feedback = correct
    st.session_state.selected_option = option
    if correct:
        st.session_state.correct += 1
    else:
        t = q["theme"]
        st.session_state.errors_by_theme[t] = st.session_state.errors_by_theme.get(t, 0) + 1


def back_to_start():
    st.session_state.screen = "start"
    st.session_state.queue = []
    st.session_state.index = 0
    st.session_state.correct = 0
    st.session_state.errors_by_theme = {}
    st.session_state.current_q = None


# ---------------- Виртуальная клавиатура ----------------
def virtual_kaz_keyboard():
    """Кнопки вставляют казахские символы в text_input (через session_state)."""
    st.caption("Қазақ әріптерін енгізу үшін батырмаларды басыңыз:")
    cols = st.columns(len(KAZ_KEYS) + 2)
    for i, k in enumerate(KAZ_KEYS):
        if cols[i].button(k, key=f"vk_{k}", use_container_width=True):
            st.session_state.user_answer = (st.session_state.get("user_answer") or "") + k
            st.rerun()
    if cols[-2].button("␣", key="vk_space", help="пробел", use_container_width=True):
        st.session_state.user_answer = (st.session_state.get("user_answer") or "") + " "
        st.rerun()
    if cols[-1].button("⌫", key="vk_back", help="удалить последний символ", use_container_width=True):
        st.session_state.user_answer = (st.session_state.get("user_answer") or "")[:-1]
        st.rerun()


# ---------------- Экраны ----------------
def screen_start():
    st.title("📚 Бәйшешек — қазақ тілі тесті")
    st.caption("5-сынып, 2-бөлім · тест на знание слов и выражений (темы 7-13)")

    counts = {"word": 0, "phrase": 0, "fill": 0}
    for q in QUESTIONS:
        counts[q["type"]] = counts.get(q["type"], 0) + 1
    st.info(
        f"**База:** {len(QUESTIONS)} единиц · "
        f"{counts['word']} слов · {counts['phrase']} фраз · "
        f"{counts['fill']} упражнений с пропусками"
    )

    st.subheader("Тақырыптар (темы)")
    all_themes = st.checkbox("Барлығы (все темы)", value=True, key="theme_all")
    selected_themes = []
    cols = st.columns(2)
    for i, t in enumerate(THEMES):
        col = cols[i % 2]
        checked = col.checkbox(
            f"{t['id']}. {t['name']} · _{t['ru']}_",
            value=all_themes,
            key=f"theme_{t['id']}",
        )
        if checked:
            selected_themes.append(t["id"])

    st.subheader("Тапсырма түрі (тип задания)")
    type_cols = st.columns(2)
    selected_types = []
    for i, (key, label) in enumerate(TYPE_LABELS.items()):
        col = type_cols[i % 2]
        if col.checkbox(label, value=True, key=f"type_{key}"):
            selected_types.append(key)

    st.subheader("Жауап беру тәсілі (режим ответа)")
    st.caption("Применяется к словам и фразам · упражнения с пропусками всегда показываются как варианты")
    answer_mode = st.radio(
        "Режим ответа",
        options=["type", "choice", "mixed"],
        format_func=lambda x: {
            "type":   "✍️ Жазу (ввод текста)",
            "choice": "🔘 Таңдау (4 варианта)",
            "mixed":  "🔀 Аралас (ввод и варианты случайно)",
        }[x],
        horizontal=True,
        label_visibility="collapsed",
    )

    st.subheader("Сұрақтар саны")
    count = st.radio(
        "Количество вопросов",
        options=["10", "20", "40", "all"],
        format_func=lambda x: "Барлығы (все)" if x == "all" else x,
        horizontal=True,
        label_visibility="collapsed",
    )

    st.markdown("---")
    if st.button("🚀 Бастау · Начать", type="primary", use_container_width=True):
        if not selected_themes:
            st.error("Кем дегенде бір тақырыпты таңдаңыз / Выберите хотя бы одну тему")
        elif not selected_types:
            st.error("Кем дегенде бір тапсырма түрін таңдаңыз / Выберите хотя бы один тип задания")
        else:
            start_quiz(selected_themes, selected_types, count, answer_mode)
            st.rerun()


def screen_quiz():
    q = st.session_state.current_q
    total = len(st.session_state.queue)
    done = st.session_state.index

    # Шапка: счёт + прогресс
    head_cols = st.columns([2, 1])
    head_cols[0].progress((done) / total, text=f"Сұрақ {done + 1} / {total}")
    head_cols[1].metric("Дұрыс", f"{st.session_state.correct} / {done}")

    # Бейдж направления
    st.caption(f"🏷️ **{q['direction']}**")

    # Сам вопрос
    st.markdown(
        f"<div style='font-size: 28px; text-align: center; padding: 20px; "
        f"background: #f0f4f8; border-radius: 8px; margin: 16px 0;'>"
        f"{q['prompt']}</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"💡 _{q['hint']}_")

    # ----- Режим текстового ввода -----
    if q["mode"] == "text":
        feedback_disabled = st.session_state.feedback is not None
        st.text_input(
            "Жауабыңызды жазыңыз / Введите ответ",
            key="user_answer",
            disabled=feedback_disabled,
            label_visibility="collapsed",
            placeholder="Жауап...",
        )

        if q.get("show_kaz_keyboard") and not feedback_disabled:
            virtual_kaz_keyboard()

        # Кнопки действия
        if st.session_state.feedback is None:
            if st.button("✓ Тексеру · Проверить", type="primary", use_container_width=True):
                submit_text_answer()
                st.rerun()
        else:
            show_feedback()
            if st.button("→ Келесі · Следующий", type="primary", use_container_width=True):
                next_question()
                st.rerun()

    # ----- Режим выбора варианта (fill) -----
    else:
        feedback_disabled = st.session_state.feedback is not None
        for opt in q["options"]:
            is_correct = check_answer(opt, q["expected"])
            is_selected = opt == st.session_state.selected_option
            if feedback_disabled:
                # После выбора подсвечиваем правильный/неправильный
                if is_correct:
                    st.success(f"✓ {opt}")
                elif is_selected:
                    st.error(f"✗ {opt}")
                else:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{opt}", unsafe_allow_html=True)
            else:
                if st.button(opt, key=f"opt_{opt}", use_container_width=True):
                    submit_option(opt)
                    st.rerun()

        if feedback_disabled:
            show_feedback()
            if st.button("→ Келесі · Следующий", type="primary", use_container_width=True):
                next_question()
                st.rerun()

    # Кнопка выхода
    st.markdown("---")
    if st.button("Шығу · Завершить", use_container_width=False):
        st.session_state.screen = "result"
        st.rerun()


def show_feedback():
    q = st.session_state.current_q
    expected = q["expected"]
    if isinstance(expected, list):
        expected_str = " / ".join(expected)
    else:
        expected_str = expected
    if st.session_state.feedback:
        st.success(f"✓ **Дұрыс!** Жауап: **{expected_str}**")
    else:
        st.error(f"✗ **Қате.** Дұрыс жауап: **{expected_str}**")


def screen_result():
    st.title("🏁 Тест аяқталды!")
    total = len(st.session_state.queue)
    correct = st.session_state.correct
    pct = round(correct / total * 100) if total else 0

    cols = st.columns(3)
    cols[0].metric("Дұрыс / Барлығы", f"{correct} / {total}")
    cols[1].metric("Пайыз", f"{pct}%")

    if pct >= 90:
        verdict = "🌟 Тамаша! Сіз қазақ тілін өте жақсы білесіз."
    elif pct >= 70:
        verdict = "👍 Жақсы! Жалғастыра беріңіз."
    elif pct >= 50:
        verdict = "🙂 Орташа. Сөздерді қайталау керек."
    else:
        verdict = "📚 Көбірек дайындалу қажет. Бастан қайталаңыз."

    st.info(verdict)

    # Статистика по темам, где были ошибки
    if st.session_state.errors_by_theme:
        st.subheader("Қателер бойынша тақырыптар")
        st.caption("Темы, где были ошибки — стоит повторить:")
        for tid, n in sorted(st.session_state.errors_by_theme.items(), key=lambda x: -x[1]):
            theme = next((t for t in THEMES if t["id"] == tid), None)
            if theme:
                st.write(f"- **{theme['name']}** ({theme['ru']}): {n} қате")

    st.markdown("---")
    cols = st.columns(2)
    if cols[0].button("🔄 Қайтадан · Заново (те же вопросы)", type="primary", use_container_width=True):
        random.shuffle(st.session_state.queue)
        st.session_state.index = 0
        st.session_state.correct = 0
        st.session_state.errors_by_theme = {}
        item, allowed = st.session_state.queue[0]
        st.session_state.current_q = build_question(item, allowed, st.session_state.answer_mode)
        st.session_state.user_answer = ""
        st.session_state.feedback = None
        st.session_state.selected_option = None
        st.session_state.screen = "quiz"
        st.rerun()
    if cols[1].button("🏠 Басты бетке · К началу", use_container_width=True):
        back_to_start()
        st.rerun()


# ---------------- Запуск ----------------
init_state()

screen = st.session_state.screen
if screen == "start":
    screen_start()
elif screen == "quiz":
    screen_quiz()
elif screen == "result":
    screen_result()
