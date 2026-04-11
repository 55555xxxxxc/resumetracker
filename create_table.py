import sqlite3

# Connect to the database (creates it if it doesn't exist)
conn = sqlite3.connect('resumes.db')
cursor = conn.cursor()

# Create the table with new columns for score and recommended companies
cursor.execute('''
CREATE TABLE IF NOT EXISTS resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    skills TEXT,
    experience INTEGER,
    resume_file TEXT,
    score INTEGER,
    recommended_companies TEXT
)
''')

# Commit changes and close connection
conn.commit()
conn.close()

print("SQLite table updated successfully!")
