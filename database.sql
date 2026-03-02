CREATE DATABASE IF NOT EXISTS timetable_db;
USE timetable_db;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50),
    password VARCHAR(50),
    role ENUM('admin', 'user')
);

CREATE TABLE staff (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50)
);

CREATE TABLE classes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    class_name VARCHAR(50)
);

CREATE TABLE staff_subjects_classes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    staff_name VARCHAR(100),
    subject_name VARCHAR(100),
    class_name VARCHAR(50),
    periods_per_week INT,
    user_id INT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE timetable (
    id INT AUTO_INCREMENT PRIMARY KEY,
    class_name VARCHAR(50),
    day VARCHAR(20),
    period INT,
    subject_name VARCHAR(100),
    staff_name VARCHAR(100),
    user_id INT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);