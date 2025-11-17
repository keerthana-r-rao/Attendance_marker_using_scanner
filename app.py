# colourapp.py — Single-file Flask QR Attendance System (FINAL)
# Hacker Theme + Popup QR Scanner (HD) + Manual Upload + Photos + Manual Mark
# Admin: admin / 1234

import os, io, csv, json
from datetime import date, datetime
from flask import Flask, request, redirect, url_for, render_template_string, session, send_file, jsonify
import qrcode
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet

# ---------------- CONFIG ----------------
ADMIN_USER = "admin"
ADMIN_PASS = "1234"
BASE = os.path.abspath(os.path.dirname(__file__))
STUDENTS_CSV = os.path.join(BASE, "students.csv")
ATTENDANCE_CSV = os.path.join(BASE, "attendance.csv")
QRCODES_DIR = os.path.join(BASE, "qrcodes")
PHOTOS_DIR = os.path.join(BASE, "photos")
ALLOWED_EXT = {"png","jpg","jpeg"}

os.makedirs(QRCODES_DIR, exist_ok=True)
os.makedirs(PHOTOS_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = "secret-change-me"

# ---------------- HELPERS ----------------
def ensure_students_csv():
    if not os.path.exists(STUDENTS_CSV):
        with open(STUDENTS_CSV, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=["id","roll","name","photo"]).writeheader()

def ensure_attendance():
    if not os.path.exists(ATTENDANCE_CSV):
        with open(ATTENDANCE_CSV, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=["date","time","id","roll","name","method","photo"]).writeheader()

def load_students():
    ensure_students_csv()
    if os.path.exists(STUDENTS_CSV):
        df = pd.read_csv(STUDENTS_CSV, dtype=str).fillna("")
    else:
        df = pd.DataFrame(columns=["id","roll","name","photo"])
    return df.to_dict(orient="records")

def save_student(record):
    ensure_students_csv()
    df = pd.read_csv(STUDENTS_CSV, dtype=str).fillna("") if os.path.exists(STUDENTS_CSV) else pd.DataFrame()
    if not df.empty and record['id'] in df['id'].values:
        df.loc[df['id']==record['id'], ['roll','name','photo']] = [record['roll'], record['name'], record['photo']]
    else:
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True) if not df.empty else pd.DataFrame([record])
    df.to_csv(STUDENTS_CSV, index=False)

def generate_qr(sid, name):
    data = json.dumps({"id": sid, "name": name})
    img = qrcode.make(data)
    path = os.path.join(QRCODES_DIR, f"{sid}.png")
    img.save(path)
    return path

def mark_attendance(sid, method="qr"):
    ensure_attendance()
    students = {s['id']: s for s in load_students()}
    if sid not in students:
        return False, "Unknown student"
    today = date.today().isoformat()
    df = pd.read_csv(ATTENDANCE_CSV, dtype=str).fillna("") if os.path.exists(ATTENDANCE_CSV) else pd.DataFrame()
    # prevent duplicates today
    if not df.empty:
        if not df[(df['date']==today) & (df['id']==sid)].empty:
            return True, f"Already marked: {students[sid]['name']}"
    now = datetime.now().strftime("%H:%M:%S")
    row = {"date": today, "time": now, "id": sid, "roll": students[sid].get('roll',''), "name": students[sid].get('name',''), "method": method, "photo": students[sid].get('photo','')}
    df2 = pd.DataFrame([row])
    df_all = pd.concat([df, df2], ignore_index=True) if not df.empty else df2
    df_all.to_csv(ATTENDANCE_CSV, index=False)
    return True, f"Marked {students[sid].get('name','')}"

def allowed_file(filename):
    return "." in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

