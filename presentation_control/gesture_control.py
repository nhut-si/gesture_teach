import time

# Các mode hoạt động
PRESENTATION_MODE = 0
DRAWING_MODE = 1
ERASING_MODE = 2

class GestureController:
    def __init__(self):
        self.current_mode = PRESENTATION_MODE
        self.last_gesture_time = 0
        # GIÁ TRỊ NÀY QUYẾT ĐỊNH ĐỘ TRỄ CHUYỂN MODE (tính bằng giây)
        self.gesture_cooldown = 0.8  # Reduced for faster response 
        
    def detect_mode(self, fingers):
        current_time = time.time()
        # Nếu chưa đủ thời gian chờ kể từ lần chuyển mode trước, giữ nguyên mode cũ
        if current_time - self.last_gesture_time < self.gesture_cooldown: 
            return self.current_mode
            
        # Các cử chỉ chuyển mode
        if fingers == [0, 1, 1, 0, 0]:  # Ngón trỏ và giữa = chế độ vẽ
            self.current_mode = DRAWING_MODE
            self.last_gesture_time = current_time # Cập nhật thời điểm chuyển mode
        elif fingers == [0, 1, 1, 1, 0]:  # Ngón trỏ, giữa, áp út = chế độ xóa
            self.current_mode = ERASING_MODE
            self.last_gesture_time = current_time # Cập nhật thời điểm chuyển mode
        elif fingers == [0, 1, 0, 0, 1]:  #trỏ và út = chế độ trình chiếu
            self.current_mode = PRESENTATION_MODE
            self.last_gesture_time = current_time # Cập nhật thời điểm chuyển mode
            
        return self.current_mode
        
    def get_mode_name(self):
        if self.current_mode == PRESENTATION_MODE:
            return "Trình chiếu"
        elif self.current_mode == DRAWING_MODE:
            return "Vẽ"
        elif self.current_mode == ERASING_MODE:
            return "Xóa"
        return "Không xác định"