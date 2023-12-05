import random
from datetime import datetime

from sqlalchemy import Column, String, Integer, ForeignKey, Text, DateTime, BigInteger
from sqlalchemy.orm import relationship

from bot.db.base import BaseModel


def generate_random_code():
    symbols = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k",
               "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z"]
    code = "".join([random.choice(symbols) for _ in range(6)])
    return code


class Courses(BaseModel):
    __tablename__ = 'courses'  # noqa

    id = Column(Integer, unique=True, nullable=False, primary_key=True, autoincrement=True)
    name = Column(String(30), nullable=False)
    key = Column(String(6), default=generate_random_code())
    teacher = Column(BigInteger, ForeignKey('users.user_id'))
    students = relationship('CoursesStudents', backref='courses')


class Publications(BaseModel):
    __tablename__ = 'publications'  # noqa

    id = Column(Integer, unique=True, nullable=False, primary_key=True, autoincrement=True)
    title = Column(String(60), nullable=False)
    text = Column(Text, nullable=True)
    course_id = Column(Integer, ForeignKey('courses.id'))
    max_grade = Column(Integer, nullable=True)
    add_date = Column(DateTime(), default=datetime.now())
    finish_date = Column(DateTime(), default=None, nullable=True)


class Submissions(BaseModel):
    __tablename__ = 'submissions'  # noqa

    id = Column(Integer, unique=True, nullable=False, primary_key=True, autoincrement=True)
    text = Column(Text, nullable=True)
    publication = Column(Integer, ForeignKey('publications.id'))
    student = Column(BigInteger, ForeignKey('users.user_id'))
    grade = Column(Integer, nullable=True)
    add_date = Column(DateTime(), default=datetime.now())
    update_date = Column(DateTime(), default=datetime.now(), onupdate=datetime.now())


class Media(BaseModel):
    __tablename__ = 'media'  # noqa

    id = Column(Integer, unique=True, nullable=False, primary_key=True, autoincrement=True)
    file_id = Column(String(120), unique=True, primary_key=True, nullable=False, autoincrement=False)
    media_type = Column(String(30), nullable=False)
    publication = Column(Integer, ForeignKey('publications.id'), nullable=True)
    submission = Column(Integer, ForeignKey('submissions.id'), nullable=True)
