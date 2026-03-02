CREATE TABLE IF NOT EXISTS staff_subjects_classes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    staff_name VARCHAR(100),
    subject_name VARCHAR(100),
    class_name VARCHAR(50),
    periods_per_week INT
);
