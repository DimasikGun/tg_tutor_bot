import re
from datetime import datetime

from aiogram import Router, F
from aiogram.enums import ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, \
    InputMediaPhoto, InputMediaVideo, InputMediaAudio, InputMediaDocument, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db import Courses, Publications, Media, Users, CoursesStudents
from handlers.common.keyboards import choose
from handlers.common.pagination import pagination_handler, Pagination, paginator
from handlers.common.queries import get_students, get_code, delete_course, get_publications, delete_publication_query
from handlers.common.services import CourseInteract, publications, create_inline_courses, course_info, \
    single_publication
from handlers.tutors import keyboards as kb
from handlers.tutors.filters import Teacher
from handlers.tutors.services import student_name_builder

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


@router.callback_query(Teacher(), CourseInteract.single_course, Pagination.filter(F.action.in_(('prev', 'next'))),
                       Pagination.filter(F.entity_type == 'publications'))
async def pagination_handler_teacher(query: CallbackQuery, callback_data: Pagination, session: AsyncSession,
                                     state: FSMContext):
    data = await state.get_data()
    course_id = data['course_id']
    posts = await get_publications(session, course_id)
    await pagination_handler(query, callback_data, posts)


@router.message(Teacher(), F.text == 'Publications', CourseInteract.single_course)
async def publications_teacher(message: Message, session: AsyncSession, state: FSMContext):
    await publications(message, session, state, kb)


@router.callback_query(Teacher(), CourseInteract.single_course, Pagination.filter(F.action.in_(('prev', 'next'))),
                       Pagination.filter(F.entity_type == 'students'))
async def pagination_handler_students(query: CallbackQuery, callback_data: Pagination, session: AsyncSession,
                                      state: FSMContext):
    data = await state.get_data()
    course_id = data['course_id']
    students = await get_students(session, course_id)
    await pagination_handler(query, callback_data, students)


