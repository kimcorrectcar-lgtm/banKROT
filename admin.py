import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import delete, func, select

from config import ADMIN_IDS
from database import SessionLocal
from handlers import audit, get_role, tester_ids
from keyboards import (
    admin_back_keyboard,
    admin_keyboard,
    admin_leads_keyboard,
    admin_status_keyboard,
    admin_testers_keyboard,
    main_keyboard,
)
from models import Lead, SecurityAudit, Tester, User

logger = logging.getLogger(__name__)
router = Router()


class TesterForm(StatesGroup):
    add_id = State()
    remove_id = State()


class LeadStatusForm(StatesGroup):
    status_id = State()
    status = State()


class UserDeleteForm(StatesGroup):
    telegram_id = State()


async def is_admin(message: Message) -> bool:
    return message.from_user.id in ADMIN_IDS and await get_role(message.from_user.id) == "admin"


async def deny(message: Message):
    await message.answer("⛔ Недостаточно прав.")


async def admin_or_deny(message: Message) -> bool:
    if not await is_admin(message):
        await deny(message)
        return False
    return True


def admin_back(text: str | None) -> bool:
    return text in {"🔙 В админ-меню", "🔙 В главное меню", "◀️ В главное меню", "◀️ Отмена"}


async def go_back_from_admin_state(message: Message, state: FSMContext) -> bool:
    if not admin_back(message.text):
        return False
    await state.clear()
    if message.text == "🔙 В админ-меню":
        await message.answer("<b>🔐 Панель администратора</b>", reply_markup=admin_keyboard())
    else:
        await message.answer("<b>Главное меню</b>", reply_markup=main_keyboard("admin"))
    return True


@router.message(F.text == "🔐 Администратор")
async def menu(message: Message, state: FSMContext):
    if not await admin_or_deny(message):
        return
    await state.clear()
    try:
        await audit(message.from_user.id, "admin", "open_admin")
    except Exception:
        logger.exception("Admin audit failed")
    await message.answer("<b>🔐 Панель администратора</b>\n\nВыберите раздел:", reply_markup=admin_keyboard())


@router.message(F.text == "👥 Тестировщики")
async def testers(message: Message, state: FSMContext):
    if not await admin_or_deny(message):
        return
    await state.clear()
    ids = sorted(x for x in await tester_ids() if x not in ADMIN_IDS)
    text = "<b>👥 Тестировщики</b>\n\n" + ("\n".join(map(str, ids)) if ids else "Список пуст.")
    await message.answer(text, reply_markup=admin_testers_keyboard())


@router.message(F.text == "➕ Добавить тестировщика")
async def add_start(message: Message, state: FSMContext):
    if not await admin_or_deny(message):
        return
    await state.clear()
    await state.set_state(TesterForm.add_id)
    await message.answer("Введите Telegram ID тестировщика числом.", reply_markup=admin_back_keyboard())


@router.message(TesterForm.add_id)
async def add_tester(message: Message, state: FSMContext):
    if not await admin_or_deny(message):
        return
    if await go_back_from_admin_state(message, state):
        return

    try:
        tid = int((message.text or "").strip())
    except ValueError:
        await message.answer("Telegram ID должен быть числом.", reply_markup=admin_back_keyboard())
        return

    if tid <= 0:
        await message.answer("Telegram ID должен быть положительным числом.", reply_markup=admin_back_keyboard())
        return
    if tid in ADMIN_IDS:
        await message.answer("Этот ID уже является администратором.", reply_markup=admin_back_keyboard())
        return

    try:
        async with SessionLocal() as session:
            result = await session.execute(select(Tester).where(Tester.telegram_id == tid))
            if result.scalar_one_or_none() is None:
                session.add(Tester(telegram_id=tid))
                await session.commit()
        try:
            await audit(message.from_user.id, "admin", "add_tester", "telegram_user", str(tid))
        except Exception:
            logger.exception("Audit failed after adding tester %s", tid)
        await state.clear()
        await message.answer("✅ Тестировщик добавлен.", reply_markup=admin_testers_keyboard())
    except Exception:
        logger.exception("Failed to add tester %s", tid)
        await message.answer("⚠️ Не удалось добавить тестировщика. Проверьте логи сервиса.", reply_markup=admin_back_keyboard())


