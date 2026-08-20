from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def consent_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="✅ Я прочитал и соглашаюсь"
                )
            ],
            [
                KeyboardButton(
                    text="❌ Отказаться"
                )
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📋 Услуги"
                ),
                KeyboardButton(
                    text="👤 Личный кабинет"
                ),
            ],
            [
                KeyboardButton(
                    text="📄 Документы"
                ),
                KeyboardButton(
                    text="ℹ️ О нас"
                ),
            ],
            [
                KeyboardButton(
                    text="📞 Связаться"
                ),
                KeyboardButton(
                    text="☎️ Позвонить"
                ),
            ],
        ],
        resize_keyboard=True,
    )


def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Оставить имя и номер"
                )
            ],
            [
                KeyboardButton(
                    text="💬 Написать в мессенджере"
                )
            ],
            [
                KeyboardButton(
                    text="☎️ Позвонить"
                )
            ],
            [
                KeyboardButton(
                    text="⬅️ Назад"
                )
            ],
        ],
        resize_keyboard=True,
    )
