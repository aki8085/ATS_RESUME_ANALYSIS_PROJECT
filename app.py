import os, json, requests
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database import get_db, init_db
from analyzer import analyze

app = Flask(__name__)
app.secret_key = 'ats_secret_2024_xk9'

# ── Google OAuth config ───────────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = '992933129-bmactm45foi6svhqh4acj4b345efgkdk.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET = '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'   
GOOGLE_REDIRECT_URI  = 'http://127.0.0.1:5000/google/callback'

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

with app.app_context():
    init_db()

# ── helpers ───────────────────────────────────────────────────────────────────
def logged_in():
    return 'user_id' in session

def save_history(user_id, result):
    db = get_db()
    db.execute('''INSERT INTO history
        (user_id,filename,score,word_count,tech_count,soft_count,
         missing_kw,matched_kw,suggestions,sections)
        VALUES (?,?,?,?,?,?,?,?,?,?)''', (
        user_id,
        result['filename'],
        result['score'],
        result['word_count'],
        len(result['found_tech']),
        len(result['found_soft']),
        json.dumps(result['missing_keywords']),
        json.dumps(result['matched_keywords']),
        json.dumps(result['suggestions']),
        json.dumps(result['sections'])
    ))
    db.commit()
    db.close()

def get_user_stats(user_id):
    db   = get_db()
    rows = db.execute(
        'SELECT score, missing_kw FROM history WHERE user_id=? ORDER BY created_at DESC',
        (user_id,)
    ).fetchall()
    db.close()
    if not rows:
        return {'total_scans': 0, 'avg_score': None, 'best_score': None, 'last_missing': None}
    scores       = [r['score'] for r in rows if r['score'] is not None]
    last_missing = json.loads(rows[0]['missing_kw'] or '[]')
    return {
        'total_scans':  len(rows),
        'avg_score':    round(sum(scores) / len(scores), 1) if scores else None,
        'best_score':   round(max(scores), 1)              if scores else None,
        'last_missing': len(last_missing)                  if last_missing else None
    }

