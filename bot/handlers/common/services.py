from contextlib import suppress

from aiogram.enums import ContentType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, InputMediaVideo, \
    InputMediaAudio, InputMediaDocument
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from db.queries import get_user, get_publications, get_course_by_id, get_single_publication, \
    get_single_submission_by_student_and_publication, get_media


async def student_name_builder(student):
    if student.username:
        student_name = student.first_name
    elif student.first_name:
        student_name = '@' + student.username
    else:
        student_name = f'student_{student.user_id}'
    return student_name


async def submission_name_builder(session, student_id):
    user = await get_user(session, student_id)
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
            return
    else:
        if page_num > 0:
            page = page_num - 1
        else:
            page = 0
            await query.answer('This is the first page')
            return

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
        elif callback_data.entity_type == 'courses':
            for i in range(start_index, end_index):
                builder.row(InlineKeyboardButton(text=records[i].name, callback_data=f'course_{records[i].id}'))
        else:
            for i in range(start_index, end_index):
                student_name = await submission_name_builder(session, records[i].student)
                builder.row(InlineKeyboardButton(text=student_name, callback_data=f'submission_{records[i].id}'))

        builder.row(*pag.buttons, width=2)
        await query.message.edit_reply_markup(reply_markup=builder.as_markup())
    await query.answer()


class CourseInteract(StatesGroup):
    single_course = State()


async def create_inline_courses(courses, message, kb):
    if courses:
        pag = paginator(entity_type='courses')
        builder = InlineKeyboardBuilder()
        for course in courses:
            builder.row(InlineKeyboardButton(text=course.name, callback_data=f'course_{course.id}'))

        builder.row(*pag.buttons, width=2)
        await message.answer('Here is courses:', reply_markup=builder.as_markup())
        await message.answer('Or an option below:', reply_markup=kb.courses)
    else:
        await message.answer('You don`t have any courses for now', reply_markup=kb.courses)


async def publications(message: Message, session: AsyncSession, state: FSMContext, kb):
    data = await state.get_data()
    posts = await get_publications(session, data['course_id'], 5)
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


async def course_info(callback: CallbackQuery, session: AsyncSession, state: FSMContext, kb, course_id):
    course = await get_course_by_id(session, course_id)
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
    publication = await get_single_publication(session, publication_id)
    if publication.max_grade:
        if user == 'student':
            submission = await get_single_submission_by_student_and_publication(session, publication_id,
                                                                                callback.message.from_user.id)
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
    else:
        if user == 'teacher':
            await callback.message.answer(f'Here is publication', reply_markup=kb.publication_interact_unsubmitable)
        else:
            await callback.message.answer(f'Here is publication', reply_markup=kb.single_course)

    media_files = await get_media(session, publication_id)

    if media_files:
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

    media_files = await get_media(session, submission_id=submission.id)

    if media_files:
        await media_sort(media_files, media_group, audio, documents)

    await message.answer(
        f'SUBMITED: <b>{submission.add_date}</b>\n{submission.text}', reply_markup=keyboard,
        parse_mode='HTML')

    await media_group_send(message, media_group, audio, documents)
