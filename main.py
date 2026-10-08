import os
import sys
import re
import random
import asyncio
import importlib.util
from pathlib import Path
from datetime import datetime
from colorama import Fore, Style, init

from telethon import TelegramClient, events
from telethon.tl.types import User, MessageEntityMention
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    ApiIdInvalidError,
)

init(autoreset=True)

# ---------- Баннер ----------
BANNER = f"""
{Fore.CYAN}{Style.BRIGHT}
██╗   ██╗███████╗██████╗  █████╗     ██████╗  ██████╗ ████████╗
██║   ██║██╔════╝██╔══██╗██╔══██╗    ██╔══██╗██╔═══██╗╚══██╔══╝
██║   ██║█████╗  ██████╔╝███████║    ██████╔╝██║   ██║   ██║   
██║   ██║██╔══╝  ██╔══██╗██╔══██║    ██╔══██╗██║   ██║   ██║   
╚██████╔╝███████╗██████╔╝██║  ██║    ██████╔╝╚██████╔╝   ██║   
 ╚═════╝ ╚══════╝╚═════╝ ╚═╝  ╚═╝    ╚═════╝  ╚═════╝    ╚═╝   
{Style.RESET_ALL}
{Fore.MAGENTA}              ⚡ UserBot v2.1 ⚡
{Fore.YELLOW}              by panihida
{Style.RESET_ALL}
"""

SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

PHRASES_DIR = Path("phrases")
PHRASES_DIR.mkdir(exist_ok=True)

PHRASES_FILE = PHRASES_DIR / "phrases.txt"

MODULES_DIR = Path("modules")
MODULES_DIR.mkdir(exist_ok=True)

# ---------- Глобальное состояние ----------
TAR_TARGETS = {}
TYPING_TASKS = {}
PHRASES = []

# Реестр модулей: {name: {"module": obj, "path": Path, "help": str, "cmds": [...]}}
LOADED_MODULES = {}

# Порядковый номер -> имя модуля (перестраивается при каждом list)
MODULE_INDEX = []

DEFAULT_PHRASES = [
    "ты че такой дерзкий",
    "иди уроки делай",
    "мама тебя зовёт",
    "ты кто вообще такой",
    "хахаха смешной",
    "ой всё",
    "ну ты и клоун",
    "иди поспи",
    "тебе не стыдно",
    "чё пристал",
    "отстань от меня",
    "хватит спамить",
    "я тебя не знаю",
    "уйди пожалуйста",
]


# =========================================================
#                    УТИЛИТЫ
# =========================================================
def clear():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    clear()
    print(BANNER)


def ask(prompt: str, color=Fore.CYAN) -> str:
    return input(f"{color}▸ {Fore.WHITE}{prompt}{Style.RESET_ALL}").strip()


def info(text: str):
    print(f"{Fore.BLUE}[i]{Style.RESET_ALL} {text}")


def ok(text: str):
    print(f"{Fore.GREEN}[✓]{Style.RESET_ALL} {text}")


def warn(text: str):
    print(f"{Fore.YELLOW}[!]{Style.RESET_ALL} {text}")


def err(text: str):
    print(f"{Fore.RED}[✗]{Style.RESET_ALL} {text}")


def list_sessions():
    return [f.stem for f in SESSIONS_DIR.glob("*.session")]


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[a-zA-Z]", "", text)
    text = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]", "", text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_phrases_from_file(path: Path) -> int:
    global PHRASES
    if not path.exists():
        return 0

    raw_lines = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="cp1251") as f:
                raw_lines = f.readlines()
        except Exception:
            return 0
    except Exception:
        return 0

    cleaned = []
    for line in raw_lines:
        norm = normalize_text(line)
        if norm and len(norm) > 1:
            cleaned.append(norm)

    if not cleaned:
        return 0

    PHRASES = cleaned

    try:
        with open(PHRASES_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(cleaned))
    except Exception:
        pass

    return len(cleaned)


def load_cached_phrases():
    global PHRASES
    if PHRASES_FILE.exists():
        try:
            with open(PHRASES_FILE, "r", encoding="utf-8") as f:
                PHRASES = [l.strip() for l in f if l.strip()]
        except Exception:
            PHRASES = []


# =========================================================
#                    РЕЕСТР МОДУЛЕЙ
# =========================================================
def rebuild_index():
    """Пересобирает нумерованный список модулей (сортировка по имени)."""
    global MODULE_INDEX
    MODULE_INDEX = sorted(LOADED_MODULES.keys())


