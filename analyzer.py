import re
import PyPDF2
import docx

TECH_SKILLS = [
    "python","java","javascript","c++","c#","sql","mysql","postgresql","mongodb",
    "react","angular","vue","node.js","flask","django","fastapi","html","css",
    "bootstrap","tailwind","git","github","docker","kubernetes","aws","azure","gcp",
    "linux","bash","rest api","graphql","tensorflow","pytorch","machine learning",
    "deep learning","data science","excel","tableau","power bi","spark","hadoop",
    "spring","kotlin","typescript","redis","kafka","php","ruby","swift","elasticsearch"
]

SOFT_SKILLS = [
    "leadership","communication","teamwork","problem solving","analytical",
    "critical thinking","time management","adaptability","creativity",
    "collaboration","project management","attention to detail","multitasking",
    "decision making","interpersonal","presentation","negotiation","mentoring"
]

ACTION_VERBS = [
    "developed","designed","implemented","built","created","managed","led",
    "improved","optimized","analyzed","deployed","integrated","automated",
    "collaborated","delivered","achieved","reduced","increased","launched",
    "maintained","resolved","streamlined","architected"
]

SECTIONS = {
    "education":      ["education","academic","qualification","degree","university","college","b.tech","mca","bsc","msc"],
    "experience":     ["experience","employment","work history","internship","intern"],
    "skills":         ["skills","technical skills","core competencies","technologies","tools"],
    "projects":       ["projects","personal projects","academic projects","portfolio"],
    "certifications": ["certifications","certificates","courses","training","achievements"],
    "summary":        ["summary","objective","profile","about me","overview","career objective"]
}

def extract_text(path, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    try:
        if ext == 'pdf':
            text = ""
            with open(path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() or ""
            return text
        elif ext == 'docx':
            doc = docx.Document(path)
            return "\n".join(p.text for p in doc.paragraphs)
        elif ext == 'txt':
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
    except Exception as e:
        return ""
    return ""

def detect_sections(text):
    t = text.lower()
    return {s: any(k in t for k in kws) for s, kws in SECTIONS.items()}

def calculate_score(resume_text, jd_text):
    rl, jl = resume_text.lower(), jd_text.lower()
    stop = {"the","and","for","are","with","this","that","from","have","will",
            "your","our","you","all","can","was","has","been","they","their",
            "which","would","more","also","about","its","but","not","use","per"}
    jw = set(re.findall(r'\b[a-z]{3,}\b', jl)) - stop
    rw = set(re.findall(r'\b[a-z]{3,}\b', rl)) - stop
    matched = jw & rw
    jtech = [s for s in TECH_SKILLS if s in jl]
    rtech = [s for s in TECH_SKILLS if s in rl]
    mtech = set(jtech) & set(rtech)
    misstech = set(jtech) - set(rtech)
    kw_score   = (len(matched) / max(len(jw), 1)) * 60
    tech_score = (len(mtech)   / max(len(jtech), 1)) * 40 if jtech else 40
    raw = min(kw_score + tech_score, 100)
    score = round(30 + (raw / 100) * 65, 1)
    miss = list(misstech) + [w for w in sorted(jw - rw) if w not in misstech and len(w) > 4]
    return score, list(mtech), miss[:12]

def generate_suggestions(text, sections, score, missing):
    s = []
    if not sections.get("summary"):
        s.append({"priority":"high","icon":"📝","title":"Add a professional summary","detail":"3–4 lines at the top highlighting your profile and career goal."})
    if not sections.get("skills"):
        s.append({"priority":"high","icon":"🛠️","title":"Add a skills section","detail":"A dedicated skills section greatly improves ATS keyword matching."})
    if not sections.get("projects"):
        s.append({"priority":"medium","icon":"💡","title":"Add a projects section","detail":"For MCA profiles, list academic or personal projects with tech stack used."})
    if not sections.get("certifications"):
        s.append({"priority":"low","icon":"🏆","title":"Add certifications","detail":"Courses from Coursera, NPTEL, or Google boost your profile considerably."})
    if missing:
        s.append({"priority":"high","icon":"🔑","title":f"{len(missing)} keywords missing from JD","detail":f"Add these to your resume: {', '.join(missing[:8])}."})
    if score < 50:
        s.append({"priority":"high","icon":"⚠️","title":"Low match — tailor your resume","detail":"Mirror the job description language and add relevant skills."})
    elif score < 70:
        s.append({"priority":"medium","icon":"📈","title":"Moderate match — a few tweaks needed","detail":"Quantify achievements (e.g. 'improved speed by 30%') and add JD keywords."})
    verbs = [v for v in ACTION_VERBS if v in text.lower()]
    if len(verbs) < 5:
        s.append({"priority":"medium","icon":"✍️","title":"Use strong action verbs","detail":"Start bullets with: Developed, Implemented, Optimized, Designed, Led."})
    wc = len(text.split())
    if wc < 300:
        s.append({"priority":"high","icon":"📄","title":"Resume too short","detail":f"Only ~{wc} words found. Aim for 400–700 words for a 1-page resume."})
    return s

def analyze(path, filename, jd_text=""):
    text = extract_text(path, filename)
    if not text.strip():
        return None, "Could not extract text from file."
    sections = detect_sections(text)
    rl = text.lower()
    found_tech = [s for s in TECH_SKILLS if s in rl]
    found_soft = [s for s in SOFT_SKILLS if s in rl]
    if jd_text.strip():
        score, matched, missing = calculate_score(text, jd_text)
    else:
        score, matched, missing = None, [], []
    suggestions = generate_suggestions(text, sections, score or 0, missing)
    return {
        "filename":         filename,
        "score":            score,
        "sections":         sections,
        "found_tech":       found_tech,
        "found_soft":       found_soft,
        "matched_keywords": matched,
        "missing_keywords": missing,
        "suggestions":      suggestions,
        "word_count":       len(text.split())
    }, None