from aiogram.enums import ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, InputMediaVideo, \
    InputMediaAudio, InputMediaDocument
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Publications, Courses, Media
from handlers.common.pagination import paginator


class CourseInteract(StatesGroup):
    single_course = State()


async def publications(message: Message, session: AsyncSession, state: FSMContext, kb):
    course_id = await state.get_data()
    stmt = select(Publications).where(Publications.course_id == course_id['course_id']).order_by(
        Publications.add_date.desc()).limit(5)
    res = await session.execute(stmt)
    posts = res.scalars().all()
    if posts:
        pag = paginator()
        builder = InlineKeyboardBuilder()
        for post in posts:
            builder.row(InlineKeyboardButton(text=post.title, callback_data=f'publication_{post.id}'))

        builder.row(*pag.buttons, width=2)
        await state.set_state(CourseInteract.single_course)
        await message.answer('Here is publications:', reply_markup=builder.as_markup())
    else:
        await state.set_state(CourseInteract.single_course)
        await message.answer('There is no any publications yet', reply_markup=kb.single_course)


async def create_inline_courses(courses, message, kb):
    builder = InlineKeyboardBuilder()
    for course in courses:
        builder.add(InlineKeyboardButton(text=course.name, callback_data=f'course_{course.id}'))
    builder.adjust(2)
    await message.answer('Choose a course:', reply_markup=builder.as_markup())
    await message.answer('Or an option below:', reply_markup=kb.courses)


# TODO: REMOVE REPETITIVE COURSE QUERY
async def course_info(callback: CallbackQuery, session: AsyncSession, state: FSMContext, kb, course_id):
    stmt = select(Courses).where(Courses.id == course_id)
    result = await session.execute(stmt)
    course = result.scalar()
    if course:
        await state.set_state(CourseInteract.single_course)
        await state.update_data(course_id=course_id)
        await callback.answer(f'Here is "{course.name}"')
        await callback.message.answer(f'Course "{course.name}"', reply_markup=kb.single_course)
    else:
        await callback.message.answer('Course not found', reply_markup=kb.courses)


async def single_publication(callback: CallbackQuery, session: AsyncSession, state: FSMContext, kb):
    media_group = []
    audio = []
    documents = []

    publication_id = int(callback.data[12:])
    stmt = select(Publications).where(Publications.id == publication_id)
    result = await session.execute(stmt)
    publication = result.scalar()

    query = select(Media).where(Media.publication == publication_id)
    result = await session.execute(query)
    media_files = result.scalars().all()

    for media in media_files:
        if media.media_type == str(ContentType.PHOTO):
            media_group.append(InputMediaPhoto(media=media.file_id))
        elif media.media_type == str(ContentType.VIDEO):
            media_group.append(InputMediaVideo(media=media.file_id))
        elif media.media_type == str(ContentType.AUDIO):
            audio.append(InputMediaAudio(media=media.file_id))
        else:
            documents.append(InputMediaDocument(media=media.file_id))
    await callback.message.answer(
        f'SUBMIT UNTIL: {publication.finish_date}\n<b>{publication.title}</b>\n{publication.text}', parse_mode='HTML',
        reply_markup=kb.single_course)

    if media_group:
        await callback.message.answer_media_group(media_group)
    if documents:
        await callback.message.answer('Documents:')
        await callback.message.answer_media_group(documents)
    if audio:
        await callback.message.answer('Audio:')
        await callback.message.answer_media_group(audio)
    await callback.answer()
