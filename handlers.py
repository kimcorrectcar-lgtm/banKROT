from datetime import datetime, timezone

from sqlalchemy import select

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from config import (
    COMPANY_NAME,
    MANAGER_PHONE,
    MANAGER_TELEGRAM,
    MANAGER_WHATSAPP,
)
from database import AsyncSessionLocal
from keyboards import (
    back_keyboard,
    cancel_keyboard,
    consent_keyboard,
    contact_keyboard,
    main_menu_keyboard,
)
from models import (
    Consent,
    ContactRequest,
    User,
)


router = Router()


class ContactStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()


async def get_or_create_user(
    message: Message,
) -> User:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id
                == message.from_user.id
            )
        )

        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=message.from_user.id,
                telegram_username=(
                    message.from_user.username
                ),
                telegram_first_name=(
                    message.from_user.first_name
                ),
                telegram_last_name=(
                    message.from_user.last_name
                ),
            )

            session.add(user)

            await session.commit()
            await session.refresh(user)

        else:
            user.telegram_username = (
                message.from_user.username
            )

            user.telegram_first_name = (
                message.from_user.first_name
            )

            user.telegram_last_name = (
                message.from_user.last_name
            )

            await session.commit()

        return user


async def user_has_consent(
    telegram_id: int,
) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.consent_given).where(
                User.telegram_id == telegram_id
            )
        )

        value = result.scalar_one_or_none()

        return bool(value)


async def save_consent(
    message: Message,
) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id
                == message.from_user.id
            )
        )

        user = result.scalar_one()

        user.consent_given = True
        user.consent_at = datetime.now(
            timezone.utc,
        )

        consent = Consent(
            user_id=user.id,
            document_type=(
                "personal_data_processing"
            ),
            document_version="1.0",
            accepted=True,
        )

        session.add(consent)

        await session.commit()


@router.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    user = await get_or_create_user(
        message,
    )

    if user.consent_given:
        await message.answer(
            "С возвращением в banKROT.\n\n"
            "Выберите нужный раздел:",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(
        f"Здравствуйте! Это {COMPANY_NAME}.\n\n"
        "Мы помогаем клиентам разобраться "
        "с вопросами, связанными с банкротством "
        "физических лиц и сопровождением "
        "соответствующих процедур.\n\n"
        "Перед началом работы ознакомьтесь "
        "с документами:\n\n"
        "📄 Политика конфиденциальности\n"
        "📄 Согласие на обработку "
        "персональных данных\n"
        "📄 Пользовательское соглашение\n\n"
        "⚠️ Текущие тексты документов являются "
        "техническими версиями и должны быть "
        "заменены на юридически проверенные "
        "документы перед публичным запуском.\n\n"
        "Для продолжения необходимо "
        "подтвердить согласие.",
        reply_markup=consent_keyboard(),
    )


@router.message(
    F.text == "❌ Отказаться",
)
async def decline_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "Вы отказались от продолжения работы "
        "с ботом.\n\n"
        "Персональные данные для дальнейшей "
        "работы бот запрашивать не будет.\n\n"
        "Если захотите продолжить, нажмите "
        "/start.",
    )


@router.message(
    F.text == "✅ Я прочитал и соглашаюсь",
)
async def consent_handler(
    message: Message,
) -> None:
    await save_consent(message)

    await message.answer(
        "Спасибо. Согласие зафиксировано.\n\n"
        "Теперь доступно главное меню banKROT.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(
    F.text == "🧮 Оценить мою ситуацию",
)
async def situation_handler(
    message: Message,
) -> None:
    if not await user_has_consent(
        message.from_user.id,
    ):
        await message.answer(
            "Сначала необходимо принять условия "
            "работы с ботом. Нажмите /start.",
        )
        return

    await message.answer(
        "🧮 Оценка ситуации\n\n"
        "Здесь будет пошаговая анкета "
        "предварительной оценки ситуации.\n\n"
        "Мы специально не будем запрашивать "
        "паспортные данные, СНИЛС, медицинские "
        "сведения и другие избыточные "
        "чувствительные данные.\n\n"
        "Следующим этапом добавим сюда вопросы "
        "о задолженности, просрочках, доходах, "
        "имуществе и другие сведения, необходимые "
        "именно для предварительной оценки.",
        reply_markup=back_keyboard(),
    )


@router.message(
    F.text == "📋 Моя заявка",
)
async def application_handler(
    message: Message,
) -> None:
    await message.answer(
        "📋 Моя заявка\n\n"
        "Пока у вас нет активной заявки.\n\n"
        "После прохождения предварительной "
        "анкеты здесь появится номер заявки "
        "и её текущий статус.",
        reply_markup=back_keyboard(),
    )


@router.message(
    F.text == "💼 Услуги",
)
async def services_handler(
    message: Message,
) -> None:
    await message.answer(
        "💼 Услуги\n\n"
        "В этом разделе появится каталог услуг:\n\n"
        "• Банкротство физических лиц\n"
        "• Консультация специалиста\n"
        "• Анализ ситуации\n"
        "• Подготовка документов\n"
        "• Сопровождение процедуры\n\n"
        "Каталог будет подключён следующим этапом.",
        reply_markup=back_keyboard(),
    )


@router.message(
    F.text == "📄 Документы",
)
async def documents_handler(
    message: Message,
) -> None:
    await message.answer(
        "📄 Документы\n\n"
        "1. Политика конфиденциальности\n"
        "2. Согласие на обработку "
        "персональных данных\n"
        "3. Пользовательское соглашение\n"
        "4. Другие необходимые документы\n\n"
        "Сейчас здесь установлены технические "
        "заглушки. После подготовки юридических "
        "документов мы подключим их реальные версии.",
        reply_markup=back_keyboard(),
    )


