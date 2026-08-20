from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import delete, select

from config import (
    MANAGER_MAX_LEADS_CHAT_ID,
    MANAGER_PHONE,
    MANAGER_TELEGRAM,
    MANAGER_WHATSAPP,
)
from database import SessionLocal
from keyboards import (
    back_keyboard,
    cabinet_keyboard,
    contact_keyboard,
    consent_keyboard,
    documents_keyboard,
    main_keyboard,
    phone_keyboard,
    service_actions_keyboard,
    services_keyboard,
)
from models import Lead, User


router = Router()


SERVICES = {
    "⚖️ Банкротство физлица": (
        "Банкротство физического лица",
        "Помощь в подготовке и сопровождении процедуры банкротства гражданина. "
        "Конкретные условия и возможность применения процедуры определяются "
        "после консультации специалиста.",
    ),
    "💼 Банкротство ИП": (
        "Банкротство индивидуального предпринимателя",
        "Консультация по особенностям банкротства ИП "
        "и возможным вариантам дальнейших действий.",
    ),
    "💬 Консультация": (
        "Первичная консультация",
        "Обсудим вашу ситуацию, объясним общий порядок действий "
        "и подскажем, какие вопросы стоит подготовить для специалиста.",
    ),
    "🔎 Проверка ситуации": (
        "Предварительная оценка ситуации",
        "Поможем предварительно оценить ситуацию и определить, "
        "какой формат консультации вам подходит.",
    ),
    "📑 Консультация по документам": (
        "Консультация по документам",
        "Разберём, какие документы могут понадобиться "
        "для дальнейшей работы. Бот не запрашивает паспортные "
        "и медицинские данные.",
    ),
}


class LeadForm(StatesGroup):
    service = State()
    name = State()
    phone = State()


class DeleteForm(StatesGroup):
    confirm = State()


WELCOME_TEXT = (
    "<b>Здравствуйте! Это banKROT.</b>\n\n"
    "Помогаем разобраться в вопросах банкротства "
    "и получить консультацию специалиста.\n\n"
    "Бот не запрашивает паспортные данные, сведения "
    "о здоровье и другие специальные категории "
    "персональных данных."
)


CONSENT_TEXT = (
    "<b>Перед началом работы</b>\n\n"
    "Ознакомьтесь с документами, размещёнными "
    "в разделе «Документы», и выберите вариант ниже.\n\n"
    "Для продолжения необходимо подтвердить согласие."
)


async def save_user(
    message: Message,
    consented: bool = False,
) -> None:
    if SessionLocal is None:
        return

    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id == message.from_user.id
            )
        )

        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
            )

            session.add(user)

        else:
            user.username = message.from_user.username
            user.first_name = message.from_user.first_name

        if consented:
            user.consented_at = datetime.now(timezone.utc)

        await session.commit()


async def user_consented(
    telegram_id: int,
) -> bool:
    if SessionLocal is None:
        return False

    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id == telegram_id
            )
        )

        user = result.scalar_one_or_none()

        return bool(
            user and user.consented_at
        )


async def create_lead(
    telegram_id: int,
    name: str,
    phone: str,
    service: str | None,
) -> Lead | None:
    if SessionLocal is None:
        return None

    async with SessionLocal() as session:
        lead = Lead(
            telegram_id=telegram_id,
            name=name.strip(),
            phone=phone.strip(),
            service=service,
        )

        session.add(lead)

        await session.commit()
        await session.refresh(lead)

        return lead


async def get_user_leads(
    telegram_id: int,
) -> list[Lead]:
    if SessionLocal is None:
        return []

    async with SessionLocal() as session:
        result = await session.execute(
            select(Lead)
            .where(Lead.telegram_id == telegram_id)
            .order_by(Lead.created_at.desc())
        )

        return list(
            result.scalars().all()
        )


async def delete_user_data(
    telegram_id: int,
) -> None:
    if SessionLocal is None:
        return

    async with SessionLocal() as session:
        await session.execute(
            delete(Lead).where(
                Lead.telegram_id == telegram_id
            )
        )

        await session.execute(
            delete(User).where(
                User.telegram_id == telegram_id
            )
        )

        await session.commit()


async def notify_manager(
    message: Message,
    lead: Lead,
) -> None:
    if not MANAGER_MAX_LEADS_CHAT_ID:
        return

    try:
        chat_id = int(
            MANAGER_MAX_LEADS_CHAT_ID
        )
    except ValueError:
        return

    service = lead.service or "Не выбрана"

    text = (
        "<b>🆕 Новая заявка banKROT</b>\n\n"
        f"Заявка №{lead.id}\n"
        f"Услуга: {service}\n"
        f"Имя: {lead.name}\n"
        f"Телефон: {lead.phone}\n"
        f"Telegram ID: {lead.telegram_id}\n"
        f"Статус: {lead.status}"
    )

    await message.bot.send_message(
        chat_id,
        text,
    )