@router.message(F.text == "➖ Удалить тестировщика")
async def remove_start(message: Message, state: FSMContext):
    if not await admin_or_deny(message):
        return
    await state.clear()
    await state.set_state(TesterForm.remove_id)
    await message.answer("Введите Telegram ID тестировщика.", reply_markup=admin_back_keyboard())


@router.message(TesterForm.remove_id)
async def remove_tester(message: Message, state: FSMContext):
    if not await admin_or_deny(message):
        return
    if await go_back_from_admin_state(message, state):
        return

    try:
        tid = int((message.text or "").strip())
    except ValueError:
        await message.answer("Telegram ID должен быть числом.", reply_markup=admin_back_keyboard())
        return

    if tid in ADMIN_IDS:
        await message.answer("Администратора удалить нельзя.", reply_markup=admin_back_keyboard())
        return

    try:
        async with SessionLocal() as session:
            await session.execute(delete(Tester).where(Tester.telegram_id == tid))
            await session.commit()
        try:
            await audit(message.from_user.id, "admin", "remove_tester", "telegram_user", str(tid))
        except Exception:
            logger.exception("Audit failed after removing tester %s", tid)
        await state.clear()
        await message.answer("✅ Тестировщик удалён.", reply_markup=admin_testers_keyboard())
    except Exception:
        logger.exception("Failed to remove tester %s", tid)
        await message.answer("⚠️ Не удалось удалить тестировщика. Проверьте логи сервиса.", reply_markup=admin_back_keyboard())


@router.message(F.text == "📋 Заявки")
async def leads(message: Message, state: FSMContext):
    if not await admin_or_deny(message):
        return
    await state.clear()
    async with SessionLocal() as session:
        result = await session.execute(select(Lead).order_by(Lead.created_at.desc()).limit(20))
        rows = list(result.scalars().all())
    if not rows:
        await message.answer("Заявок пока нет.", reply_markup=admin_leads_keyboard())
        return
    lines = ["<b>📋 Последние заявки</b>"]
    lines.extend(f"№{x.id} | {x.service or 'Обращение'} | <b>{x.status}</b>" for x in rows)
    await message.answer("\n".join(lines), reply_markup=admin_leads_keyboard())


@router.message(F.text == "✏️ Изменить статус")
async def status_start(message: Message, state: FSMContext):
    if not await admin_or_deny(message):
        return
    await state.clear()
    await state.set_state(LeadStatusForm.status_id)
    await message.answer("Введите номер заявки.", reply_markup=admin_back_keyboard())


@router.message(LeadStatusForm.status_id)
async def status_id(message: Message, state: FSMContext):
    if not await admin_or_deny(message):
        return
    if await go_back_from_admin_state(message, state):
        return
    try:
        lid = int((message.text or "").strip())
    except ValueError:
        await message.answer("Номер заявки должен быть числом.", reply_markup=admin_back_keyboard())
        return
    if lid <= 0:
        await message.answer("Номер заявки должен быть положительным числом.", reply_markup=admin_back_keyboard())
        return

    async with SessionLocal() as session:
        lead = await session.get(Lead, lid)
    if lead is None:
        await message.answer("Заявка не найдена. Введите другой номер или вернитесь назад.", reply_markup=admin_back_keyboard())
        return

    await state.update_data(lead_id=lid)
    await state.set_state(LeadStatusForm.status)
    await message.answer(
        f"Текущий статус: <b>{lead.status}</b>\nВыберите новый:",
        reply_markup=admin_status_keyboard(),
    )


