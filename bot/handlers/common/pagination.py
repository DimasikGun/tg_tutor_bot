from contextlib import suppress

from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Publications


class Pagination(CallbackData, prefix='pag'):
    action: str
    page: int


def paginator(page: int = 0):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text='⬅', callback_data=Pagination(action='prev', page=page).pack()),
        InlineKeyboardButton(text='➡', callback_data=Pagination(action='next', page=page).pack()),
        width=2
    )
    return builder


async def pagination_handler(query: CallbackQuery, callback_data: Pagination, session: AsyncSession, state: FSMContext):
    course_id = await state.get_data()
    stmt = select(Publications).where(Publications.course_id == course_id['course_id']).order_by(
        Publications.add_date.desc())
    res = await session.execute(stmt)
    posts = res.scalars().all()

    page_num = int(callback_data.page)

    if callback_data.action == 'next':
        if page_num < (len(posts) // 5):
            page = page_num + 1
        else:
            page = page_num
            await query.answer('This is the last page')
    else:
        if page_num > 0:
            page = page_num - 1
        else:
            page = 0
            await query.answer('This is the first page')

    with suppress(TelegramBadRequest):
        pag = paginator(page)
        builder = InlineKeyboardBuilder()
        start_index = page * 5
        end_index = min(start_index + 5, len(posts))

        for i in range(start_index, end_index):
            builder.row(InlineKeyboardButton(text=posts[i].title,
                                             callback_data=f'publication_{posts[i].id}'))

        builder.row(*pag.buttons, width=2)
        await query.message.edit_reply_markup(reply_markup=builder.as_markup())
    await query.answer()
