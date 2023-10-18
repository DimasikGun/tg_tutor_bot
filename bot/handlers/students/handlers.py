from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import CoursesStudents, Courses
from handlers.students import keyboards as kb

router = Router()


@router.message(F.text == 'My courses')
async def student_courses(message: Message, session: AsyncSession):
    stmt = select(CoursesStudents).where(CoursesStudents.student_id == message.from_user.id)
    res = await session.execute(stmt)
    if res.all():
        await message.answer('Here are your courses:', reply_markup=kb.courses)
    else:
        await message.answer('You haven`t joined any courses yet', reply_markup=kb.courses)


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
    # Parse the course_id and key from the code
    course_id = int(code[6:])
    key = str(code[:6])

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