# ── auth ──────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if logged_in():
        return redirect(url_for('home'))
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password'].strip()
        db   = get_db()
        user = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        db.close()
        if user and user['password'] and check_password_hash(user['password'], password):
            session['user_id']   = user['id']
            session['user_name'] = user['name']
            session['avatar']    = user['avatar'] or ''
            return redirect(url_for('home'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if logged_in():
        return redirect(url_for('home'))
    if request.method == 'POST':
        name     = request.form['name'].strip()
        email    = request.form['email'].strip().lower()
        password = request.form['password'].strip()
        db = get_db()
        if db.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone():
            flash('Email already registered.', 'error')
            db.close()
            return redirect(url_for('signup'))
        db.execute('INSERT INTO users (name,email,password) VALUES (?,?,?)',
                   (name, email, generate_password_hash(password)))
        db.commit()
        db.close()
        flash('Account created! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── Google OAuth ──────────────────────────────────────────────────────────────
@app.route('/google/login')
def google_login():
    auth_url = (
        'https://accounts.google.com/o/oauth2/v2/auth'
        f'?client_id={GOOGLE_CLIENT_ID}'
        f'&redirect_uri={GOOGLE_REDIRECT_URI}'
        f'&response_type=code'
        f'&scope=openid email profile'
        f'&prompt=select_account'
    )
    return redirect(auth_url)

@app.route('/google/callback')
def google_callback():
    code = request.args.get('code')
    if not code:
        flash('Google login failed — no code returned.', 'error')
        return redirect(url_for('login'))

    token_res = requests.post('https://oauth2.googleapis.com/token', data={
        'code':          code,
        'client_id':     GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri':  GOOGLE_REDIRECT_URI,
        'grant_type':    'authorization_code'
    })

    token_data   = token_res.json()
    print("TOKEN RESPONSE:", token_data)   # shows in terminal for debugging

    access_token = token_data.get('access_token')
    if not access_token:
        error_msg  = token_data.get('error', 'unknown')
        error_desc = token_data.get('error_description', '')
        flash(f'Google login failed: {error_msg} — {error_desc}', 'error')
        return redirect(url_for('login'))

    info      = requests.get('https://www.googleapis.com/oauth2/v2/userinfo',
                             headers={'Authorization': f'Bearer {access_token}'}).json()
    google_id = info.get('id')
    email     = info.get('email', '').lower()
    name      = info.get('name', '')
    avatar    = info.get('picture', '')

    db   = get_db()
    user = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
    if user:
        db.execute('UPDATE users SET google_id=?,avatar=? WHERE id=?',
                   (google_id, avatar, user['id']))
        db.commit()
        uid, uname = user['id'], user['name']
    else:
        cur = db.execute(
            'INSERT INTO users (name,email,google_id,avatar) VALUES (?,?,?,?)',
            (name, email, google_id, avatar)
        )
        db.commit()
        uid, uname = cur.lastrowid, name
    db.close()

    session['user_id']   = uid
    session['user_name'] = uname
    session['avatar']    = avatar
    return redirect(url_for('home'))

# ── pages ─────────────────────────────────────────────────────────────────────
@app.route('/home')
def home():
    if not logged_in():
        return redirect(url_for('login'))
    stats = get_user_stats(session['user_id'])
    return render_template('home.html',
                           name=session['user_name'],
                           avatar=session.get('avatar', ''),
                           **stats)

@app.route('/analyze', methods=['GET', 'POST'])
def analyze_page():
    if not logged_in():
        return redirect(url_for('login'))
    if request.method == 'POST':
        if 'resume' not in request.files or not request.files['resume'].filename:
            return jsonify({'error': 'No file uploaded'}), 400
        file = request.files['resume']
        ext  = file.filename.rsplit('.', 1)[-1].lower()
        if ext not in {'pdf', 'docx', 'txt'}:
            return jsonify({'error': 'Only PDF, DOCX, TXT allowed'}), 400
        fname = secure_filename(file.filename)
        path  = os.path.join(UPLOAD_FOLDER, fname)
        file.save(path)
        jd     = request.form.get('job_description', '')
        result, err = analyze(path, fname, jd)
        if err:
            return jsonify({'error': err}), 400
        save_history(session['user_id'], result)
        return jsonify(result)
    return render_template('analyze.html',
                           name=session['user_name'],
                           avatar=session.get('avatar', ''))

@app.route('/history')
def history():
    if not logged_in():
        return redirect(url_for('login'))
    db   = get_db()
    rows = db.execute(
        'SELECT * FROM history WHERE user_id=? ORDER BY created_at DESC',
        (session['user_id'],)
    ).fetchall()
    db.close()
    records = []
    for r in rows:
        records.append({
            'id':          r['id'],
            'filename':    r['filename'],
            'score':       r['score'],
            'word_count':  r['word_count'],
            'tech_count':  r['tech_count'],
            'soft_count':  r['soft_count'],
            'missing_kw':  json.loads(r['missing_kw']  or '[]'),
            'matched_kw':  json.loads(r['matched_kw']  or '[]'),
            'suggestions': json.loads(r['suggestions']  or '[]'),
            'sections':    json.loads(r['sections']     or '{}'),
            'created_at':  r['created_at']
        })
    return render_template('history.html',
                           name=session['user_name'],
                           avatar=session.get('avatar', ''),
                           records=records)

@app.route('/history/delete/<int:hid>', methods=['POST'])
def delete_history(hid):
    if not logged_in():
        return jsonify({'error': 'unauthorized'}), 401
    db = get_db()
    db.execute('DELETE FROM history WHERE id=? AND user_id=?',
               (hid, session['user_id']))
    db.commit()
    db.close()
    return jsonify({'ok': True})

if __name__ == '__main__':
    app.run(debug=True)