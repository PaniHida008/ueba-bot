# modules/скрин.py
"""
Модуль троллинга.

Режимы:
    .тарс              — ответ на сообщения цели (скрин + фраза)
    .арс [кд]          — СПАМ: скрин + "<юзер>, <фраза>"
    .ар [кд]           — СПАМ: "<юзер>, <фраза>" без скрина

В начале фразы — упоминание юзера:
    • если есть @username → @username
    • иначе → кликабельная ссылка tg://user?id=<id>
"""
import io
import re
import html
import random
import asyncio
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HELP = "троллинг: .тарс (реплай-ответ) / .арс / .ар (спам)"
COMMANDS = [
    ".тарс",
    ".тарс <кд>",
    ".арс",
    ".арс <кд>",
    ".ар",
    ".ар <кд>",
]

# ---------- Настройки скрина ----------
SCREENSHOT_WIDTH = 640
SCREENSHOT_HEIGHT = 320
BG_COLOR = (23, 33, 43)
CARD_COLOR = (32, 45, 58)
TEXT_COLOR = (240, 240, 240)
SUB_COLOR = (140, 155, 170)
ACCENT = (82, 136, 193)
AVATAR_SIZE = 120

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)


# ---------- Списки целей ----------
TAR_SCREEN_TARGETS = {}   # .тарс
AR_SCREEN_TARGETS = {}    # .арс
AR_TEXT_TARGETS = {}      # .ар


