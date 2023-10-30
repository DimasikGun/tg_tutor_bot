from aiogram import Router, F
from aiogram.enums import ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, \
    InputMediaPhoto, InputMediaVideo, InputMediaAudio, InputMediaDocument
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db import Courses, Publications, Media, CoursesStudents
from handlers.common.pagination import pagination_handler, Pagination
from handlers.common.queries import get_students, get_code
from handlers.common.services import CourseInteract, publications, create_inline_courses, course_info, \
    single_publication
from handlers.tutors import keyboards as kb
from handlers.tutors.filters import Teacher

router = Router()


@router.message(Teacher(), F.text == 'My courses')
async def tutor_courses(message: Message, session: AsyncSession):
    stmt = select(Courses).where(Courses.teacher == message.from_user.id)
    res = await session.execute(stmt)
    courses = res.scalars().all()
    if courses:
        await create_inline_courses(courses, message, kb)
    else:
        await message.answer('You don`t have any courses for now', reply_markup=kb.courses)


@router.callback_query(Teacher(), F.data.startswith('course_'))
async def teacher_course_info(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    course_id = int(callback.data[7:])
    await course_info(callback, session, state, kb, course_id)
    code = await get_code(session, course_id)
    students = await get_students(session, course_id)
    await callback.message.answer(f'Now there are <b>{len(students) if students else "no"}</b> students\nInvite code:',
                                  parse_mode='HTML')
    await callback.message.answer(f'<b>{code}</b>',
                                  parse_mode='HTML')


@router.callback_query(Teacher(), CourseInteract.single_course, Pagination.filter(F.action.in_(('prev', 'next'))))
async def pagination_handler_teacher(query: CallbackQuery, callback_data: Pagination, session: AsyncSession,
                                     state: FSMContext):
    await pagination_handler(query, callback_data, session, state)


@router.message(Teacher(), F.text == 'Publications', CourseInteract.single_course)
async def publications_teacher(message: Message, session: AsyncSession, state: FSMContext):
    await publications(message, session, state, kb)


class AddPublication(StatesGroup):
    title = State()
    text = State()
    media = State()


@router.message(Teacher(), F.text == 'Add publication', CourseInteract.single_course)
async def add_publication_start(message: Message, state: FSMContext):
    await state.set_state(AddPublication.title)
    await message.answer('How would you like to call your publication?', reply_markup=ReplyKeyboardRemove())


@router.message(Teacher(), AddPublication.title)
async def add_publication_title(message: Message, state: FSMContext):
    if len(message.text) >= 35:
        # If the name is too long, stay in the AddCourse.name state and inform the user
        await state.set_state(AddPublication.title)
        await message.answer('Name is too long, try shorter')
    else:
        # If the name is acceptable, move to the AddCourse.confirm state
        await state.update_data(title=message.text, media=[])
        await state.set_state(AddPublication.text)
        await message.answer('Now enter a text of your publication:')


@router.message(Teacher(), AddPublication.text)
async def add_publication_text(message: Message, state: FSMContext):
    if len(message.text) >= 4096:
        # If the name is too long, stay in the AddCourse.name state and inform the user
        await state.set_state(AddPublication.text)
        await message.answer('Text is too long, try shorter')
    else:
        # If the name is acceptable, move to the AddCourse.confirm state
        await state.update_data(text=message.text)
        await state.set_state(AddPublication.media)
        await message.answer('Now send a media for your publication or press "Ready" button', reply_markup=kb.ready)


@router.message(Teacher(), F.text == 'Ready', AddPublication.media)
async def add_publication_preview(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    media_group = []
    audio = []
    documents = []

    publication = await session.merge(Publications(title=data['title'], course_id=data['course_id'], text=data['text']))
    await session.commit()
    await message.reply(
        f'Your post have been created. It will look like this:',
        reply_markup=kb.single_course)

    for media in data['media']:
        await session.merge(Media(media_type=media[0], file_id=media[1], publication=publication.id))
        await session.commit()
        if media[0] == str(ContentType.PHOTO):
            media_group.append(InputMediaPhoto(media=media[1]))
        elif media[0] == str(ContentType.VIDEO):
            media_group.append(InputMediaVideo(media=media[1]))
        elif media[0] == str(ContentType.AUDIO):
            audio.append(InputMediaAudio(media=media[1]))
        else:
            documents.append(InputMediaDocument(media=media[1]))

    await message.answer(f'<b>{data["title"]}</b>\n{data["text"]}', parse_mode='HTML')

    if media_group:
        await message.answer_media_group(media_group)
    if documents:
        await message.answer('Documents:')
        await message.answer_media_group(documents)
    if audio:
        await message.answer('Audio:')
        await message.answer_media_group(audio)
    await publications_teacher(message, session, state)


@router.message(Teacher(), AddPublication.media)
async def add_publication_media(message: Message, state: FSMContext):
    message_type = message.content_type
    data = await state.get_data()

    if message_type in (
            ContentType.VIDEO, ContentType.AUDIO, ContentType.DOCUMENT):
        file_id = eval(f"message.{message_type}.file_id")
        await state.set_state(AddPublication.media)
        media = data['media']
        media.append((str(message_type), file_id))
        await state.update_data(media=media)  # Update the 'media' key in data
        await message.answer('Media added, add more or press "Ready"')

    elif message_type == ContentType.PHOTO:
        file_id = message.photo[-1].file_id
        await state.set_state(AddPublication.media)
        media = data['media']
        media.append((str(message_type), file_id))
        await state.update_data(media=media)  # Update the 'media' key in data
        await message.answer('Media added, add more or press "Ready"')

    else:
        await state.set_state(AddPublication.media)
        await message.answer('Not supported media type, try something else')

    if len(data['media']) >= 20:
        await add_publication_preview(message, state)  # Pass the message and state to the function


@router.callback_query(Teacher(), F.data.startswith('publication_'))
async def teacher_single_publication(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await single_publication(callback, session, state, kb)
    await state.set_state(CourseInteract.single_course)
    await publications_teacher(callback.message, session, state)


class AddCourse(StatesGroup):
    name = State()
    confirm = State()


@router.message(Teacher(), F.text == 'Add course')
async def add_course_start(message: Message, state: FSMContext):
    # Set the state to AddCourse.name to collect the course name
    await state.set_state(AddCourse.name)
    await message.answer('How would you like to call your course?', reply_markup=ReplyKeyboardRemove())


@router.message(Teacher(), AddCourse.name)
async def add_course(message: Message, state: FSMContext):
    # Update the state posts with the course name
    if len(message.text) >= 30:
        # If the name is too long, stay in the AddCourse.name state and inform the user
        await state.set_state(AddCourse.name)
        await message.answer('Name is too long, try shorter')
    else:
        # If the name is acceptable, move to the AddCourse.confirm state
        await state.update_data(name=message.text)
        await state.set_state(AddCourse.confirm)
        await message.answer(f'Are you sure with name: "{message.text}"?', reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="Yes"),
                    KeyboardButton(text="No"),
                ],
                [KeyboardButton(text="Cancel")]
            ], resize_keyboard=True))


