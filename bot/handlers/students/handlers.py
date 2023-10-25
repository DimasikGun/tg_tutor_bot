from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import CoursesStudents, Courses, Publications
from handlers.students import keyboards as kb
from handlers.tutors.handlers import CourseInteract, Pagination, paginator

router = Router()


@router.message(F.text == 'My courses')
async def student_courses(message: Message, session: AsyncSession):
    stmt = select(Courses).join(CoursesStudents).filter(CoursesStudents.student_id == message.from_user.id)
    result = await session.execute(stmt)
    courses = result.scalars().all()

    if courses:
        builder = InlineKeyboardBuilder()
        for course in courses:
            builder.add(InlineKeyboardButton(text=course.name, callback_data=f'course_{course.id}'))
        builder.adjust(2)
        await message.answer('Choose a course:', reply_markup=builder.as_markup())
        await message.answer('Or an option below:', reply_markup=kb.courses)
    else:
        await message.answer('You haven`t joined any courses yet', reply_markup=kb.courses)


# TODO: REFACTOR
@router.callback_query(F.data.startswith('course_'))
async def course_info(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
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


@router.callback_query(CourseInteract.pagination, Pagination.filter(F.action.in_(('prev', 'next'))))
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


@router.message(F.text == 'Publications', CourseInteract.publications)
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


class JoinCourse(StatesGroup):
    join = State()


@router.message(F.text == 'Join course')
async def add_course_start(message: Message, state: FSMContext):
    await state.set_state(JoinCourse.join)
    await message.answer('Enter a code of course', reply_markup=ReplyKeyboardRemove())


@router.message(JoinCourse.join)
async def add_course(message: Message, state: FSMContext, session: AsyncSession):
    # Extract the code from the message text
    code = message.text
    try:
        # Parse the course_id and key from the code
        course_id = int(code[6:])
        key = str(code[:6])
    except ValueError:
        await state.clear()
        await message.answer('Wrong code', reply_markup=kb.courses)
        return

    # Check if the provided course_id and key match a course in the database
    stmt = select(Courses).where(Courses.id == course_id and Courses.key == key)
    res = await session.execute(stmt)
    res = res.scalar()

    try:
        # If the course exists, get its name
        name = res.name
        # Check if there is an existing record in CoursesStudents for this user and course
        stmt = select(CoursesStudents).where(
            CoursesStudents.course_id == course_id,
            CoursesStudents.student_id == message.from_user.id
        )
        res = await session.execute(stmt)
        existing_record = res.scalar()

        if existing_record:
            # If an existing record is found, inform the user
            await message.answer(f'You`ve already joined "{name}" course', reply_markup=kb.courses)
        else:
            # If no existing record is found, clear state, create a new CoursesStudents record, and commit the changes
            await state.clear()
            await session.merge(CoursesStudents(course_id=course_id, student_id=message.from_user.id))
            await session.commit()
            await message.answer(f'You`ve just joined a "{name}" course', reply_markup=kb.courses)

    except AttributeError:
        # If there is no matching course, inform the user
        await message.answer('There is no course with such code(', reply_markup=kb.courses)
