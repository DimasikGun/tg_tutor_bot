__all__ = ['BaseModel', 'CoursesStudents', 'Users', 'Courses',  'Media', 'Publications', 'Submissions']

from bot.db.base import BaseModel
from bot.db.users import Users, CoursesStudents
from bot.db.courses import Courses, Publications, Media, Submissions
