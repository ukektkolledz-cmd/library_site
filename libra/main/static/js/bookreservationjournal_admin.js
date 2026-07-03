document.addEventListener('DOMContentLoaded', function() {
    const studentRows = document.querySelectorAll('.form-row.field-student_name, .form-row.field-group_name');
    const teacherRow = document.querySelector('.form-row.field-teacher_name');

    function updateFields() {
        const selected = document.querySelector('input[name="person_type"]:checked');
        const isTeacher = selected && selected.value === 'teacher';

        studentRows.forEach(function(row) {
            row.style.display = isTeacher ? 'none' : '';
        });

        if (teacherRow) {
            teacherRow.style.display = '';
        }
    }

    const radios = document.querySelectorAll('input[name="person_type"]');
    radios.forEach(function(radio) {
        radio.addEventListener('change', updateFields);
    });

    updateFields();
});
