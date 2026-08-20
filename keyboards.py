from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def consent_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="✅ Я прочитал и соглашаюсь",
                ),
            ],
            [
                KeyboardButton(
                    text="❌ Отказаться",
                ),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder=(
            "Выберите вариант"
        ),
    )


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🧮 Оценить мою ситуацию",
                ),
            ],
            [
                KeyboardButton(
                    text="📋 Моя заявка",
                ),
                KeyboardButton(
                    text="💼 Услуги",
                ),
            ],
            [
                KeyboardButton(
                    text="📄 Документы",
                ),
                KeyboardButton(
                    text="👤 Личный кабинет",
                ),
            ],
            [
                KeyboardButton(
                    text="ℹ️ О нас",
                ),
                KeyboardButton(
                    text="📞 Связаться с нами",
                ),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder=(
            "Выберите раздел"
        ),
    )


def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="✍️ Оставить имя и телефон",
                ),
            ],
            [
                KeyboardButton(
                    text="📞 Позвонить нам",
                ),
            ],
            [
                KeyboardButton(
                    text="💬 Telegram",
                ),
                KeyboardButton(
                    text="🟢 WhatsApp",
                ),
            ],
            [
                KeyboardButton(
                    text="⬅️ Назад",
                ),
            ],
        ],
        resize_keyboard=True,
    )


def back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="⬅️ Назад",
                ),
            ],
            [
                KeyboardButton(
                    text="🏠 Главное меню",
                ),
            ],
            [
                KeyboardButton(
                    text="📞 Связаться с нами",
                ),
            ],
        ],
        resize_keyboard=True,
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="❌ Отменить",
                ),
            ],
        ],
        resize_keyboard=True,
    )
