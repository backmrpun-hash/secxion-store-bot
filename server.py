from flask import Flask, render_template, request, redirect
from firebase_admin import db
import os

# ตั้งค่าให้หา index.html ในโฟลเดอร์ปัจจุบัน
app = Flask(__name__, template_folder='.')

@app.route('/')
def index():
    try:
        # ป้องกันเว็บล่มถ้าไม่มี Path stocks ใน DB
        stocks_data = db.reference('/stocks').get()
        stocks = stocks_data if isinstance(stocks_data, dict) else {}
        return render_template('index.html', stocks=stocks)
    except Exception as e:
        return f"Database Error: {e}"

@app.route('/add_stock', methods=['POST'])
def add_stock():
    item_type = request.form.get('type')
    raw_detail = request.form.get('detail')
    
    if item_type and raw_detail:
        # แยกบรรทัด, ลบช่องว่าง, และกรองบรรทัดว่างออก
        lines = raw_detail.split('\n')
        items_to_add = [line.strip() for line in lines if line.strip()]
        
        if items_to_add:
            ref = db.reference(f'/stocks/{item_type}')
            for item in items_to_add:
                ref.push(item) # ส่งเข้า Firebase ทีละชิ้น
                
    return redirect('/')

def run_web():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
