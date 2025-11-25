import os
import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

import streamlit as st
from openai import OpenAI
import requests

# ---------- НАСТРОЙКИ ФАЙЛОВ ----------

CONTENT_FILE = "content.json"
DIARY_FILE = "diary.json"

# ---------- ЗАГРУЗКА PERSONA ----------

try:
    with open("persona.txt", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read().strip()
except Exception:
    SYSTEM_PROMPT = (
        "Ты личный ассистент Асели: продюсер контента, коуч по фокусу и мягкий стратег. "
        "Помогаешь ей вести блог, укреплять личный бренд, держать фокус, не ругаешь, а поддерживаешь."
    )


# ---------- БЕЗОПАСНОЕ ПОЛУЧЕНИЕ OPENAI-КЛИЕНТА ----------

def get_openai_client() -> Optional[OpenAI]:
    """
    Аккуратно получаем OpenAI-клиент:
    1) Пробуем st.secrets["OPENAI_API_KEY"]
    2) Если нет — пробуем переменную окружения OPENAI_API_KEY
    3) Если всё равно нет — возвращаем None (а не падаем)
    """
    api_key = None

    # 1. из secrets (Streamlit Cloud / локально через .streamlit/secrets.toml)
    try:
        api_key = st.secrets.get("OPENAI_API_KEY", None)
    except Exception:
        api_key = None

    # 2. если не нашли — пробуем env
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        return None

    return OpenAI(api_key=api_key)


# ---------- TELEGRAM ----------

# Твои значения, если хочешь использовать Телеграм
TELEGRAM_BOT_TOKEN = "8420911157:AAHwNS8HsG-_DgWKGg3KSeGkEB8fRVJnCTo"
TELEGRAM_CHAT_ID = 5049239963


def send_telegram_message(text: str) -> bool:
    """Отправка сообщения в Telegram. Возвращает True при успехе."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("ВСТАВЬ_"):
        return False
    if not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


# ---------- УТИЛИТЫ ДЛЯ КОНТЕНТА ----------

def load_content() -> List[Dict[str, Any]]:
    if not os.path.exists(CONTENT_FILE):
        return []
    try:
        with open(CONTENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_content(items: List[Dict[str, Any]]) -> None:
    with open(CONTENT_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def get_next_content_id(items: List[Dict[str, Any]]) -> int:
    if not items:
        return 1
    return max(int(i.get("id", 0)) for i in items) + 1


def get_content_by_id(items: List[Dict[str, Any]], item_id: int) -> Optional[Dict[str, Any]]:
    for it in items:
        if int(it.get("id", 0)) == int(item_id):
            return it
    return None


def parse_date_str(d: str) -> Optional[date]:
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except Exception:
        return None


# ---------- УТИЛИТЫ ДЛЯ ДНЕВНИКА ----------

def load_diary() -> List[Dict[str, Any]]:
    if not os.path.exists(DIARY_FILE):
        return []
    try:
        with open(DIARY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_diary(entries: List[Dict[str, Any]]) -> None:
    with open(DIARY_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


# ---------- ГЕНЕРАЦИЯ КОНТЕНТА ЧЕРЕЗ OPENAI ----------

def convert_post_to_formats(item: Dict[str, Any], tone: str) -> str:
    """
    Взять ОДИН текст и сделать:
    - Reels-сценарий
    - LinkedIn-пост
    - Instagram-карусель
    - структуру YouTube
    """
    client = get_openai_client()
    if client is None:
        return "⚠️ Не найден OPENAI_API_KEY. Добавь ключ в secrets или переменные окружения."

    body = (item.get("body") or "").strip()
    title = item.get("title") or ""
    topic = item.get("topic") or ""
    platform = item.get("platform") or ""
    base_info = f"Платформа: {platform}. Категория: {topic}. Заголовок: {title}."

    user_prompt = f"""Ты — продюсер контента Асели.

Вот исходный текст поста (на русском, можно немного редактировать, но сохраняй смысл и голос):

\"\"\"{body}\"\"\"


{base_info}

Нужно на основе этого текста создать четыре формата контента:
1) Reels-сценарий
2) LinkedIn-пост
3) Instagram-карусель
4) YouTube-структуру

Общая тональность: {tone}.

Правила:
- Пиши на русском.
- Сохраняй авторский голос: живой, честный, иногда дерзкий, без воды.
- Не придумывай новые факты, держись в логике исходного текста.