# ---------------- HTML BASE ----------------
BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>QR Attendance - Hacker</title>
<style>
:root{--neon:#00ff66}
body{margin:0;background:#000;color:var(--neon);font-family:Consolas,monospace;padding:20px}
.card{background:#050505;border:1px solid rgba(0,255,102,0.06);padding:18px;border-radius:10px;margin-top:18px}
.btn{padding:8px 12px;border-radius:8px;background:#001100;color:var(--neon);border:1px solid #003300;text-decoration:none}
.btn2{padding:8px 12px;border-radius:8px;background:transparent;border:1px solid var(--neon);color:var(--neon);text-decoration:none}
input,select{width:100%;padding:8px;margin-top:8px;border-radius:6px;border:1px solid rgba(0,255,102,0.06);background:#000;color:var(--neon)}
.qrimg{width:96px;border-radius:6px;border:1px solid rgba(0,255,102,0.06)}
table{width:100%;border-collapse:collapse;margin-top:12px}
th,td{padding:10px;border-bottom:1px dashed rgba(0,255,102,0.04);text-align:left}
.modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);justify-content:center;align-items:center;z-index:9999}
.modal-card{background:#000;border:1px solid var(--neon);padding:18px;border-radius:10px;width:90%;max-width:520px}
.small{font-size:13px;color:#99ffb3}
.success{color:#a8ffb0}
</style>
</head>
<body>
<h2>QR Attendance - Hacker Mode</h2>
<a class='btn2' href='{{url_for("logout")}}'>Logout</a>

{{content|safe}}

<!-- POPUP QR MODAL -->
<div id='qrModal' class='modal'>
  <div class='modal-card'>
    <h3>Scan QR</h3>
    <video id='qrVideo' style='width:100%;border:1px solid rgba(0,255,102,0.06);'></video>
    <div style='margin-top:12px;text-align:left'>
      <img id='attPhoto' src='' style='width:120px;float:left;margin-right:12px;display:none;border:1px solid rgba(0,255,102,0.06);border-radius:6px'>
      <div id='attInfo' style='min-height:40px'></div>
    </div>
    <div style='clear:both;margin-top:12px;text-align:right'>
      <button class='btn2' onclick='closeQR()'>Close</button>
    </div>
  </div>
</div>

<script src="https://unpkg.com/@zxing/library@latest"></script>

<script>
let codeReader;

function openQR(){
  document.getElementById('qrModal').style.display='flex';
  startZXing();
}

function closeQR(){
  document.getElementById('qrModal').style.display='none';
  if(codeReader){ codeReader.reset(); }
}

function startZXing(){
  codeReader = new ZXing.BrowserMultiFormatReader();
  const videoElem = document.getElementById('qrVideo');

  codeReader.decodeFromVideoDevice(null, videoElem, (result, err) => {
    if(result){
      fetch('/scan_qr_detect',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({qr:result.getText()})
      })
      .then(r=>r.json())
      .then(d=>{
        alert(d.message);
      });

      closeQR();
    }
  });
}
</script>
</body>
</html>
"""

# ---------------- ROUTES ----------------
@app.route('/', methods=['GET','POST'])
def login():
    if request.method=='POST':
        if request.form.get('username')==ADMIN_USER and request.form.get('password')==ADMIN_PASS:
            session['user']=ADMIN_USER
            return redirect(url_for('home'))
    return render_template_string("""
    <style>body{background:#000;color:#00ff66;font-family:Consolas;display:flex;align-items:center;justify-content:center;height:100vh}
    .box{padding:30px;border:1px solid #006600;border-radius:10px;background:#050505;width:320px}</style>
    <div class='box'><h3>Admin Login</h3><form method='post'><input name='username' placeholder='Username'><input name='password' type='password' placeholder='Password'><button class='btn' style='width:100%;margin-top:10px'>Login</button></form></div>
    """)

@app.route('/logout')
def logout():
    session.clear();
    return redirect(url_for('login'))

@app.route('/scan_qr_detect', methods=['POST'])
def scan_qr_detect():
    payload = request.get_json() or {}
    qrdata = payload.get('qr','')
    try:
        obj = json.loads(qrdata)
        sid = obj.get('id','')
    except Exception:
        return jsonify({'message':'Invalid QR','name':'','roll':'','photo':''})
    ok,msg = mark_attendance(sid, method='qr')
    # return student info for popup
    students = {s['id']: s for s in load_students()}
    s = students.get(sid, {})
    return jsonify({'message':msg,'name':s.get('name',''),'roll':s.get('roll',''),'photo':s.get('photo','')})

@app.route('/photo/<filename>')
def photo_file(filename):
    path = os.path.join(PHOTOS_DIR, filename)
    if os.path.exists(path):
        return send_file(path)
    return ('',404)

@app.route('/home')
def home():
    if session.get('user')!=ADMIN_USER:
        return redirect(url_for('login'))

    students = load_students()
    # auto-clean attendance for deleted students
    valid_ids = {s['id'] for s in students}
    if os.path.exists(ATTENDANCE_CSV):
        df_att = pd.read_csv(ATTENDANCE_CSV, dtype=str).fillna("")
        df_att = df_att[df_att['id'].isin(valid_ids)]
        df_att.to_csv(ATTENDANCE_CSV, index=False)

    today = date.today().isoformat()
    rows = []
    if os.path.exists(ATTENDANCE_CSV):
        df = pd.read_csv(ATTENDANCE_CSV, dtype=str).fillna("")
        rows = df[df['date']==today].to_dict(orient='records')

    html = ""
    html += "<div class='card'><h3>Add Student</h3>"
    html += "<form method='post' action='"+url_for('add_student')+"' enctype='multipart/form-data'>"
    html += "<input name='id' placeholder='Student ID' required>"
    html += "<input name='roll' placeholder='Roll Number'>"
    html += "<input name='name' placeholder='Full Name' required>"
    html += "<input type='file' name='photo'>"
    html += "<div style='margin-top:8px'><button class='btn'>Add Student</button> <a class='btn2' onclick='openQR()'>Scan QR (Camera)</a></div>"
    html += "</form></div>"

    html += "<div class='card'><h3>Students</h3>"
    if not students:
        html += "<p class='small'>No students yet. Add using the form above.</p>"
    else:
        html += "<table><tr><th>ID</th><th>Roll</th><th>Name</th><th>QR</th><th>Actions</th></tr>"
        for s in students:
            html += "<tr>"
            html += f"<td>{s['id']}</td><td>{s['roll']}</td><td>{s['name']}</td>"
            qrpath = url_for('qr_file', filename=s['id']+'.png')
            html += f"<td><img class='qrimg' src='{qrpath}'></td>"
            html += "<td>"
            html += f"<a class='btn2' href='{url_for('mark_manual', sid=s['id'])}'>Mark</a> &nbsp;"
            html += f"<a class='btn2' href='{url_for('show_qr', sid=s['id'])}'>Show QR</a> &nbsp;"
            html += f"<a class='btn2' href='{url_for('delete_student', sid=s['id'])}' style='color:#ff8888;border-color:#ff8888'>Delete</a>"
            html += "</td></tr>"
        html += "</table>"
    html += "</div>"

    html += "<div class='card'><h3>Today's Attendance</h3>"
    if not rows:
        html += "<p class='small'>No records today</p>"
    else:
        html += "<table><tr><th>Time</th><th>ID</th><th>Name</th><th>Method</th></tr>"
        for r in rows:
            html += f"<tr><td>{r['time']}</td><td>{r['id']}</td><td>{r['name']}</td><td>{r['method']}</td></tr>"
        html += "</table>"
    html += "</div>"

    return render_template_string(BASE_HTML, content=html)

@app.route('/qr/<filename>')
def qr_file(filename):
    path = os.path.join(QRCODES_DIR, filename)
    if not os.path.exists(path):
        sid = filename.split('.')[0]
        generate_qr(sid, sid)
    return send_file(path)

@app.route('/show_qr/<sid>')
def show_qr(sid):
    return f"<div style='background:#000;color:#00ff66;padding:20px;min-height:100vh'><h2>{sid}</h2><img src='{url_for('qr_file', filename=sid+'.png')}' style='width:320px'><br><a href='{url_for('home')}' style='color:#00ff66'>Back</a></div>"

@app.route('/delete_student/<sid>')
def delete_student(sid):
    if os.path.exists(STUDENTS_CSV):
        df = pd.read_csv(STUDENTS_CSV, dtype=str).fillna("")
        df = df[df['id'] != sid]
        df.to_csv(STUDENTS_CSV, index=False)
    qr = os.path.join(QRCODES_DIR, f"{sid}.png")
    if os.path.exists(qr): os.remove(qr)
    if os.path.exists(ATTENDANCE_CSV):
        at = pd.read_csv(ATTENDANCE_CSV, dtype=str).fillna("")
        at = at[at['id'] != sid]
        at.to_csv(ATTENDANCE_CSV, index=False)
    return redirect(url_for('home'))

@app.route('/mark_manual/<sid>')
def mark_manual(sid):
    ok,msg = mark_attendance(sid, method='manual')
    return redirect(url_for('home'))

@app.route('/add_student', methods=['POST'])
def add_student():
    sid = request.form.get('id','').strip()
    roll = request.form.get('roll','').strip()
    name = request.form.get('name','').strip()
    if not sid or not name:
        return redirect(url_for('home'))
    photo = ''
    if 'photo' in request.files:
        f = request.files['photo']
        if f and f.filename and allowed_file(f.filename):
            ext = f.filename.rsplit('.',1)[1].lower()
            photo = f"{sid}.{ext}"
            f.save(os.path.join(PHOTOS_DIR, photo))
    save_student({'id':sid,'roll':roll,'name':name,'photo':photo})
    generate_qr(sid, name)
    return redirect(url_for('home'))

# ---------------- RUN ----------------
if __name__ == '__main__':
    ensure_students_csv()
    ensure_attendance()
    app.run(debug=True, port=5000)
