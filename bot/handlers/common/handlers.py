from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.common import keyboards as kb
from db import Users

router = Router()


@router.message(Command('start'))
async def cmd_start(message: Message):
    await message.answer('Hello, are you a teacher or a student?', reply_markup=kb.start)


@router.message(F.text == 'Home page')
async def cmd_start(message: Message):
    await message.answer('Home page', reply_markup=kb.main)


@router.callback_query(F.data.in_(('student', 'teacher')))
async def give_role(callback: CallbackQuery, session: AsyncSession):
    user = await session.get(Users, callback.from_user.id)
    if user:
        await callback.answer('You`ve already chosen', show_alert=True)
    else:
        if callback.data == 'student':
            await session.merge(
                Users(user_id=callback.from_user.id, username=callback.from_user.username, is_teacher=False))
            await callback.answer('Ok, i get it, Ur a student')
            await callback.message.answer('Now choose one option below', reply_markup=kb.main)
        else:
            await session.merge(
                Users(user_id=callback.from_user.id, username=callback.from_user.username, is_teacher=True))
            await callback.answer('Ok, i get it, Ur a teacher')
            await callback.message.answer('Now choose one option below', reply_markup=kb.main)
        await session.commit()


@router.message()
async def echo(message: Message):
    await message.answer('i don`t get it(')