Структура ответа:

### 🎬 Reels-сценарий
- 1 строка хука
- 5–10 очень коротких реплик (1–2 секунды каждая), каждая с новой строки, без тире.
- Короткая подпись под Reels (1–2 предложения).

### 💼 LinkedIn-пост
- Хук (1–2 строки).
- 2–4 абзаца раскрытия мысли (по 2–4 строки каждый).
- Небольшой вывод.
- Мягкий призыв к диалогу (вопрос или приглашение поделиться опытом).

### 📊 Instagram-карусель
Сделай структуру по слайдам (Слайд 1, Слайд 2 и т.д.)
- Слайд 1: сильная фраза / хук.
- Слайды 2–4: раскрытие проблемы или истории.
- Слайды 5–6: инсайт, сдвиг взгляда, опора.
- Слайд 7: вывод или приглашение.

### ▶️ YouTube-структура
- Предложи название видео.
- 10–15 секундный хук (что сказать в начале).
- 3–5 блоков содержания с кратким описанием.
- Идея завершения и мягкий призыв (подписка, комментарии, следующий шаг).
"""

    try:
        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Ошибка при генерации форматов:\n\n`{e}`"


def generate_ideas_from_strategy(strategy_text: str, topics: List[str]) -> str:
    client = get_openai_client()
    if client is None:
        return "⚠️ Не найден OPENAI_API_KEY. Добавь ключ в secrets или переменные окружения."

    topics_str = ", ".join(topics)
    prompt = f"""Ты помогаешь Аселе как стратег и продюсер.

Вот её заметки по позиционированию и стратегии:

\"\"\"{strategy_text}\"\"\"


Основные темы бренда: {topics_str}.

Сгенерируй:
1) 10 идей постов для Instagram (короткие формулировки).
2) 5 идей постов для LinkedIn.
3) 3 идеи длинного YouTube-видео.

Пиши списками, на русском, в её живом, честном стиле, без пафоса.
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"⚠️ Ошибка при генерации идей:\n\n`{e}`"


def generate_trends(area: str) -> str:
    client = get_openai_client()
    if client is None:
        return "⚠️ Не найден OPENAI_API_KEY. Добавь ключ в secrets или переменные окружения."

    prompt = f"""Представь, что ты консультант по трендам для Асели.

Область: {area}.

Опиши:
- 5–7 актуальных трендов в этой области (как сдвиги в мышлении, подходах, практике).
- Для каждого тренда: почему он важен и как человек-эксперт может на этом выделиться в блоге.

Не придумывай новости, а опирайся на устойчивые сдвиги последних лет.
Пиши по-русски, без сухого официоза.
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"⚠️ Ошибка при генерации трендов:\n\n`{e}`"


def generate_post_from_scratch(
    platform: str,
    topic: str,
    goal: str,
    tone: str,
    extra_notes: str,
) -> str:
    """
    Генерация НОВОГО поста с нуля (для Instagram или LinkedIn).
    """
    client = get_openai_client()
    if client is None:
        return "⚠️ Не найден OPENAI_API_KEY. Добавь ключ в secrets или переменные окружения."

    prompt = f"""Ты — личный контент-продюсер Асели.

Нужно сгенерировать новый пост.

Платформа: {platform}
Тема / категория: {topic}
Цель поста: {goal}
Желаемая тональность: {tone}

Дополнительные заметки автора:
\"\"\"{extra_notes}\"\"\"


Правила:
- Пиши на русском.
- Сохраняй живой, честный, чуть дерзкий, но тёплый голос.
- Без инфоцыганщины, без воды, с опорой на личный опыт и наблюдения.
- Для Instagram / LinkedIn можно делать 3–6 абзацев по 2–4 строки.

Сделай:
- Сначала предложи короткий хук (1–2 строки).
- Потом основной текст поста.
- В конце 1 мягкий призыв: поделиться мыслью, опытом или сохраниться в закладки.
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"⚠️ Ошибка при генерации поста:\n\n`{e}`"


# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ НЕДЕЛИ ----------

def filter_items_by_week(items: List[Dict[str, Any]], week_start: date) -> List[Dict[str, Any]]:
    week_end = week_start + timedelta(days=6)
    result = []
    for it in items:
        d = parse_date_str(it.get("planned_date") or "")
        if d and week_start <= d <= week_end:
            result.append(it)
    return result