async def start_lead(
    message: Message,
    state: FSMContext,
    service: str | None = None,
) -> None:
    await state.clear()

    await state.update_data(
        service=service
    )

    await state.set_state(
        LeadForm.name
    )

    service_text = (
        f" по услуге «{service}»"
        if service
        else ""
    )

    await message.answer(
        f"<b>📝 Оставить заявку{service_text}</b>\n\n"
        "Напишите ваше имя. Паспортные данные "
        "и другие специальные сведения не нужны.",
        reply_markup=back_keyboard(),
    )


@router.message(CommandStart())
async def start(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await save_user(message)

    if await user_consented(
        message.from_user.id
    ):
        await message.answer(
            "С возвращением в <b>banKROT</b>.\n\n"
            "Выберите нужный раздел:",
            reply_markup=main_keyboard(),
        )

        return

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
async def consent(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await save_user(
        message,
        consented=True,
    )

    await message.answer(
        "Спасибо. Согласие зафиксировано.\n\n"
        "<b>Главное меню:</b>",
        reply_markup=main_keyboard(),
    )


@router.message(
    F.text == "❌ Отказаться"
)
async def decline(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "Вы отказались от продолжения работы "
        "с ботом.\n\n"
        "Для повторного входа используйте /start.",
        reply_markup=consent_keyboard(),
    )


@router.message(
    F.text == "📋 Услуги"
)
async def services(
    message: Message,
) -> None:
    await message.answer(
        "<b>📋 Услуги</b>\n\n"
        "Выберите услугу:",
        reply_markup=services_keyboard(),
    )


@router.message(
    F.text.in_(list(SERVICES.keys()))
)
async def service_detail(
    message: Message,
    state: FSMContext,
) -> None:
    title, description = SERVICES[
        message.text
    ]

    await state.update_data(
        service=title
    )

    await message.answer(
        f"<b>{title}</b>\n\n"
        f"{description}\n\n"
        "Если хотите обсудить ситуацию "
        "с менеджером, выберите удобный вариант ниже.",
        reply_markup=service_actions_keyboard(),
    )


@router.message(
    F.text == "📝 Оставить заявку"
)
async def new_lead(
    message: Message,
    state: FSMContext,
) -> None:
    if not await user_consented(
        message.from_user.id
    ):
        await message.answer(
            CONSENT_TEXT,
            reply_markup=consent_keyboard(),
        )

        return

    data = await state.get_data()

    await start_lead(
        message,
        state,
        data.get("service"),
    )


@router.message(
    F.text == "◀️ К услугам"
)
async def back_services(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "<b>📋 Услуги</b>\n\n"
        "Выберите услугу:",
        reply_markup=services_keyboard(),
    )


@router.message(
    F.text == "📞 Связаться с менеджером"
)
async def manager_contact(
    message: Message,
) -> None:
    await message.answer(
        "<b>📞 Связаться с менеджером</b>\n\n"
        "Выберите удобный способ:",
        reply_markup=contact_keyboard(),
    )


@router.message(
    F.text == "📱 Отправить мой номер"
)
async def request_phone(
    message: Message,
    state: FSMContext,
) -> None:
    if not await user_consented(
        message.from_user.id
    ):
        await message.answer(
            CONSENT_TEXT,
            reply_markup=consent_keyboard(),
        )

        return

    data = await state.get_data()

    await state.update_data(
        service=data.get("service")
    )

    await state.set_state(
        LeadForm.name
    )

    await message.answer(
        "Введите ваше имя:",
        reply_markup=back_keyboard(),
    )


@router.message(F.contact)
async def received_contact(
    message: Message,
    state: FSMContext,
) -> None:
    if not await user_consented(
        message.from_user.id
    ):
        await message.answer(
            CONSENT_TEXT,
            reply_markup=consent_keyboard(),
        )

        return

    data = await state.get_data()

    name = (
        data.get("name")
        or message.from_user.first_name
        or "Пользователь"
    )

    service = data.get("service")

    lead = await create_lead(
        message.from_user.id,
        name,
        message.contact.phone_number,
        service,
    )

    await state.clear()

    if lead:
        await notify_manager(
            message,
            lead,
        )

        await message.answer(
            f"<b>Заявка №{lead.id} создана.</b>\n\n"
            "Менеджер свяжется с вами "
            "по указанному номеру.",
            reply_markup=main_keyboard(),
        )

    else:
        await message.answer(
            "Не удалось сохранить заявку. "
            "Попробуйте ещё раз позже.",
            reply_markup=main_keyboard(),
        )


@router.message(
    LeadForm.name
)
async def lead_name(
    message: Message,
    state: FSMContext,
) -> None:
    if (
        message.text
        and message.text.startswith("◀️")
    ):
        await state.clear()

        await message.answer(
            "Главное меню:",
            reply_markup=main_keyboard(),
        )

        return

    name = (
        message.text or ""
    ).strip()

    if len(name) < 2 or len(name) > 100:
        await message.answer(
            "Пожалуйста, укажите имя текстом "
            "(от 2 до 100 символов)."
        )

        return

    await state.update_data(
        name=name
    )

    await state.set_state(
        LeadForm.phone
    )

    await message.answer(
        "Теперь отправьте номер телефона "
        "кнопкой «📱 Отправить мой номер» "
        "или введите его текстом.",
        reply_markup=phone_keyboard(),
    )


@router.message(
    LeadForm.phone
)
async def lead_phone(
    message: Message,
    state: FSMContext,
) -> None:
    if message.text == "◀️ Отмена":
        await state.clear()

        await message.answer(
            "Заявка отменена.",
            reply_markup=main_keyboard(),
        )

        return

    phone = (
        message.text or ""
    ).strip()

    if len(phone) < 6 or len(phone) > 30:
        await message.answer(
            "Похоже, номер указан некорректно. "
            "Попробуйте ещё раз."
        )

        return

    data = await state.get_data()

    lead = await create_lead(
        message.from_user.id,
        data.get(
            "name",
            "Пользователь",
        ),
        phone,
        data.get("service"),
    )

    await state.clear()

    if lead:
        await notify_manager(
            message,
            lead,
        )

        await message.answer(
            f"<b>Заявка №{lead.id} создана.</b>\n\n"
            "Менеджер свяжется с вами.",
            reply_markup=main_keyboard(),
        )

    else:
        await message.answer(
            "Не удалось сохранить заявку. "
            "Попробуйте позже.",
            reply_markup=main_keyboard(),
        )


@router.message(
    F.text == "👤 Личный кабинет"
)
async def cabinet(
    message: Message,
) -> None:
    if not await user_consented(
        message.from_user.id
    ):
        await message.answer(
            CONSENT_TEXT,
            reply_markup=consent_keyboard(),
        )

        return

    await message.answer(
        "<b>👤 Личный кабинет</b>\n\n"
        "Здесь можно посмотреть заявки "
        "и их статус, а также удалить "
        "сохранённые данные.",
        reply_markup=cabinet_keyboard(),
    )


@router.message(
    F.text == "📌 Статус заявки"
)
async def lead_status(
    message: Message,
) -> None:
    leads = await get_user_leads(
        message.from_user.id
    )

    if not leads:
        await message.answer(
            "У вас пока нет заявок.",
            reply_markup=cabinet_keyboard(),
        )

        return

    lead = leads[0]

    await message.answer(
        f"<b>📌 Последняя заявка №{lead.id}</b>\n\n"
        f"Услуга: {lead.service or 'Не указана'}\n"
        f"Статус: <b>{lead.status}</b>",
        reply_markup=cabinet_keyboard(),
    )


@router.message(
    F.text == "🗂 Мои заявки"
)
async def my_leads(
    message: Message,
) -> None:
    leads = await get_user_leads(
        message.from_user.id
    )

    if not leads:
        await message.answer(
            "У вас пока нет заявок.",
            reply_markup=cabinet_keyboard(),
        )

        return

    lines = [
        "<b>🗂 Мои заявки</b>"
    ]

    for lead in leads[:10]:
        lines.append(
            f"№{lead.id} — "
            f"{lead.service or 'Обращение'} — "
            f"<b>{lead.status}</b>"
        )

    await message.answer(
        "\n".join(lines),
        reply_markup=cabinet_keyboard(),
    )


def delete_confirmation_keyboard():
    from keyboards import kb

    return kb(
        [
            ["🗑 Да, удалить"],
            ["◀️ Отмена"],
        ]
    )


@router.message(
    F.text == "🗑 Удалить мои данные"
)
async def delete_data_start(
    message: Message,
    state: FSMContext,
) -> None:
    await state.set_state(
        DeleteForm.confirm
    )

    await message.answer(
        "<b>Удаление данных</b>\n\n"
        "Будут удалены сохранённые данные "
        "пользователя и заявки из базы бота.\n\n"
        "Подтвердить удаление?",
        reply_markup=delete_confirmation_keyboard(),
    )


@router.message(
    DeleteForm.confirm,
    F.text == "🗑 Да, удалить",
)
async def delete_data_confirm(
    message: Message,
    state: FSMContext,
) -> None:
    await delete_user_data(
        message.from_user.id
    )

    await state.clear()

    await message.answer(
        "Сохранённые данные и заявки удалены "
        "из базы бота.\n\n"
        "Для дальнейшей работы потребуется "
        "снова ознакомиться с документами "
        "и дать согласие.",
        reply_markup=consent_keyboard(),
    )


@router.message(
    DeleteForm.confirm,
    F.text == "◀️ Отмена",
)
async def delete_data_cancel(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "Удаление отменено.",
        reply_markup=cabinet_keyboard(),
    )


@router.message(
    F.text == "📄 Документы"
)
async def documents(
    message: Message,
) -> None:
    await message.answer(
        "<b>📄 Документы</b>\n\n"
        "Здесь размещаются актуальные документы компании.",
        reply_markup=documents_keyboard(),
    )


@router.message(
    F.text == "📄 Политика конфиденциальности"
)
async def privacy(
    message: Message,
) -> None:
    await message.answer(
        "<b>📄 Политика конфиденциальности</b>\n\n"
        "В этот раздел будет внесён утверждённый "
        "текст политики конфиденциальности компании.\n\n"
        "До публикации юридически согласованного "
        "текста бот не выдаёт этот черновик "
        "за официальный документ.",
        reply_markup=documents_keyboard(),
    )


@router.message(
    F.text == "📄 Согласие на обработку ПД"
)
async def pd_consent(
    message: Message,
) -> None:
    await message.answer(
        "<b>📄 Согласие на обработку "
        "персональных данных</b>\n\n"
        "В этот раздел будет внесён утверждённый "
        "компанией текст согласия.\n\n"
        "Бот проектируется с минимизацией "
        "собираемых данных и не запрашивает "
        "паспортные или медицинские сведения.",
        reply_markup=documents_keyboard(),
    )


@router.message(
    F.text == "📄 Пользовательские условия"
)
async def terms(
    message: Message,
) -> None:
    await message.answer(
        "<b>📄 Пользовательские условия</b>\n\n"
        "Здесь будет опубликована утверждённая "
        "редакция пользовательских условий сервиса.",
        reply_markup=documents_keyboard(),
    )


@router.message(
    F.text == "ℹ️ О нас"
)
async def about(
    message: Message,
) -> None:
    await message.answer(
        "<b>ℹ️ О нас</b>\n\n"
        "Здесь размещается информация о компании, "
        "специалистах, порядке работы "
        "и официальных контактах.",
        reply_markup=main_keyboard(),
    )


@router.message(
    F.text == "📞 Связаться"
)
async def contact(
    message: Message,
) -> None:
    await message.answer(
        "<b>📞 Связаться с менеджером</b>\n\n"
        "Выберите удобный способ связи:",
        reply_markup=contact_keyboard(),
    )


@router.message(
    F.text == "☎️ Позвонить"
)
async def call(
    message: Message,
) -> None:
    await message.answer(
        f"<b>☎️ Позвонить</b>\n\n"
        f"Официальный номер: {MANAGER_PHONE}",
        reply_markup=contact_keyboard(),
    )


@router.message(
    F.text == "💬 Написать в мессенджере"
)
async def messenger(
    message: Message,
) -> None:
    lines = [
        "<b>💬 Написать в мессенджере</b>"
    ]

    if MANAGER_TELEGRAM:
        lines.append(
            f"Telegram: {MANAGER_TELEGRAM}"
        )

    if MANAGER_WHATSAPP:
        lines.append(
            f"WhatsApp: {MANAGER_WHATSAPP}"
        )

    if len(lines) == 1:
        lines.append(
            "Ссылки на официальные мессенджеры "
            "пока не настроены."
        )

    await message.answer(
        "\n\n".join(lines),
        reply_markup=contact_keyboard(),
    )


@router.message(
    F.text == "◀️ В главное меню"
)
async def main_menu(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "<b>Главное меню</b>",
        reply_markup=main_keyboard(),
    )


@router.message(
    F.text == "⬅️ Назад"
)
async def old_back(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "<b>Главное меню</b>",
        reply_markup=main_keyboard(),
    )
