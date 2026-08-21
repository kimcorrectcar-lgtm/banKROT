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
    DEV_MODE,
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
    service_actions_keyboard,
    services_keyboard,
)
from models import Lead, SecurityAudit, Tester, User
from security import audit_actor_ref, clean_name, decrypt, encrypt, normalize_phone, role_for
from texts import CONSENT_TEXT, SERVICES, WELCOME_TEXT

router = Router()


class LeadForm(StatesGroup):
    name = State()
    phone = State()


class ContactForm(StatesGroup):
    name = State()
    phone = State()


class DeleteForm(StatesGroup):
    confirm = State()


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


async def save_user(message: Message) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        if user is None:
            session.add(User(telegram_id=message.from_user.id, consented_at=datetime.now(timezone.utc)))
        else:
            user.consented_at = datetime.now(timezone.utc)
        await session.commit()


async def user_consented(tid: int) -> bool:
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == tid))
        user = result.scalar_one_or_none()
        return bool(user and user.consented_at)


async def audit(actor_id: int, role: str, action: str, target_type: str | None = None, target_id: str | None = None):
    async with SessionLocal() as session:
        session.add(SecurityAudit(
            actor_telegram_id=int(audit_actor_ref(actor_id)[:15], 16),
            actor_role=role,
            action=action,
            target_type=target_type,
            target_id=target_id,
        ))
        await session.commit()


async def create_lead(tid: int, name: str, phone: str, service: str | None) -> Lead:
    async with SessionLocal() as session:
        lead = Lead(
            telegram_id=tid,
            name=encrypt(name),
            phone=encrypt(phone),
            service=service,
        )
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
        return lead


async def notify_manager(message: Message, lead: Lead) -> None:
    if not MANAGER_LEADS_CHAT_ID:
        return
    try:
        chat_id = int(MANAGER_LEADS_CHAT_ID)
    except ValueError:
        return
    await message.bot.send_message(
        chat_id,
        "<b>🆕 Новая заявка banKROT</b>\n\n"
        f"Заявка №{lead.id}\n"
        f"Услуга: {lead.service or 'Не выбрана'}\n"
        "Контактные данные доступны только авторизованному администратору в панели бота.\n"
        f"Статус: {lead.status}",
    )


async def start_lead(message: Message, state: FSMContext, service: str | None = None):
    if not await user_consented(message.from_user.id):
        return await message.answer(CONSENT_TEXT, reply_markup=consent_keyboard())
    await state.clear()
    await state.update_data(service=service)
    await state.set_state(LeadForm.name)
    await message.answer(
        "📝 <b>Оставить заявку</b>\n\nВведите только имя.\n"
        "Паспортные, медицинские и другие специальные данные не нужны.",
        reply_markup=back_keyboard(),
    )


async def start_contact(message: Message, state: FSMContext):
    if not await user_consented(message.from_user.id):
        return await message.answer(CONSENT_TEXT, reply_markup=consent_keyboard())
    await state.clear()
    await state.set_state(ContactForm.name)
    await message.answer("Введите имя для обратной связи.", reply_markup=back_keyboard())


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    role = await ensure_access(message)
    if role is None:
        return
    await state.clear()
    if await user_consented(message.from_user.id):
        await message.answer("С возвращением в <b>banKROT</b>.", reply_markup=main_keyboard(role))
        return
    await message.answer(WELCOME_TEXT)
    await message.answer(CONSENT_TEXT, reply_markup=consent_keyboard())


@router.message(F.text == "📄 Документы")
async def documents(message: Message):
    if await ensure_access(message) is None:
        return
    await message.answer("<b>📄 Документы</b>\n\nВыберите документ:", reply_markup=documents_keyboard())


@router.message(F.text == "📄 Политика конфиденциальности")
async def privacy(message: Message):
    if await ensure_access(message) is None:
        return
    await message.answer(
        "<b>📄 Политика конфиденциальности</b>\n\n"
        "Здесь размещается утверждённая владельцем сервиса редакция политики. "
        "Текущая версия проекта содержит технический шаблон и не заменяет юридический документ.",
        reply_markup=documents_keyboard(),
    )


@router.message(F.text == "📄 Согласие на обработку ПД")
async def pd_consent(message: Message):
    if await ensure_access(message) is None:
        return
    await message.answer(
        "<b>📄 Согласие на обработку персональных данных</b>\n\n"
        "Документ должен быть утверждён оператором персональных данных с учётом фактических целей, "
        "состава данных, сроков хранения и способов обработки.",
        reply_markup=documents_keyboard(),
    )


@router.message(F.text == "📄 Пользовательские условия")
async def terms(message: Message):
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
    await audit(message.from_user.id, role, "consent")
    await message.answer("Согласие зафиксировано.\n\n<b>Главное меню:</b>", reply_markup=main_keyboard(role))