@router.message(F.text.casefold() == "cancel")
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        text="Action was cancelled",
        reply_markup=kb.courses)


@router.message(Teacher(), AddCourse.confirm, F.text.casefold() == 'yes')
async def add_course_confirmed(message: Message, session: AsyncSession, state: FSMContext):
    # Retrieve the course name from the state posts, create a new course, and commit it
    data = await state.get_data()
    await state.clear()
    await session.merge(Courses(name=data['name'], teacher=message.from_user.id))
    await session.commit()
    await message.reply(
        f'Your course "{data["name"]}" have been created',
        reply_markup=kb.courses)
    await tutor_courses(message, session)


@router.message(Teacher(), AddCourse.confirm, F.text.casefold() == 'no')
async def add_course_declined(message: Message, state: FSMContext):
    # If the user declines, return to the AddCourse.name state
    await state.set_state(AddCourse.name)
    await message.answer("Then enter a new one", reply_markup=ReplyKeyboardRemove())


@router.message(Teacher(), AddCourse.confirm)
async def add_course_unknown(message: Message):
    # Handle an unknown response in the AddCourse.confirm state
    await message.reply('I don`t get it, choose "yes", "no" or "cancel"')


class EditCourse(StatesGroup):
    name = State()
    name_confirm = State()
    delete_confirm = State()


