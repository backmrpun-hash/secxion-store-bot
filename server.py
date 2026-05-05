from flask import Flask, render_template, request, redirect
from firebase_admin import db
import os

app = Flask(__name__, template_folder='.')

# หน้าแรก: ดึงสต็อกมาโชว์
@app.route('/')
def index():
    try:
        stocks_data = db.reference('/stocks').get()
        stocks = stocks_data if stocks_data else {}
        return render_template('index.html', stocks=stocks)
    except Exception as e:
        return f"Error: {e}"

# ระบบเพิ่ม Stock
@app.route('/add_stock', methods=['POST'])
def add_stock():
    item_type = request.form.get('type')
    raw_detail = request.form.get('detail')
    
    if item_type and raw_detail:
        # แยกข้อมูลด้วยการขึ้นบรรทัดใหม่ และลบช่องว่างหัว-ท้ายบรรทัดออก
        items = [line.strip() for line in raw_detail.split('\n') if line.strip()]
        
        # วนลูปส่งเข้า Firebase ทีละอัน
        stock_ref = db.reference(f'/stocks/{item_type}')
        for item in items:
            stock_ref.push(item)
            
    return redirect('/')

def run_web():
    # Railway จะกำหนด PORT มาให้เอง ถ้าไม่มีจะใช้ 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