@router.message(F.text == "❌ Отказаться")
async def decline(message: Message, state: FSMContext):
    if await ensure_access(message) is None:
        return
    await state.clear()
    async with SessionLocal() as session:
        await session.execute(delete(Lead).where(Lead.telegram_id == message.from_user.id))
        await session.execute(delete(User).where(User.telegram_id == message.from_user.id))
        await session.commit()
    await message.answer("Вы отказались от продолжения работы. Данные заявки не сохраняются.", reply_markup=consent_keyboard())


@router.message(F.text == "📋 Услуги")
async def services(message: Message):
    if await ensure_access(message) is None:
        return
    await message.answer("<b>📋 Услуги</b>\n\nВыберите услугу:", reply_markup=services_keyboard())


@router.message(F.text.in_(list(SERVICES.keys())))
async def service_detail(message: Message, state: FSMContext):
    if await ensure_access(message) is None:
        return
    title, description = SERVICES[message.text]
    await state.update_data(service=title)
    await message.answer(f"<b>{title}</b>\n\n{description}\n\nВыберите действие:", reply_markup=service_actions_keyboard())


@router.message(F.text == "📝 Оставить заявку")
async def new_lead(message: Message, state: FSMContext):
    if await ensure_access(message) is None:
        return
    data = await state.get_data()
    await start_lead(message, state, data.get("service"))


@router.message(LeadForm.name)
async def lead_name(message: Message, state: FSMContext):
    role = await ensure_access(message)
    if role is None:
        return
    if message.text and message.text.startswith("◀️"):
        await state.clear()
        return await message.answer("Главное меню:", reply_markup=main_keyboard(role))
    name = clean_name(message.text or "")
    if not name:
        return await message.answer("Введите имя без лишних символов, максимум 100 знаков.")
    await state.update_data(name=name)
    await state.set_state(LeadForm.phone)
    await message.answer("Теперь отправьте номер кнопкой ниже или введите его вручную.", reply_markup=phone_keyboard())


@router.message(LeadForm.phone)
async def lead_phone(message: Message, state: FSMContext):
    role = await ensure_access(message)
    if role is None:
        return
    if message.text == "◀️ Отмена":
        await state.clear()
        return await message.answer("Заявка отменена.", reply_markup=main_keyboard(role))
    phone = message.contact.phone_number if message.contact else message.text or ""
    phone = normalize_phone(phone)
    if not phone:
        return await message.answer("Не удалось распознать номер. Используйте кнопку отправки номера.", reply_markup=phone_keyboard())
    data = await state.get_data()
    lead = await create_lead(message.from_user.id, data["name"], phone, data.get("service"))
    await audit(message.from_user.id, role, "create_lead", "lead", str(lead.id))
    await notify_manager(message, lead)
    await state.clear()
    await message.answer(
        f"✅ Заявка №{lead.id} принята. Менеджер свяжется с вами.",
        reply_markup=main_keyboard(role),
    )


@router.message(F.text == "📞 Связаться")
@router.message(F.text == "📞 Связаться с менеджером")
async def contact(message: Message):
    if await ensure_access(message) is None:
        return
    await message.answer("<b>📞 Связаться с менеджером</b>\n\nВыберите способ связи:", reply_markup=contact_keyboard())


@router.message(F.text == "📱 Оставить имя и номер")
async def contact_lead(message: Message, state: FSMContext):
    if await ensure_access(message) is None:
        return
    await start_contact(message, state)


@router.message(ContactForm.name)
async def contact_name(message: Message, state: FSMContext):
    role = await ensure_access(message)
    if role is None:
        return
    if message.text and message.text.startswith("◀️"):
        await state.clear()
        return await message.answer("Главное меню:", reply_markup=main_keyboard(role))
    name = clean_name(message.text or "")
    if not name:
        return await message.answer("Введите корректное имя.")
    await state.update_data(name=name)
    await state.set_state(ContactForm.phone)
    await message.answer("Отправьте номер кнопкой ниже или введите его вручную.", reply_markup=phone_keyboard())


@router.message(ContactForm.phone)
async def contact_phone(message: Message, state: FSMContext):
    role = await ensure_access(message)
    if role is None:
        return
    if message.text == "◀️ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_keyboard(role))
    phone = message.contact.phone_number if message.contact else message.text or ""
    phone = normalize_phone(phone)
    if not phone:
        return await message.answer("Не удалось распознать номер.", reply_markup=phone_keyboard())
    data = await state.get_data()
    lead = await create_lead(message.from_user.id, data["name"], phone, "Обратная связь")
    await audit(message.from_user.id, role, "create_contact_request", "lead", str(lead.id))
    await notify_manager(message, lead)
    await state.clear()
    await message.answer(f"✅ Запрос №{lead.id} передан менеджеру.", reply_markup=main_keyboard(role))


