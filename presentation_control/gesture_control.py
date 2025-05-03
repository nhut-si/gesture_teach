import time

# Các mode hoạt động
PRESENTATION_MODE = 0
DRAWING_MODE = 1
ERASING_MODE = 2

class GestureController:
    def __init__(self):
        self.current_mode = PRESENTATION_MODE
        self.last_gesture_time = 0
        self.gesture_cooldown = 0.4  # Reduced for faster response
        
    def detect_mode(self, fingers):
        current_time = time.time()
        if current_time - self.last_gesture_time < self.gesture_cooldown:
            return self.current_mode
            
        # Các cử chỉ chuyển mode
        if fingers == [0, 1, 1, 0, 0]:  # Ngón trỏ và giữa = chế độ vẽ
            self.current_mode = DRAWING_MODE
            self.last_gesture_time = current_time
        elif fingers == [0, 1, 1, 1, 0]:  # Ngón trỏ, giữa, áp út = chế độ xóa
            self.current_mode = ERASING_MODE
            self.last_gesture_time = current_time
        elif fingers == [1, 1, 0, 0, 0]:  # Ngón cái và trỏ = chế độ trình chiếu
            self.current_mode = PRESENTATION_MODE
            self.last_gesture_time = current_time
            
        return self.current_mode
        
    def get_mode_name(self):
        if self.current_mode == PRESENTATION_MODE:
            return "Trình chiếu"
        elif self.current_mode == DRAWING_MODE:
            return "Vẽ"
        elif self.current_mode == ERASING_MODE:
            return "Xóa"
        return "Không xác định"