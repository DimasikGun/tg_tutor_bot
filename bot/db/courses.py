import random

from sqlalchemy import Column, String, Integer, ForeignKey, Text
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
    name = Column(String(60), nullable=False)
    key = Column(String(6), default=generate_random_code())
    teacher = Column(Integer, ForeignKey('users.user_id'))
    students = relationship('CoursesStudents', backref='courses')


class MediaPublications(BaseModel):
    __tablename__ = 'media_publications'  # noqa
    id = Column(Integer, unique=True, nullable=False, primary_key=True, autoincrement=True)
    media_id = Column(Integer, ForeignKey('media.id'))
    publication_id = Column(Integer, ForeignKey('publications.id'))


class Publications(BaseModel):
    __tablename__ = 'publications'  # noqa

    id = Column(Integer, unique=True, nullable=False, primary_key=True, autoincrement=True)
    title = Column(String(60), nullable=True)
    text = Column(Text, nullable=False)
    course = Column(Integer, ForeignKey('courses.id'))
    media = relationship('MediaPublications', backref='publications')


class Media(BaseModel):
    __tablename__ = 'media'  # noqa

    id = Column(Integer, unique=True, nullable=False, primary_key=True, autoincrement=True)
    file_id = Column(String(64), unique=True, primary_key=True, nullable=False, autoincrement=False)
    media_type = Column(String(12), nullable=False)
    publications = relationship('MediaPublications', backref='media')