def compute_week_stats(items: List[Dict[str, Any]]) -> Dict[str, int]:
    stats = {"instagram": 0, "linkedin": 0, "youtube": 0}
    for it in items:
        plat = (it.get("platform") or "").lower()
        if "insta" in plat:
            stats["instagram"] += 1
        elif "link" in plat:
            stats["linkedin"] += 1
        elif "youtube" in plat or "yt" in plat:
            stats["youtube"] += 1
    return stats


# ---------- UI НАСТРОЙКА ----------

st.set_page_config(
    page_title="Аселя — личный ассистент бренда",
    page_icon="🧠",
    layout="wide",
)

st.sidebar.title("Аселя-бросила-хаос 🎯")
st.sidebar.markdown("Твоя система фокуса, контента и дневника в одном месте.")

# ---------- ЗАГРУЗКА ДАННЫХ ----------

content_items = load_content()
diary_entries = load_diary()
today = date.today()

# ---------- ТАБЫ ----------

(
    tab_plan,
    tab_instagram,
    tab_linkedin,
    tab_youtube,
    tab_diary,
    tab_factory,
    tab_trends,
    tab_all,
) = st.tabs(
    [
        "📅 План недели",
        "📸 Instagram",
        "💼 LinkedIn",
        "▶️ YouTube",
        "📖 Дневник",
        "🧬 Контент-фабрика",
        "🌍 Тренды",
        "📝 Весь контент + Telegram",
    ]
)

# ---------- ТАБ: ПЛАН НЕДЕЛИ ----------

with tab_plan:
    st.header("📅 План недели и счётчик контента")

    selected_week_monday = st.date_input("Неделя с (понедельник)", today)
    wd = selected_week_monday.weekday()
    if wd != 0:
        selected_week_monday = selected_week_monday - timedelta(days=wd)

    week_items = filter_items_by_week(content_items, selected_week_monday)
    stats = compute_week_stats(week_items)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Instagram за неделю", f"{stats['instagram']} / 25")
    with col2:
        st.metric("LinkedIn за неделю", f"{stats['linkedin']} / 3")
    with col3:
        st.metric("YouTube за неделю", f"{stats['youtube']} / 1")

    st.markdown("### Таблица контента на эту неделю")

    if week_items:
        rows = []
        for it in week_items:
            rows.append(
                {
                    "ID": it.get("id"),
                    "Дата": it.get("planned_date"),
                    "Платформа": it.get("platform"),
                    "Категория": it.get("topic"),
                    "Формат": it.get("format"),
                    "Заголовок": it.get("title"),
                    "Статус": it.get("status"),
                }
            )
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("На эту неделю пока нет контента. Это не осуждение, а приглашение наиграться идеями 🙂")

    st.markdown("---")
    st.subheader("👀 Посмотреть пост по ID + конвертация")

    if "plan_selected_id" not in st.session_state:
        st.session_state["plan_selected_id"] = None

    plan_view_id = st.number_input("ID поста", min_value=1, step=1, key="plan_view_id")
    if st.button("Показать", key="plan_view_btn"):
        st.session_state["plan_selected_id"] = int(plan_view_id)

    sel_id = st.session_state["plan_selected_id"]
    if sel_id is not None:
        item = get_content_by_id(content_items, sel_id)
        if not item:
            st.warning(f"Пост с ID {sel_id} не найден.")
        else:
            st.markdown(f"**Платформа:** {item.get('platform')}")
            st.markdown(f"**Дата:** {item.get('planned_date')}")
            st.markdown(f"**Категория:** {item.get('topic')}")
            st.markdown(f"**Формат:** {item.get('format')}")
            st.markdown(f"**Заголовок:** {item.get('title')}")
            st.markdown("**Текст:**")
            st.write(item.get("body") or "_(пусто)_")

            st.markdown("### 🔄 Конвертация в несколько форматов")

            tone = st.selectbox(
                "Тональность",
                [
                    "Честно и уязвимо",
                    "Глубоко и рефлексивно",
                    "Спокойно-экспертно",
                    "Дерзко и прямолинейно",
                    "С юмором",
                ],
                key="plan_tone",
            )

            if st.button("✨ Сгенерировать Reels, LinkedIn, карусель и YouTube", key="plan_conv_btn"):
                with st.spinner("Готовлю форматы…"):
                    res = convert_post_to_formats(item, tone)
                st.markdown("### ✨ Сгенерированные версии")
                st.markdown(res)

