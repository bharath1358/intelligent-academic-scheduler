📅 Intelligent Academic Scheduler

Intelligent Academic Scheduler is a Flask-based web application that automatically generates optimized school and college timetables.
The system ensures staff conflict avoidance, workload balancing, and proper lab session allocation using structured scheduling logic.

🚀 Features

Automatic timetable generation

Staff clash prevention

No empty periods

Weekly subject period control

Lab session allocation (2–3 continuous periods)

Role-based login system (Admin & User)

User-specific timetable management

Separate school and college scheduling logic

Responsive Bootstrap interface

🛠️ Technologies Used

Frontend:

HTML

CSS

Bootstrap

Jinja2

Backend:

Python (Flask)

Database:

MySQL / MariaDB

Tools:

Git

GitHub

📂 Project Structure

intelligent-academic-scheduler
│
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

Clone the Repository:

git clone https://github.com/bharath1358/intelligent-academic-scheduler.git

cd intelligent-academic-scheduler

Create Virtual Environment (Optional):

python -m venv venv
venv\Scripts\activate

Install Dependencies:

pip install -r requirements.txt

Setup Database:

Create a MySQL database

Import the SQL files:

database.sql

timetable.sql

staff_subjects_classes.sql

Update database credentials in config.py

Run the Application:

python app.py

Open in browser:

http://127.0.0.1:5000/

👤 Admin Capabilities

Manage users

Map staff to subjects and classes

Generate timetables

View and delete timetables

📌 Notes

Prevents staff time-slot conflicts

Ensures all periods are filled

Implements workload balancing logic

Designed to simulate real-world academic scheduling constraints

🎓 Academic Purpose

This project was developed for educational purposes to demonstrate full-stack development using Flask and MySQL with constraint-based scheduling logic.

👨‍💻 Author

Bharath K