def get_module_by_number(num: int):
    """Возвращает (name, data) по номеру или (None, None)."""
    rebuild_index()
    if 1 <= num <= len(MODULE_INDEX):
        name = MODULE_INDEX[num - 1]
        return name, LOADED_MODULES[name]
    return None, None


def collect_module_commands(module) -> list:
    """
    Ищет в объекте модуля все команды — по атрибуту COMMANDS
    или по паттернам, если модуль их регистрирует через setup.
    Модуль может просто объявить список COMMANDS = ['.м-анимация', ...]
    """
    cmds = getattr(module, "COMMANDS", None)
    if cmds:
        return list(cmds)
    return []


# =========================================================
#                ЛОГИН
# =========================================================
async def login_flow():
    print_banner()

    sessions = list_sessions()

    if sessions:
        info(f"Найдено сохранённых сессий: {len(sessions)}")
        for i, s in enumerate(sessions, 1):
            print(f"   {Fore.CYAN}{i}.{Style.RESET_ALL} {s}")
        print(f"   {Fore.CYAN}0.{Style.RESET_ALL} Войти в новый аккаунт\n")

        choice = ask("Выбери номер сессии (Enter — новая): ")
        if choice.isdigit() and int(choice) > 0:
            idx = int(choice) - 1
            if 0 <= idx < len(sessions):
                return sessions[idx]
        print()

    print(f"{Fore.MAGENTA}━━━ Вход в новый аккаунт ━━━{Style.RESET_ALL}\n")
    info("Получить API_ID и API_HASH: https://my.telegram.org/apps\n")

    try:
        api_id = int(ask("API_ID: "))
    except ValueError:
        err("API_ID должен быть числом!")
        sys.exit(1)

    api_hash = ask("API_HASH: ")
    if not api_hash:
        err("API_HASH не может быть пустым!")
        sys.exit(1)

    phone = ask("Номер телефона (например +79991234567): ")
    if not phone:
        err("Телефон не может быть пустым!")
        sys.exit(1)

    session_name = ask("Имя сессии (например main): ") or "userbot"
    session_path = SESSIONS_DIR / session_name

    print()
    info("Подключаюсь к Telegram...")

    client = TelegramClient(str(session_path), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        try:
            await client.send_code_request(phone)
            ok("Код отправлен в Telegram!")

            code = ask("Введи код из Telegram: ")

            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                warn("Включена двухэтапная аутентификация (2FA)")
                password = ask("Введи пароль 2FA: ")
                await client.sign_in(password=password)

        except PhoneCodeInvalidError:
            err("Неверный код!")
            sys.exit(1)
        except PhoneNumberInvalidError:
            err("Неверный номер телефона!")
            sys.exit(1)
        except ApiIdInvalidError:
            err("Неверный API_ID или API_HASH!")
            sys.exit(1)

    me = await client.get_me()
    ok(f"Успешный вход: {me.first_name} (@{me.username or 'нет username'})")
    info(f"ID: {me.id}")

    await client.disconnect()

    with open(SESSIONS_DIR / f"{session_name}.cfg", "w") as f:
        f.write(f"{api_id}\n{api_hash}\n{phone}\n")

    ok(f"Сессия сохранена в: {session_path}.session")
    return session_name


# =========================================================
#                ЗАГРУЗЧИК МОДУЛЕЙ
# =========================================================
def load_module_from_path(path: Path):
    name = path.stem
    spec = importlib.util.spec_from_file_location(f"ubmod_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Не смог создать spec для {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def register_module(client, path: Path, ctx: dict):
    name = path.stem
    try:
        module = load_module_from_path(path)
    except Exception as e:
        err(f"Ошибка загрузки модуля {name}: {e}")
        return False

    LOADED_MODULES[name] = {
        "module": module,
        "path": path,
        "help": getattr(module, "HELP", "—"),
        "commands": collect_module_commands(module),
    }

    setup = getattr(module, "setup", None)
    if callable(setup):
        try:
            result = setup(client, ctx)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            err(f"Ошибка setup() в модуле {name}: {e}")
            return False

    ok(f"Модуль загружен: {name}")
    return True


async def load_all_modules(client, ctx: dict):
    files = sorted(MODULES_DIR.glob("*.py"))
    files = [f for f in files if not f.name.startswith("_")]

    if not files:
        info("Модулей не найдено (папка modules/ пуста)")
        return

    info(f"Найдено модулей: {len(files)}")
    for f in files:
        await register_module(client, f, ctx)

    rebuild_index()


# =========================================================
#                ТЕКСТ ПОМОЩИ
# =========================================================
def build_help_text() -> str:
    pool = PHRASES if PHRASES else DEFAULT_PHRASES
    source = "txt-файл" if PHRASES else "дефолт"

    base = (
        "🤖 **UEBA BOT — команды**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📥 `.my`\n"
        "   └ _реплай на txt → загрузить фразы_\n\n"
        "🎯 `.тар`\n"
        "   └ _реплай на юзера → вкл/выкл троллинг_\n\n"
        "⌨️ `.тайп`\n"
        "   └ _вкл/выкл 'печатает' в текущем чате_\n\n"
        "📊 `.ar`\n"
        "   └ _статистика фраз_\n\n"
        "📦 **Модули**\n"
        "   └ `.py` _реплай на .py → установить_\n"
        "   └ `.m` _список модулей с номерами_\n"
        "   └ `.ms <номер>` _инфо о модуле_\n"
        "   └ `.md <номер>` _удалить модуль_\n\n"
        "❓ `.help`\n"
        "   └ _это меню_\n"
    )

    base += (
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 Фраз в базе: **{len(pool)}** (`{source}`)\n"
        f"🟢 .тар активно: **{len(TAR_TARGETS)}**\n"
        f"⌨️ Чатов с .тайп: **{len(TYPING_TASKS)}**\n"
        f"📦 Модулей: **{len(LOADED_MODULES)}**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    return base


# =========================================================
#                ЗАПУСК ЮЗЕРБОТА
# =========================================================
async def start_userbot(session_name: str):
    cfg_path = SESSIONS_DIR / f"{session_name}.cfg"
    if not cfg_path.exists():
        err("Не найден конфиг сессии. Удали .session и зайди заново.")
        return

    with open(cfg_path) as f:
        api_id, api_hash, phone = f.read().splitlines()

    client = TelegramClient(str(SESSIONS_DIR / session_name), int(api_id), api_hash)
    await client.start(phone=phone)

    me = await client.get_me()
    MY_ID = me.id
    MY_USERNAME = (me.username or "").lower()

    load_cached_phrases()

    ctx = {
        "PHRASES": PHRASES,
        "DEFAULT_PHRASES": DEFAULT_PHRASES,
        "TAR_TARGETS": TAR_TARGETS,
        "TYPING_TASKS": TYPING_TASKS,
        "LOADED_MODULES": LOADED_MODULES,
        "MY_ID": MY_ID,
        "MY_USERNAME": MY_USERNAME,
        "MODULES_DIR": MODULES_DIR,
        "PHRASES_FILE": PHRASES_FILE,
        "normalize_text": normalize_text,
        "load_phrases_from_file": load_phrases_from_file,
        "register_module": lambda p: register_module(client, p, ctx),
    }

    print()
    print(f"{Fore.MAGENTA}═══════════════════════════════════════{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{Style.BRIGHT}   🤖 USERBOT ЗАПУЩЕН{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}═══════════════════════════════════════{Style.RESET_ALL}")
    print(f"   Аккаунт: {Fore.CYAN}{me.first_name}{Style.RESET_ALL}")
    print(f"   Юзернейм: {Fore.CYAN}@{me.username or '—'}{Style.RESET_ALL}")
    print(f"   ID: {Fore.CYAN}{me.id}{Style.RESET_ALL}")
    print(f"   Фраз в базе: {Fore.CYAN}{len(PHRASES)}{Style.RESET_ALL}")
    if PHRASES:
        print(f"   Источник: {Fore.CYAN}{PHRASES_FILE}{Style.RESET_ALL}")
    else:
        print(f"   {Fore.YELLOW}txt не загружен — используются дефолтные фразы{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}═══════════════════════════════════════{Style.RESET_ALL}")

    print()
    info("Загружаю модули...")
    await load_all_modules(client, ctx)

    print()
    print(f"{Fore.YELLOW}Введи .help в чате, чтобы увидеть все команды{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Ctrl+C — выход{Style.RESET_ALL}\n")

    # =========================================================
    #              КОМАНДА .help
    # =========================================================
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.help$"))
    async def help_cmd(event):
        try:
            await event.delete()
        except Exception:
            pass
        msg = await client.send_message(event.chat_id, build_help_text())
        await asyncio.sleep(25)
        try:
            await msg.delete()
        except Exception:
            pass

    # =========================================================
    #              КОМАНДА .m — список модулей
    # =========================================================
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.m$"))
    async def m_cmd(event):
        try:
            await event.delete()
        except Exception:
            pass

        rebuild_index()

        if not MODULE_INDEX:
            msg = await client.send_message(
                event.chat_id, "📦 **Модулей нет**"
            )
            await asyncio.sleep(5)
            try:
                await msg.delete()
            except Exception:
                pass
            return

        lines = [
            "📦 **Список модулей**",
            "━━━━━━━━━━━━━━━━━━━━",
        ]
        for i, name in enumerate(MODULE_INDEX, 1):
            data = LOADED_MODULES[name]
            h = data["help"]
            lines.append(f"`{i}.` 🧩 **{name}** — _{h}_")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"Всего: **{len(MODULE_INDEX)}**")
        lines.append("")
        lines.append("`.ms <номер>` — инфо о модуле")
        lines.append("`.md <номер>` — удалить модуль")

        msg = await client.send_message(event.chat_id, "\n".join(lines))
        await asyncio.sleep(25)
        try:
            await msg.delete()
        except Exception:
            pass

    # =========================================================
    #              КОМАНДА .ms <номер> — инфо
    # =========================================================
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.ms\s*(\d+)$"))
    async def ms_cmd(event):
        try:
            await event.delete()
        except Exception:
            pass

        num = int(event.pattern_match.group(1))
        name, data = get_module_by_number(num)

        if not name:
            msg = await client.send_message(
                event.chat_id,
                f"❌ Нет модуля с номером **{num}**\n"
                f"Посмотреть список: `.m`"
            )
            await asyncio.sleep(4)
            try:
                await msg.delete()
            except Exception:
                pass
            return

        module = data["module"]
        path = data["path"]
        help_txt = data["help"]
        cmds = data["commands"]

        # размер файла
        try:
            size = path.stat().st_size
            size_txt = f"{size} байт"
        except Exception:
            size_txt = "—"

        text = (
            f"🧩 **Модуль #{num} — {name}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 Описание: _{help_txt}_\n"
            f"📄 Файл: `{path.name}`\n"
            f"💾 Размер: {size_txt}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )

        if cmds:
            text += "⚙️ **Команды:**\n"
            for c in cmds:
                text += f"   • `{c}`\n"
        else:
            text += "⚙️ **Команды:** _не указаны_\n"
            text += f"   _проверь `.help` или используй префикс `.м-{name}`_\n"

        text += "━━━━━━━━━━━━━━━━━━━━\n"
        text += f"Удалить: `.md {num}`"

        msg = await client.send_message(event.chat_id, text)
        await asyncio.sleep(20)
        try:
            await msg.delete()
        except Exception:
            pass

    # =========================================================
    #              КОМАНДА .md <номер> — удалить
    # =========================================================
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.md\s*(\d+)$"))
    async def md_cmd(event):
        try:
            await event.delete()
        except Exception:
            pass

        num = int(event.pattern_match.group(1))
        name, data = get_module_by_number(num)

        if not name:
            msg = await client.send_message(
                event.chat_id,
                f"❌ Нет модуля с номером **{num}**\n"
                f"Посмотреть список: `.m`"
            )
            await asyncio.sleep(4)
            try:
                await msg.delete()
            except Exception:
                pass
            return

        path = data["path"]

        # удаляем файл
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            msg = await client.send_message(
                event.chat_id, f"❌ Не смог удалить файл: {e}"
            )
            await asyncio.sleep(4)
            try:
                await msg.delete()
            except Exception:
                pass
            return

        # убираем из реестра
        LOADED_MODULES.pop(name, None)
        rebuild_index()

        msg = await client.send_message(
            event.chat_id,
            f"🗑 **Модуль удалён**\n"
            f"🧩 #{num} `{name}`\n"
            f"_Хендлеры отключатся после перезапуска бота_",
        )
        await asyncio.sleep(6)
        try:
            await msg.delete()
        except Exception:
            pass

    # =========================================================
    #              КОМАНДА .my
    # =========================================================
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.my$"))
    async def my_cmd(event):
        try:
            await event.delete()
        except Exception:
            pass

        if not event.is_reply:
            msg = await client.send_message(
                event.chat_id,
                "❌ Ответь `.my` на **txt-файл**, чтобы загрузить фразы",
            )
            await asyncio.sleep(4)
            await msg.delete()
            return

        reply = await event.get_reply_message()
        if not reply or not reply.document:
            msg = await client.send_message(
                event.chat_id, "❌ В сообщении нет файла"
            )
            await asyncio.sleep(4)
            await msg.delete()
            return

        fname = ""
        for attr in reply.document.attributes:
            if hasattr(attr, "file_name"):
                fname = attr.file_name or ""
                break

        if not fname.lower().endswith(".txt"):
            msg = await client.send_message(
                event.chat_id, "❌ Нужен именно `.txt` файл"
            )
            await asyncio.sleep(4)
            await msg.delete()
            return

        info(f"Скачиваю {fname}...")
        download_path = PHRASES_DIR / fname

        try:
            await reply.download_media(file=str(download_path))
        except Exception as e:
            err(f"Ошибка скачивания: {e}")
            msg = await client.send_message(
                event.chat_id, f"❌ Не смог скачать: {e}"
            )
            await asyncio.sleep(4)
            await msg.delete()
            return

        count = load_phrases_from_file(download_path)

        if count == 0:
            msg = await client.send_message(
                event.chat_id, "❌ В файле нет валидных фраз"
            )
            await asyncio.sleep(4)
            await msg.delete()
            return

        ok(f"Загружено фраз: {count}")
        msg = await client.send_message(
            event.chat_id,
            f"✅ **Фразы загружены**\n"
            f"📄 Файл: `{fname}`\n"
            f"💬 Фраз в базе: **{count}**",
        )
        await asyncio.sleep(5)
        await msg.delete()

    # =========================================================
    #              КОМАНДА .py
    # =========================================================
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.py(?:\s+(.+))?$"))
    async def py_cmd(event):
        try:
            await event.delete()
        except Exception:
            pass

        arg = (event.pattern_match.group(1) or "").strip()

        # ---------- .py list ----------
        if arg.lower() in ("list", "список"):
            rebuild_index()
            if not MODULE_INDEX:
                msg = await client.send_message(
                    event.chat_id, "📦 Модулей нет"
                )
            else:
                lines = ["📦 **Загруженные модули:**", "━━━━━━━━━━━━━━━━━━"]
                for i, name in enumerate(MODULE_INDEX, 1):
                    h = LOADED_MODULES[name]["help"]
                    lines.append(f"`{i}.` 🧩 **{name}** — _{h}_")
                lines.append("━━━━━━━━━━━━━━━━━━")
                lines.append(f"Всего: **{len(MODULE_INDEX)}**")
                msg = await client.send_message(
                    event.chat_id, "\n".join(lines)
                )
            await asyncio.sleep(15)
            try:
                await msg.delete()
            except Exception:
                pass
            return

        # ---------- .py del <имя> ----------
        if arg.lower().startswith(("del ", "удалить ", "удали ")):
            parts = arg.split(maxsplit=1)
            if len(parts) < 2:
                msg = await client.send_message(
                    event.chat_id, "❌ `.py del <имя>`"
                )
                await asyncio.sleep(3)
                await msg.delete()
                return

            name = parts[1].strip().removesuffix(".py")
            path = MODULES_DIR / f"{name}.py"

            if path.exists():
                try:
                    path.unlink()
                except Exception as e:
                    msg = await client.send_message(
                        event.chat_id, f"❌ Не удалил: {e}"
                    )
                    await asyncio.sleep(3)
                    await msg.delete()
                    return

            LOADED_MODULES.pop(name, None)
            rebuild_index()
            msg = await client.send_message(
                event.chat_id,
                f"🗑 Модуль `{name}` удалён\n"
                f"_(хендлеры останутся до перезапуска)_",
            )
            await asyncio.sleep(5)
            await msg.delete()
            return

        # ---------- .py (без аргумента) ----------
        if not event.is_reply:
            rebuild_index()
            msg = await client.send_message(
                event.chat_id,
                "📦 **.py — менеджер модулей**\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "• `.py` _(реплай на .py)_ → установить\n"
                "• `.py list` → список\n"
                "• `.py del <имя>` → удалить\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"📁 Папка: `modules/`\n"
                f"📦 Загружено: **{len(MODULE_INDEX)}**",
            )
            await asyncio.sleep(15)
            try:
                await msg.delete()
            except Exception:
                pass
            return

        reply = await event.get_reply_message()
        if not reply or not reply.document:
            msg = await client.send_message(
                event.chat_id, "❌ В сообщении нет файла"
            )
            await asyncio.sleep(4)
            await msg.delete()
            return

        fname = ""
        for attr in reply.document.attributes:
            if hasattr(attr, "file_name"):
                fname = attr.file_name or ""
                break

        if not fname.lower().endswith(".py"):
            msg = await client.send_message(
                event.chat_id, "❌ Нужен именно `.py` файл"
            )
            await asyncio.sleep(4)
            await msg.delete()
            return

        safe_name = re.sub(r"[^\w\-]", "_", fname)[:60]
        if not safe_name.endswith(".py"):
            safe_name += ".py"

        target_path = MODULES_DIR / safe_name

        info(f"Скачиваю модуль {fname} → {target_path.name}...")

        try:
            await reply.download_media(file=str(target_path))
        except Exception as e:
            err(f"Ошибка скачивания: {e}")
            msg = await client.send_message(
                event.chat_id, f"❌ Не смог скачать: {e}"
            )
            await asyncio.sleep(4)
            await msg.delete()
            return

        success = await register_module(client, target_path, ctx)
        rebuild_index()

        if success:
            ok(f"Модуль {target_path.stem} активирован")
            msg = await client.send_message(
                event.chat_id,
                f"✅ **Модуль установлен**\n"
                f"🧩 Имя: `{target_path.stem}`\n"
                f"📄 Файл: `{safe_name}`\n"
                f"_Проверить: `.m`_",
            )
        else:
            msg = await client.send_message(
                event.chat_id,
                f"⚠️ Модуль `{target_path.stem}` скачан, но не загрузился.\n"
                f"_Проверь синтаксис / импорты._",
            )
        await asyncio.sleep(8)
        try:
            await msg.delete()
        except Exception:
            pass

    # =========================================================
    #              КОМАНДА .ar
    # =========================================================
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.ar$"))
    async def ar_cmd(event):
        try:
            await event.delete()
        except Exception:
            pass

        pool = PHRASES if PHRASES else DEFAULT_PHRASES
        source = "txt-файл" if PHRASES else "дефолт"

        total_phrases = len(pool)
        total_words = sum(len(p.split()) for p in pool)
        total_chars = sum(len(p) for p in pool)
        avg_words = round(total_words / total_phrases, 2) if total_phrases else 0
        longest = max(pool, key=lambda x: len(x.split())) if pool else "—"
        shortest = min(pool, key=lambda x: len(x.split())) if pool else "—"

        text = (
            f"📊 **Статистика фраз**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 Всего фраз: **{total_phrases}**\n"
            f"🔤 Всего слов: **{total_words}**\n"
            f"🔡 Всего символов: **{total_chars}**\n"
            f"📈 Среднее слов/фраза: **{avg_words}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📚 Источник: `{source}`\n"
            f"🟢 Таргетов .тар: **{len(TAR_TARGETS)}**\n"
            f"⌨️ Чатов с .тайп: **{len(TYPING_TASKS)}**\n"
            f"📦 Модулей: **{len(LOADED_MODULES)}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔺 Самая длинная: _{longest[:60]}_\n"
            f"🔻 Самая короткая: _{shortest[:60]}_"
        )

        msg = await client.send_message(event.chat_id, text)
        await asyncio.sleep(15)
        try:
            await msg.delete()
        except Exception:
            pass

    # =========================================================
    #              КОМАНДА .тар
    # =========================================================
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.тар$"))
    async def tar_cmd(event):
        try:
            await event.delete()
        except Exception:
            pass

        if not event.is_reply:
            if TAR_TARGETS:
                TAR_TARGETS.clear()
                msg = await client.send_message(
                    event.chat_id, "я те мать убил"
                )
                await asyncio.sleep(3)
                await msg.delete()
            else:
                msg = await client.send_message(
                    event.chat_id,
                    "⚠️ Ответь `.тар` на сообщение юзера, чтобы включить\n"
                    "либо (без реплая) — чтобы выключить всех",
                )
                await asyncio.sleep(5)
                await msg.delete()
            return

        reply = await event.get_reply_message()
        if not reply:
            return

        try:
            target = await reply.get_sender()
        except Exception:
            return

        if target is None or not isinstance(target, User):
            msg = await client.send_message(
                event.chat_id, "❌ Это не пользователь"
            )
            await asyncio.sleep(3)
            await msg.delete()
            return

        if target.id == MY_ID:
            msg = await client.send_message(
                event.chat_id, "❌ Нельзя таргетить себя"
            )
            await asyncio.sleep(3)
            await msg.delete()
            return

        target_id = target.id

        if target_id in TAR_TARGETS:
            del TAR_TARGETS[target_id]
            msg = await client.send_message(
                event.chat_id, "я те мать убил"
            )
        else:
            TAR_TARGETS[target_id] = True
            msg = await client.send_message(
                event.chat_id, "я тебе мать ебал"
            )
        await asyncio.sleep(4)
        await msg.delete()

    # =========================================================
    #              КОМАНДА .тайп
    # =========================================================
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.тайп$"))
    async def typ_cmd(event):
        try:
            await event.delete()
        except Exception:
            pass

        chat_id = event.chat_id

        if chat_id in TYPING_TASKS:
            task = TYPING_TASKS.pop(chat_id)
            if not task.done():
                task.cancel()
            msg = await client.send_message(chat_id, "⌨️ **.тайп ВЫКЛ**")
            await asyncio.sleep(3)
            try:
                await msg.delete()
            except Exception:
                pass
            return

        task = asyncio.create_task(typing_loop(client, chat_id))
        TYPING_TASKS[chat_id] = task
        msg = await client.send_message(
            chat_id, "⌨️ **.тайп ВКЛ**\n_печатаю бесконечно..._"
        )
        await asyncio.sleep(3)
        try:
            await msg.delete()
        except Exception:
            pass

    async def typing_loop(cli, chat_id):
        try:
            while True:
                try:
                    async with cli.action(chat_id, "typing"):
                        await asyncio.sleep(5)
                except asyncio.CancelledError:
                    break
                except Exception:
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    # =========================================================
    #           ОТВЕТЧИК .тар
    # =========================================================
    @client.on(events.NewMessage(incoming=True))
    async def tar_responder(event):
        if not TAR_TARGETS:
            return

        try:
            sender = await event.get_sender()
        except Exception:
            return

        if sender is None or not isinstance(sender, User):
            return

        if sender.id not in TAR_TARGETS:
            return

        text = normalize_text(event.raw_text or "")
        if not text:
            return

        pool = PHRASES if PHRASES else DEFAULT_PHRASES
        reply = random.choice(pool)

        try:
            await event.reply(reply)
        except Exception as e:
            err(f"Не отправил ответ: {e}")

    # =========================================================
    #           АВТООТВЕТ НА УПОМИНАНИЯ / РЕПЛАИ
    # =========================================================
    @client.on(events.NewMessage(incoming=True))
    async def auto_reply(event):
        try:
            sender = await event.get_sender()
        except Exception:
            return

        if sender is None or not isinstance(sender, User):
            return
        if sender.bot:
            return
        if sender.id in TAR_TARGETS:
            return

        triggered = False

        if event.is_reply:
            try:
                reply_msg = await event.get_reply_message()
                if reply_msg:
                    reply_sender = await reply_msg.get_sender()
                    if reply_sender and getattr(reply_sender, "id", None) == MY_ID:
                        triggered = True
            except Exception:
                pass

        if not triggered and MY_USERNAME:
            text_lower = (event.raw_text or "").lower()
            if f"@{MY_USERNAME}" in text_lower:
                triggered = True

        if not triggered and event.message.entities:
            for ent in event.message.entities:
                if isinstance(ent, MessageEntityMention):
                    mention = (event.raw_text or "")[ent.offset:ent.offset + ent.length]
                    if mention.lower().lstrip("@") == MY_USERNAME:
                        triggered = True
                        break

        if not triggered:
            return

        pool = PHRASES if PHRASES else DEFAULT_PHRASES
        reply = random.choice(pool)

        try:
            await event.reply(reply)
        except Exception as e:
            err(f"Автоответ не отправлен: {e}")

    await client.run_until_disconnected()


async def main():
    try:
        session_name = await login_flow()
        await start_userbot(session_name)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Выход...{Style.RESET_ALL}")


if __name__ == "__main__":
    asyncio.run(main())