# ---------- ТАБ: INSTAGRAM ----------

with tab_instagram:
    st.header("📸 Instagram — база постов")

    # --- Блок: генерация НОВОГО поста через ИИ ---
    st.subheader("✨ Сгенерировать новый пост для Instagram")

    with st.form("ig_ai_generate_form"):
        ig_ai_topic = st.text_input("Тема / категория поста", key="ig_ai_topic")
        ig_ai_goal = st.text_input("Цель поста (что человек должен понять/почувствовать)", key="ig_ai_goal")
        ig_ai_tone = st.selectbox(
            "Желаемая тональность",
            [
                "Честно и уязвимо",
                "Глубоко и рефлексивно",
                "Спокойно-экспертно",
                "Дерзко и прямолинейно",
                "С юмором",
            ],
            key="ig_ai_tone",
        )
        ig_ai_notes = st.text_area(
            "Черновые мысли / опорные фразы (можно пару пунктов, можно пусто)",
            key="ig_ai_notes",
        )

        gen_ig_btn = st.form_submit_button("✨ Сгенерировать текст поста")
        if gen_ig_btn:
            if not ig_ai_topic.strip():
                st.warning("Добавь хотя бы тему поста — из пустоты сложно делать честный текст 🙂")
            else:
                with st.spinner("Готовлю текст поста…"):
                    res = generate_post_from_scratch(
                        platform="Instagram",
                        topic=ig_ai_topic,
                        goal=ig_ai_goal,
                        tone=ig_ai_tone,
                        extra_notes=ig_ai_notes,
                    )
                st.markdown("### 📝 Сгенерированный пост")
                st.session_state["ig_ai_generated_text"] = res
                st.markdown(res)

    if "ig_ai_generated_text" in st.session_state and st.session_state["ig_ai_generated_text"]:
        st.markdown("---")
        st.subheader("💾 Сохранить сгенерированный пост как запись в базе")

        with st.form("ig_ai_save_form"):
            ig_save_date = st.date_input("Дата", today, key="ig_ai_save_date")
            ig_save_category = st.text_input("Категория (для фильтрации)", value="Потенциалы", key="ig_ai_save_cat")
            ig_save_format = st.selectbox(
                "Формат",
                ["Reels", "Пост", "Карусель", "Stories"],
                key="ig_ai_save_format",
            )
            ig_save_status = st.selectbox(
                "Статус",
                ["Черновик", "Запланировано", "Опубликовано"],
                key="ig_ai_save_status",
            )
            ig_save_title = st.text_input("Заголовок / опорная фраза", key="ig_ai_save_title")
            ig_save_body = st.text_area(
                "Текст (можешь чуть подправить перед сохранением)",
                value=st.session_state["ig_ai_generated_text"],
                height=250,
                key="ig_ai_save_body",
            )

            save_ai_ig_btn = st.form_submit_button("💾 Сохранить как пост Instagram")
            if save_ai_ig_btn:
                new_item = {
                    "id": get_next_content_id(content_items),
                    "platform": "Instagram",
                    "planned_date": ig_save_date.isoformat(),
                    "topic": ig_save_category,
                    "format": ig_save_format,
                    "status": ig_save_status,
                    "title": ig_save_title,
                    "body": ig_save_body,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                }
                content_items.append(new_item)
                save_content(content_items)
                st.success(f"Сохранили сгенерированный пост Instagram с ID {new_item['id']}")

    st.markdown("---")
    st.subheader("✍️ Добавить пост вручную")

    with st.form("ig_form"):
        col1, col2 = st.columns(2)
        with col1:
            ig_date = st.date_input("Дата", today, key="ig_date")
            ig_category = st.selectbox(
                "Категория",
                ["Потенциалы", "Америка", "Искусственный интеллект", "Жизнь"],
                key="ig_cat",
            )
        with col2:
            ig_format = st.selectbox(
                "Формат",
                ["Reels", "Пост", "Карусель", "Stories"],
                key="ig_format",
            )
            ig_status = st.selectbox(
                "Статус",
                ["Черновик", "Запланировано", "Опубликовано"],
                key="ig_status",
            )

        ig_title = st.text_input("Заголовок / опорная фраза", key="ig_title")
        ig_body = st.text_area("Текст поста / сценарий", height=200, key="ig_body")

        submitted = st.form_submit_button("💾 Сохранить пост")
        if submitted:
            new_item = {
                "id": get_next_content_id(content_items),
                "platform": "Instagram",
                "planned_date": ig_date.isoformat(),
                "topic": ig_category,
                "format": ig_format,
                "status": ig_status,
                "title": ig_title,
                "body": ig_body,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            content_items.append(new_item)
            save_content(content_items)
            st.success(f"Сохранили пост Instagram с ID {new_item['id']}")

    st.markdown("### Посты Instagram")

    ig_items = [it for it in content_items if (it.get("platform") or "").lower().startswith("insta")]
    if ig_items:
        rows = []
        for it in ig_items:
            rows.append(
                {
                    "ID": it.get("id"),
                    "Дата": it.get("planned_date"),
                    "Категория": it.get("topic"),
                    "Формат": it.get("format"),
                    "Заголовок": it.get("title"),
                    "Статус": it.get("status"),
                }
            )
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("Пока нет постов Instagram.")

    st.markdown("---")
    st.markdown("### 👀 Посмотреть пост + конвертация")

    if "ig_selected_id" not in st.session_state:
        st.session_state["ig_selected_id"] = None

    ig_view_id = st.number_input("ID поста", min_value=1, step=1, key="ig_view_id")
    if st.button("Показать", key="ig_view_btn"):
        st.session_state["ig_selected_id"] = int(ig_view_id)

    ig_sel_id = st.session_state["ig_selected_id"]
    if ig_sel_id is not None:
        item = get_content_by_id(content_items, ig_sel_id)
        if not item or (item.get("platform") or "").lower().startswith("insta") is False:
            st.warning(f"Пост Instagram с ID {ig_sel_id} не найден.")
        else:
            st.markdown(f"**Дата:** {item.get('planned_date')}")
            st.markdown(f"**Категория:** {item.get('topic')}")
            st.markdown(f"**Формат:** {item.get('format')}")
            st.markdown(f"**Заголовок:** {item.get('title')}")
            st.markdown("**Текст:**")
            st.write(item.get("body") or "_(пусто)_")

            tone = st.selectbox(
                "Тональность",
                [
                    "Честно и уязвимо",
                    "Глубоко и рефлексивно",
                    "Спокойно-экспертно",
                    "Дерзко и прямолинейно",
                    "С юмором",
                ],
                key="ig_tone",
            )
            if st.button("✨ Сгенерировать все форматы", key="ig_conv_btn"):
                with st.spinner("Готовлю форматы…"):
                    res = convert_post_to_formats(item, tone)
                st.markdown("### ✨ Сгенерированные версии")
                st.markdown(res)

# ---------- ТАБ: LINKEDIN ----------

with tab_linkedin:
    st.header("💼 LinkedIn — база постов")

    # --- Блок: генерация НОВОГО поста через ИИ ---
    st.subheader("✨ Сгенерировать новый пост для LinkedIn")

    with st.form("li_ai_generate_form"):
        li_ai_topic = st.text_input("Тема / категория поста", key="li_ai_topic")
        li_ai_goal = st.text_input("Цель поста (что человек/HR/лидер должен понять/почувствовать)", key="li_ai_goal")
        li_ai_tone = st.selectbox(
            "Желаемая тональность",
            [
                "Спокойно-экспертно",
                "Глубоко и рефлексивно",
                "Честно и уязвимо",
                "Дерзко и прямолинейно",
            ],
            key="li_ai_tone",
        )
        li_ai_notes = st.text_area(
            "Черновые мысли / факты / кейсы (можно коротко)",
            key="li_ai_notes",
        )

        gen_li_btn = st.form_submit_button("✨ Сгенерировать LinkedIn-пост")
        if gen_li_btn:
            if not li_ai_topic.strip():
                st.warning("Добавь хотя бы тему поста.")
            else:
                with st.spinner("Готовлю LinkedIn-пост…"):
                    res = generate_post_from_scratch(
                        platform="LinkedIn",
                        topic=li_ai_topic,
                        goal=li_ai_goal,
                        tone=li_ai_tone,
                        extra_notes=li_ai_notes,
                    )
                st.markdown("### 📝 Сгенерированный LinkedIn-пост")
                st.session_state["li_ai_generated_text"] = res
                st.markdown(res)

    if "li_ai_generated_text" in st.session_state and st.session_state["li_ai_generated_text"]:
        st.markdown("---")
        st.subheader("💾 Сохранить сгенерированный LinkedIn-пост")

        with st.form("li_ai_save_form"):
            li_save_date = st.date_input("Дата", today, key="li_ai_save_date")
            li_save_category = st.text_input("Категория", value="L&D", key="li_ai_save_cat")
            li_save_status = st.selectbox(
                "Статус",
                ["Черновик", "Запланировано", "Опубликовано"],
                key="li_ai_save_status",
            )
            li_save_tone = st.selectbox(
                "Тональность поста (для внутренней пометки)",
                ["Scholar/AI", "Insights", "Репост + комментарий"],
                key="li_ai_save_tone_sel",
            )

            li_save_title = st.text_input("Заголовок / хук", key="li_ai_save_title")
            li_save_body = st.text_area(
                "Текст поста (можно поправить перед сохранением)",
                value=st.session_state["li_ai_generated_text"],
                height=250,
                key="li_ai_save_body",
            )

            save_ai_li_btn = st.form_submit_button("💾 Сохранить как LinkedIn-пост")
            if save_ai_li_btn:
                new_item = {
                    "id": get_next_content_id(content_items),
                    "platform": "LinkedIn",
                    "planned_date": li_save_date.isoformat(),
                    "topic": li_save_category,
                    "format": "Пост",
                    "status": li_save_status,
                    "title": li_save_title,
                    "body": li_save_body,
                    "tone": li_save_tone,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                }
                content_items.append(new_item)
                save_content(content_items)
                st.success(f"Сохранили сгенерированный пост LinkedIn с ID {new_item['id']}")

    st.markdown("---")
    st.subheader("✍️ Добавить пост вручную")

    with st.form("li_form"):
        col1, col2 = st.columns(2)
        with col1:
            li_date = st.date_input("Дата", today, key="li_date")
            li_category = st.selectbox(
                "Категория",
                ["L&D", "Talent & Potential", "Business", "Жизнь"],
                key="li_cat",
            )
        with col2:
            li_status = st.selectbox(
                "Статус",
                ["Черновик", "Запланировано", "Опубликовано"],
                key="li_status",
            )
            li_tone = st.selectbox(
                "Тональность поста (для пометки)",
                ["Scholar/AI", "Insights", "Репост + комментарий"],
                key="li_tone_sel",
            )

        li_title = st.text_input("Заголовок / хук", key="li_title")
        li_body = st.text_area("Текст поста", height=250, key="li_body")

        submitted_li = st.form_submit_button("💾 Сохранить пост")
        if submitted_li:
            new_item = {
                "id": get_next_content_id(content_items),
                "platform": "LinkedIn",
                "planned_date": li_date.isoformat(),
                "topic": li_category,
                "format": "Пост",
                "status": li_status,
                "title": li_title,
                "body": li_body,
                "tone": li_tone,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            content_items.append(new_item)
            save_content(content_items)
            st.success(f"Сохранили пост LinkedIn с ID {new_item['id']}")

    st.markdown("### Посты LinkedIn")

    li_items = [it for it in content_items if (it.get("platform") or "").lower().startswith("link")]
    if li_items:
        rows = []
        for it in li_items:
            rows.append(
                {
                    "ID": it.get("id"),
                    "Дата": it.get("planned_date"),
                    "Категория": it.get("topic"),
                    "Заголовок": it.get("title"),
                    "Статус": it.get("status"),
                    "Тональность": it.get("tone"),
                }
            )
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("Пока нет постов LinkedIn.")

    st.markdown("---")
    st.markdown("### 👀 Посмотреть пост + конвертация")

    if "li_selected_id" not in st.session_state:
        st.session_state["li_selected_id"] = None

    li_view_id = st.number_input("ID поста", min_value=1, step=1, key="li_view_id")
    if st.button("Показать", key="li_view_btn"):
        st.session_state["li_selected_id"] = int(li_view_id)

    li_sel_id = st.session_state["li_selected_id"]
    if li_sel_id is not None:
        item = get_content_by_id(content_items, li_sel_id)
        if not item or (item.get("platform") or "").lower().startswith("link") is False:
            st.warning(f"Пост LinkedIn с ID {li_sel_id} не найден.")
        else:
            st.markdown(f"**Дата:** {item.get('planned_date')}")
            st.markdown(f"**Категория:** {item.get('topic')}")
            st.markdown(f"**Заголовок:** {item.get('title')}")
            st.markdown("**Текст:**")
            st.write(item.get("body") or "_(пусто)_")

            tone = st.selectbox(
                "Тональность конвертации",
                [
                    "Честно и уязвимо",
                    "Глубоко и рефлексивно",
                    "Спокойно-экспертно",
                    "Дерзко и прямолинейно",
                    "С юмором",
                ],
                key="li_tone",
            )
            if st.button("✨ Сгенерировать все форматы", key="li_conv_btn"):
                with st.spinner("Готовлю форматы…"):
                    res = convert_post_to_formats(item, tone)
                st.markdown("### ✨ Сгенерированные версии")
                st.markdown(res)

# ---------- ТАБ: YOUTUBE ----------

with tab_youtube:
    st.header("▶️ YouTube — идеи и структуры")

    st.markdown("### Быстрый скелет видео")

    with st.form("yt_form"):
        yt_title = st.text_input("Идея / тема видео", key="yt_title")
        yt_goal = st.text_input("Цель видео (что зритель должен понять/почувствовать)", key="yt_goal")
        yt_notes = st.text_area("Черновые мысли / тезисы", height=200, key="yt_notes")

        yt_btn = st.form_submit_button("✨ Сгенерировать структуру видео")
        if yt_btn:
            client = get_openai_client()
            if client is None:
                ans = "⚠️ Не найден OPENAI_API_KEY. Добавь ключ в secrets или переменные окружения."
            else:
                user_prompt = f"""Помоги Аселе набросать структуру YouTube-видео.

Тема: {yt_title}
Цель видео: {yt_goal}

Её черновые мысли:
\"\"\"{yt_notes}\"\"\"


Сделай:
- Предложение названия
- Хук на 10–15 секунд в её живом откровенном стиле
- 3–5 блоков содержания с кратким описанием
- Идею завершения и мягкий призыв к дальнейшему действию
"""
                try:
                    resp = client.chat.completions.create(
                        model="gpt-5.1",
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.7,
                    )
                    ans = resp.choices[0].message.content
                except Exception as e:
                    ans = f"⚠️ Ошибка при генерации структуры видео:\n\n`{e}`"

            st.markdown("### 🧩 Предложенная структура")
            st.markdown(ans)

# ---------- ТАБ: ДНЕВНИК ----------

with tab_diary:
    st.header("📖 Дневник Асели — материал для книги")

    st.markdown(
        "Это пространство, где ты фиксируешь свой путь: фокус дня, эмоции, выводы. "
        "Потом мы сможем собрать из этого книгу."
    )

    with st.form("diary_form"):
        d_date = st.date_input("Дата", today, key="diary_date")
        d_focus = st.text_input("Фокус дня (1–2 фразы)", key="diary_focus")
        d_state = st.text_area("Как я себя чувствую? Что происходит внутри?", height=120, key="diary_state")
        d_action = st.text_area("Что я сделала сегодня для своего пути / бренда / себя?", height=120, key="diary_action")
        d_insight = st.text_area("Инсайты, мысли, фразы, которые хочется сохранить", height=120, key="diary_insight")

        btn_diary = st.form_submit_button("💾 Сохранить запись")
        if btn_diary:
            new_entry = {
                "date": d_date.isoformat(),
                "focus": d_focus,
                "state": d_state,
                "action": d_action,
                "insight": d_insight,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            diary_entries.append(new_entry)
            save_diary(diary_entries)
            st.success("Запись в дневнике сохранена 💛")

    st.markdown("### Последние записи")

    if diary_entries:
        diary_sorted = sorted(diary_entries, key=lambda x: x.get("date", ""), reverse=True)
        show = diary_sorted[:10]
        rows = []
        for e in show:
            rows.append(
                {
                    "Дата": e.get("date"),
                    "Фокус": e.get("focus"),
                    "Действия": (e.get("action") or "")[:80] + "...",
                    "Инсайт": (e.get("insight") or "")[:80] + "...",
                }
            )
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("Пока нет записей. Это место ждёт твою честность и глубину.")

    st.markdown("---")
    if st.button("📤 Экспортировать весь дневник в текст"):
        parts = []
        for e in sorted(diary_entries, key=lambda x: x.get("date", "")):
            parts.append(
                f"## {e.get('date')}\n\n"
                f"**Фокус:** {e.get('focus')}\n\n"
                f"**Состояние:**\n{e.get('state')}\n\n"
                f"**Действия:**\n{e.get('action')}\n\n"
                f"**Инсайт:**\n{e.get('insight')}\n\n---\n"
            )
        full_text = "\n".join(parts) if parts else "_Пока нет записей_"
        st.markdown(full_text)

# ---------- ТАБ: КОНТЕНТ-ФАБРИКА ----------

with tab_factory:
    st.header("🧬 Контент-фабрика: стратегия и идеи")

    st.markdown("Здесь живут твои стратегия, позиционирование и генерация идей.")

    strategy_text = st.text_area(
        "Твои заметки по позиционированию, стратегии, кому и чем ты хочешь быть",
        height=200,
        key="strategy_text",
    )

    st.markdown("Отметь ключевые темы бренда, на которых хочешь держать фокус:")

    col_a, col_b, col_c, col_d = st.columns(4)
    topics = []
    with col_a:
        if st.checkbox("Потенциалы", value=True, key="topic_pot"):
            topics.append("Потенциалы")
    with col_b:
        if st.checkbox("Америка", value=True, key="topic_usa"):
            topics.append("Америка")
    with col_c:
        if st.checkbox("Искусственный интеллект", value=True, key="topic_ai"):
            topics.append("Искусственный интеллект")
    with col_d:
        if st.checkbox("Жизнь", value=True, key="topic_life"):
            topics.append("Жизнь")

    if st.button("✨ Сгенерировать идеи по стратегии"):
        if not strategy_text.strip():
            st.warning("Напиши хотя бы пару мыслей по стратегии — из пустоты даже ИИ не сделает честную магию 🙂")
        else:
            with st.spinner("Готовлю идеи..."):
                ideas = generate_ideas_from_strategy(strategy_text, topics)
            st.markdown("### 💡 Идеи для контента")
            st.markdown(ideas)

# ---------- ТАБ: ТРЕНДЫ ----------

with tab_trends:
    st.header("🌍 Тренды для блога и мышления")

    st.markdown("Выбери область, по которой хочешь подсветку трендов:")

    area = st.selectbox(
        "Область",
        [
            "AI и трансформация работы",
            "Learning & Development / корпоративное обучение",
            "Talent & Potential / раскрытие потенциала",
            "Эмиграция, жизнь в США, адаптация",
            "Creator economy / блогеры, создатели контента",
        ],
    )

    if st.button("🔥 Показать тренды и как их использовать в контенте"):
        with st.spinner("Думаю над трендами..."):
            txt = generate_trends(area)
        st.markdown("### 📌 Тренды и точки контента")
        st.markdown(txt)

# ---------- ТАБ: ВЕСЬ КОНТЕНТ + TELEGRAM ----------

with tab_all:
    st.header("📝 Весь контент + отправка в Telegram")

    if content_items:
        rows = []
        for it in sorted(content_items, key=lambda x: (x.get("planned_date") or "", x.get("id") or 0)):
            rows.append(
                {
                    "ID": it.get("id"),
                    "Дата": it.get("planned_date"),
                    "Платформа": it.get("platform"),
                    "Категория": it.get("topic"),
                    "Формат": it.get("format"),
                    "Заголовок": it.get("title"),
                    "Статус": it.get("status"),
                }
            )
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("Контента пока нет. Всё впереди.")

    st.markdown("---")
    st.subheader("📲 Отправить текст поста в Telegram")

    send_id = st.number_input("ID поста", min_value=1, step=1, key="send_id")
    if st.button("Отправить этот пост в Telegram"):
        item = get_content_by_id(content_items, int(send_id))
        if not item:
            st.warning(f"Пост с ID {int(send_id)} не найден.")
        else:
            text = f"{item.get('platform')} • {item.get('planned_date')} • {item.get('title')}\n\n{item.get('body')}"
            ok = send_telegram_message(text)
            if ok:
                st.success("Отправлено в Telegram ✅")
            else:
                st.error("Не удалось отправить. Проверь TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID в файле.")

