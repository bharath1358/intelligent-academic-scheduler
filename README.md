📅 Intelligent Academic Scheduler

Intelligent Academic Scheduler is a Flask-based web application designed to automatically generate optimized school and college timetables. The system intelligently assigns staff and subjects, prevents scheduling conflicts, balances workload, and handles lab session allocation using structured constraint-based logic.

🚀 Features

AI-style automated timetable generation
Staff clash prevention
Workload balancing per class and per staff
No empty periods in timetable
Lab session allocation (2–3 continuous periods)
Weekly subject period control
Role-based authentication (Admin & User)
User-specific timetable management
Separate school and college scheduling logic
Simple and responsive user interface

🛠️ Technologies Used

Frontend: HTML, CSS, Bootstrap
Backend: Flask (Python)
Database: MySQL / MariaDB
Templating Engine: Jinja2
Version Control: Git & GitHub

📂 Project Structure

intelligent-academic-scheduler/
├── app.py
├── config.py
├── requirements.txt
├── database.sql
├── timetable.sql
├── staff_subjects_classes.sql
├── templates/
├── static/
└── README.md

⚙️ Installation & Setup

Clone the Repository

git clone https://github.com/bharath1358/intelligent-academic-scheduler.git

cd intelligent-academic-scheduler

(Optional) Create Virtual Environment

python -m venv venv
venv\Scripts\activate

Install Python Dependencies

pip install -r requirements.txt

Setup MySQL Database

Create a new MySQL database

Import the following SQL files:

database.sql

timetable.sql

staff_subjects_classes.sql

Update database credentials in config.py

Run the Application

python app.py

Open in browser:

http://127.0.0.1:5000/

👤 Admin Panel

Create admin account through registration or database setup.

Admin Capabilities:

Manage users
Map staff to subjects and classes
Generate timetables automatically
View and delete timetables
Control school and college mode

📌 Notes

Ensures staff are not assigned to multiple classes at the same time
Guarantees all periods are filled
Implements workload distribution constraints
Designed to simulate real-world academic scheduling complexity

🎓 Academic Purpose

This project is developed for educational purposes to demonstrate full-stack web development using Flask and MySQL with constraint-based scheduling logic and database-driven design.

👨‍💻 Author

Bharath K