@router.message(
    F.text == "👤 Личный кабинет",
)
async def profile_handler(
    message: Message,
) -> None:
    await message.answer(
        "👤 Личный кабинет\n\n"
        "Здесь будут доступны:\n\n"
        "• данные профиля;\n"
        "• мои заявки;\n"
        "• статусы заявок;\n"
        "• мои документы;\n"
        "• настройки уведомлений;\n"
        "• удаление данных.\n\n"
        "Личный кабинет будем расширять "
        "по мере разработки проекта.",
        reply_markup=back_keyboard(),
    )


@router.message(
    F.text == "ℹ️ О нас",
)
async def about_handler(
    message: Message,
) -> None:
    await message.answer(
        "ℹ️ О нас\n\n"
        "Здесь будет информация о компании, "
        "специалистах, направлениях работы, "
        "реквизитах и контактах.\n\n"
        "Когда у нас будут реальные данные "
        "компании, мы вынесем их в отдельные "
        "настройки, чтобы их можно было менять "
        "без переписывания кода.",
        reply_markup=back_keyboard(),
    )


@router.message(
    F.text == "📞 Связаться с нами",
)
async def contact_handler(
    message: Message,
) -> None:
    await message.answer(
        "📞 Связаться с нами\n\n"
        "Выберите удобный способ:",
        reply_markup=contact_keyboard(),
    )


@router.message(
    F.text == "✍️ Оставить имя и телефон",
)
async def contact_start_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await state.set_state(
        ContactStates.waiting_for_name,
    )

    await message.answer(
        "Как к вам обращаться?",
        reply_markup=cancel_keyboard(),
    )


@router.message(
    ContactStates.waiting_for_name,
)
async def contact_name_handler(
    message: Message,
    state: FSMContext,
) -> None:
    if message.text == "❌ Отменить":
        await state.clear()

        await message.answer(
            "Обращение отменено.",
            reply_markup=main_menu_keyboard(),
        )
        return

    name = message.text.strip()

    if len(name) < 2:
        await message.answer(
            "Пожалуйста, укажите имя или как "
            "к вам удобно обращаться.",
        )
        return

    if len(name) > 255:
        await message.answer(
            "Имя получилось слишком длинным. "
            "Пожалуйста, укажите его короче.",
        )
        return

    await state.update_data(
        contact_name=name,
    )

    await state.set_state(
        ContactStates.waiting_for_phone,
    )

    await message.answer(
        "Теперь укажите номер телефона, "
        "по которому менеджер сможет "
        "с вами связаться.",
        reply_markup=cancel_keyboard(),
    )


@router.message(
    ContactStates.waiting_for_phone,
)
async def contact_phone_handler(
    message: Message,
    state: FSMContext,
) -> None:
    if message.text == "❌ Отменить":
        await state.clear()

        await message.answer(
            "Обращение отменено.",
            reply_markup=main_menu_keyboard(),
        )
        return

    phone = message.text.strip()

    if len(phone) < 7:
        await message.answer(
            "Похоже, номер слишком короткий. "
            "Пожалуйста, укажите номер ещё раз.",
        )
        return

    if len(phone) > 50:
        await message.answer(
            "Номер телефона выглядит "
            "некорректно. Пожалуйста, "
            "укажите его ещё раз.",
        )
        return

    data = await state.get_data()

    name = data.get(
        "contact_name",
        "Не указано",
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id
                == message.from_user.id
            )
        )

        user = result.scalar_one()

        request = ContactRequest(
            user_id=user.id,
            name=name,
            phone=phone,
            source="telegram_bot",
            status="new",
        )

        session.add(request)

        await session.commit()
        await session.refresh(request)

        request_id = request.id

    await state.clear()

    await message.answer(
        "✅ Спасибо!\n\n"
        f"Обращение №{request_id} создано.\n"
        "Менеджер свяжется с вами "
        "по указанному номеру.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(
    F.text == "📞 Позвонить нам",
)
async def call_handler(
    message: Message,
) -> None:
    await message.answer(
        "📞 Вы можете позвонить нам:\n\n"
        f"{MANAGER_PHONE}",
        reply_markup=contact_keyboard(),
    )


@router.message(
    F.text == "💬 Telegram",
)
async def telegram_handler(
    message: Message,
) -> None:
    await message.answer(
        "💬 Написать нам в Telegram:\n\n"
        f"{MANAGER_TELEGRAM}",
        reply_markup=contact_keyboard(),
    )


@router.message(
    F.text == "🟢 WhatsApp",
)
async def whatsapp_handler(
    message: Message,
) -> None:
    await message.answer(
        "🟢 Написать нам в WhatsApp:\n\n"
        f"{MANAGER_WHATSAPP}",
        reply_markup=contact_keyboard(),
    )


@router.message(
    F.text == "⬅️ Назад",
)
async def back_handler(
    message: Message,
) -> None:
    await message.answer(
        "Главное меню:",
        reply_markup=main_menu_keyboard(),
    )


@router.message(
    F.text == "🏠 Главное меню",
)
async def home_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "🏠 Главное меню",
        reply_markup=main_menu_keyboard(),
    )


@router.message()
async def unknown_handler(
    message: Message,
) -> None:
    await message.answer(
        "Пожалуйста, используйте кнопки меню.",
        reply_markup=main_menu_keyboard(),
    )