# ---------- Шрифты ----------
def _get_font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    if bold:
        candidates.insert(0, "C:/Windows/Fonts/segoeuib.ttf")
        candidates.insert(1, "C:/Windows/Fonts/arialbd.ttf")
        candidates.insert(2, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    for c in candidates:
        try:
            if Path(c).exists():
                return ImageFont.truetype(c, size)
        except Exception:
            continue
    try:
        return ImageFont.truetype("arial", size)
    except Exception:
        return ImageFont.load_default()


# ---------- Рендер скрина ----------
def draw_profile_screenshot(
    first_name: str,
    last_name: str,
    username: str,
    user_id: int,
    phone: str = None,
    avatar_bytes: bytes = None,
    is_premium: bool = False,
    is_bot: bool = False,
) -> io.BytesIO:
    img = Image.new("RGB", (SCREENSHOT_WIDTH, SCREENSHOT_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, SCREENSHOT_WIDTH, 50], fill=(20, 28, 37))
    draw.text((20, 15), "<", fill=ACCENT, font=_get_font(24, bold=True))
    draw.text((50, 15), "Профиль", fill=TEXT_COLOR, font=_get_font(20, bold=True))

    card_x1, card_y1 = 20, 70
    card_x2, card_y2 = SCREENSHOT_WIDTH - 20, SCREENSHOT_HEIGHT - 20
    draw.rounded_rectangle(
        [card_x1, card_y1, card_x2, card_y2], radius=15, fill=CARD_COLOR
    )

    avatar_x = card_x1 + 30
    avatar_y = card_y1 + 30
    avatar_img = None

    if avatar_bytes:
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGB")
            w, h = avatar_img.size
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            avatar_img = avatar_img.crop((left, top, left + side, top + side))
            avatar_img = avatar_img.resize((AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)
        except Exception:
            avatar_img = None

    if avatar_img is None:
        avatar_img = Image.new("RGB", (AVATAR_SIZE, AVATAR_SIZE), (60, 80, 100))
        d2 = ImageDraw.Draw(avatar_img)
        letter = (first_name or "?")[0].upper()
        font_big = _get_font(60, bold=True)
        bbox = d2.textbbox((0, 0), letter, font=font_big)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        d2.text(
            ((AVATAR_SIZE - tw) / 2 - bbox[0], (AVATAR_SIZE - th) / 2 - bbox[1]),
            letter, fill=TEXT_COLOR, font=font_big,
        )

    mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
    img.paste(avatar_img, (avatar_x, avatar_y), mask)

    text_x = avatar_x + AVATAR_SIZE + 25
    text_y = avatar_y + 10

    full_name = f"{first_name or ''} {last_name or ''}".strip() or "Без имени"
    if is_premium:
        full_name = "⭐ " + full_name

    draw.text((text_x, text_y), full_name, fill=TEXT_COLOR, font=_get_font(24, bold=True))

    if username:
        draw.text((text_x, text_y + 40), f"@{username}", fill=ACCENT, font=_get_font(18))
    else:
        draw.text((text_x, text_y + 40), "нет username", fill=SUB_COLOR, font=_get_font(16))

    draw.text((text_x, text_y + 70), f"ID: {user_id}", fill=SUB_COLOR, font=_get_font(16))

    if phone:
        draw.text((text_x, text_y + 95), f"📞 {phone}", fill=SUB_COLOR, font=_get_font(14))

    if is_bot:
        draw.text(
            (text_x, text_y + 95 if not phone else text_y + 120),
            "🤖 бот", fill=SUB_COLOR, font=_get_font(14),
        )

    draw.text(
        (card_x1 + 30, card_y2 - 40),
        "скриншот профиля · ueba bot",
        fill=SUB_COLOR, font=_get_font(12),
    )

    out = io.BytesIO()
    out.name = "screenshot.png"
    img.save(out, format="PNG", optimize=True)
    out.seek(0)
    return out


async def fetch_avatar_bytes(client, user) -> bytes:
    try:
        return await client.download_profile_photo(user, file=bytes)
    except Exception:
        return None


# ---------- Нормализация ----------
def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[a-zA-Z]", "", text)
    text = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]", "", text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------- Парсер КД ----------
def parse_cooldown(arg: str) -> float:
    if not arg:
        return 0.0
    try:
        v = float(arg.replace(",", "."))
    except Exception:
        return 0.0
    if v < 0:
        v = 0.0
    if v > 60:
        v = 60.0
    return v


# ---------- Упоминание юзера (HTML) ----------
def make_user_mention_html(user) -> str:
    """
    Возвращает HTML-строку-упоминание:
      • если есть username → @username (кликабельный сам по себе)
      • иначе → <a href="tg://user?id=ID">Имя</a>
    """
    username = getattr(user, "username", None)
    if username:
        return f"@{html.escape(username)}"

    uid = getattr(user, "id", None)
    name = getattr(user, "first_name", None) or "юзер"
    name_esc = html.escape(name)
    return f'<a href="tg://user?id={uid}">{name_esc}</a>'


# =========================================================
#                        SETUP
# =========================================================
def setup(client, ctx):
    from telethon import events
    from telethon.tl.types import User

    MY_ID = ctx["MY_ID"]
    PHRASES = ctx["PHRASES"]
    DEFAULT_PHRASES = ctx["DEFAULT_PHRASES"]

    def get_pool():
        return PHRASES if PHRASES else DEFAULT_PHRASES

    # =========================================================
    #         ФОНОВЫЕ СПАМ-ЗАДАЧИ
    # =========================================================
    async def spam_text_loop(chat_id, target, cooldown):
        """Спам: <юзер>, <фраза>"""
        mention = make_user_mention_html(target)

        while True:
            try:
                pool = get_pool()
                phrase = random.choice(pool)
                text = f"{mention}, {html.escape(phrase)}"
                await client.send_message(chat_id, text, parse_mode="html")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[ар спам] ошибка: {e}")
                await asyncio.sleep(1)
                continue

            try:
                if cooldown > 0:
                    await asyncio.sleep(cooldown)
                else:
                    await asyncio.sleep(0)
            except asyncio.CancelledError:
                break

    async def spam_screen_loop(chat_id, target, cooldown):
        """Спам: скрин + <юзер>, <фраза>"""
        avatar = await fetch_avatar_bytes(client, target)
        mention = make_user_mention_html(target)

        while True:
            try:
                pool = get_pool()
                phrase = random.choice(pool)
                caption = f"{mention}, {html.escape(phrase)}"

                buf = draw_profile_screenshot(
                    first_name=target.first_name or "",
                    last_name=target.last_name or "",
                    username=target.username or "",
                    user_id=target.id,
                    phone=getattr(target, "phone", None),
                    avatar_bytes=avatar,
                    is_premium=getattr(target, "premium", False),
                    is_bot=getattr(target, "bot", False),
                )
                await client.send_file(
                    chat_id, buf,
                    caption=caption,
                    parse_mode="html",
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[арс спам] ошибка: {e}")
                await asyncio.sleep(1)
                continue

            try:
                if cooldown > 0:
                    await asyncio.sleep(cooldown)
                else:
                    await asyncio.sleep(0)
            except asyncio.CancelledError:
                break

    # =========================================================
    #                 КОМАНДА .тарс
    # =========================================================
    @client.on(events.NewMessage(
        outgoing=True,
        pattern=r"^\.тарс(?:\s+([\d.,]+))?$"
    ))
    async def tars_cmd(event):
        try:
            await event.delete()
        except Exception:
            pass

        arg = event.pattern_match.group(1) or ""
        cooldown = parse_cooldown(arg)

        if not event.is_reply:
            if TAR_SCREEN_TARGETS:
                TAR_SCREEN_TARGETS.clear()
                msg = await client.send_message(event.chat_id, "я те мать убил")
                await asyncio.sleep(3)
                try:
                    await msg.delete()
                except Exception:
                    pass
            else:
                msg = await client.send_message(
                    event.chat_id,
                    "⚠️ Ответь `.тарс` на сообщение юзера\n"
                    "КД: `.тарс 0.1` — задержка 100мс"
                )
                await asyncio.sleep(5)
                try:
                    await msg.delete()
                except Exception:
                    pass
            return

        reply = await event.get_reply_message()
        try:
            target = await reply.get_sender()
        except Exception:
            return

        if target is None or not isinstance(target, User):
            msg = await client.send_message(event.chat_id, "❌ Это не пользователь")
            await asyncio.sleep(3)
            try:
                await msg.delete()
            except Exception:
                pass
            return

        if target.id == MY_ID:
            msg = await client.send_message(event.chat_id, "❌ Нельзя таргетить себя")
            await asyncio.sleep(3)
            try:
                await msg.delete()
            except Exception:
                pass
            return

        target_id = target.id

        if target_id in TAR_SCREEN_TARGETS:
            del TAR_SCREEN_TARGETS[target_id]
            msg = await client.send_message(event.chat_id, "я те мать убил")
        else:
            TAR_SCREEN_TARGETS[target_id] = {"cooldown": cooldown}
            c = f"\n_КД: {cooldown}с_" if cooldown else ""
            msg = await client.send_message(event.chat_id, f"я тебе мать ебал{c}")
        await asyncio.sleep(4)
        try:
            await msg.delete()
        except Exception:
            pass

    # =========================================================
    #                 КОМАНДА .арс
    # =========================================================
    @client.on(events.NewMessage(
        outgoing=True,
        pattern=r"^\.арс(?:\s+([\d.,]+))?$"
    ))
    async def ars_cmd(event):
        try:
            await event.delete()
        except Exception:
            pass

        arg = event.pattern_match.group(1) or ""
        cooldown = parse_cooldown(arg)

        if not event.is_reply:
            if AR_SCREEN_TARGETS:
                for tid, cfg in list(AR_SCREEN_TARGETS.items()):
                    task = cfg.get("task")
                    if task and not task.done():
                        task.cancel()
                AR_SCREEN_TARGETS.clear()
                msg = await client.send_message(event.chat_id, "я те мать убил")
                await asyncio.sleep(3)
                try:
                    await msg.delete()
                except Exception:
                    pass
            else:
                msg = await client.send_message(
                    event.chat_id,
                    "⚠️ Ответь `.арс` на сообщение юзера\n"
                    "_спам: скрин + `<юзер>, <фраза>`_\n"
                    "КД: `.арс 0.1` — 100мс"
                )
                await asyncio.sleep(5)
                try:
                    await msg.delete()
                except Exception:
                    pass
            return

        reply = await event.get_reply_message()
        try:
            target = await reply.get_sender()
        except Exception:
            return

        if target is None or not isinstance(target, User):
            msg = await client.send_message(event.chat_id, "❌ Это не пользователь")
            await asyncio.sleep(3)
            try:
                await msg.delete()
            except Exception:
                pass
            return

        if target.id == MY_ID:
            msg = await client.send_message(event.chat_id, "❌ Нельзя таргетить себя")
            await asyncio.sleep(3)
            try:
                await msg.delete()
            except Exception:
                pass
            return

        target_id = target.id
        chat_id = event.chat_id

        if target_id in AR_SCREEN_TARGETS:
            cfg = AR_SCREEN_TARGETS.pop(target_id)
            task = cfg.get("task")
            if task and not task.done():
                task.cancel()
            msg = await client.send_message(event.chat_id, "я те мать убил")
        else:
            task = asyncio.create_task(
                spam_screen_loop(chat_id, target, cooldown)
            )
            AR_SCREEN_TARGETS[target_id] = {
                "cooldown": cooldown,
                "task": task,
                "chat_id": chat_id,
            }
            c = f"\n_КД: {cooldown}с_" if cooldown else ""
            msg = await client.send_message(event.chat_id, f"я тебе мать ебал{c}")
        await asyncio.sleep(4)
        try:
            await msg.delete()
        except Exception:
            pass

    # =========================================================
    #                 КОМАНДА .ар
    # =========================================================
    @client.on(events.NewMessage(
        outgoing=True,
        pattern=r"^\.ар(?:\s+([\d.,]+))?$"
    ))
    async def ar_cmd(event):
        try:
            await event.delete()
        except Exception:
            pass

        arg = event.pattern_match.group(1) or ""
        cooldown = parse_cooldown(arg)

        if not event.is_reply:
            if AR_TEXT_TARGETS:
                for tid, cfg in list(AR_TEXT_TARGETS.items()):
                    task = cfg.get("task")
                    if task and not task.done():
                        task.cancel()
                AR_TEXT_TARGETS.clear()
                msg = await client.send_message(event.chat_id, "я те мать убил")
                await asyncio.sleep(3)
                try:
                    await msg.delete()
                except Exception:
                    pass
            else:
                msg = await client.send_message(
                    event.chat_id,
                    "⚠️ Ответь `.ар` на сообщение юзера\n"
                    "_спам: `<юзер>, <фраза>` без скрина_\n"
                    "КД: `.ар 0.1` — 100мс"
                )
                await asyncio.sleep(5)
                try:
                    await msg.delete()
                except Exception:
                    pass
            return

        reply = await event.get_reply_message()
        try:
            target = await reply.get_sender()
        except Exception:
            return

        if target is None or not isinstance(target, User):
            msg = await client.send_message(event.chat_id, "❌ Это не пользователь")
            await asyncio.sleep(3)
            try:
                await msg.delete()
            except Exception:
                pass
            return

        if target.id == MY_ID:
            msg = await client.send_message(event.chat_id, "❌ Нельзя таргетить себя")
            await asyncio.sleep(3)
            try:
                await msg.delete()
            except Exception:
                pass
            return

        target_id = target.id
        chat_id = event.chat_id

        if target_id in AR_TEXT_TARGETS:
            cfg = AR_TEXT_TARGETS.pop(target_id)
            task = cfg.get("task")
            if task and not task.done():
                task.cancel()
            msg = await client.send_message(event.chat_id, "я те мать убил")
        else:
            task = asyncio.create_task(
                spam_text_loop(chat_id, target, cooldown)
            )
            AR_TEXT_TARGETS[target_id] = {
                "cooldown": cooldown,
                "task": task,
                "chat_id": chat_id,
            }
            c = f"\n_КД: {cooldown}с_" if cooldown else ""
            msg = await client.send_message(event.chat_id, f"я тебе мать ебал{c}")
        await asyncio.sleep(4)
        try:
            await msg.delete()
        except Exception:
            pass

    # =========================================================
    #      .тарс — реакция на сообщения цели
    # =========================================================
    @client.on(events.NewMessage(incoming=True))
    async def on_target_msg(event):
        if not TAR_SCREEN_TARGETS:
            return

        try:
            sender = await event.get_sender()
        except Exception:
            return

        if sender is None or not isinstance(sender, User):
            return

        if sender.id not in TAR_SCREEN_TARGETS:
            return

        text = normalize_text(event.raw_text or "")
        if not text:
            return

        cfg = TAR_SCREEN_TARGETS[sender.id]
        cd = cfg.get("cooldown", 0)
        if cd:
            await asyncio.sleep(cd)

        pool = get_pool()
        phrase = random.choice(pool)

        try:
            avatar = await fetch_avatar_bytes(client, sender)
            buf = draw_profile_screenshot(
                first_name=sender.first_name or "",
                last_name=sender.last_name or "",
                username=sender.username or "",
                user_id=sender.id,
                phone=getattr(sender, "phone", None),
                avatar_bytes=avatar,
                is_premium=getattr(sender, "premium", False),
                is_bot=getattr(sender, "bot", False),
            )
            await client.send_file(
                event.chat_id, buf,
                caption=phrase,
                reply_to=event.id,
            )
        except Exception as e:
            print(f"[тарс] ошибка: {e}")