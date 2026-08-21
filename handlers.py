import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import delete, select

from config import (
    ENV_TESTER_IDS,
    MANAGER_LEADS_CHAT_ID,
    MANAGER_PHONE,
    MANAGER_TELEGRAM,
    MANAGER_WHATSAPP,
)
from database import SessionLocal
from keyboards import (
    back_keyboard,
    cabinet_keyboard,
    consent_keyboard,
    contact_keyboard,
    delete_confirmation_keyboard,
    documents_keyboard,
    main_keyboard,
    phone_keyboard,
    profile_actions_keyboard,
    service_actions_keyboard,
    services_keyboard,
)
from models import Lead, SecurityAudit, Tester, User
from security import (
    audit_actor_ref,
    clean_name,
    decrypt,
    encrypt,
    normalize_phone,
    role_for,
)
from texts import CONSENT_TEXT, SERVICES, WELCOME_TEXT

logger = logging.getLogger(__name__)
router = Router()


class LeadForm(StatesGroup):
    name = State()
    phone = State()


class ContactForm(StatesGroup):
    name = State()
    phone = State()


class DeleteForm(StatesGroup):
    confirm = State()


def is_back(text: str | None) -> bool:
    return text in {"◀️ В главное меню", "◀️ Отмена"}


async def tester_ids() -> set[int]:
    ids = set(ENV_TESTER_IDS)

    async with SessionLocal() as session:
        result = await session.execute(select(Tester.telegram_id))
        ids.update(result.scalars().all())

    return ids


async def get_role(tid: int) -> str | None:
    return role_for(tid, await tester_ids())


async def ensure_access(message: Message) -> str | None:
    role = await get_role(message.from_user.id)

    if role is None:
        await message.answer("🔒 Бот находится в закрытом режиме разработки.")

    return role


async def save_user(
    message: Message,
    *,
    name: str | None = None,
    phone: str | None = None,
) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=message.from_user.id,
                consented_at=datetime.now(timezone.utc),
            )
            session.add(user)
        else:
            user.consented_at = (
                user.consented_at or datetime.now(timezone.utc)
            )

        if name:
            user.name = encrypt(name)

        if phone:
            user.phone = encrypt(phone)

        await session.commit()


