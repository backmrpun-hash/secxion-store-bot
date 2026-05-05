from flask import Flask, render_template, request, redirect
from firebase_admin import db
import os

# ตั้งค่าให้หา HTML ในโฟลเดอร์ปัจจุบัน
app = Flask(__name__, template_folder='.')

@app.route('/')
def index():
    try:
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
        # แยกบรรทัด ตัดช่องว่าง และกรองบรรทัดว่างออก
        items = [line.strip() for line in raw_detail.split('\n') if line.strip()]
        
        if items:
            ref = db.reference(f'/stocks/{item_type}')
            for item in items:
                ref.push(item) # เพิ่มเข้า Firebase ทีละบรรทัด
                
    return redirect('/')

def run_web():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
