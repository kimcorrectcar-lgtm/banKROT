from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def kb(
    rows: list[list[str]],
    *,
    contact_button: bool = False,
) -> ReplyKeyboardMarkup:
    keyboard: list[list[KeyboardButton]] = []

    for row in rows:
        buttons = [
            KeyboardButton(text=text)
            for text in row
        ]

        keyboard.append(buttons)

    if contact_button:
        keyboard = [
            [
                KeyboardButton(
                    text="📱 Отправить мой номер",
                    request_contact=True,
                )
            ]
        ] + keyboard

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
    )


def consent_keyboard() -> ReplyKeyboardMarkup:
    return kb(
        [
            ["✅ Я прочитал и соглашаюсь"],
            ["❌ Отказаться"],
        ]
    )


def main_keyboard() -> ReplyKeyboardMarkup:
    return kb(
        [
            ["📋 Услуги", "📝 Оставить заявку"],
            ["👤 Личный кабинет", "📄 Документы"],
            ["ℹ️ О нас", "📞 Связаться"],
        ]
    )


def services_keyboard() -> ReplyKeyboardMarkup:
    return kb(
        [
            ["⚖️ Банкротство физлица"],
            ["💼 Банкротство ИП"],
            ["💬 Консультация"],
            ["🔎 Проверка ситуации"],
            ["📑 Консультация по документам"],
            ["📝 Оставить заявку"],
            ["📞 Связаться с менеджером"],
            ["◀️ В главное меню"],
        ]
    )


def service_actions_keyboard() -> ReplyKeyboardMarkup:
    return kb(
        [
            ["📝 Оставить заявку"],
            ["📞 Связаться с менеджером"],
            ["☎️ Позвонить"],
            ["💬 Написать в мессенджере"],
            ["◀️ К услугам"],
        ]
    )


def cabinet_keyboard() -> ReplyKeyboardMarkup:
    return kb(
        [
            ["📌 Статус заявки"],
            ["🗂 Мои заявки"],
            ["🗑 Удалить мои данные"],
            ["📞 Связаться с менеджером"],
            ["◀️ В главное меню"],
        ]
    )


def documents_keyboard() -> ReplyKeyboardMarkup:
    return kb(
        [
            ["📄 Политика конфиденциальности"],
            ["📄 Согласие на обработку ПД"],
            ["📄 Пользовательские условия"],
            ["◀️ В главное меню"],
        ]
    )


def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Отправить мой номер",
                    request_contact=True,
                )
            ],
            [
                KeyboardButton(text="☎️ Позвонить")
            ],
            [
                KeyboardButton(
                    text="💬 Написать в мессенджере"
                )
            ],
            [
                KeyboardButton(
                    text="📝 Оставить заявку"
                )
            ],
            [
                KeyboardButton(
                    text="◀️ В главное меню"
                )
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    return kb(
        [
            ["◀️ Отмена"],
        ],
        contact_button=True,
    )


def back_keyboard() -> ReplyKeyboardMarkup:
    return kb(
        [
            ["◀️ В главное меню"],
        ]
    )
