from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from sqlalchemy import desc
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import requests
from contextlib import contextmanager

from database import engine, SessionLocal
from models import Base, Result
from scraper import DataScraper, generate_mock_data
from predictor import TaiXiuPredictor  # ← THÊM DÒNG NÀY (import predictor)

# Tạo bảng database
Base.metadata.create_all(bind=engine)

# ==================== KHỞI TẠO APP ====================
app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

scraper = DataScraper()

# ==================== QUẢN LÝ DATABASE ====================

@contextmanager
def get_db_connection():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==================== TỰ ĐỘNG CẬP NHẬT ====================

def auto_fetch_data():
    try:
        with get_db_connection() as db:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 Đang tự động cập nhật...")
            new_count = scraper.update_data(db, 100)
            if new_count > 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Đã thêm {new_count} bản ghi mới")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 📭 Không có dữ liệu mới")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Lỗi: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=auto_fetch_data, trigger="interval", seconds=30, id="auto_fetch_job")
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ==================== API ENDPOINTS ====================

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/data/fetch', methods=['POST'])
def fetch_data():
    try:
        with get_db_connection() as db:
            new_count = scraper.update_data(db, 100)
            return jsonify({'status': 'success', 'new_records': new_count, 'message': f'Đã thêm {new_count} bản ghi'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/data/mock', methods=['POST'])
def create_mock():
    try:
        with get_db_connection() as db:
            new_count = generate_mock_data(db, 100)
            return jsonify({'status': 'success', 'new_records': new_count, 'message': f'Đã tạo {new_count} bản ghi mẫu'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/data/history', methods=['GET'])
def get_history():
    try:
        with get_db_connection() as db:
            limit = request.args.get('limit', 50, type=int)
            results = db.query(Result).order_by(desc(Result.time)).limit(limit).all()
            data = [{
                'id': r.id, 
                'session': r.session, 
                'result': r.result, 
                'time': r.time.strftime('%Y-%m-%d %H:%M:%S') if r.time else None
            } for r in results]
            total = db.query(Result).count()
            return jsonify({'status': 'success', 'data': data, 'total': total})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/data/delete', methods=['DELETE'])
def delete_data():
    try:
        confirm = request.json.get('confirm', False) if request.json else False
        if not confirm:
            return jsonify({'status': 'error', 'message': 'Cần xác nhận'}), 400
        with get_db_connection() as db:
            count = db.query(Result).delete()
            db.commit()
            return jsonify({'status': 'success', 'deleted': count, 'message': f'Đã xóa {count} bản ghi'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ==================== THÊM ENDPOINT DỰ ĐOÁN VÀO ĐÂY ====================

@app.route('/api/predict', methods=['GET'])
def get_prediction():
    """Dự đoán phiên tiếp theo"""
    try:
        with get_db_connection() as db:
            predictor = TaiXiuPredictor(db)
            result = predictor.predict()
            return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ==================== KẾT THÚC ====================

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 TOOL TÀI XỈU - DỰ ĐOÁN THÔNG MINH")
    print("=" * 50)
    print("📁 Database: instance/taixiu.db")
    print("⏰ Tự động cập nhật API mỗi 30 giây")
    print("🎯 Dự đoán phiên tiếp theo")
    print("🌐 Truy cập: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)