#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from telethon import TelegramClient, events, functions, types
from telethon.errors import SessionPasswordNeededError
import asyncio
import time
import logging
import random
import json
import os
import re
import aiohttp
from urllib.parse import urlparse

# ========== Настройки логирования ==========
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

logging.getLogger("telethon").setLevel(logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.ERROR)

# ========== Логин (интерактивный, сохраняется в login.json) ==========
LOGIN_FILE = "login.json"

def load_login():
    if os.path.exists(LOGIN_FILE):
        try:
            with open(LOGIN_FILE, 'r') as f:
                data = json.load(f)
            if (data.get('api_id') and data.get('api_hash') and data.get('phone_number')
                    and data.get('owner_id') and data.get('session_name')):
                return data
        except Exception:
            pass
    return None

def save_login(data):
    try:
        with open(LOGIN_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"𖣂 ошибка сохранения логина: {e} 𖣂")

def ask_input(prompt):
    val = input(prompt).strip()
    return val

def interactive_login():
    print("𖣂 первый запуск — нужна авторизация 𖣂")
    while True:
        try:
            api_id = int(ask_input("api_id: "))
            break
        except ValueError:
            print("𖣂 api_id должен быть числом, попробуй снова 𖣂")
    api_hash = ask_input("api_hash: ")
    phone_number = ask_input("номер телефона (с +код страны): ")
    while True:
        try:
            owner_id = int(ask_input("твой telegram id (кого бот будет слушаться): "))
            break
        except ValueError:
            print("𖣂 id должен быть числом, попробуй снова 𖣂")
    session_name = ask_input("имя сессии (например lehatroll2): ").strip() or "session"
    data = {
        "api_id": api_id,
        "api_hash": api_hash,
        "phone_number": phone_number,
        "owner_id": owner_id,
        "session_name": session_name,
    }
    save_login(data)
    return data

_login = load_login() or interactive_login()
api_id = _login['api_id']
api_hash = _login['api_hash']
phone_number = _login['phone_number']
OWNER_ID = _login['owner_id']
SESSION_NAME = _login['session_name']

# ========== Глобальные переменные ==========
CONFIG_FILE = "config.json"
STATE_FILE = "state.json"       # <-- файл для сохранения active_attacks / fbl_targets
MENU_PHOTO_DEFAULT = "menu_photo.jpg"
MENU_MEDIA = "https://x0.at/dfQc.jpg"

IMAGES_DIR = "downloaded_images"
TEMPLATES_DIR = "templates"
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

photo_path = MENU_PHOTO_DEFAULT
start_time = time.time()
words_list = []
active_attacks = {}
fbl_targets = {}

# Кастомизация меню
MENU_ICON = "𖣂"
MENU_NAME = "omyter bot"
MENU_LANG = "en"  # "en" или "ru"

# Переводы описаний команд
MENU_TRANSLATIONS = {
    "en": {
        ".fk":      "int id_c media header temp",
        ".fklist":  "fk chat list",
        ".stop":    "chat_id",
        ".time":    "uptime bot / machine",
        ".ping":    "bot ping",
        ".id":      "chat id / user id",
        ".x0":      "media host",
        ".set":     "upload template",
        ".fbl":     "int us_id c_id media head temp",
        ".offfbl":  "user_id",
        ".fbllist": "autoreply list",
        ".tlist":   "template list",
        ".tag":     "reply int / c_id us_id int media header",
        ".tagoff":  "chat_id",
        ".lang":    "set language",
        ".forever": "chat_id — infinite typing",
        ".stfv":    "chat_id — stop typing",
    },
    "ru": {
        ".fk":      "интервал чат медиа шапка шаблон",
        ".fklist":  "список атак",
        ".stop":    "chat_id",
        ".time":    "аптайм бот / дедик",
        ".ping":    "пинг бота",
        ".id":      "id чата / юзера",
        ".x0":      "захостить медиа",
        ".set":     "загрузить шаблон",
        ".fbl":     "реплай / инт us_id c_id медиа шапка",
        ".offfbl":  "user_id",
        ".fbllist": "список автоответов",
        ".tlist":   "список шаблонов",
        ".tag":     "реплай инт / c_id us_id инт медиа",
        ".tagoff":  "chat_id",
        ".lang":    "смена языка",
        ".forever": "chat_id — бесконечный тайп",
        ".stfv":    "chat_id — стоп тайп",
    }
}


# ========== Утилиты: загрузка/сохранение конфига ==========
def load_config():
    global photo_path, words_list, MENU_MEDIA, MENU_ICON, MENU_NAME, MENU_LANG
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                photo_path = cfg.get("photo_path", MENU_PHOTO_DEFAULT)
                words_list = cfg.get("words", [])
                if cfg.get("menu_media"):  MENU_MEDIA = cfg["menu_media"]
                if cfg.get("menu_icon"):   MENU_ICON  = cfg["menu_icon"]
                if cfg.get("menu_name"):   MENU_NAME  = cfg["menu_name"]
                if cfg.get("menu_lang"):   MENU_LANG  = cfg["menu_lang"]
        except Exception as e:
            logger.warning(f"Не удалось загрузить config.json: {e}")
            photo_path = MENU_PHOTO_DEFAULT
            words_list = []
    else:
        photo_path = MENU_PHOTO_DEFAULT
        words_list = []

def save_config():
    try:
        cfg = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["photo_path"] = photo_path
        cfg["words"]      = words_list
        cfg["menu_icon"]  = MENU_ICON
        cfg["menu_name"]  = MENU_NAME
        cfg["menu_lang"]  = MENU_LANG
        if MENU_MEDIA:
            cfg["menu_media"] = MENU_MEDIA
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка при сохранении конфига: {e}")

