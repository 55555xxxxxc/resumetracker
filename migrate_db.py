import sqlite3

# Connect to your existing database
conn = sqlite3.connect('resumes.db')  # Use your database name
cursor = conn.cursor()

# --- 1. Create Users Table ---
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT CHECK(role IN ('admin','user')) DEFAULT 'user'
);
''')
print("✅ Users table created.")

# --- 2. Create Job Applications Table ---
cursor.execute('''
CREATE TABLE IF NOT EXISTS job_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL,
    company_name TEXT NOT NULL,
    status TEXT CHECK(status IN ('applied','shortlisted','interview','rejected','selected')) DEFAULT 'applied',
    notes TEXT,
    FOREIGN KEY (resume_id) REFERENCES resumes(id)
);
''')
print("✅ Job applications table created.")

conn.commit()
conn.close()
print("🎉 Database migration complete!")
