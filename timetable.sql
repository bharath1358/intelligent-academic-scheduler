CREATE TABLE IF NOT EXISTS timetable (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    class_name VARCHAR(50),
    day VARCHAR(20),
    period INT,
    subject_name VARCHAR(100),
    staff_name VARCHAR(100)
);