# ========== Сохранение/восстановление состояния (attacks + fbl) ==========
def save_state():
    """Сохраняем active_attacks и fbl_targets в state.json (без template-списков — они в файлах)."""
    try:
        attacks_serial = {}
        for cid, cfg in active_attacks.items():
            attacks_serial[str(cid)] = {
                "interval": cfg.get("interval"),
                "header": cfg.get("header", ""),
                "image_url": cfg.get("image_url"),
                "local_image": cfg.get("local_image"),
                "template_name": cfg.get("template_name", ""),
            }
        fbl_serial = {}
        for uid, cfg in fbl_targets.items():
            fbl_serial[str(uid)] = {
                "interval": cfg.get("interval"),
                "chat_id": cfg.get("chat_id"),
                "header": cfg.get("header", ""),
                "image_url": cfg.get("image_url"),
                "local_image": cfg.get("local_image"),
                "template_name": cfg.get("template_name", ""),
            }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"attacks": attacks_serial, "fbl": fbl_serial}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения state.json: {e}")

def load_state():
    """Восстанавливаем active_attacks и fbl_targets из state.json при старте."""
    global active_attacks, fbl_targets
    if not os.path.exists(STATE_FILE):
        return
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        for cid_str, cfg in state.get("attacks", {}).items():
            cid = int(cid_str)
            tpl_name = cfg.get("template_name", "")
            tpl_lines = load_template(tpl_name) if tpl_name and tpl_name not in ("глобальный (.set)", "") else words_list
            active_attacks[cid] = {
                "interval": cfg.get("interval", 5),
                "header": cfg.get("header", ""),
                "image_url": cfg.get("image_url"),
                "local_image": cfg.get("local_image"),
                "template": tpl_lines,
                "template_name": tpl_name,
            }

        for uid_str, cfg in state.get("fbl", {}).items():
            uid = int(uid_str)
            tpl_name = cfg.get("template_name", "")
            tpl_lines = load_template(tpl_name) if tpl_name and tpl_name not in ("глобальный (.set)", "") else words_list
            fbl_targets[uid] = {
                "interval": cfg.get("interval", 5),
                "chat_id": cfg.get("chat_id"),
                "header": cfg.get("header", ""),
                "image_url": cfg.get("image_url"),
                "local_image": cfg.get("local_image"),
                "template": tpl_lines,
                "template_name": tpl_name,
                "last_time": 0.0,
            }
        logger.warning(f"Состояние восстановлено: {len(active_attacks)} атак, {len(fbl_targets)} fbl")
    except Exception as e:
        logger.error(f"Ошибка загрузки state.json: {e}")

# ========== Загрузка шаблона из папки templates/ ==========
def load_template(template_name: str):
    if not template_name.endswith(".txt"):
        template_name += ".txt"
    path = os.path.join(TEMPLATES_DIR, template_name)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        return lines if lines else None
    except Exception as e:
        logger.warning(f"Ошибка чтения шаблона {path}: {e}")
        return None

def list_templates():
    try:
        return [f for f in os.listdir(TEMPLATES_DIR) if f.endswith(".txt")]
    except:
        return []

# ===== Проверка владельца =====
def is_owner(sender_id):
    return sender_id == OWNER_ID

# ========== Клиент Telegram ==========
client = TelegramClient(SESSION_NAME, api_id, api_hash)

# ========== Вспомогательные функции ==========
async def delete_command(event):
    try:
        await event.delete()
    except:
        pass

async def send_to_saved(text, current_chat_id=None):
    """Отправляет уведомление в избранное ровно один раз,
    если команда уже выполняется в избранном — не дублирует."""
    try:
        me = await client.get_me()
        if current_chat_id == me.id:
            return  # уже там, дублировать не надо — event.respond сам ответит в этот же чат
        await client.send_message(me.id, text, parse_mode='html')
    except Exception as e:
        logger.error(f"ошибка отправки в избранное: {e}")

async def get_chat_name(chat_id):
    """Возвращает человекочитаемое название чата по id."""
    try:
        entity = await client.get_entity(chat_id)
        title = getattr(entity, 'title', None)
        if title:
            return title
        first = getattr(entity, 'first_name', None)
        last = getattr(entity, 'last_name', None)
        if first or last:
            return f"{first or ''} {last or ''}".strip()
        username = getattr(entity, 'username', None)
        if username:
            return f"@{username}"
        return str(chat_id)
    except Exception:
        return str(chat_id)

def is_direct_image_url(url: str):
    if not url:
        return False
    if 'x0.at' in url:
        return True
    return bool(re.search(r'\.(jpg|jpeg|png|gif|webp)(\?|$)', url, re.IGNORECASE))

async def download_image(url: str):
    if not url:
        return None
    parsed = urlparse(url)
    fname = os.path.basename(parsed.path) or "img"
    if not os.path.splitext(fname)[1]:
        fname += ".jpg"
    fname = f"{int(time.time() * 1000)}_{fname}"
    local_path = os.path.join(IMAGES_DIR, fname)
    try:
        async with aiohttp.ClientSession() as session:
            if is_direct_image_url(url):
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30), allow_redirects=True) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        ct = resp.headers.get("Content-Type", "")
                        ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}
                        for mime, ext in ext_map.items():
                            if mime in ct:
                                local_path = local_path.rsplit(".", 1)[0] + ext
                                break
                        with open(local_path, "wb") as f:
                            f.write(data)
                        return local_path
                    else:
                        return None
            else:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20), allow_redirects=True) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                        if m:
                            img_url = m.group(1)
                            if img_url:
                                async with session.get(img_url, timeout=aiohttp.ClientTimeout(total=20)) as resp2:
                                    if resp2.status == 200:
                                        data = await resp2.read()
                                        ext = os.path.splitext(urlparse(img_url).path)[1] or ".jpg"
                                        if not local_path.endswith(ext):
                                            local_path = local_path + ext
                                        with open(local_path, "wb") as f:
                                            f.write(data)
                                        return local_path
                        m2 = re.search(r'(https?://i\.imgur\.com/\S+\.(?:jpg|jpeg|png|gif|webp))', html, re.IGNORECASE)
                        if m2:
                            img_url = m2.group(1)
                            async with session.get(img_url, timeout=aiohttp.ClientTimeout(total=20)) as resp2:
                                if resp2.status == 200:
                                    data = await resp2.read()
                                    ext = os.path.splitext(urlparse(img_url).path)[1] or ".jpg"
                                    if not local_path.endswith(ext):
                                        local_path = local_path + ext
                                    with open(local_path, "wb") as f:
                                        f.write(data)
                                    return local_path
                        return None
                    else:
                        return None
    except Exception as e:
        logger.exception(f"Ошибка при скачивании изображения {url}: {e}")
        return None