async def get_user_profile(tid: int) -> tuple[str | None, str | None]:
    """
    Return saved name/phone.

    For old installations, recover missing profile values from the latest
    lead and migrate them into User.
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == tid)
        )
        user = result.scalar_one_or_none()

        name = decrypt(user.name) if user and user.name else None
        phone = decrypt(user.phone) if user and user.phone else None

        if name and phone:
            return name, phone

        lead_result = await session.execute(
            select(Lead)
            .where(Lead.telegram_id == tid)
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
        lead = lead_result.scalar_one_or_none()

        if lead:
            try:
                name = name or decrypt(lead.name)
                phone = phone or decrypt(lead.phone)
            except Exception:
                logger.exception(
                    "Could not recover old encrypted profile for telegram_id=%s",
                    tid,
                )

        if user and (name or phone):
            if name:
                user.name = encrypt(name)
            if phone:
                user.phone = encrypt(phone)
            await session.commit()

        return name, phone


async def user_consented(tid: int) -> bool:
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == tid)
        )
        user = result.scalar_one_or_none()

        return bool(user and user.consented_at)


async def audit(
    actor_id: int,
    role: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
) -> None:
    async with SessionLocal() as session:
        session.add(
            SecurityAudit(
                actor_telegram_id=int(
                    audit_actor_ref(actor_id)[:15],
                    16,
                ),
                actor_role=role,
                action=action,
                target_type=target_type,
                target_id=target_id,
            )
        )
        await session.commit()


async def create_lead(
    tid: int,
    name: str,
    phone: str,
    service: str | None,
) -> Lead:
    async with SessionLocal() as session:
        lead = Lead(
            telegram_id=tid,
            name=encrypt(name),
            phone=encrypt(phone),
            service=service,
        )
        session.add(lead)
        await session.flush()

        result = await session.execute(
            select(User).where(User.telegram_id == tid)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=tid,
                consented_at=datetime.now(timezone.utc),
            )
            session.add(user)

        user.name = encrypt(name)
        user.phone = encrypt(phone)

        await session.commit()
        await session.refresh(lead)

        return lead


async def notify_manager(message: Message, lead: Lead) -> None:
    """
    Notification failure must never roll back a successfully saved lead.
    """
    if not MANAGER_LEADS_CHAT_ID:
        logger.warning(
            "MANAGER_LEADS_CHAT_ID is not configured; lead #%s was saved",
            lead.id,
        )
        return

    try:
        chat_id = int(MANAGER_LEADS_CHAT_ID)

        await message.bot.send_message(
            chat_id,
            "<b>🆕 Новая заявка banKROT</b>\n\n"
            f"Заявка №{lead.id}\n"
            f"Услуга: {lead.service or 'Не выбрана'}\n"
            "Контактные данные доступны только авторизованному "
            "администратору в панели бота.\n"
            f"Статус: {lead.status}",
        )
    except Exception:
        logger.exception(
            "Manager notification failed for lead #%s",
            lead.id,
        )


async def submit_existing_profile(
    message: Message,
    role: str,
    service: str | None,
) -> bool:
    """Create a lead from an already saved profile without silent failures."""
    try:
        name, phone = await get_user_profile(message.from_user.id)

        if not name or not phone:
            return False

        lead = await create_lead(
            message.from_user.id,
            name,
            phone,
            service,
        )

        # Audit is secondary: a logging failure must not make a successful
        # user action look like a silent failure.
        try:
            await audit(
                message.from_user.id,
                role,
                "create_lead_from_profile",
                "lead",
                str(lead.id),
            )
        except Exception:
            logger.exception("Audit failed after lead #%s was created", lead.id)

        await notify_manager(message, lead)

        await message.answer(
            f"✅ Заявка №{lead.id} принята.\n"
            "Использованы сохранённые имя и номер.\n"
            "Менеджер свяжется с вами.",
            reply_markup=main_keyboard(role),
        )
        return True

    except Exception:
        logger.exception(
            "Saved-profile lead submission failed for telegram_id=%s",
            message.from_user.id,
        )
        await message.answer(
            "⚠️ Не удалось отправить заявку менеджеру.\n\n"
            "Ваши сохранённые имя и номер не удалены. "
            "Попробуйте ещё раз через «Оставить заявку»."
            ,
            reply_markup=main_keyboard(role),
        )
        return True


async def start_lead(
    message: Message,
    state: FSMContext,
    service: str | None = None,
) -> None:
    if not await user_consented(message.from_user.id):
        await message.answer(
            CONSENT_TEXT,
            reply_markup=consent_keyboard(),
        )
        return

    name, phone = await get_user_profile(message.from_user.id)

    await state.clear()
    await state.update_data(service=service)

    if name and phone:
        await message.answer(
            "📝 <b>Оставить заявку</b>\n\n"
            f"Имя: <b>{name}</b>\n"
            f"Номер: <b>{phone}</b>\n\n"
            "Данные уже сохранены в личном кабинете. "
            "Можно сразу отправить заявку менеджеру.",
            reply_markup=profile_actions_keyboard(),
        )
        return

    if not name:
        await state.set_state(LeadForm.name)
        await message.answer(
            "📝 <b>Оставить заявку</b>\n\n"
            "Введите имя. После сохранения повторно спрашивать его "
            "не будем.",
            reply_markup=back_keyboard(),
        )
        return

    await state.update_data(name=name)
    await state.set_state(LeadForm.phone)

    await message.answer(
        f"Имя: <b>{name}</b> сохранено.\n\n"
        "Теперь отправьте номер телефона.",
        reply_markup=phone_keyboard(),
    )


async def start_contact(
    message: Message,
    state: FSMContext,
) -> None:
    if not await user_consented(message.from_user.id):
        await message.answer(
            CONSENT_TEXT,
            reply_markup=consent_keyboard(),
        )
        return

    name, phone = await get_user_profile(message.from_user.id)

    await state.clear()

    if name and phone:
        await message.answer(
            f"Ваши данные уже сохранены:\n"
            f"Имя: <b>{name}</b>\n"
            f"Номер: <b>{phone}</b>\n\n"
            "Можно сразу передать запрос менеджеру.",
            reply_markup=profile_actions_keyboard(contact_mode=True),
        )
        return

    if not name:
        await state.set_state(ContactForm.name)
        await message.answer(
            "Введите имя. Я сохраню его в личном кабинете.",
            reply_markup=back_keyboard(),
        )
        return

    await state.update_data(name=name)
    await state.set_state(ContactForm.phone)

    await message.answer(
        f"Имя: <b>{name}</b> уже сохранено. "
        "Теперь отправьте номер.",
        reply_markup=phone_keyboard(),
    )


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    role = await ensure_access(message)

    if role is None:
        return

    await state.clear()

    if await user_consented(message.from_user.id):
        await message.answer(
            "С возвращением в <b>banKROT</b>.",
            reply_markup=main_keyboard(role),
        )
        return

    await message.answer(WELCOME_TEXT)
    await message.answer(
        CONSENT_TEXT,
        reply_markup=consent_keyboard(),
    )


@router.message(F.text == "📄 Документы")
async def documents(message: Message, state: FSMContext):
    await state.clear()

    if await ensure_access(message) is None:
        return

    await message.answer(
        "<b>📄 Документы</b>\n\nВыберите документ:",
        reply_markup=documents_keyboard(),
    )


@router.message(F.text == "📄 Политика конфиденциальности")
async def privacy(message: Message, state: FSMContext):
    await state.clear()

    if await ensure_access(message) is None:
        return

    await message.answer(
        "<b>📄 Политика конфиденциальности</b>\n\n"
        "Здесь размещается утверждённая владельцем сервиса редакция "
        "политики. Текущая версия проекта содержит технический "
        "шаблон и не заменяет юридический документ.",
        reply_markup=documents_keyboard(),
    )


@router.message(F.text == "📄 Согласие на обработку ПД")
async def pd_consent(message: Message, state: FSMContext):
    await state.clear()

    if await ensure_access(message) is None:
        return

    await message.answer(
        "<b>📄 Согласие на обработку персональных данных</b>\n\n"
        "Документ должен быть утверждён оператором персональных "
        "данных с учётом фактических целей, состава данных, сроков "
        "хранения и способов обработки.",
        reply_markup=documents_keyboard(),
    )


@router.message(F.text == "📄 Пользовательские условия")
async def terms(message: Message, state: FSMContext):
    await state.clear()

    if await ensure_access(message) is None:
        return

    await message.answer(
        "<b>📄 Пользовательские условия</b>\n\n"
        "Здесь размещается утверждённая редакция условий использования сервиса.",
        reply_markup=documents_keyboard(),
    )


@router.message(F.text == "✅ Я прочитал и соглашаюсь")
async def consent(message: Message, state: FSMContext):
    role = await ensure_access(message)

    if role is None:
        return

    await state.clear()
    await save_user(message)

    await audit(
        message.from_user.id,
        role,
        "consent",
    )

    await message.answer(
        "Согласие зафиксировано.\n\n<b>Главное меню:</b>",
        reply_markup=main_keyboard(role),
    )


@router.message(F.text == "❌ Отказаться")
async def decline(message: Message, state: FSMContext):
    if await ensure_access(message) is None:
        return

    await state.clear()

    async with SessionLocal() as session:
        await session.execute(
            delete(SecurityAudit).where(
                SecurityAudit.actor_telegram_id
                == int(audit_actor_ref(message.from_user.id)[:15], 16)
            )
        )
        await session.execute(
            delete(Lead).where(
                Lead.telegram_id == message.from_user.id
            )
        )
        await session.execute(
            delete(User).where(
                User.telegram_id == message.from_user.id
            )
        )
        await session.commit()

    await message.answer(
        "Вы отказались от продолжения работы. "
        "Данные заявки не сохраняются.",
        reply_markup=consent_keyboard(),
    )


@router.message(F.text == "📋 Услуги")
async def services(message: Message, state: FSMContext):
    await state.clear()

    if await ensure_access(message) is None:
        return

    await message.answer(
        "<b>📋 Услуги</b>\n\nВыберите услугу:",
        reply_markup=services_keyboard(),
    )


@router.message(F.text.in_(list(SERVICES.keys())))
async def service_detail(message: Message, state: FSMContext):
    if await ensure_access(message) is None:
        return

    title, description = SERVICES[message.text]

    await state.clear()
    await state.update_data(service=title)

    await message.answer(
        f"<b>{title}</b>\n\n"
        f"{description}\n\n"
        "Выберите действие:",
        reply_markup=service_actions_keyboard(),
    )


@router.message(F.text == "📝 Оставить заявку")
async def new_lead(message: Message, state: FSMContext):
    role = await ensure_access(message)

    if role is None:
        return

    data = await state.get_data()
    await start_lead(
        message,
        state,
        data.get("service"),
    )


@router.message(F.text == "✅ Отправить заявку менеджеру")
async def submit_profile_lead(
    message: Message,
    state: FSMContext,
):
    role = await ensure_access(message)

    if role is None:
        return

    data = await state.get_data()
    service = data.get("service")

    await state.clear()

    if not await submit_existing_profile(
        message,
        role,
        service,
    ):
        await start_lead(
            message,
            state,
            service,
        )


@router.message(F.text == "✏️ Изменить данные")
async def edit_profile(message: Message, state: FSMContext):
    role = await ensure_access(message)

    if role is None:
        return

    await state.clear()
    await state.set_state(LeadForm.name)

    await message.answer(
        "Введите новое имя. Затем я попрошу номер телефона.",
        reply_markup=back_keyboard(),
    )


@router.message(LeadForm.name)
async def lead_name(
    message: Message,
    state: FSMContext,
):
    role = await ensure_access(message)

    if role is None:
        return

    if is_back(message.text):
        await state.clear()
        await message.answer(
            "Главное меню:",
            reply_markup=main_keyboard(role),
        )
        return

    name = clean_name(message.text or "")

    if not name:
        await message.answer(
            "Введите корректное имя, максимум 100 знаков.",
            reply_markup=back_keyboard(),
        )
        return

    # Save immediately. This is important: even if the user abandons
    # the following phone step, the name is already stored.
    await save_user(message, name=name)

    await state.update_data(name=name)
    await state.set_state(LeadForm.phone)

    await message.answer(
        "✅ Имя сохранено в личном кабинете.\n\n"
        "Теперь отправьте номер кнопкой ниже или введите его вручную.",
        reply_markup=phone_keyboard(),
    )


@router.message(LeadForm.phone)
async def lead_phone(
    message: Message,
    state: FSMContext,
):
    role = await ensure_access(message)

    if role is None:
        return

    if is_back(message.text):
        await state.clear()
        await message.answer(
            "Заявка отменена.",
            reply_markup=main_keyboard(role),
        )
        return

    # Telegram's contact button produces Message.contact and normally
    # has no text. Therefore this handler MUST process contact first.
    raw_phone = (
        message.contact.phone_number
        if message.contact is not None
        else (message.text or "")
    )

    if message.contact is not None:
        if message.contact.user_id not in (
            None,
            message.from_user.id,
        ):
            await message.answer(
                "Пожалуйста, отправьте свой номер через кнопку ниже.",
                reply_markup=phone_keyboard(),
            )
            return

    phone = normalize_phone(raw_phone)

    if not phone:
        await message.answer(
            "Не удалось распознать номер.\n"
            "Пример: +79991234567",
            reply_markup=phone_keyboard(),
        )
        return

    data = await state.get_data()
    name = data.get("name")

    if not name:
        name, _ = await get_user_profile(
            message.from_user.id
        )

    if not name:
        await state.set_state(LeadForm.name)
        await message.answer(
            "Сначала укажите имя.",
            reply_markup=back_keyboard(),
        )
        return

    # Persist the phone BEFORE creating the lead.
    # Thus the profile remains complete even if a later notification
    # or audit operation has a problem.
    await save_user(
        message,
        name=name,
        phone=phone,
    )

    try:
        lead = await create_lead(
            message.from_user.id,
            name,
            phone,
            data.get("service"),
        )

        await audit(
            message.from_user.id,
            role,
            "create_lead",
            "lead",
            str(lead.id),
        )

        await notify_manager(
            message,
            lead,
        )

    except Exception:
        logger.exception(
            "Lead creation failed for telegram_id=%s",
            message.from_user.id,
        )
        await state.clear()
        await message.answer(
            "⚠️ Номер сохранён в личном кабинете, "
            "но заявку сейчас не удалось создать. "
            "Попробуйте ещё раз через «Оставить заявку».",
            reply_markup=main_keyboard(role),
        )
        return

    await state.clear()

    await message.answer(
        f"✅ Заявка №{lead.id} принята.\n"
        "Имя и номер сохранены в личном кабинете.",
        reply_markup=main_keyboard(role),
    )


@router.message(F.text == "📞 Связаться")
@router.message(F.text == "📞 Связаться с менеджером")
async def contact(message: Message, state: FSMContext):
    await state.clear()

    if await ensure_access(message) is None:
        return

    await message.answer(
        "<b>📞 Связаться с менеджером</b>\n\n"
        "Выберите способ связи:",
        reply_markup=contact_keyboard(),
    )


@router.message(F.text == "📱 Оставить имя и номер")
async def contact_lead(
    message: Message,
    state: FSMContext,
):
    if await ensure_access(message) is None:
        return

    await start_contact(
        message,
        state,
    )


@router.message(F.text == "✅ Передать мои данные менеджеру")
async def submit_contact_profile(
    message: Message,
    state: FSMContext,
):
    role = await ensure_access(message)

    if role is None:
        return

    try:
        name, phone = await get_user_profile(message.from_user.id)

        if not name or not phone:
            await start_contact(message, state)
            return

        lead = await create_lead(
            message.from_user.id,
            name,
            phone,
            "Обратная связь",
        )

        try:
            await audit(
                message.from_user.id,
                role,
                "create_contact_request_from_profile",
                "lead",
                str(lead.id),
            )
        except Exception:
            logger.exception("Audit failed after contact lead #%s was created", lead.id)

        await notify_manager(message, lead)
        await state.clear()

        await message.answer(
            f"✅ Запрос №{lead.id} передан менеджеру.",
            reply_markup=main_keyboard(role),
        )
    except Exception:
        logger.exception(
            "Saved-profile contact submission failed for telegram_id=%s",
            message.from_user.id,
        )
        await state.clear()
        await message.answer(
            "⚠️ Не удалось передать запрос менеджеру.\n\n"
            "Сохранённые данные профиля не удалены. "
            "Попробуйте ещё раз.",
            reply_markup=main_keyboard(role),
        )


@router.message(ContactForm.name)
async def contact_name(
    message: Message,
    state: FSMContext,
):
    role = await ensure_access(message)

    if role is None:
        return

    if is_back(message.text):
        await state.clear()
        await message.answer(
            "Главное меню:",
            reply_markup=main_keyboard(role),
        )
        return

    name = clean_name(message.text or "")

    if not name:
        await message.answer(
            "Введите корректное имя.",
            reply_markup=back_keyboard(),
        )
        return

    # Save name immediately, not only after phone is received.
    await save_user(
        message,
        name=name,
    )

    await state.update_data(name=name)
    await state.set_state(ContactForm.phone)

    await message.answer(
        "✅ Имя сохранено в личном кабинете.\n\n"
        "Теперь отправьте номер.",
        reply_markup=phone_keyboard(),
    )


@router.message(ContactForm.phone)
async def contact_phone(
    message: Message,
    state: FSMContext,
):
    role = await ensure_access(message)

    if role is None:
        return

    if is_back(message.text):
        await state.clear()
        await message.answer(
            "Отменено.",
            reply_markup=main_keyboard(role),
        )
        return

    raw_phone = (
        message.contact.phone_number
        if message.contact is not None
        else (message.text or "")
    )

    if message.contact is not None:
        if message.contact.user_id not in (
            None,
            message.from_user.id,
        ):
            await message.answer(
                "Пожалуйста, отправьте свой номер через кнопку ниже.",
                reply_markup=phone_keyboard(),
            )
            return

    phone = normalize_phone(raw_phone)

    if not phone:
        await message.answer(
            "Не удалось распознать номер.\n"
            "Пример: +79991234567",
            reply_markup=phone_keyboard(),
        )
        return

    data = await state.get_data()
    name = data.get("name")

    if not name:
        name, _ = await get_user_profile(
            message.from_user.id
        )

    if not name:
        await state.set_state(ContactForm.name)
        await message.answer(
            "Сначала укажите имя.",
            reply_markup=back_keyboard(),
        )
        return

    # Save the profile first. The profile must not depend on successful
    # manager notification.
    await save_user(
        message,
        name=name,
        phone=phone,
    )

    try:
        lead = await create_lead(
            message.from_user.id,
            name,
            phone,
            "Обратная связь",
        )

        await audit(
            message.from_user.id,
            role,
            "create_contact_request",
            "lead",
            str(lead.id),
        )

        await notify_manager(
            message,
            lead,
        )

    except Exception:
        logger.exception(
            "Contact request creation failed for telegram_id=%s",
            message.from_user.id,
        )
        await state.clear()
        await message.answer(
            "⚠️ Номер сохранён в личном кабинете, "
            "но запрос сейчас не удалось передать менеджеру. "
            "Попробуйте ещё раз.",
            reply_markup=main_keyboard(role),
        )
        return

    await state.clear()

    await message.answer(
        f"✅ Запрос №{lead.id} передан менеджеру.\n"
        "Имя и номер сохранены.",
        reply_markup=main_keyboard(role),
    )


@router.message(F.text == "☎️ Позвонить")
async def call_manager(message: Message, state: FSMContext):
    await state.clear()

    if await ensure_access(message) is None:
        return

    await message.answer(
        "<b>☎️ Позвонить менеджеру</b>\n\n"
        f"Телефон: {MANAGER_PHONE or 'номер пока не настроен'}",
        reply_markup=contact_keyboard(),
    )


@router.message(F.text == "💬 Написать в мессенджере")
async def messenger(message: Message, state: FSMContext):
    await state.clear()

    if await ensure_access(message) is None:
        return

    lines = ["<b>💬 Мессенджеры</b>"]

    if MANAGER_TELEGRAM:
        lines.append(f"Telegram: {MANAGER_TELEGRAM}")

    if MANAGER_WHATSAPP:
        lines.append(f"WhatsApp: {MANAGER_WHATSAPP}")

    if len(lines) == 1:
        lines.append("Контакты пока не настроены.")

    await message.answer(
        "\n".join(lines),
        reply_markup=contact_keyboard(),
    )


@router.message(F.text == "👤 Личный кабинет")
async def cabinet(message: Message, state: FSMContext):
    await state.clear()

    role = await ensure_access(message)

    if role is None:
        return

    if not await user_consented(message.from_user.id):
        await message.answer(
            CONSENT_TEXT,
            reply_markup=consent_keyboard(),
        )
        return

    name, phone = await get_user_profile(
        message.from_user.id
    )

    profile = [
        "<b>👤 Личный кабинет</b>",
        "",
        f"Имя: <b>{name or 'не указано'}</b>",
        f"Телефон: <b>{phone or 'не указан'}</b>",
        "",
        "Сохранённые данные используются повторно и "
        "не запрашиваются заново, пока вы сами их не измените.",
    ]

    await message.answer(
        "\n".join(profile),
        reply_markup=cabinet_keyboard(),
    )


@router.message(F.text == "✏️ Изменить мои данные")
async def change_profile(
    message: Message,
    state: FSMContext,
):
    role = await ensure_access(message)

    if role is None:
        return

    await state.clear()
    await state.set_state(LeadForm.name)

    await message.answer(
        "Введите новое имя. После этого бот попросит новый номер телефона.",
        reply_markup=back_keyboard(),
    )


@router.message(F.text == "🗂 Мои заявки")
async def my_leads(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    role = await ensure_access(message)

    if role is None:
        return

    async with SessionLocal() as session:
        result = await session.execute(
            select(Lead)
            .where(Lead.telegram_id == message.from_user.id)
            .order_by(Lead.created_at.desc())
            .limit(20)
        )
        rows = list(result.scalars().all())

    if not rows:
        await message.answer(
            "У вас пока нет заявок.",
            reply_markup=cabinet_keyboard(),
        )
        return

    lines = ["<b>🗂 Мои заявки</b>"]

    for lead in rows:
        lines.append(
            f"№{lead.id} — "
            f"{lead.service or 'Обращение'} — "
            f"<b>{lead.status}</b>"
        )

    await message.answer(
        "\n".join(lines),
        reply_markup=cabinet_keyboard(),
    )


@router.message(F.text == "📌 Статус заявки")
async def status(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    role = await ensure_access(message)

    if role is None:
        return

    async with SessionLocal() as session:
        result = await session.execute(
            select(Lead)
            .where(Lead.telegram_id == message.from_user.id)
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
        lead = result.scalar_one_or_none()

    text = (
        "Заявок пока нет."
        if lead is None
        else f"Последняя заявка №{lead.id}: <b>{lead.status}</b>"
    )

    await message.answer(
        text,
        reply_markup=cabinet_keyboard(),
    )


@router.message(F.text == "🗑 Удалить мои данные")
async def delete_my_data(
    message: Message,
    state: FSMContext,
):
    if await ensure_access(message) is None:
        return

    await state.clear()
    await state.set_state(DeleteForm.confirm)

    await message.answer(
        "Удалить данные профиля и все заявки? "
        "Это действие необратимо.",
        reply_markup=delete_confirmation_keyboard(),
    )


@router.message(DeleteForm.confirm, F.text == "🗑 Да, удалить")
async def confirm_delete(
    message: Message,
    state: FSMContext,
):
    role = await ensure_access(message)

    if role is None:
        return

    async with SessionLocal() as session:
        await session.execute(
            delete(Lead).where(
                Lead.telegram_id == message.from_user.id
            )
        )
        await session.execute(
            delete(SecurityAudit).where(
                SecurityAudit.actor_telegram_id
                == int(
                    audit_actor_ref(message.from_user.id)[:15],
                    16,
                )
            )
        )
        await session.execute(
            delete(User).where(
                User.telegram_id == message.from_user.id
            )
        )
        await session.commit()

    await state.clear()

    await message.answer(
        "✅ Данные удалены.",
        reply_markup=consent_keyboard(),
    )


@router.message(DeleteForm.confirm, F.text == "◀️ Отмена")
async def cancel_delete(
    message: Message,
    state: FSMContext,
):
    role = await ensure_access(message)

    if role is None:
        return

    await state.clear()

    await message.answer(
        "Удаление отменено.",
        reply_markup=cabinet_keyboard(),
    )


@router.message(F.text == "ℹ️ О нас")
async def about(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    role = await ensure_access(message)

    if role is None:
        return

    await message.answer(
        "<b>ℹ️ О нас</b>\n\n"
        "banKROT — информационный сервис для обращения к специалистам "
        "по вопросам банкротства.\n\n"
        "Информация бота не является индивидуальной юридической консультацией.",
        reply_markup=main_keyboard(role),
    )


@router.message(F.text == "◀️ К услугам")
async def back_services(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    if await ensure_access(message) is None:
        return

    await message.answer(
        "Выберите услугу:",
        reply_markup=services_keyboard(),
    )


@router.message(F.text == "◀️ В главное меню")
async def main_menu(
    message: Message,
    state: FSMContext,
):
    role = await ensure_access(message)

    if role is None:
        return

    await state.clear()

    await message.answer(
        "<b>Главное меню</b>",
        reply_markup=main_keyboard(role),
    )
