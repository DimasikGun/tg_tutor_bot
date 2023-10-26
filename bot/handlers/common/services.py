from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Publications, Courses
from handlers.common.pagination import paginator


class CourseInteract(StatesGroup):
    single_course = State()
    publications = State()
    pagination = State()


async def publications(message: Message, session: AsyncSession, state: FSMContext, kb):
    course_id = await state.get_data()
    stmt = select(Publications).where(Publications.course == course_id['course']).order_by(
        Publications.add_date.desc()).limit(5)
    res = await session.execute(stmt)
    posts = res.scalars().all()
    if posts:
        pag = paginator()
        builder = InlineKeyboardBuilder()
        for post in posts:
            builder.row(InlineKeyboardButton(text=post.title, callback_data=f'publication_{post.id}'))

        builder.row(*pag.buttons, width=2)
        await state.set_state(CourseInteract.pagination)
        await message.answer('Here is publications:', reply_markup=builder.as_markup())
    else:
        await state.clear()
        await message.answer('There is no any publications yet', reply_markup=kb.single_course)


async def create_inline_courses(courses, message, kb):
    builder = InlineKeyboardBuilder()
    for course in courses:
        builder.add(InlineKeyboardButton(text=course.name, callback_data=f'course_{course.id}'))
    builder.adjust(2)
    await message.answer('Choose a course:', reply_markup=builder.as_markup())
    await message.answer('Or an option below:', reply_markup=kb.courses)


async def course_info(callback: CallbackQuery, session: AsyncSession, state: FSMContext, kb):
    course_id = int(callback.data[7:])
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
