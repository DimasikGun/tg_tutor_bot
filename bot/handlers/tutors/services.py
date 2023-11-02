async def student_name_builder(student):
    if student.username:
        student_name = student.first_name
    elif student.first_name:
        student_name = '@' + student.username
    else:
        student_name = f'student_{student.user_id}'
    return student_name
