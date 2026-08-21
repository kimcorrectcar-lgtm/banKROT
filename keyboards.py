from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def kb(rows: list[list[str]], *, contact_button: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text=item) for item in row] for row in rows]
    if contact_button:
        keyboard.insert(0, [KeyboardButton(text="📱 Отправить мой номер", request_contact=True)])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, is_persistent=True)


def consent_keyboard():
    return kb([["📄 Документы"], ["✅ Я прочитал и соглашаюсь"], ["❌ Отказаться"]])


def main_keyboard(role: str | None = None):
    rows = [
        ["📋 Услуги", "📝 Оставить заявку"],
        ["👤 Личный кабинет", "📄 Документы"],
        ["ℹ️ О нас", "📞 Связаться"],
    ]
    if role == "admin":
        rows.append(["🔐 Администратор"])
    return kb(rows)


def services_keyboard():
    return kb([
        ["⚖️ Банкротство физлица"],
        ["💼 Банкротство ИП"],
        ["💬 Консультация"],
        ["🔎 Проверка ситуации"],
        ["📑 Консультация по документам"],
        ["📝 Оставить заявку"],
        ["📞 Связаться с менеджером"],
        ["◀️ В главное меню"],
    ])


def service_actions_keyboard():
    return kb([
        ["📝 Оставить заявку"],
        ["📞 Связаться с менеджером"],
        ["☎️ Позвонить"],
        ["💬 Написать в мессенджере"],
        ["◀️ К услугам"],
    ])


def cabinet_keyboard():
    return kb([
        ["📌 Статус заявки"],
        ["🗂 Мои заявки"],
        ["🗑 Удалить мои данные"],
        ["📞 Связаться с менеджером"],
        ["◀️ В главное меню"],
    ])


def documents_keyboard():
    return kb([
        ["📄 Политика конфиденциальности"],
        ["📄 Согласие на обработку ПД"],
        ["📄 Пользовательские условия"],
        ["◀️ В главное меню"],
    ])


def contact_keyboard():
    return kb([
        ["📱 Оставить имя и номер"],
        ["☎️ Позвонить"],
        ["💬 Написать в мессенджере"],
        ["📝 Оставить заявку"],
        ["◀️ В главное меню"],
    ])


def phone_keyboard():
    return kb([["◀️ Отмена"]], contact_button=True)


def back_keyboard():
    return kb([["◀️ В главное меню"]])


def admin_keyboard():
    return kb([
        ["👥 Тестировщики", "📋 Заявки"],
        ["📊 Статистика", "🛡 Журнал безопасности"],
        ["🗑 Удалить данные пользователя"],
        ["◀️ В главное меню"],
    ])


def admin_testers_keyboard():
    return kb([["➕ Добавить тестировщика"], ["➖ Удалить тестировщика"], ["🔙 В админ-меню"]])


def admin_leads_keyboard():
    return kb([["🔎 Заявка по ID"], ["✏️ Изменить статус"], ["🔙 В админ-меню"]])


def admin_status_keyboard():
    return kb([
        ["🆕 Новая"], ["📞 Связались"], ["🟡 В работе"],
        ["🟢 Завершена"], ["🔴 Отменена"], ["🔙 В админ-меню"],
    ])


def delete_confirmation_keyboard():
    return kb([["🗑 Да, удалить"], ["◀️ Отмена"]])
