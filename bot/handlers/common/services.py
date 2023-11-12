from contextlib import suppress

from aiogram.enums import ContentType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, InputMediaVideo, \
    InputMediaAudio, InputMediaDocument
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Publications, Courses, Media, Submissions, Users


async def student_name_builder(student):
    if student.username:
        student_name = student.first_name
    elif student.first_name:
        student_name = '@' + student.username
    else:
        student_name = f'student_{student.user_id}'
    return student_name


async def submission_name_builder(session, student_id):
    stmt = select(Users).where(Users.user_id == student_id)
    result = await session.execute(stmt)
    user = result.scalar()

    return await student_name_builder(user)


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


async def pagination_handler(query: CallbackQuery, callback_data: Pagination, records, session=None):
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
        else:
            for i in range(start_index, end_index):
                student_name = await submission_name_builder(session, records[i].student)
                builder.row(InlineKeyboardButton(text=student_name, callback_data=f'submission_{records[i].id}'))

        builder.row(*pag.buttons, width=2)
        await query.message.edit_reply_markup(reply_markup=builder.as_markup())
    await query.answer()


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


async def media_sort(media_files, media_group: list, audio: list, documents: list):
    for media in media_files:
        if media.media_type == str(ContentType.PHOTO):
            media_group.append(InputMediaPhoto(media=media.file_id))
        elif media.media_type == str(ContentType.VIDEO):
            media_group.append(InputMediaVideo(media=media.file_id))
        elif media.media_type == str(ContentType.AUDIO):
            audio.append(InputMediaAudio(media=media.file_id))
        else:
            documents.append(InputMediaDocument(media=media.file_id))


async def media_group_send(message: Message, media_group: list, audio: list, documents: list):
    if media_group:
        await message.answer_media_group(media_group)
    if documents:
        await message.answer('Documents:')
        await message.answer_media_group(documents)
    if audio:
        await message.answer('Audio:')
        await message.answer_media_group(audio)


async def single_publication(callback: CallbackQuery, session: AsyncSession, state: FSMContext, kb, user='teacher'):
    media_group = []
    audio = []
    documents = []
    publication_id = int(callback.data[12:])
    stmt = select(Publications).where(Publications.id == publication_id)
    result = await session.execute(stmt)
    publication = result.scalar()
    if user == 'student':
        stmt = select(Submissions).where(
            Submissions.publication == publication_id and Submissions.student == callback.message.from_user.id)
        result = await session.execute(stmt)
        submission = result.scalar()
        if submission:
            if submission.grade:
                await callback.message.answer(f'Grade: {submission.grade}/{publication.max_grade}',
                                              reply_markup=kb.publication_interact_submitted)
            else:
                await callback.message.answer(f'Not graded. Max. grade: {publication.max_grade}',
                                              reply_markup=kb.publication_interact_submitted)

        else:
            await callback.message.answer(f'Max. grade: {publication.max_grade}',
                                          reply_markup=kb.publication_interact_not_submitted)
    else:
        await callback.message.answer(f'Max. grade: {publication.max_grade}', reply_markup=kb.publication_interact)

    query = select(Media).where(Media.publication == publication_id)
    result = await session.execute(query)
    media_files = result.scalars().all()

    await media_sort(media_files, media_group, audio, documents)

    await callback.message.answer(
        f'SUBMIT UNTIL: {publication.finish_date}\n<b>{publication.title}</b>\n{publication.text}',
        parse_mode='HTML') if publication.finish_date is not None else await callback.message.answer(
        f'<b>{publication.title}</b>\n{publication.text}',
        parse_mode='HTML')

    await media_group_send(callback.message, media_group, audio, documents)
    await callback.answer()


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


async def single_submission(message: Message, session: AsyncSession, submission, kb, max_grade, user='teacher'):
    media_group = []
    audio = []
    documents = []

    if submission.grade:
        await message.answer(f'Grade: {submission.grade}/{max_grade}')
    else:
        await message.answer(f'Not graded. Max. grade: {max_grade}')

    if user == 'teacher':
        if submission.grade:
            keyboard = kb.submission_graded
        else:
            keyboard = kb.submission_not_graded
    else:
        keyboard = kb.publication_interact_submitted

    stmt = select(Media).where(Media.submission == submission.id)
    result = await session.execute(stmt)
    media_files = result.scalars().all()

    await media_sort(media_files, media_group, audio, documents)

    await message.answer(
        f'SUBMITED: <b>{submission.add_date}</b>\n{submission.text}', reply_markup=keyboard,
        parse_mode='HTML')

    await media_group_send(message, media_group, audio, documents)