@router.message(F.text == "☎️ Позвонить")
async def call_manager(message: Message):
    if await ensure_access(message) is None:
        return
    text = "<b>☎️ Позвонить менеджеру</b>\n\n"
    text += f"Телефон: {MANAGER_PHONE or 'номер пока не настроен'}"
    await message.answer(text, reply_markup=contact_keyboard())


@router.message(F.text == "💬 Написать в мессенджере")
async def messenger(message: Message):
    if await ensure_access(message) is None:
        return
    lines = ["<b>💬 Мессенджеры</b>"]
    if MANAGER_TELEGRAM:
        lines.append(f"Telegram: {MANAGER_TELEGRAM}")
    if MANAGER_WHATSAPP:
        lines.append(f"WhatsApp: {MANAGER_WHATSAPP}")
    if len(lines) == 1:
        lines.append("Контакты пока не настроены.")
    await message.answer("\n".join(lines), reply_markup=contact_keyboard())


@router.message(F.text == "👤 Личный кабинет")
async def cabinet(message: Message):
    if await ensure_access(message) is None:
        return
    if not await user_consented(message.from_user.id):
        return await message.answer(CONSENT_TEXT, reply_markup=consent_keyboard())
    await message.answer("<b>👤 Личный кабинет</b>\n\nВыберите раздел:", reply_markup=cabinet_keyboard())


@router.message(F.text == "🗂 Мои заявки")
async def my_leads(message: Message):
    role = await ensure_access(message)
    if role is None:
        return
    async with SessionLocal() as session:
        result = await session.execute(select(Lead).where(Lead.telegram_id == message.from_user.id).order_by(Lead.created_at.desc()).limit(20))
        rows = list(result.scalars().all())
    if not rows:
        return await message.answer("У вас пока нет заявок.", reply_markup=cabinet_keyboard())
    lines = ["<b>🗂 Мои заявки</b>"]
    for lead in rows:
        lines.append(f"№{lead.id} — {lead.service or 'Обращение'} — <b>{lead.status}</b>")
    await message.answer("\n".join(lines), reply_markup=cabinet_keyboard())


@router.message(F.text == "📌 Статус заявки")
async def status(message: Message):
    role = await ensure_access(message)
    if role is None:
        return
    async with SessionLocal() as session:
        result = await session.execute(select(Lead).where(Lead.telegram_id == message.from_user.id).order_by(Lead.created_at.desc()).limit(1))
        lead = result.scalar_one_or_none()
    text = "Заявок пока нет." if lead is None else f"Последняя заявка №{lead.id}: <b>{lead.status}</b>"
    await message.answer(text, reply_markup=cabinet_keyboard())


@router.message(F.text == "🗑 Удалить мои данные")
async def delete_my_data(message: Message, state: FSMContext):
    if await ensure_access(message) is None:
        return
    await state.clear()
    await state.set_state(DeleteForm.confirm)
    await message.answer("Удалить данные профиля и все заявки? Это действие необратимо.", reply_markup=delete_confirmation_keyboard())


@router.message(DeleteForm.confirm, F.text == "🗑 Да, удалить")
async def confirm_delete(message: Message, state: FSMContext):
    role = await ensure_access(message)
    if role is None:
        return
    async with SessionLocal() as session:
        await session.execute(delete(Lead).where(Lead.telegram_id == message.from_user.id))
        await session.execute(delete(User).where(User.telegram_id == message.from_user.id))
        await session.commit()
    await state.clear()
    await message.answer("✅ Данные удалены.", reply_markup=consent_keyboard())


@router.message(DeleteForm.confirm, F.text == "◀️ Отмена")
async def cancel_delete(message: Message, state: FSMContext):
    role = await ensure_access(message)
    if role is None:
        return
    await state.clear()
    await message.answer("Удаление отменено.", reply_markup=cabinet_keyboard())


@router.message(F.text == "ℹ️ О нас")
async def about(message: Message):
    role = await ensure_access(message)
    if role is None:
        return
    await message.answer(
        "<b>ℹ️ О нас</b>\n\n"
        "banKROT — информационный сервис для обращения к специалистам по вопросам банкротства.\n\n"
        "Информация бота не является индивидуальной юридической консультацией.",
        reply_markup=main_keyboard(role),
    )


@router.message(F.text == "◀️ К услугам")
async def back_services(message: Message):
    if await ensure_access(message) is None:
        return
    await message.answer("Выберите услугу:", reply_markup=services_keyboard())


@router.message(F.text == "◀️ В главное меню")
async def main_menu(message: Message, state: FSMContext):
    role = await ensure_access(message)
    if role is None:
        return
    await state.clear()
    await message.answer("<b>Главное меню</b>", reply_markup=main_keyboard(role))
