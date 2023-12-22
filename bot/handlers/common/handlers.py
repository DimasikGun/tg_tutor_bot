from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.handlers.common import keyboards as kb
from db.queries import create_user, get_user

router = Router()


@router.message(Command('start'))
async def cmd_start(message: Message, session: AsyncSession):
    """
    Handles the '/start' command and welcomes the user or asks for their role.

    Args:
        message (Message): The message containing the command.
        session (AsyncSession): The database session.

    Returns:
        None
    """
    user = await get_user(session, message.from_user.id)
    if user:
        await message.answer('Home page', reply_markup=kb.main)
    else:
        await message.answer('Hello, are you a teacher or a student?', reply_markup=kb.start)


@router.message(F.text == 'Home page')
async def cmd_home(message: Message):
    """
    Handles the 'Home page' text command and navigates to the home page.

    Args:
        message (Message): The message containing the command.

    Returns:
        None
    """
    await message.answer('Home page', reply_markup=kb.main)


@router.callback_query(F.data.in_(('student', 'teacher')))
async def give_role(callback: CallbackQuery, session: AsyncSession):
    """
    Handles the callback query for choosing a role (student or teacher).

    Args:
        callback (CallbackQuery): The callback query.
        session (AsyncSession): The database session.

    Returns:
        None
    """
    user = await get_user(session, callback.message.from_user.id)
    if user:
        await callback.answer('You`ve already chosen', show_alert=True)
    else:
        if callback.data == 'student':
            await create_user(session, callback, is_teacher=False)
            await callback.answer('Ok, I get it, you are a student')
            await callback.message.answer('Now choose one option below', reply_markup=kb.main)
        else:
            await create_user(session, callback, is_teacher=True)
            await callback.answer('Ok, I get it, you are a teacher')
            await callback.message.answer('Now choose one option below', reply_markup=kb.main)
        await session.commit()


@router.message(Command('cancel'))
@router.message(F.text.casefold() == "cancel")
async def cmd_cancel(message: Message, state: FSMContext):
    """
    Handles the 'cancel' command and cancels the current action.

    Args:
        message (Message): The message containing the command.
        state (FSMContext): The finite state machine context.

    Returns:
        None
    """
    await state.clear()
    await message.answer(
        text="Action was cancelled",
        reply_markup=kb.main)


@router.message()
async def echo(message: Message):
    """
    Handles messages that don't match any specific command and echoes a response.

    Args:
        message (Message): The message.

    Returns:
        None
    """
    await message.answer('I don`t get it(')
