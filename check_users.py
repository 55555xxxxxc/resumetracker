import sqlite3

conn = sqlite3.connect('resumes.db')
cursor = conn.cursor()

cursor.execute("SELECT id, username, role FROM users")
users = cursor.fetchall()

print("Users in database:")
for user in users:
    print(user)

conn.close()
