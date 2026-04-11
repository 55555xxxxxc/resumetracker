import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import PyPDF2
import requests
from dotenv import load_dotenv

# -------------------- LOAD ENV --------------------
load_dotenv()
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")

# -------------------- APP CONFIG --------------------
app = Flask(__name__)
app.secret_key = 'super_secret_key'
DATABASE = 'resumes.db'
app.config['UPLOAD_FOLDER'] = 'resumes'

# -------------------- JOB REQUIREMENTS --------------------
JOB_REQUIREMENTS = {
    'skills': ['python', 'flask', 'sql'],
    'min_experience': 3
}

# -------------------- DATABASE HELPERS --------------------
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            email TEXT,
            skills TEXT,
            experience INTEGER,
            resume_file TEXT,
            score INTEGER,
            recommended_companies TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_id INTEGER,
            job_title TEXT,
            company TEXT,
            status TEXT DEFAULT 'Applied',
            notes TEXT,
            FOREIGN KEY(resume_id) REFERENCES resumes(id)
        )
    ''')

    conn.commit()
    conn.close()

# -------------------- PDF & SCORING --------------------
def extract_text_from_pdf(file_path):
    text = ''
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text.lower() + ' '
    return text

def calculate_score(skills_text, experience_years):
    skills_count = sum(1 for skill in JOB_REQUIREMENTS['skills'] if skill in skills_text)
    skills_score = (skills_count / len(JOB_REQUIREMENTS['skills'])) * 50
    exp_score = 30 if experience_years >= JOB_REQUIREMENTS['min_experience'] else 0
    return int(skills_score + exp_score)

# -------------------- ADZUNA API --------------------
def get_recommended_jobs(keyword):
    url = "https://api.adzuna.com/v1/api/jobs/us/search/1"
    params = {
        'app_id': ADZUNA_APP_ID,
        'app_key': ADZUNA_APP_KEY,
        'results_per_page': 5,
        'what': keyword
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            jobs = response.json().get('results', [])
            return [
                f"{job['title']} @ {job['company']['display_name']}"
                for job in jobs if job.get('company')
            ]
    except Exception as e:
        print("Adzuna API error:", e)
    return []

# -------------------- AUTH --------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        role = request.form.get('role', 'user')

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)',
                (username, email, password, role)
            )
            conn.commit()
            flash('Signup successful! Please login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or Email already exists!')
        finally:
            conn.close()

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            session['user_id'] = user['id']
            session['role'] = user['role']
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials!')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------- HOME --------------------
@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

# -------------------- DASHBOARD --------------------
@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()

    if session['role'] == 'admin':
        cursor.execute('SELECT * FROM resumes')
    else:
        cursor.execute('SELECT * FROM resumes WHERE user_id = ?', (session['user_id'],))

    resumes = cursor.fetchall()
    resumes_list = []

    for resume in resumes:
        cursor.execute('SELECT * FROM applications WHERE resume_id = ?', (resume['id'],))
        apps = cursor.fetchall()
        resume_dict = dict(resume)
        resume_dict['applications'] = apps
        resumes_list.append(resume_dict)

    conn.close()
    return render_template('index.html', resumes=resumes_list)

# -------------------- RESUME MANAGEMENT --------------------
@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        skills = request.form['skills'].lower()
        experience = int(request.form['experience'])
        resume = request.files['resume']

        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        resume_path = os.path.join(app.config['UPLOAD_FOLDER'], resume.filename)
        resume.save(resume_path)

        resume_text = extract_text_from_pdf(resume_path)
        score = calculate_score(resume_text, experience)

        # ✅ ONLY CHANGE ADDED HERE
        main_skill = skills.split(',')[0]
        recommended_jobs = get_recommended_jobs(main_skill)
        recommended = ', '.join(recommended_jobs)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO resumes
            (user_id, name, email, skills, experience, resume_file, score, recommended_companies)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], name, email, skills,
              experience, resume.filename, score, recommended))
        conn.commit()
        conn.close()

        flash('Resume added successfully with recommended jobs!')
        return redirect(url_for('index'))

    return render_template('add.html')

# -------------------- APPLICATIONS --------------------
@app.route('/add_application/<int:resume_id>', methods=['GET', 'POST'])
def add_application(resume_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        job_title = request.form['job_title']
        company = request.form['company']
        notes = request.form.get('notes', '')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO applications (resume_id, job_title, company, notes) VALUES (?, ?, ?, ?)',
            (resume_id, job_title, company, notes)
        )
        conn.commit()
        conn.close()

        flash('Application added successfully!')
        return redirect(url_for('index'))

    return render_template('add_application.html', resume_id=resume_id)

@app.route('/view_applications/<int:resume_id>')
def view_applications(resume_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM applications WHERE resume_id = ?', (resume_id,))
    applications = cursor.fetchall()
    conn.close()

    return render_template('view_applications.html',
                           applications=applications,
                           resume_id=resume_id)

@app.route('/update_application/<int:app_id>', methods=['POST'])
def update_application(app_id):
    if 'username' not in session or session['role'] != 'admin':
        flash('Only admin can update application status.')
        return redirect(url_for('index'))

    status = request.form['status']
    notes = request.form.get('notes', '')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE applications SET status = ?, notes = ? WHERE id = ?',
        (status, notes, app_id)
    )
    conn.commit()
    conn.close()

    flash('Application updated!')
    return redirect(request.referrer or url_for('index'))

# -------------------- ADMIN ROUTES --------------------
@app.route('/all_applications')
def all_applications():
    if 'username' not in session or session.get('role') != 'admin':
        flash("Only admin can view all applications")
        return redirect(url_for('index'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM applications')
    applications = cursor.fetchall()
    conn.close()

    return render_template('applications.html', applications=applications)

@app.route('/delete_all_resumes')
def delete_all_resumes():
    if 'username' not in session or session.get('role') != 'admin':
        flash("Only admin can delete resumes")
        return redirect(url_for('index'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM applications')
    cursor.execute('DELETE FROM resumes')
    conn.commit()
    conn.close()

    flash("All old resumes deleted successfully!")
    return redirect(url_for('index'))

# -------------------- RUN APP --------------------
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