@router.message(Teacher(), F.text == 'Students', CourseInteract.single_course)
async def students(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    course_id = data['course_id']
    stmt = select(Users).join(CoursesStudents).where(Courses.id == course_id).limit(5)
    res = await session.execute(stmt)
    students = res.scalars().all()
    if students:
        pag = paginator(entity_type='students')
        builder = InlineKeyboardBuilder()
        for student in students:
            student_name = await student_name_builder(student)
            builder.row(InlineKeyboardButton(text=student_name, callback_data=f'student_{student.user_id}'))

        builder.row(*pag.buttons, width=2)
        await state.set_state(CourseInteract.single_course)
        await message.answer('Here is students:', reply_markup=builder.as_markup())
    else:
        await state.set_state(CourseInteract.single_course)
        await message.answer('There is no any students yet', reply_markup=kb.single_course)


class Students(StatesGroup):
    delete_confirm = State()


@router.callback_query(Teacher(), F.data.startswith('student_'), CourseInteract.single_course)
async def single_student(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    student_id = int(callback.data[8:])
    stmt = select(Users).where(Users.user_id == student_id)
    result = await session.execute(stmt)
    student = result.scalar()
    if student.username:
        student_name = '@' + student.username
    elif student.first_name:
        student_name = student.first_name
    else:
        student_name = callback.data
    await callback.answer()
    keyboard = choose
    keyboard.keyboard.pop()
    await callback.message.answer(f'Do you want to delete {student_name} from your course?',
                                  reply_markup=keyboard)
    await state.set_state(Students.delete_confirm)
    await state.update_data(student_id=student_id)


@router.message(Teacher(), Students.delete_confirm, F.text.casefold() == 'yes')
async def delete_student_confirmed(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    course_id = data['course_id']
    student_id = data['student_id']
    stmt = delete(CoursesStudents).where(
        CoursesStudents.course_id == course_id and CoursesStudents.user_id == student_id)
    await session.execute(stmt)
    await session.commit()
    await message.reply(
        f'User have been deleted from your course',
        reply_markup=kb.single_course)
    await state.set_state(CourseInteract.single_course)
    await students(message, session, state)


@router.message(Teacher(), Students.delete_confirm, F.text.casefold() == 'no')
async def delete_student_declined(message: Message, session: AsyncSession, state: FSMContext):
    await state.set_state(CourseInteract.single_course)
    await students(message, session, state)
    await message.answer('Or choose an option below:', reply_markup=kb.single_course)


class AddPublication(StatesGroup):
    title = State()
    text = State()
    media = State()
    date = State()
    time = State()


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
async def add_publication_ready(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()

    publication = await session.merge(Publications(title=data['title'], course_id=data['course_id'], text=data['text']))
    await session.commit()

    for media in data['media']:
        await session.merge(Media(media_type=media[0], file_id=media[1], publication=publication.id))

    await session.commit()
    await message.answer('All media have been added')
    await state.set_state(AddPublication.date)
    await state.update_data(publication_id=publication.id, date=None, time=None)
    await message.answer('Now enter finish date(dd.mm.yyyy) or press "Ready" button', reply_markup=kb.ready)


@router.message(Teacher(), AddPublication.media)
async def add_publication_media(message: Message, session: AsyncSession, state: FSMContext):
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
        await add_publication_ready(message, session, state)


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
    await message.answer('Publication has been added', reply_markup=kb.single_course)
    await publications_teacher(message, session, state)


@router.message(Teacher(), AddPublication.date)
async def add_publication_date(message: Message, session: AsyncSession, state: FSMContext):
    date_pattern = r'\d{2}.\d{2}.\d{4}'
    if message.text == 'Ready':
        await add_publication_preview(message, session, state)
    elif not re.match(date_pattern, message.text.strip()):
        await message.answer('Wrong date pattern, try again')
        await state.set_state(AddPublication.date)
    else:
        await state.set_state(AddPublication.time)
        await state.update_data(date=message.text)
        await message.answer('Now enter finish time (hh:mm) or press "Ready" button')


@router.message(Teacher(), AddPublication.time)
async def add_publication_time(message: Message, session: AsyncSession, state: FSMContext):
    time_pattern = r'\d{2}:\d{2}'
    if message.text == 'Ready':
        await add_publication_preview(message, session, state)
    elif not re.match(time_pattern, message.text.strip()):
        await message.answer('Wrong time pattern, try again')
        await state.set_state(AddPublication.time)
    else:
        await state.update_data(time=message.text)
        await add_publication_preview(message, session, state)


class PublicationInteract(StatesGroup):
    single_publication = State()


@router.callback_query(Teacher(), F.data.startswith('publication_'))
async def teacher_single_publication(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await single_publication(callback, session, state, kb)
    await callback.message.answer('Choose what to do with publication:', reply_markup=ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text='Edit'),
                KeyboardButton(text='Delete'),
            ],
            [KeyboardButton(text='Go back')]
        ], resize_keyboard=True))
    await state.set_state(PublicationInteract.single_publication)
    await state.update_data(publication_id=int(callback.data[12:]))


@router.message(Teacher(), PublicationInteract.single_publication, F.text == 'Edit')
async def edit_publication(message: Message, session: AsyncSession, state: FSMContext):
    await message.answer('Publication has been edited', reply_markup=kb.single_course)


@router.message(Teacher(), PublicationInteract.single_publication, F.text == 'Delete')
async def delete_publication(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    await delete_publication_query(session, data['publication_id'])
    await message.answer('Publication has been deleted', reply_markup=kb.single_course)
    await state.set_state(CourseInteract.single_course)
    await publications_teacher(message, session, state)


@router.message(Teacher(), PublicationInteract.single_publication, F.text == 'Go back')
async def publication_go_back(message: Message, session: AsyncSession, state: FSMContext):
    await message.answer('No further actions with publication', reply_markup=kb.single_course)
    await state.set_state(CourseInteract.single_course)
    await publications_teacher(message, session, state)


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
        await message.answer(f'Are you sure with name: "{message.text}"?', reply_markup=choose)


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
    keyboard = choose
    keyboard.keyboard.pop()
    await state.set_state(EditCourse.delete_confirm)
    await message.answer(f'Are you sure you want to delete your course?', reply_markup=keyboard)


@router.message(Teacher(), EditCourse.delete_confirm, F.text.casefold() == 'yes')
async def change_course_name_confirmed(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    course_id = data['course_id']
    await delete_course(session, course_id)
    await message.reply(
        f'Course have been deleted',
        reply_markup=kb.courses)
    await state.clear()
    await tutor_courses(message, session)


@router.message(Teacher(), EditCourse.delete_confirm, F.text.casefold() == 'no')
async def change_course_name_declined(message: Message, session: AsyncSession):
    await tutor_courses(message, session)
