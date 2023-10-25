from contextlib import suppress

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, \
    CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Courses, Publications
from handlers.tutors import keyboards as kb
from handlers.tutors.filters import Teacher

router = Router()


class CourseInteract(StatesGroup):
    single_course = State()
    publications = State()
    pagination = State()


@router.message(Teacher(), F.text == 'My courses')
async def tutor_courses(message: Message, session: AsyncSession):
    stmt = select(Courses).where(Courses.teacher == message.from_user.id)
    res = await session.execute(stmt)
    courses = res.scalars().all()
    if courses:
        builder = InlineKeyboardBuilder()
        for course in courses:
            builder.add(InlineKeyboardButton(text=course.name, callback_data=f'course_{course.id}'))
        builder.adjust(2)
        await message.answer('Choose a course:', reply_markup=builder.as_markup())
        await message.answer('Or an option below:', reply_markup=kb.courses)
    else:
        await message.answer('You don`t have any courses for now', reply_markup=kb.courses)


@router.callback_query(Teacher(), F.data.startswith('course_'))
async def teacher_course_info(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    course_id = int(callback.data[7:])
    print(course_id)
    stmt = select(Courses).where(Courses.id == course_id)
    result = await session.execute(stmt)
    course = result.scalar()
    if course:
        await state.set_state(CourseInteract.publications)
        await state.update_data(course=course_id)
        await callback.answer(f'Here is {course.name}')
        await callback.message.answer(f'Course {course.name}', reply_markup=kb.single_course)
    else:
        await callback.message.answer('Course not found', reply_markup=kb.courses)


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


@router.callback_query(Teacher(), CourseInteract.pagination, Pagination.filter(F.action.in_(('prev', 'next'))))
async def pagination_handler(query: CallbackQuery, callback_data: Pagination, session: AsyncSession, state: FSMContext):
    course_id = await state.get_data()
    stmt = select(Publications).where(Publications.course == course_id['course'])
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


@router.message(Teacher(), F.text == 'Publications', CourseInteract.publications)
async def publications(message: Message, session: AsyncSession, state: FSMContext):
    course_id = await state.get_data()
    stmt = select(Publications).where(Publications.course == course_id['course'])
    res = await session.execute(stmt)
    posts = res.scalars().all()
    if posts:
        pag = paginator()
        builder = InlineKeyboardBuilder()
        num = 0
        for post in posts:
            if num < 5:
                num += 1
                builder.row(InlineKeyboardButton(text=post.title, callback_data=f'publication_{post.id}'))

        builder.row(*pag.buttons, width=2)
        await state.set_state(CourseInteract.pagination)
        await message.answer('Here is publications:', reply_markup=builder.as_markup())
    else:
        await state.clear()
        await message.answer('There is no any publications yet', reply_markup=kb.single_course)


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
    await state.update_data(name=message.text)
    if len(message.text) >= 30:
        # If the name is too long, stay in the AddCourse.name state and inform the user
        await state.set_state(AddCourse.name)
        await message.answer('Name is too long, try shorter')
    else:
        # If the name is acceptable, move to the AddCourse.confirm state
        await state.set_state(AddCourse.confirm)
        await message.answer(f'Are you sure with name: "{message.text}"?', reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="Yes"),
                    KeyboardButton(text="No"),
                ]
            ], resize_keyboard=True))


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


@router.message(Teacher(), AddCourse.confirm, F.text.casefold() == 'no')
async def add_course_declined(message: Message, state: FSMContext):
    # If the user declines, return to the AddCourse.name state
    await state.set_state(AddCourse.name)
    await message.answer("Then enter a new one", reply_markup=ReplyKeyboardRemove())


@router.message(Teacher(), AddCourse.confirm)
async def add_course_unknown(message: Message):
    # Handle an unknown response in the AddCourse.confirm state
    await message.reply('I don`t get it, choose "yes" or "no"(')

# @router.message()
# async def echo(message: Message):
#     message_type = message.content_type
#     # photo = message.photo[-1].file_id
#
#     if message_type in (
#             ContentType.VIDEO, ContentType.ANIMATION, ContentType.AUDIO, ContentType.DOCUMENT,
#             ContentType.VOICE,
#             ContentType.VIDEO_NOTE, ContentType.STICKER):
#         file_id = eval(f"message.{message_type}.file_id")
#
#         # file_id = getattr(message, message_type + "_file_id", None)
#     elif message_type == ContentType.PHOTO:
#         file_id = message.photo[-1].file_id
#     else:
#         file_id = None
#     # Отправляем ответ
#     await message.answer(f"I don't get it(, type: {message_type} with id: {file_id}")
#     await message.answer_video(file_id)
