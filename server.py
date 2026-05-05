from flask import Flask, render_template, request, redirect
import firebase_admin
from firebase_admin import db
import os

app = Flask(__name__)

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

@app.route('/')
def index():
    users = db.reference('/users').get() or {}
    return render_template('index.html', users=users)

@app.route('/update_stock', methods=['POST'])
def update_stock():
    # โค้ดสำหรับเพิ่ม Stock ผ่านหน้าเว็บ
    return redirect('/')