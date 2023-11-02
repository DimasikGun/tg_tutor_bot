from contextlib import suppress

from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from handlers.tutors.services import student_name_builder


class Pagination(CallbackData, prefix='pag'):
    action: str
    page: int
    entity_type: str


def paginator(page: int = 0, entity_type: str = 'publications'):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text='⬅',
                             callback_data=Pagination(action='prev', page=page, entity_type=entity_type).pack()),
        InlineKeyboardButton(text='➡',
                             callback_data=Pagination(action='next', page=page, entity_type=entity_type).pack()),
        width=2
    )
    return builder


async def pagination_handler(query: CallbackQuery, callback_data: Pagination, records):
    page_num = int(callback_data.page)

    if callback_data.action == 'next':
        if page_num < (len(records) // 5):
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
        pag = paginator(page, entity_type=callback_data.entity_type)
        builder = InlineKeyboardBuilder()
        start_index = page * 5
        end_index = min(start_index + 5, len(records))

        if callback_data.entity_type == 'publications':
            for i in range(start_index, end_index):
                builder.row(InlineKeyboardButton(text=records[i].title, callback_data=f'publication_{records[i].id}'))
        elif callback_data.entity_type == 'students':
            for i in range(start_index, end_index):
                student_name = await student_name_builder(i)
                builder.row(InlineKeyboardButton(text=student_name, callback_data=f'student_{records[i].user_id}'))

        builder.row(*pag.buttons, width=2)
        await query.message.edit_reply_markup(reply_markup=builder.as_markup())
    await query.answer()