# ========== Меню — динамический текст ==========
def build_menu_text(chat_id, user_id):
    i = MENU_ICON
    t = MENU_TRANSLATIONS.get(MENU_LANG, MENU_TRANSLATIONS["en"])
    return (
        f"<b>{i} {MENU_NAME} {i}</b>\n\n"
        f"{i} | <code>.fk</code> – {t['.fk']}\n"
        f"{i} | <code>.fklist</code> – {t['.fklist']}\n"
        f"{i} | <code>.stop</code> – {t['.stop']}\n"
        f"{i} | <code>.time</code> – {t['.time']}\n"
        f"{i} | <code>.ping</code> – {t['.ping']}\n"
        f"{i} | <code>.id</code> – {t['.id']}\n"
        f"{i} | <code>.x0</code> – {t['.x0']}\n"
        f"{i} | <code>.set</code> – {t['.set']}\n"
        f"{i} | <code>.fbl</code> – {t['.fbl']}\n"
        f"{i} | <code>.offfbl</code> – {t['.offfbl']}\n"
        f"{i} | <code>.fbllist</code> – {t['.fbllist']}\n"
        f"{i} | <code>.tlist</code> – {t['.tlist']}\n"
        f"{i} | <code>.tag</code> – {t['.tag']}\n"
        f"{i} | <code>.tagoff</code> – {t['.tagoff']}\n"
        f"{i} | <code>.forever</code> – {t['.forever']}\n"
        f"{i} | <code>.stfv</code> – {t['.stfv']}\n\n"
        f"this chat id: <code>{chat_id}</code>\n"
        f"your user id: <code>{user_id}</code>\n"
        f"bot owner — <a href='https://t.me/omyter'>@omyter</a>"
    )

def build_settings_text(chat_id, user_id):
    i = MENU_ICON
    t = MENU_TRANSLATIONS.get(MENU_LANG, MENU_TRANSLATIONS["en"])
    return (
        f"<b>{i} settings {i}</b>\n\n"
        f"{i} | <code>.name</code> – bot name\n"
        f"{i} | <code>.we</code> – menu icon\n"
        f"{i} | <code>.icon</code> – menu photo\n"
        f"{i} | <code>.lang</code> – {t['.lang']}\n\n"
        f"this chat id: <code>{chat_id}</code>\n"
        f"your user id: <code>{user_id}</code>"
    )

def get_system_uptime() -> str:
    try:
        import psutil
        total_seconds = int(time.time() - psutil.boot_time())
    except Exception:
        try:
            with open("/proc/uptime", "r") as f:
                total_seconds = int(float(f.read().split()[0]))
        except Exception:
            return "н/д"
    days    = total_seconds // 86400
    hours   = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    secs    = total_seconds % 60
    parts = []
    if days:    parts.append(f"{days}д")
    if hours:   parts.append(f"{hours}ч")
    parts.append(f"{minutes}м")
    parts.append(f"{secs}с")
    return " ".join(parts)

def format_bot_uptime() -> str:
    total_seconds = int(time.time() - start_time)
    days    = total_seconds // 86400
    hours   = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    secs    = total_seconds % 60
    parts = []
    if days:    parts.append(f"{days}д")
    if hours:   parts.append(f"{hours}ч")
    parts.append(f"{minutes}м")
    parts.append(f"{secs}с")
    return " ".join(parts)

