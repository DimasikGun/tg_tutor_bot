from datetime import datetime

from sqlalchemy import Column, String, DateTime, BigInteger, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship

from bot.db.base import BaseModel


class CoursesStudents(BaseModel):
    __tablename__ = 'courses_students'  # noqa
    id = Column(Integer, unique=True, nullable=False, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey('courses.id'))
    student_id = Column(Integer, ForeignKey('users.user_id'), index=True)


class Users(BaseModel):
    __tablename__ = 'users'  # noqa

    user_id = Column(BigInteger, unique=True, nullable=False, primary_key=True, autoincrement=False)  # tg user id
    username = Column(String(32), nullable=True)
    first_name = Column(String(64), nullable=True)
    second_name = Column(String(64), nullable=True)
    is_teacher = Column(Boolean, default=False)
    reg_date = Column(DateTime(), default=datetime.now())
    upd_date = Column(DateTime(), default=datetime.now(), onupdate=datetime.now())
    courses = relationship('CoursesStudents', backref='students')

    def __str__(self):
        return f'<User: {self.user_id}>'
