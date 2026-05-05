from flask import Flask, render_template, request, redirect
from firebase_admin import db
import os

app = Flask(__name__, template_folder='.')

@app.route('/')
def index():
    stocks_data = db.reference('/stocks').get()
    stocks = stocks_data if isinstance(stocks_data, dict) else {}
    return render_template('index.html', stocks=stocks)

@app.route('/add_category', methods=['POST'])
def add_category():
    cat_name = request.form.get('cat_name').strip().lower()
    if cat_name:
        # สร้างหมวดหมู่ใหม่โดยใส่ค่าเริ่มต้นไว้
        db.reference(f'/stocks/{cat_name}').update({'_init': 'placeholder'})
    return redirect('/')

@app.route('/del_category', methods=['POST'])
def del_category():
    cat_name = request.form.get('cat_name')
    if cat_name:
        db.reference(f'/stocks/{cat_name}').delete()
    return redirect('/')

@app.route('/add_stock', methods=['POST'])
def add_stock():
    item_type = request.form.get('type')
    raw_detail = request.form.get('detail')
    if item_type and raw_detail:
        items = [line.strip() for line in raw_detail.split('\n') if line.strip()]
        ref = db.reference(f'/stocks/{item_type}')
        for item in items:
            ref.push(item)
    return redirect('/')

def run_web():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