@router.message(Teacher(), F.text == 'Edit course', CourseInteract.single_course)
async def edit_course(message: Message, state: FSMContext):
    await message.answer('Edit your course', reply_markup=kb.edit_course)
    await state.set_state(CourseInteract.single_course)


@router.message(Teacher(), F.text == 'Change name', CourseInteract.single_course)
async def change_course_name_start(message: Message, state: FSMContext):
    await state.set_state(EditCourse.name)
    await message.answer('Enter a new name for your course', reply_markup=ReplyKeyboardRemove())


@router.message(Teacher(), EditCourse.name)
async def change_course_name(message: Message, state: FSMContext):
    await add_course(message, state)
    await state.set_state(EditCourse.name_confirm)


@router.message(Teacher(), EditCourse.name_confirm, F.text.casefold() == 'yes')
async def change_course_name_confirmed(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    stmt = update(Courses).where(Courses.id == data['course_id']).values(name=data['name'])
    await session.execute(stmt)
    await session.commit()
    await message.reply(
        f'Course name have been changed to "{data["name"]}"',
        reply_markup=kb.courses)
    await tutor_courses(message, session)
    await state.set_state(CourseInteract.single_course)


@router.message(Teacher(), EditCourse.name_confirm, F.text.casefold() == 'no')
async def change_course_name_declined(message: Message, state: FSMContext):
    await message.answer("Then enter a new one", reply_markup=ReplyKeyboardRemove())
    await state.set_state(EditCourse.name)


@router.message(Teacher(), EditCourse.name_confirm)
async def add_course_unknown(message: Message):
    await message.reply('I don`t get it, choose "yes", "no" or "cancel"')


@router.message(Teacher(), F.text == 'Delete course', CourseInteract.single_course)
async def change_course_name_start(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.set_state(EditCourse.delete_confirm)
    await message.answer(f'Are you sure you want to delete your course?',
                         reply_markup=ReplyKeyboardMarkup(
                             keyboard=[
                                 [
                                     KeyboardButton(text="Yes"),
                                     KeyboardButton(text="No"),
                                 ]], resize_keyboard=True))


@router.message(Teacher(), EditCourse.delete_confirm, F.text.casefold() == 'yes')
async def change_course_name_confirmed(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    course_id = data['course_id']

    # Удаление всех студентов, связанных с курсом
    stmt = delete(CoursesStudents).where(CoursesStudents.course_id == course_id)
    await session.execute(stmt)
    # Удаление всех медиафайлов, связанных с публикациями, связанными с курсом
    stmt = delete(Media).where(
        Media.publication.in_(select(Publications.id).where(Publications.course_id == course_id)))
    await session.execute(stmt)

    stmt = delete(Publications).where(Publications.course_id == course_id)
    await session.execute(stmt)

    # Удаление курса
    stmt = delete(Courses).where(Courses.id == course_id)
    await session.execute(stmt)

    await session.commit()

    await message.reply(
        f'Course have been deleted',
        reply_markup=kb.courses)
    await tutor_courses(message, session)
    await state.set_state(CourseInteract.single_course)


@router.message(Teacher(), EditCourse.name_confirm, F.text.casefold() == 'no')
async def change_course_name_declined(message: Message, session: AsyncSession, state: FSMContext):
    await tutor_courses(message, session)