@router.message(LeadStatusForm.status)
async def set_status(message: Message, state: FSMContext):
    if not await admin_or_deny(message):
        return
    if await go_back_from_admin_state(message, state):
        return

    allowed = {
        "🆕 Новая": "Новая",
        "📞 Связались": "Связались",
        "🟡 В работе": "В работе",
        "🟢 Завершена": "Завершена",
        "🔴 Отменена": "Отменена",
    }
    if message.text not in allowed:
        await message.answer("Выберите статус кнопкой.", reply_markup=admin_status_keyboard())
        return

    data = await state.get_data()
    lead_id = data.get("lead_id")
    try:
        async with SessionLocal() as session:
            lead = await session.get(Lead, int(lead_id))
            if lead is None:
                await state.clear()
                await message.answer("Заявка не найдена.", reply_markup=admin_leads_keyboard())
                return
            lead.status = allowed[message.text]
            await session.commit()
        try:
            await audit(message.from_user.id, "admin", "change_lead_status", "lead", str(lead_id))
        except Exception:
            logger.exception("Audit failed after status change for lead %s", lead_id)
        await state.clear()
        await message.answer("✅ Статус изменён.", reply_markup=admin_leads_keyboard())
    except Exception:
        logger.exception("Failed to change status for lead %s", lead_id)
        await message.answer("⚠️ Не удалось изменить статус. Попробуйте ещё раз.", reply_markup=admin_status_keyboard())


@router.message(F.text == "📊 Статистика")
async def stats(message: Message, state: FSMContext):
    if not await admin_or_deny(message):
        return
    await state.clear()
    async with SessionLocal() as session:
        users = await session.scalar(select(func.count()).select_from(User))
        leads_count = await session.scalar(select(func.count()).select_from(Lead))
        testers_count = await session.scalar(select(func.count()).select_from(Tester))
    try:
        await audit(message.from_user.id, "admin", "view_stats")
    except Exception:
        logger.exception("Stats audit failed")
    await message.answer(
        f"<b>📊 Статистика</b>\n\nПользователей: {users}\nЗаявок: {leads_count}\nТестировщиков: {testers_count}",
        reply_markup=admin_keyboard(),
    )


@router.message(F.text == "🛡 Журнал безопасности")
async def audit_log(message: Message, state: FSMContext):
    if not await admin_or_deny(message):
        return
    await state.clear()
    async with SessionLocal() as session:
        result = await session.execute(select(SecurityAudit).order_by(SecurityAudit.created_at.desc()).limit(30))
        rows = list(result.scalars().all())
    lines = ["<b>🛡 Журнал безопасности</b>"]
    lines.extend(
        f"{x.created_at} | {x.actor_role} | {x.action} | {x.target_type or ''}:{x.target_id or ''}"
        for x in rows
    )
    await message.answer("\n".join(lines) if rows else "Журнал пуст.", reply_markup=admin_keyboard())


@router.message(F.text == "🗑 Удалить данные пользователя")
async def delete_user_start(message: Message, state: FSMContext):
    if not await admin_or_deny(message):
        return
    await state.clear()
    await state.set_state(UserDeleteForm.telegram_id)
    await message.answer("Введите Telegram ID пользователя. Удаление необратимо.", reply_markup=admin_back_keyboard())


@router.message(UserDeleteForm.telegram_id)
async def delete_user(message: Message, state: FSMContext):
    if not await admin_or_deny(message):
        return
    if await go_back_from_admin_state(message, state):
        return
    try:
        tid = int((message.text or "").strip())
    except ValueError:
        await message.answer("Telegram ID должен быть числом.", reply_markup=admin_back_keyboard())
        return
    if tid in ADMIN_IDS:
        await message.answer("Удаление данных администратора через этот раздел запрещено.", reply_markup=admin_back_keyboard())
        return

    try:
        async with SessionLocal() as session:
            await session.execute(delete(Lead).where(Lead.telegram_id == tid))
            await session.execute(delete(User).where(User.telegram_id == tid))
            await session.commit()
        try:
            await audit(message.from_user.id, "admin", "delete_user_data", "telegram_user", str(tid))
        except Exception:
            logger.exception("Delete-user audit failed")
        await state.clear()
        await message.answer("✅ Данные пользователя удалены, если они существовали.", reply_markup=admin_keyboard())
    except Exception:
        logger.exception("Failed to delete user data for %s", tid)
        await message.answer("⚠️ Не удалось удалить данные. Попробуйте ещё раз.", reply_markup=admin_back_keyboard())


@router.message(F.text == "🔙 В админ-меню")
async def back_admin(message: Message, state: FSMContext):
    if not await admin_or_deny(message):
        return
    await state.clear()
    await message.answer("<b>🔐 Панель администратора</b>", reply_markup=admin_keyboard())
