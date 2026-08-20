from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from keyboards import (
    contact_keyboard,
    consent_keyboard,
    main_keyboard,
)

router = Router()


WELCOME_TEXT = (
    "<b>Здравствуйте! Это banKROT.</b>\n\n"
    "Мы помогаем разобраться в вопросах банкротства "
    "физических лиц и сопровождаем клиентов "
    "на предусмотренных этапах процедуры.\n\n"
    "<b>Важно:</b> бот не запрашивает паспортные данные, "
    "сведения о здоровье и иные специальные категории "
    "персональных данных.\n\n"
    "Перед использованием необходимо ознакомиться "
    "с документами и подтвердить согласие."
)


CONSENT_TEXT = (
    "Для продолжения ознакомьтесь с документами "
    "и выберите один вариант:\n\n"
    "📄 Политика конфиденциальности\n"
    "📄 Согласие на обработку персональных данных\n"
    "📄 Пользовательские условия"
)


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        WELCOME_TEXT
    )

    await message.answer(
        CONSENT_TEXT,
        reply_markup=consent_keyboard(),
    )


@router.message(
    F.text == "✅ Я прочитал и соглашаюсь"
)
async def consent(message: Message) -> None:
    await message.answer(
        "Спасибо. Согласие зафиксировано "
        "для работы бота.\n\n"
        "Выберите нужный раздел:",
        reply_markup=main_keyboard(),
    )


@router.message(
    F.text == "❌ Отказаться"
)
async def decline(message: Message) -> None:
    await message.answer(
        "Вы отказались от продолжения работы "
        "с ботом.\n\n"
        "Если передумаете, используйте /start."
    )


@router.message(
    F.text == "📋 Услуги"
)
async def services(message: Message) -> None:
    await message.answer(
        "<b>📋 Услуги</b>\n\n"
        "• Первичная консультация\n"
        "• Предварительная оценка ситуации\n"
        "• Сопровождение процедуры банкротства\n"
        "• Консультация по документам\n\n"
        "Перечень и условия услуг будут дополнены "
        "после согласования с вашим специалистом."
    )


@router.message(
    F.text == "👤 Личный кабинет"
)
async def cabinet(message: Message) -> None:
    await message.answer(
        "<b>👤 Личный кабинет</b>\n\n"
        "Здесь будут доступны:\n"
        "• статус обращения;\n"
        "• история обращений;\n"
        "• документы;\n"
        "• запрос на удаление данных.\n\n"
        "Функциональность кабинета подключим "
        "следующим этапом."
    )


@router.message(
    F.text == "📄 Документы"
)
async def documents(message: Message) -> None:
    await message.answer(
        "<b>📄 Документы</b>\n\n"
        "Здесь будут размещены актуальные документы компании:\n"
        "• политика конфиденциальности;\n"
        "• согласие на обработку персональных данных;\n"
        "• пользовательские условия;\n"
        "• иные необходимые документы."
    )


@router.message(
    F.text == "ℹ️ О нас"
)
async def about(message: Message) -> None:
    await message.answer(
        "<b>ℹ️ О нас</b>\n\n"
        "Здесь будет информация о компании, "
        "специалистах, порядке работы "
        "и официальных контактах."
    )


@router.message(
    F.text == "📞 Связаться"
)
async def contact(message: Message) -> None:
    await message.answer(
        "<b>📞 Связаться с менеджером</b>\n\n"
        "Выберите удобный способ связи:",
        reply_markup=contact_keyboard(),
    )


@router.message(
    F.text == "☎️ Позвонить"
)
async def call(message: Message) -> None:
    await message.answer(
        "☎️ <b>Позвонить</b>\n\n"
        "На следующем этапе сюда добавим "
        "официальный номер компании."
    )


@router.message(
    F.text == "💬 Написать в мессенджере"
)
async def messenger(message: Message) -> None:
    await message.answer(
        "💬 <b>Написать в мессенджере</b>\n\n"
        "Здесь будут официальные ссылки компании "
        "на доступные мессенджеры."
    )


@router.message(
    F.text == "⬅️ Назад"
)
async def back(message: Message) -> None:
    await message.answer(
        "Главное меню:",
        reply_markup=main_keyboard(),
    )
