from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Courses
from handlers.common.pagination import Pagination, pagination_handler
from handlers.common.services import CourseInteract, publications, create_inline_courses, course_info
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
    await course_info(callback, session, state, kb)


@router.callback_query(Teacher(), CourseInteract.pagination, Pagination.filter(F.action.in_(('prev', 'next'))))
async def pagination_handler_admin(query: CallbackQuery, callback_data: Pagination, session: AsyncSession,
                                   state: FSMContext):
    await pagination_handler(query, callback_data, session, state)


@router.message(Teacher(), F.text == 'Publications', CourseInteract.publications)
async def publications_teacher(message: Message, session: AsyncSession, state: FSMContext):
    await publications(message, session, state, kb)


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
