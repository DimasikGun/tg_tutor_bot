import re
from datetime import datetime

from aiogram.enums import ContentType
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from handlers.common.services import CourseInteract, publications
from handlers.tutors import keyboards as kb
from db import Publications


async def add_publication_preview(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    date_obj = None
    time_obj = None

    try:
        date_obj = datetime.strptime(data['date'], "%d.%m.%Y")
    except (TypeError, ValueError):
        pass

    if 'time' in data and data['time']:
        try:
            time_obj = datetime.strptime(data['time'], "%H:%M")
        except (TypeError, ValueError):
            pass

    if date_obj is not None:
        if time_obj is not None:
            date_time = datetime.combine(date_obj, time_obj.time())
        else:
            date_time = date_obj
    else:
        date_time = None

    stmt = update(Publications).where(Publications.id == data['publication_id']).values(finish_date=date_time)
    await session.execute(stmt)
    await session.commit()
    await state.set_state(CourseInteract.single_course)
    await message.answer('Submit date and time has been added', reply_markup=kb.single_course)
    await publications(message, session, state, kb)


async def add_media(message: Message, session: AsyncSession, state: FSMContext, data):
    message_type = message.content_type

    if message_type in (
            ContentType.VIDEO, ContentType.AUDIO, ContentType.DOCUMENT):
        file_id = eval(f"message.{message_type}.file_id")
        media = data['media']
        media.append((str(message_type), file_id))
        await state.update_data(media=media)  # Update the 'media' key in data
        await message.answer('Media added, add more or press "Ready"')

    elif message_type == ContentType.PHOTO:
        file_id = message.photo[-1].file_id
        media = data['media']
        media.append((str(message_type), file_id))
        await state.update_data(media=media)  # Update the 'media' key in data
        await message.answer('Media added, add more or press "Ready"')

    else:
        await message.answer('Not supported media type, try something else')


async def publication_date(message: Message, session: AsyncSession, state: FSMContext, state_name_re,
                           state_name_next):
    date_pattern = r'\d{2}.\d{2}.\d{4}'
    if message.text == 'Ready':
        await add_publication_preview(message, session, state)
    elif not re.match(date_pattern, message.text.strip()):
        await message.answer('Wrong date pattern, try again')
        await state.set_state(state_name_re)
    else:
        await state.set_state(state_name_next)
        await state.update_data(date=message.text)
        await message.answer('Now enter finish time (hh:mm) or press "Ready" button')


async def publication_time(message: Message, session: AsyncSession, state: FSMContext, state_name_re):
    time_pattern = r'\d{2}:\d{2}'
    if message.text == 'Ready':
        await add_publication_preview(message, session, state)
    elif not re.match(time_pattern, message.text.strip()):
        await message.answer('Wrong time pattern, try again')
        await state.set_state(state_name_re)
    else:
        await state.update_data(time=message.text)
        await add_publication_preview(message, session, state)