@client.on(events.NewMessage(pattern=r'^\.\s*help$'))
async def menu_handler(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    chat_id = event.chat_id
    me = await client.get_me()
    caption = build_menu_text(chat_id, me.id)
    reply_to = event.reply_to_msg_id
    try:
        await client.send_file(chat_id, MENU_MEDIA, caption=caption, reply_to=reply_to, parse_mode='html')
    except Exception:
        try:
            await client.send_message(chat_id, caption, reply_to=reply_to, parse_mode='html')
        except:
            pass

# ========== .settings ==========
@client.on(events.NewMessage(pattern=r'^\.\s*settings$'))
async def settings_handler(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    chat_id = event.chat_id
    me = await client.get_me()
    caption = build_settings_text(chat_id, me.id)
    reply_to = event.reply_to_msg_id
    try:
        await client.send_file(chat_id, MENU_MEDIA, caption=caption, reply_to=reply_to, parse_mode='html')
    except Exception:
        try:
            await client.send_message(chat_id, caption, reply_to=reply_to, parse_mode='html')
        except:
            pass

# ========== .we — смена иконки меню ==========
@client.on(events.NewMessage(pattern=r'^\.\s*we\b'))
async def we_handler(event):
    if not is_owner(event.sender_id):
        return
    global MENU_ICON
    await delete_command(event)
    # Берём всё после ".we " — работает с обычными и premium эмодзи
    raw = event.message.text
    match = re.match(r'^\.\s*we\s+', raw)
    if not match or not raw[match.end():].strip():
        await event.respond("𖣂 использование: <code>.we ✟</code> или .we + любой эмодзи", parse_mode='html')
        return
    MENU_ICON = raw[match.end():].strip()
    save_config()
    await event.respond(f"иконка меню изменена на: {MENU_ICON}", parse_mode='html')

# ========== .name — смена названия бота в меню ==========
@client.on(events.NewMessage(pattern=r'^\.\s*name\b'))
async def name_handler(event):
    if not is_owner(event.sender_id):
        return
    global MENU_NAME
    await delete_command(event)
    parts = event.message.text.strip().split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await event.respond("𖣂 использование: <code>.name lucky</code>", parse_mode='html')
        return
    MENU_NAME = parts[1].strip()
    save_config()
    await event.respond(f"название бота изменено: <code>{MENU_NAME}</code>", parse_mode='html')

# ========== .lang — смена языка описаний команд ==========
@client.on(events.NewMessage(pattern=r'^\.\s*lang\b'))
async def lang_handler(event):
    if not is_owner(event.sender_id):
        return
    global MENU_LANG
    await delete_command(event)
    parts = event.message.text.strip().split()
    if len(parts) > 1 and parts[1].lower() in ("en", "ru"):
        MENU_LANG = parts[1].lower()
    else:
        MENU_LANG = "ru" if MENU_LANG == "en" else "en"
    save_config()
    await event.respond(f"{MENU_ICON} язык изменён", parse_mode='html')

# ========== .tlist ==========
@client.on(events.NewMessage(pattern=r'^\.\s*tlist$'))
async def tlist(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    tmpl_list = list_templates()
    if not tmpl_list:
        await event.reply("**Папка `templates/` пуста.** закинь туда `.txt` файлы.")
        return
    msg = "**Шаблоны в папке `templates/`:**\n"
    for t in tmpl_list:
        path = os.path.join(TEMPLATES_DIR, t)
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            msg += f"`{t}` — {len(lines)} строк\n"
        except:
            msg += f"`{t}`\n"
    await event.reply(msg)

# ========== .fk ==========
@client.on(events.NewMessage(pattern=r'^\.\s*fk\b'))
async def fk(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    text = event.message.text.strip()
    parts = text.split()

    if len(parts) < 3:
        await event.reply("𖣂 omyt ne smog izza interval i chat_id ne ukazany")
        return

    try:
        interval = int(parts[1])
        chat_id = int(parts[2])
    except ValueError:
        await event.reply("𖣂 omyt ne smog izza interval i chat_id dolzhny byt chislami")
        return

    rest = parts[3:]

    template_name = None
    template_lines = None
    if rest and rest[-1].endswith(".txt"):
        template_name = rest[-1]
        rest = rest[:-1]
        template_lines = load_template(template_name)
        if template_lines is None:
            await event.reply(f"𖣂 omyt ne smog izza shablon {template_name} ne najden")
            return

    image_url = None
    header = ""
    if rest and re.match(r'https?://', rest[0]):
        image_url = rest[0]
        header = " ".join(rest[1:])
    else:
        header = " ".join(rest)

    local_image = await download_image(image_url) if image_url else None
    effective_words = template_lines if template_lines is not None else words_list

    active_attacks[chat_id] = {
        "interval": interval,
        "header": header,
        "image_url": image_url,
        "local_image": local_image,
        "template": effective_words,
        "template_name": template_name or "глобальный (.set)"
    }
    save_state()

    if not any(t.get_name() == f"attack_{chat_id}" for t in asyncio.all_tasks()):
        asyncio.create_task(run_attack(chat_id), name=f"attack_{chat_id}")

    chat_name = await get_chat_name(chat_id)
    off_cmd = f".stop {chat_id}"
    notif_text = (
        f"𖣂 <b>fk запущен</b>\n"
        f"чат: <code>{chat_name}</code> (<code>{chat_id}</code>)\n"
        f"интервал: <code>{interval}s</code> | шаблон: <code>{template_name or 'global'}</code>\n"
        f"выключить: <code>{off_cmd}</code>"
    )
    await event.reply(notif_text, parse_mode='html')
    await send_to_saved(notif_text, current_chat_id=event.chat_id)

async def run_attack(chat_id):
    while chat_id in active_attacks:
        cfg = active_attacks.get(chat_id)
        if not cfg:
            break
        interval = cfg.get("interval", 5)
        header = cfg.get("header", "")
        local_image = cfg.get("local_image")
        image_url = cfg.get("image_url")
        template = cfg.get("template") or words_list

        if template:
            body = random.choice(template).strip()
            msg = (header + " " + body).strip() if header else body
            try:
                if local_image and os.path.exists(local_image):
                    await client.send_message(chat_id, msg, file=local_image)
                elif image_url:
                    await client.send_message(chat_id, msg, file=image_url)
                else:
                    await client.send_message(chat_id, msg)
            except:
                try:
                    await client.send_message(chat_id, msg)
                except:
                    if chat_id in active_attacks:
                        del active_attacks[chat_id]
                        save_state()
                    break
        await asyncio.sleep(interval)

# ========== .stop ==========
@client.on(events.NewMessage(pattern=r'^\.\s*stop'))
async def stop(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    args = event.message.text.split()
    if len(args) > 1:
        try:
            chat_id = int(args[1])
            if chat_id in active_attacks:
                del active_attacks[chat_id]
                save_state()
                chat_name = await get_chat_name(chat_id)
                await event.reply(f"𖣂 атака остановлена в чате <code>{chat_name}</code> (<code>{chat_id}</code>)", parse_mode='html')
            else:
                await event.reply(f"𖣂 атака не запущена в чате <code>{chat_id}</code>", parse_mode='html')
        except ValueError:
            await event.reply("𖣂 ID чата должен быть числом", parse_mode='html')
    else:
        await event.reply(
            f"𖣂 укажи chat_id: <code>.stop chat_id</code>\n"
            f"активных атак: <code>{len(active_attacks)}</code>",
            parse_mode='html'
        )

# ========== .time ==========
@client.on(events.NewMessage(pattern=r'^\.\s*time$'))
async def show_time(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    bot_up = format_bot_uptime()
    sys_up = get_system_uptime()
    await event.respond(
        f"{MENU_ICON} machine: <code>{sys_up}</code>\n"
        f"{MENU_ICON} bot: <code>{bot_up}</code>",
        parse_mode='html'
    )

# ========== .id ==========
@client.on(events.NewMessage(pattern=r'^\.\s*id$'))
async def get_id(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    if event.is_private:
        await event.reply(f"𖣂 id chat `{event.chat_id}`")
    else:
        chat_id = event.chat_id
        if event.reply_to_msg_id:
            replied = await event.get_reply_message()
            user_id = replied.sender_id
            await event.reply(f"𖣂 id user `{user_id}`\n𖣂 id chat `{chat_id}`")
        else:
            await event.reply(f"𖣂 id chat `{chat_id}`")

# ========== .set ==========
@client.on(events.NewMessage(pattern=r'^\.\s*set(?!tings)\b'))
async def set_template(event):
    if not is_owner(event.sender_id):
        return
    global words_list
    await delete_command(event)

    args = event.message.text.strip().split()
    template_name = args[1] if len(args) > 1 else None
    if template_name and not template_name.endswith(".txt"):
        template_name += ".txt"

    if event.reply_to_msg_id:
        replied = await event.get_reply_message()
        if replied.document and replied.file.name.endswith('.txt'):
            file_path = await replied.download_media()
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f if line.strip()]
                words_list = lines
                save_config()
                save_name = template_name or replied.file.name
                if not save_name.endswith(".txt"):
                    save_name += ".txt"
                dest = os.path.join(TEMPLATES_DIR, save_name)
                with open(dest, 'w', encoding='utf-8') as f:
                    f.write("\n".join(lines))
                await event.reply(f"𖣂 шаблон сохранён: <code>{save_name}</code> — <code>{len(lines)}</code> строк", parse_mode='html')
                return
            except Exception as e:
                await event.reply(f"𖣂 ошибка: <code>{e}</code>", parse_mode='html')
                return
        elif replied.message:
            text = replied.message
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if lines:
                words_list = lines
                save_config()
                save_name = template_name or f"template_{int(time.time())}.txt"
                if not save_name.endswith(".txt"):
                    save_name += ".txt"
                dest = os.path.join(TEMPLATES_DIR, save_name)
                with open(dest, 'w', encoding='utf-8') as f:
                    f.write("\n".join(lines))
                await event.reply(f"𖣂 шаблон сохранён: <code>{save_name}</code> — <code>{len(lines)}</code> строк", parse_mode='html')
                return
    await event.reply("𖣂 реплайни на <code>.txt</code> файл или текст", parse_mode='html')

# ========== .fbl ==========
@client.on(events.NewMessage(pattern=r'^\.\s*fbl\b'))
async def fbl(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    text = event.message.text.strip()
    parts = text.split()

    user_id = None
    chat_id = None
    interval = None
    rest = []

    # ─── Быстрый режим: реплай без аргументов ───
    # .fbl (реплаем на юзера) → интервал 0, шаблон averin.txt, чат = текущий
    if event.reply_to_msg_id and len(parts) == 1:
        replied = await event.get_reply_message()
        user_id = replied.sender_id
        chat_id = event.chat_id
        interval = 0
        template_name = "averin.txt"
        template_lines = load_template(template_name)
        if template_lines is None:
            await event.reply(f"𖣂 быстрый режим требует шаблон <code>{template_name}</code> в templates/ — создай его или используй полную версию команды", parse_mode='html')
            return
        image_url = None
        header = ""
        local_image = None
        effective_words = template_lines

        fbl_targets[user_id] = {
            "interval": interval,
            "chat_id": chat_id,
            "header": header,
            "image_url": image_url,
            "local_image": local_image,
            "template": effective_words,
            "template_name": template_name,
            "last_time": 0.0
        }
        save_state()

        chat_name = await get_chat_name(chat_id)
        off_cmd = f".offfbl {user_id}"
        notif_text = (
            f"𖣂 <b>fbl запущен (быстрый режим)</b>\n"
            f"юзер: <code>{user_id}</code> | чат: <code>{chat_name}</code> (<code>{chat_id}</code>)\n"
            f"интервал: <code>{interval}s</code> | шаблон: <code>{template_name}</code>\n"
            f"выключить: <code>{off_cmd}</code>"
        )
        await event.reply(notif_text, parse_mode='html')
        await send_to_saved(notif_text, current_chat_id=event.chat_id)
        return

    # ─── Реплай-режим с аргументами: .fbl интервал [шаблон.txt] [https://фото] [шапка] ───
    if event.reply_to_msg_id and len(parts) > 1:
        try:
            interval = int(parts[1])
        except ValueError:
            await event.reply("𖣂 интервал должен быть числом", parse_mode='html')
            return
        replied = await event.get_reply_message()
        user_id = replied.sender_id
        chat_id = event.chat_id
        rest = parts[2:]

    # ─── Полная ручная версия: .fbl интервал user_id chat_id [шаблон.txt] [https://фото] [шапка] ───
    else:
        if len(parts) < 4:
            await event.reply(
                "𖣂 использование:\n"
                "• реплаем: <code>.fbl</code> (быстрый запуск)\n"
                "• реплаем: <code>.fbl интервал [шаблон.txt] [https://фото]</code>\n"
                "• вручную: <code>.fbl интервал user_id chat_id [шаблон.txt] [https://фото] [шапка]</code>",
                parse_mode='html'
            )
            return
        try:
            interval = int(parts[1])
            user_id = int(parts[2])
            chat_id = int(parts[3])
        except ValueError:
            await event.reply("𖣂 interval, user_id и chat_id должны быть числами", parse_mode='html')
            return
        rest = parts[4:]

    template_name = None
    template_lines = None
    if rest and rest[-1].endswith(".txt"):
        template_name = rest[-1]
        rest = rest[:-1]
        template_lines = load_template(template_name)
        if template_lines is None:
            await event.reply(f"𖣂 шаблон <code>{template_name}</code> не найден", parse_mode='html')
            return

    image_url = None
    header = ""
    if rest and re.match(r'https?://', rest[0]):
        image_url = rest[0]
        header = " ".join(rest[1:])
    else:
        header = " ".join(rest)

    local_image = await download_image(image_url) if image_url else None
    effective_words = template_lines if template_lines is not None else words_list

    fbl_targets[user_id] = {
        "interval": interval,
        "chat_id": chat_id,
        "header": header,
        "image_url": image_url,
        "local_image": local_image,
        "template": effective_words,
        "template_name": template_name or "глобальный (.set)",
        "last_time": 0.0
    }
    save_state()

    chat_name = await get_chat_name(chat_id)
    off_cmd = f".offfbl {user_id}"
    notif_text = (
        f"𖣂 <b>fbl запущен</b>\n"
        f"юзер: <code>{user_id}</code> | чат: <code>{chat_name}</code> (<code>{chat_id}</code>)\n"
        f"интервал: <code>{interval}s</code> | шаблон: <code>{template_name or 'global'}</code>\n"
        f"выключить: <code>{off_cmd}</code>"
    )
    await event.reply(notif_text, parse_mode='html')
    await send_to_saved(notif_text, current_chat_id=event.chat_id)

# ========== Авто-ответчик — только на чужих, не на себя ==========
@client.on(events.NewMessage)
async def auto_reply(event):
    # Не реагируем на собственные сообщения
    if event.sender_id == OWNER_ID:
        return
    sender = event.sender_id
    if sender in fbl_targets:
        cfg = fbl_targets[sender]
        now = time.time()
        template = cfg.get("template") or words_list
        if (now - cfg.get("last_time", 0) >= cfg.get("interval", 5)
                and event.chat_id == cfg.get("chat_id")
                and template):
            body = random.choice(template).strip()
            msg = (cfg.get("header", "") + " " + body).strip() if cfg.get("header") else body
            local_image = cfg.get("local_image")
            image_url = cfg.get("image_url")
            try:
                if local_image and os.path.exists(local_image):
                    await client.send_message(event.chat_id, msg, file=local_image, reply_to=event.id)
                elif image_url:
                    await client.send_message(event.chat_id, msg, file=image_url, reply_to=event.id)
                else:
                    await client.send_message(event.chat_id, msg, reply_to=event.id)
                cfg["last_time"] = now
            except Exception as e:
                logger.error(f"Ошибка автоответа для {sender} в чате {event.chat_id}: {e}")

# ========== .offfbl ==========
@client.on(events.NewMessage(pattern=r'^\.\s*offfbl'))
async def offfbl(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    args = event.message.text.split()
    if len(args) < 2:
        await event.reply("**Ошибка!** Используйте: `.offfbl <user_id>`")
        return
    try:
        user_id = int(args[1])
        if user_id in fbl_targets:
            cfg = fbl_targets.pop(user_id)
            save_state()
            chat_name = await get_chat_name(cfg.get("chat_id"))
            await event.reply(f"𖣂 автоответчик для <code>{user_id}</code> (чат <code>{chat_name}</code>) отключён", parse_mode='html')
        else:
            await event.reply(f"𖣂 автоответчик для <code>{user_id}</code> не найден", parse_mode='html')
    except ValueError:
        await event.reply("𖣂 ID должен быть числом", parse_mode='html')

# ========== .ping — реальный RTT к Telegram ==========
@client.on(events.NewMessage(pattern=r'^\.\s*ping$'))
async def ping(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    try:
        sw_start = time.perf_counter()
        await client.get_me()  # реальный запрос к Telegram API
        elapsed_ms = round((time.perf_counter() - sw_start) * 1000)
        await event.respond(f"𖣂 пинг: <code>{elapsed_ms}</code> ms 𖣂", parse_mode="html")
    except Exception as e:
        logger.error(f"ошибка .ping: {e}")
        try:
            await event.respond(f"𖣂 ошибка пинга: <code>{e}</code> 𖣂", parse_mode="html")
        except Exception:
            pass

# ========== .tag — спам-теггер (как в референсном коде) ==========
# Синтаксис: .tag <chat_id> <user_id> <интервал> [https://фото] [шапка]
# В каждое сообщение вставляет тег юзера + случайная строка шаблона
# Остановить: .tagoff <chat_id> или .tagoff (всё)
tag_attacks = {}  # {chat_id: True/False}

@client.on(events.NewMessage(pattern=r'^\.\s*tag\b'))
async def tag(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)

    parts = event.message.text.strip().split()
    chat_id = None
    user_id = None
    interval = None
    rest = []

    if event.reply_to_msg_id:
        # реплай-режим: .tag интервал [https://фото] [шапка]
        if len(parts) < 2:
            await event.respond("<b>реплай: <code>.tag интервал [https://фото] [шапка]</code></b>", parse_mode='html')
            return
        try:
            interval = int(parts[1])
        except ValueError:
            await event.respond("<b>интервал должен быть числом</b>", parse_mode='html')
            return
        replied = await event.get_reply_message()
        chat_id = event.chat_id
        user_id = replied.sender_id
        rest = parts[2:]
    else:
        # ручной режим: .tag chat_id user_id интервал [https://фото] [шапка]
        if len(parts) < 4:
            await event.respond(
                "<b>использование: <code>.tag chat_id user_id интервал [фото] [шапка]</code></b>",
                parse_mode='html'
            )
            return
        try:
            chat_id   = int(parts[1])
            user_id   = int(parts[2])
            interval  = int(parts[3])
        except ValueError:
            await event.respond("<b>chat_id, user_id и интервал должны быть числами</b>", parse_mode='html')
            return
        rest = parts[4:]

    if interval < 3:
        await event.respond("<b>задержка слишком маленькая, минимальное значение — 3</b>", parse_mode='html')
        return

    photo   = rest[0] if rest and 'https' in rest[0] else None
    caption = ' '.join(rest[1:]) if photo else ' '.join(rest)

    effective_words = words_list
    if not effective_words:
        await event.respond("<b>шаблон пустой — загрузи через <code>.set</code></b>", parse_mode='html')
        return

    tag_attacks[chat_id] = True

    chat_name = await get_chat_name(chat_id)
    off_cmd = f".tagoff {chat_id}"
    notif_text = (
        f"𖣂 <b>tag запущен</b>\n"
        f"чат: <code>{chat_name}</code> (<code>{chat_id}</code>) | юзер: <code>{user_id}</code>\n"
        f"интервал: <code>{interval}s</code>\n"
        f"выключить: <code>{off_cmd}</code>"
    )
    await event.respond(notif_text, parse_mode='html')
    await send_to_saved(notif_text, current_chat_id=event.chat_id)

    while tag_attacks.get(chat_id):
        line = random.choice(effective_words).strip()
        text = f"{caption} <a href='tg://user?id={user_id}'>{line}</a>" if caption else f"<a href='tg://user?id={user_id}'>{line}</a>"
        try:
            if photo:
                await client.send_file(chat_id, file=photo, caption=text, parse_mode='html')
            else:
                await client.send_message(chat_id, text, parse_mode='html')
        except Exception as e:
            logger.error(f"tag ошибка в {chat_id}: {e}")
            tag_attacks.pop(chat_id, None)
            break
        await asyncio.sleep(interval)

# ========== .tagoff ==========
@client.on(events.NewMessage(pattern=r'^\.\s*tagoff'))
async def tagoff(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    args = event.message.text.split()
    if len(args) > 1:
        try:
            chat_id = int(args[1])
            if chat_id in tag_attacks:
                del tag_attacks[chat_id]
                await event.respond(f"<b>остановлено в чате <code>{chat_id}</code></b>", parse_mode='html')
            else:
                await event.respond(f"<b>чат с айди <code>{chat_id}</code> не был обнаружен</b>", parse_mode='html')
        except ValueError:
            await event.respond("<b>ID чата должен быть числом</b>", parse_mode='html')
    else:
        tag_attacks.clear()
        await event.respond("<b>все теггеры остановлены</b>", parse_mode='html')

# ========== .forever — бесконечный тайпинг ==========
forever_typing = {}  # {chat_id: True/False}

@client.on(events.NewMessage(pattern=r'^\.\s*forever\b'))
async def forever_cmd(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    parts = event.message.text.strip().split()
    if len(parts) < 2:
        await event.respond("𖣂 использование: <code>.forever chat_id</code>", parse_mode='html')
        return
    try:
        chat_id = int(parts[1])
    except ValueError:
        await event.respond("𖣂 chat_id должен быть числом", parse_mode='html')
        return

    if forever_typing.get(chat_id):
        await event.respond(f"𖣂 typing уже запущен в <code>{chat_id}</code>", parse_mode='html')
        return

    forever_typing[chat_id] = True
    chat_name = await get_chat_name(chat_id)
    off_cmd = f".stfv {chat_id}"
    notif_text = (
        f"𖣂 <b>forever typing запущен</b>\n"
        f"чат: <code>{chat_name}</code> (<code>{chat_id}</code>)\n"
        f"выключить: <code>{off_cmd}</code>"
    )
    await event.respond(notif_text, parse_mode='html')
    await send_to_saved(notif_text)

    asyncio.create_task(forever_typing_loop(chat_id), name=f"forever_{chat_id}")

async def forever_typing_loop(chat_id):
    try:
        while forever_typing.get(chat_id):
            try:
                await client(functions.messages.SetTypingRequest(
                    peer=chat_id,
                    action=types.SendMessageTypingAction()
                ))
            except Exception as e:
                logger.error(f"forever typing ошибка {chat_id}: {e}")
                forever_typing.pop(chat_id, None)
                break
            await asyncio.sleep(4)  # typing action живёт ~4-6 сек, обновляем каждые 4
    except asyncio.CancelledError:
        pass

@client.on(events.NewMessage(pattern=r'^\.\s*stfv\b'))
async def stfv_cmd(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    parts = event.message.text.strip().split()
    if len(parts) > 1:
        try:
            chat_id = int(parts[1])
            if chat_id in forever_typing:
                forever_typing.pop(chat_id)
                await event.respond(f"𖣂 typing остановлен в <code>{chat_id}</code>", parse_mode='html')
            else:
                await event.respond(f"𖣂 typing не был запущен в <code>{chat_id}</code>", parse_mode='html')
        except ValueError:
            await event.respond("𖣂 chat_id должен быть числом", parse_mode='html')
    else:
        forever_typing.clear()
        await event.respond("𖣂 все typing остановлены", parse_mode='html')

# ========== .x0 ==========
@client.on(events.NewMessage(pattern=r'^\.\s*x0$'))
async def x0_upload(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    if not event.reply_to_msg_id:
        await event.reply("**Ошибка!** Ответьте командой `.x0` на медиа (фото/видео/файл).")
        return
    replied = await event.get_reply_message()
    if not (replied.photo or replied.video or replied.document):
        await event.reply("**Ошибка!** Реплай должен быть на медиа-файл.")
        return
    status_msg = await event.reply("𖣂 **Загружаю на x0.at...**")
    try:
        local_path = await replied.download_media()
        filename = os.path.basename(local_path)
        async with aiohttp.ClientSession() as session:
            with open(local_path, "rb") as f:
                form = aiohttp.FormData()
                form.add_field("file", f, filename=filename)
                async with session.post(
                    "https://x0.at/",
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    resp_text = (await resp.text()).strip()
                    if resp.status == 200 and resp_text.startswith("https://"):
                        await status_msg.edit(f"𖣂 **загружено**\n `{resp_text}`")
                    else:
                        await status_msg.edit(f"**Ошибка загрузки x0.at:** `{resp_text[:200]}`")
    except Exception as e:
        await status_msg.edit(f"**Ошибка:** `{e}`")

# ========== .fklist ==========
@client.on(events.NewMessage(pattern=r'^\.\s*fklist$'))
async def fklist(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    if not active_attacks:
        await event.reply("**нет активных .fk атак.**")
        return
    msg = "𖣂 **Активные .fk чаты:**\n"
    for cid, cfg in active_attacks.items():
        try:
            entity = await client.get_entity(cid)
            name = getattr(entity, "title", None) or getattr(entity, "username", None) or str(cid)
        except:
            name = str(cid)
        msg += (
            f"`{cid}` — **{name}**\n"
            f"  интервал: `{cfg.get('interval')} сек`\n"
            f"  шаблон: `{cfg.get('template_name', '?')}`\n"
        )
    await event.reply(msg)

# ========== .fbllist ==========
@client.on(events.NewMessage(pattern=r'^\.\s*fbllist'))
async def fbllist(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    if not fbl_targets:
        await event.reply("**нет активных автоответчиков.**")
        return
    msg = "𖣂 **активные автоответчики:**\n"
    for uid, cfg in fbl_targets.items():
        msg += (
            f"пользователь: `{uid}`\n"
            f"  чат: `{cfg.get('chat_id')}`\n"
            f"  шапка: `{cfg.get('header')}`\n"
            f"  фото: `{cfg.get('image_url')}`\n"
            f"  шаблон: `{cfg.get('template_name', '?')}`\n"
            f"  интервал: `{cfg.get('interval')} сек`\n"
        )
    await event.reply(msg)

# ========== .res — восстановление state.json из реплая на файл ==========
@client.on(events.NewMessage(pattern=r'^\.\s*res$'))
async def res_handler(event):
    if not is_owner(event.sender_id):
        return
    await delete_command(event)
    if not event.reply_to_msg_id:
        await event.respond("𖣂 ответь на файл <code>state.json</code>", parse_mode='html')
        return
    replied = await event.get_reply_message()
    if not (replied.document and replied.file and replied.file.name and replied.file.name.endswith('.json')):
        await event.respond("𖣂 реплай должен быть на <code>.json</code> файл", parse_mode='html')
        return
    status = await event.respond("𖣂 загружаю...", parse_mode='html')
    try:
        file_path = await replied.download_media()
        with open(file_path, 'r', encoding='utf-8') as f:
            state = json.load(f)
        try:
            os.remove(file_path)
        except:
            pass
        # Сохраняем как state.json и перезагружаем
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        # Останавливаем все текущие атаки
        active_attacks.clear()
        fbl_targets.clear()
        # Загружаем новое состояние
        load_state()
        # Запускаем атаки
        restored = 0
        for chat_id in list(active_attacks.keys()):
            asyncio.create_task(run_attack(chat_id), name=f"attack_{chat_id}")
            restored += 1
        await status.edit(
            f"𖣂 восстановлено: <code>{restored}</code> атак, <code>{len(fbl_targets)}</code> fbl",
            parse_mode='html'
        )
    except Exception as e:
        await status.edit(f"𖣂 ошибка: <code>{e}</code>", parse_mode='html')

# ========== .icon — смена фото меню ==========
@client.on(events.NewMessage(pattern=r'^\.\s*icon'))
async def icon_handler(event):
    if not is_owner(event.sender_id):
        return
    global MENU_MEDIA
    await delete_command(event)
    args = event.message.text.strip().split()
    # Вариант 1: .icon https://...
    if len(args) > 1 and args[1].startswith('http'):
        MENU_MEDIA = args[1]
        save_config()
        await event.respond(f"𖣂 фото меню изменено: <code>{MENU_MEDIA}</code>", parse_mode='html')
        return
    # Вариант 2: .icon реплаем на медиа
    if event.reply_to_msg_id:
        replied = await event.get_reply_message()
        if replied.photo or replied.video or replied.document:
            status = await event.respond("𖣂 загружаю...", parse_mode='html')
            try:
                local_path = await replied.download_media(file=IMAGES_DIR)
                async with aiohttp.ClientSession() as session:
                    with open(local_path, 'rb') as f:
                        form = aiohttp.FormData()
                        form.add_field('file', f, filename=os.path.basename(local_path))
                        async with session.post('https://x0.at/', data=form, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                            url = (await resp.text()).strip()
                            if resp.status == 200 and url.startswith('https://'):
                                MENU_MEDIA = url
                                save_config()
                                await status.edit(f"𖣂 фото меню изменено: <code>{MENU_MEDIA}</code>", parse_mode='html')
                            else:
                                await status.edit("𖣂 ошибка загрузки на x0.at", parse_mode='html')
            except Exception as e:
                await status.edit(f"𖣂 ошибка: <code>{e}</code>", parse_mode='html')
            return
    await event.respond("𖣂 используй: <code>.icon https://...</code> или реплай на фото", parse_mode='html')

# ========== Запуск бота ==========
async def main():
    load_config()
    load_state()   # восстанавливаем сохранённые атаки и fbl

    await client.connect()
    if not await client.is_user_authorized():
        await client.send_code_request(phone_number)
        code = ask_input("𖣂 введи код из Telegram: ")
        try:
            await client.sign_in(phone_number, code)
        except SessionPasswordNeededError:
            password = ask_input("𖣂 введи пароль (2FA): ")
            await client.sign_in(password=password)

    print("𖣂 omyt ebawit za svoix 𖣂")

    # Перезапускаем атаки которые были до выключения
    for chat_id in list(active_attacks.keys()):
        asyncio.create_task(run_attack(chat_id), name=f"attack_{chat_id}")
    if active_attacks:
        print(f"𖣂 восстановлено атак: {len(active_attacks)}")

    if fbl_targets:
        print(f"𖣂 восстановлено fbl: {len(fbl_targets)}")

    # ─── Единое стартовое уведомление в избранное ───
    try:
        lines = ["✟✟✟ averin here ✟✟✟", "𖣂 <b>бот запущен</b>"]
        if active_attacks:
            lines.append(f"\n<b>активных fk атак: {len(active_attacks)}</b>")
            for cid, cfg in active_attacks.items():
                cname = await get_chat_name(cid)
                lines.append(f"  чат <code>{cname}</code> (<code>{cid}</code>) | интервал <code>{cfg.get('interval')}s</code>")
                lines.append(f"  стоп: <code>.stop {cid}</code>")
        if fbl_targets:
            lines.append(f"\n<b>активных fbl: {len(fbl_targets)}</b>")
            for uid, cfg in fbl_targets.items():
                cname = await get_chat_name(cfg.get('chat_id'))
                lines.append(f"  юзер <code>{uid}</code> | чат <code>{cname}</code> | интервал <code>{cfg.get('interval')}s</code>")
                lines.append(f"  стоп: <code>.offfbl {uid}</code>")
        if not active_attacks and not fbl_targets:
            lines.append("\n𖣂 активных задач нет")
        me = await client.get_me()
        await client.send_message(me.id, "\n".join(lines), parse_mode='html')
    except Exception as e:
        logger.error(f"ошибка отправки стартового уведомления: {e}")

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"𖣂 omyt slomalsya: {e} 𖣂")
