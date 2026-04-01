import requests
import random
from sqlalchemy.orm import Session
from models import Result

class DataScraper:
    def __init__(self):
        # API hiện tại đang hoạt động
        self.api_url = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=98dcda471321f689025aba3324177634"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://wtxmd52.tele68.com/'
        }
    
    def fetch_from_api(self, limit=100):
        """Lấy dữ liệu từ API"""
        try:
            response = requests.get(
                self.api_url, 
                headers=self.headers, 
                timeout=10
            )
            
            if response.status_code == 200:
                # Kiểm tra nội dung có phải JSON không
                try:
                    data = response.json()
                    return data
                except:
                    print(f"API trả về không phải JSON: {response.text[:200]}")
                    return None
            else:
                print(f"API trả về lỗi: {response.status_code}")
                return None
        except Exception as e:
            print(f"Lỗi kết nối API: {e}")
            return None
    
    def parse_data(self, raw_data):
        """Chuyển dữ liệu API thành format chuẩn"""
        results = []
        
        if not raw_data or not isinstance(raw_data, dict):
            return results
        
        items = raw_data.get('list', [])
        
        for item in items:
            result_raw = item.get('resultTruyenThong', '')
            if not result_raw:
                continue
                
            # Chuẩn hóa kết quả
            if result_raw.upper() == 'TAI':
                result = 'tai'
            elif result_raw.upper() == 'XIU':
                result = 'xiu'
            else:
                continue
            
            session = str(item.get('id', ''))
            
            results.append({
                'session': session,
                'result': result,
                'source_time': ''  # API không có thời gian
            })
        
        return results
    
    def save_to_db(self, db: Session, results):
        """Lưu vào database, tránh trùng lặp"""
        new_count = 0
        for r in results:
            existing = db.query(Result).filter(Result.session == r['session']).first()
            if not existing:
                new_result = Result(
                    session=r['session'],
                    result=r['result'],
                    source_time=r['source_time']
                )
                db.add(new_result)
                new_count += 1
        db.commit()
        return new_count
    
    def update_data(self, db: Session, limit=100):
        """Cập nhật dữ liệu mới"""
        raw_data = self.fetch_from_api(limit)
        if not raw_data:
            return 0
        results = self.parse_data(raw_data)
        if not results:
            return 0
        return self.save_to_db(db, results)

def generate_mock_data(db: Session, count=100):
    """Tạo dữ liệu mẫu (dùng test)"""
    new_count = 0
    for i in range(count):
        session = f"676{1880 - i}"
        existing = db.query(Result).filter(Result.session == session).first()
        if not existing:
            result = random.choice(['tai', 'xiu'])
            new_result = Result(session=session, result=result)
            db.add(new_result)
            new_count += 1
    db.commit()
    return new_count