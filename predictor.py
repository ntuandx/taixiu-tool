from collections import Counter, defaultdict
from sqlalchemy.orm import Session
from models import Result
import time
import logging

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaiXiuPredictor:
    def __init__(self, db: Session):
        self.db = db
        self.cache = {}  # Cache kết quả để tăng tốc
        self.cache_timeout = 30  # Cache hết hạn sau 30 giây
    
    def _get_from_cache(self, key):
        """Lấy dữ liệu từ cache"""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.cache_timeout:
                return data
        return None
    
    def _set_cache(self, key, data):
        """Lưu vào cache"""
        self.cache[key] = (data, time.time())
    
    def get_recent_results(self, limit=200, retry=3):
        """Lấy N kết quả gần nhất - có retry và cache"""
        cache_key = f"recent_{limit}"
        
        # Thử lấy từ cache
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        # Nếu không có cache, query database
        for attempt in range(retry):
            try:
                results = self.db.query(Result).order_by(Result.time.desc()).limit(limit).all()
                data = [r.result for r in reversed(results)]
                self._set_cache(cache_key, data)
                return data
            except Exception as e:
                logger.warning(f"Lần {attempt + 1}/{retry} lấy dữ liệu thất bại: {e}")
                if attempt == retry - 1:
                    raise Exception(f"Không thể lấy dữ liệu sau {retry} lần thử: {e}")
                time.sleep(1)
        return []
    
    def get_all_results(self, retry=3):
        """Lấy tất cả kết quả - có retry"""
        cache_key = "all_results"
        
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        for attempt in range(retry):
            try:
                results = self.db.query(Result).order_by(Result.time).all()
                data = [r.result for r in results]
                self._set_cache(cache_key, data)
                return data
            except Exception as e:
                logger.warning(f"Lấy all results thất bại lần {attempt + 1}: {e}")
                if attempt == retry - 1:
                    raise e
                time.sleep(1)
        return []
    
    # ==================== PHƯƠNG PHÁP 1: CẦU BỆT ====================
    def analyze_streak(self, results):
        """
        Phân tích cầu bệt hiện tại
        Trả về: (dự đoán, độ tin cậy)
        """
        if len(results) < 3:
            return None, 0
        
        # Tìm độ dài chuỗi hiện tại
        current = results[-1]
        streak = 1
        for i in range(len(results) - 2, -1, -1):
            if results[i] == current:
                streak += 1
            else:
                break
        
        # Tính độ tin cậy dựa trên độ dài chuỗi
        if streak >= 8:
            confidence = 88
            return current, confidence
        elif streak >= 6:
            confidence = 82
            return current, confidence
        elif streak >= 5:
            confidence = 78
            return current, confidence
        elif streak == 4:
            confidence = 70
            return current, confidence
        elif streak == 3:
            confidence = 60
            return current, confidence
        else:
            return None, 0
    
    # ==================== PHƯƠNG PHÁP 2: CẦU 1-1 ====================
    def analyze_alternating(self, results):
        """
        Phân tích cầu 1-1 (xen kẽ Tài-Xỉu-Tài-Xỉu)
        Trả về: (dự đoán, độ tin cậy)
        """
        if len(results) < 6:
            return None, 0
        
        # Kiểm tra 5 phiên gần nhất có xen kẽ không
        last_5 = results[-5:]
        is_alternating = all(
            last_5[i] != last_5[i+1] for i in range(4)
        )
        
        if is_alternating:
            # Cầu 1-1 đang chạy, dự đoán ngược lại phiên cuối
            prediction = 'xiu' if results[-1] == 'tai' else 'tai'
            confidence = 75
            return prediction, confidence
        
        return None, 0
    
    # ==================== PHƯƠNG PHÁP 3: CẦU 2-2 ====================
    def analyze_double_alternating(self, results):
        """
        Phân tích cầu 2-2 (2 Tài - 2 Xỉu - 2 Tài)
        Trả về: (dự đoán, độ tin cậy)
        """
        if len(results) < 8:
            return None, 0
        
        # Kiểm tra mẫu 2-2-2
        last_8 = results[-8:]
        
        # Kiểm tra pattern 2-2-2
        pattern_1 = last_8[:2]   # 2 phiên đầu
        pattern_2 = last_8[2:4]  # 2 phiên giữa 1
        pattern_3 = last_8[4:6]  # 2 phiên giữa 2
        pattern_4 = last_8[6:8]  # 2 phiên cuối
        
        # Kiểm tra pattern đặc biệt
        if (pattern_1[0] == pattern_1[1] and 
            pattern_2[0] == pattern_2[1] and
            pattern_3[0] == pattern_3[1] and
            pattern_4[0] == pattern_4[1]):
            
            # Nếu pattern 1 = pattern 3 và pattern 2 = pattern 4 và khác nhau
            if pattern_1[0] == pattern_3[0] and pattern_2[0] == pattern_4[0] and pattern_1[0] != pattern_2[0]:
                confidence = 72
                return pattern_2[0], confidence  # Dự đoán tiếp theo là pattern 2
        
        return None, 0
    
    # ==================== PHƯƠNG PHÁP 4: THỐNG KÊ TẦN SUẤT ====================
    def analyze_frequency(self, results, window=50):
        """
        Phân tích tần suất trong window phiên gần nhất
        Trả về: (dự đoán, độ tin cậy)
        """
        if len(results) < window:
            window = len(results)
        
        recent = results[-window:]
        tai_count = recent.count('tai')
        xiu_count = recent.count('xiu')
        total = len(recent)
        
        if total == 0:
            return None, 0
        
        tai_rate = tai_count / total
        diff = abs(tai_rate - 0.5) * 2  # Chênh lệch so với 50%
        
        # Chỉ dự đoán khi có chênh lệch đủ lớn
        if diff > 0.2:  # Chênh lệch > 20%
            prediction = 'tai' if tai_rate > 0.5 else 'xiu'
            # Độ tin cậy tăng theo chênh lệch
            confidence = min(82, 55 + diff * 40)
            return prediction, confidence
        
        return None, 0
    
    # ==================== PHƯƠNG PHÁP 5: PHÂN TÍCH MẪU CẦU ====================
    def analyze_pattern(self, results, pattern_length=3, min_occurrences=3):
        """
        Phân tích mẫu cầu dựa trên lịch sử
        Trả về: (dự đoán, độ tin cậy)
        """
        if len(results) < pattern_length + min_occurrences:
            return None, 0
        
        # Lấy mẫu hiện tại
        current_pattern = tuple(results[-pattern_length:])
        
        # Tìm tất cả các lần xuất hiện của mẫu này trong quá khứ
        patterns = defaultdict(list)
        
        for i in range(len(results) - pattern_length - 1):
            pattern = tuple(results[i:i+pattern_length])
            next_result = results[i+pattern_length]
            patterns[pattern].append(next_result)
        
        if current_pattern not in patterns:
            return None, 0
        
        # Thống kê kết quả tiếp theo
        next_results = patterns[current_pattern]
        total = len(next_results)
        
        if total >= min_occurrences:
            counter = Counter(next_results)
            most_common = counter.most_common(1)[0]
            prediction = most_common[0]
            # Độ tin cậy dựa trên tỷ lệ xuất hiện
            ratio = most_common[1] / total
            confidence = min(85, 50 + ratio * 40)
            return prediction, confidence
        
        return None, 0
    
    # ==================== PHƯƠNG PHÁP 6: XÁC SUẤT MARKOV ====================
    def analyze_markov(self, results, order=2, min_occurrences=3):
        """
        Phân tích Markov bậc 2 (dựa vào 2 phiên trước)
        Trả về: (dự đoán, độ tin cậy)
        """
        if len(results) < order + min_occurrences:
            return None, 0
        
        # Lấy N phiên gần nhất
        last_states = tuple(results[-order:])
        
        # Xây dựng ma trận chuyển tiếp
        transitions = defaultdict(Counter)
        
        for i in range(len(results) - order - 1):
            state = tuple(results[i:i+order])
            next_state = results[i+order]
            transitions[state][next_state] += 1
        
        if last_states not in transitions:
            return None, 0
        
        counter = transitions[last_states]
        total = sum(counter.values())
        
        if total >= min_occurrences:
            most_common = counter.most_common(1)[0]
            prediction = most_common[0]
            ratio = most_common[1] / total
            confidence = min(80, 50 + ratio * 35)
            return prediction, confidence
        
        return None, 0
    
    # ==================== PHƯƠNG PHÁP 7: PHÂN TÍCH XU HƯỚNG ====================
    def analyze_trend(self, results, window=20):
        """
        Phân tích xu hướng gần đây
        Trả về: (dự đoán, độ tin cậy)
        """
        if len(results) < window:
            return None, 0
        
        recent = results[-window:]
        
        # Đếm số lần thay đổi
        changes = 0
        for i in range(1, len(recent)):
            if recent[i] != recent[i-1]:
                changes += 1
        
        change_rate = changes / (len(recent) - 1)
        
        # Nếu tỷ lệ thay đổi thấp (< 30%), xu hướng ổn định
        if change_rate < 0.3:
            # Dự đoán theo xu hướng hiện tại
            prediction = recent[-1]
            confidence = min(75, 60 + (1 - change_rate) * 30)
            return prediction, confidence
        
        # Nếu tỷ lệ thay đổi cao (> 70%), dự đoán sẽ thay đổi
        if change_rate > 0.7:
            prediction = 'xiu' if recent[-1] == 'tai' else 'tai'
            confidence = min(70, 55 + change_rate * 20)
            return prediction, confidence
        
        return None, 0
    
    # ==================== PHƯƠNG PHÁP 8: THỐNG KÊ THEO KHUNG GIỜ ====================
    def analyze_hourly(self, results_with_time=None):
        """
        Phân tích theo khung giờ (cần có thời gian)
        TODO: Implement khi có dữ liệu thời gian từ API
        """
        return None, 0
    
    # ==================== DỰ ĐOÁN TỔNG HỢP ====================
    def predict(self, use_cache=True):
        """
        Dự đoán tổng hợp từ tất cả các phương pháp
        Trả về: dict với kết quả dự đoán và chi tiết
        """
        try:
            # Lấy dữ liệu
            results = self.get_recent_results(200)
            
            if len(results) < 10:
                return {
                    'status': 'error',
                    'message': f'Cần ít nhất 10 phiên để dự đoán (hiện có {len(results)} phiên)',
                    'predictions': []
                }
            
            # Danh sách các phương pháp dự đoán
            methods = [
                ('Cầu bệt', self.analyze_streak, 1.2),
                ('Cầu 1-1', self.analyze_alternating, 1.0),
                ('Cầu 2-2', self.analyze_double_alternating, 1.0),
                ('Tần suất 50 phiên', self.analyze_frequency, 0.9),
                ('Mẫu cầu 3 phiên', self.analyze_pattern, 1.1),
                ('Xác suất Markov', self.analyze_markov, 1.0),
                ('Xu hướng gần đây', self.analyze_trend, 0.8)
            ]
            
            predictions = []
            
            for name, func, weight in methods:
                try:
                    pred, conf = func(results)
                    if pred:
                        predictions.append({
                            'method': name,
                            'prediction': pred,
                            'confidence': conf,
                            'weight': weight
                        })
                except Exception as e:
                    logger.warning(f"Lỗi phương pháp {name}: {e}")
                    continue
            
            if not predictions:
                return {
                    'status': 'warning',
                    'message': 'Không có phương pháp nào đủ tin cậy để dự đoán',
                    'predictions': []
                }
            
            # Tính điểm weighted cho Tài và Xỉu
            tai_score = 0
            xiu_score = 0
            total_weight = 0
            
            for p in predictions:
                w = p['weight'] * (p['confidence'] / 100)
                total_weight += w
                if p['prediction'] == 'tai':
                    tai_score += w
                else:
                    xiu_score += w
            
            # Dự đoán cuối cùng
            if tai_score > xiu_score:
                final_prediction = 'tai'
                final_confidence = int((tai_score / total_weight) * 100) if total_weight > 0 else 0
            else:
                final_prediction = 'xiu'
                final_confidence = int((xiu_score / total_weight) * 100) if total_weight > 0 else 0
            
            # Giới hạn độ tin cậy
            final_confidence = min(95, final_confidence)
            
            # Lấy 3 phiên gần nhất
            last_3 = results[-3:] if len(results) >= 3 else results
            
            # Phân tích thêm: dự đoán ngược lại nếu độ tin cậy quá thấp
            if final_confidence < 55:
                # Nếu độ tin cậy thấp, đưa ra cảnh báo
                warning = "Độ tin cậy thấp, kết quả có thể không chính xác"
            else:
                warning = None
            
            return {
                'status': 'success',
                'final_prediction': final_prediction,
                'final_confidence': final_confidence,
                'last_3': last_3,
                'total_analyzed': len(results),
                'predictions': sorted(predictions, key=lambda x: x['confidence'], reverse=True),
                'tai_score': int(tai_score * 100),
                'xiu_score': int(xiu_score * 100),
                'warning': warning,
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Lỗi dự đoán: {e}")
            return {
                'status': 'error',
                'message': f'Lỗi khi dự đoán: {str(e)}',
                'predictions': []
            }
    
    def get_prediction_stats(self):
        """
        Lấy thống kê về độ chính xác của dự đoán (nếu có lưu lịch sử)
        """
        # TODO: Lưu lịch sử dự đoán vào database để đánh giá
        return {
            'total_predictions': 0,
            'correct_predictions': 0,
            'accuracy': 0
        }
    
    def clear_cache(self):
        """Xóa cache"""
        self.cache.clear()
        logger.info("Đã xóa cache")