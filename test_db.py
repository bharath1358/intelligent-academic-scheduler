import mysql.connector

try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",  # or your password
        database="timetable_db"
    )
    print("✅ MySQL Connected Successfully!")
except mysql.connector.Error as err:
    print("❌ Connection failed:", err)
