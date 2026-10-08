# 🤖 UEBA BOT

Юзербот для Telegram с модулями и троллинг-режимами.

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://python.org)
[![Telethon](https://img.shields.io/badge/Telethon-1.36%2B-blue)](https://github.com/LonamiWebs/Telethon)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## ✨ Возможности

- 📥 Загрузка фраз из `.txt` файла
- 🎯 Троллинг с фразами и скринами профиля
- ⌨️ Режим "печатает..." в чате
- 🧩 Система модулей (свои команды)
- 📊 Статистика по фразам
- 💾 Сохранение сессий (вход один раз)

---

## 📱 Установка на Termux (Android)

### 1. Скачай Termux

**Только из F-Droid**: https://f-droid.org/packages/com.termux/  
⚠️ Из Google Play — старая версия, ничего не работает.

### 2. Установи бота одной командой

Открой Termux и введи:

```bash
bash <(curl -sL https://raw.githubusercontent.com/PaniHida008/ueba-bot/main/install.sh)
```

### 3. Первый запуск

Бот спросит:
- **API_ID** — число
- **API_HASH** — строка
- **Номер телефона** — `+79991234567`
- **Код** — придёт в Telegram

Всё — бот запущен. Открой **Избранное** и напиши `.help`.

---

## 💻 Установка на ПК (Windows / Mac / Linux)

```bash
git clone https://github.com/PaniHida008/ueba-bot.git
cd ueba-bot
pip install -r requirements.txt
python main.py
```

---

## 🔑 Где взять API_ID и API_HASH

1. Зайди на https://my.telegram.org/apps
2. Войди по своему номеру
3. **API development tools** → создай приложение
4. Скопируй `api_id` и `api_hash`

---

## ⚙️ Команды

| Команда | Что делает |
|---|---|
| `.help` | список всех команд |
| `.my` | загрузить фразы из `.txt` (реплай на файл) |
| `.тарс [кд]` | ответ на сообщения цели: скрин + фраза |
| `.арс [кд]` | спам: скрин + `<юзер>, <фраза>` |
| `.ар [кд]` | спам: `<юзер>, <фраза>` без скрина |
| `.ar` | статистика по фразам |
| `.m` | список модулей |
| `.ms <номер>` | инфо о модуле |
| `.md <номер>` | удалить модуль |
| `.py` | установить модуль (реплай на `.py`) |

**Кулдаун**: `.ар 0.1` — задержка 100 мс между сообщениями.

---

## 🧩 Как создать свой модуль

Создай файл `modules/my_module.py`:

```python
from telethon import events

HELP = "короткое описание модуля"
COMMANDS = [".м-my_module"]

def setup(client, ctx):
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.м-my_module$"))
    async def cmd(event):
        await event.delete()
        await client.send_message(event.chat_id, "привет из модуля!")
```

Закинь файл в Telegram → ответь `.py` на файл → команда `.м-my_module` работает.

---

## 📁 Структура

```
ueba-bot/
├── main.py              # ядро бота
├── requirements.txt     # зависимости
├── install.sh           # установщик
├── modules/             # плагины
│   └── скрин.py
├── sessions/            # сессии (создаётся автоматически)
└── phrases/             # фразы (создаётся автоматически)
```

---

## ⚠️ Дисклеймер

Юзербот — **нарушение ToS Telegram**. Использование может привести к **бану аккаунта**.  
Используй на свой страх и риск, желательно на отдельном аккаунте.

Автор не несёт ответственности за последствия.

---

## 📜 Лицензия

MIT — делай что хочешь, только не жалуйся.
