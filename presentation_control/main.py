import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.protobuf")
import sys
import os
import cv2
import numpy as np
import time
from hand_detector import HandDetector
from gesture_control import GestureController, PRESENTATION_MODE, DRAWING_MODE, ERASING_MODE
from drawing_utils import DrawingCanvas
# SlideController is removed
from ui.gui import AppGUI
from database import Database
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QTimer
import logging

class MainApp:
    """Main application class for GestureTeach."""
    def __init__(self):
        self.app = QApplication(sys.argv)
        # Apply a style? e.g., self.app.setStyle('Fusion')
        self.db = Database()
        if not self.db.connection or not self.db.connection.is_connected():
             # Critical error if DB connection failed on startup
             QMessageBox.critical(None, "Database Error", "Failed to connect to the database. Please check configuration and server status.\nApplication will exit.")
             logging.critical("Database connection failed on startup.")
             sys.exit(1)

        self.gui = AppGUI(self.db) # Pass DB instance to GUI

        # Webcam Initialization
        self.cap = cv2.VideoCapture(0) # Try default camera first
        if not self.cap.isOpened():
             # Try alternative camera indices if default fails? Optional.
             logging.warning("Default webcam (index 0) not found. Trying index 1...")
             self.cap = cv2.VideoCapture(1)
             if not self.cap.isOpened():
                 QMessageBox.critical(self.gui, "Webcam Error", "Failed to open default webcam (index 0 or 1).\nCheck if it is connected and not used by another application.")
                 logging.critical("Failed to open webcam (index 0 or 1).")
                 sys.exit(1)
             else:
                  logging.info("Using webcam index 1.")
        else:
            logging.info("Using default webcam index 0.")


        # Set desired webcam resolution (use constants)
        self.WEBCAM_WIDTH = 1280
        self.WEBCAM_HEIGHT = 720
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.WEBCAM_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.WEBCAM_HEIGHT)
        # Verify resolution if needed
        actual_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if actual_width != self.WEBCAM_WIDTH or actual_height != self.WEBCAM_HEIGHT:
             logging.warning(f"Webcam resolution set to {actual_width}x{actual_height}, requested {self.WEBCAM_WIDTH}x{self.WEBCAM_HEIGHT}.")
             # Update dimensions if they differ significantly?
             self.WEBCAM_WIDTH = int(actual_width)
             self.WEBCAM_HEIGHT = int(actual_height)
        else:
             logging.info(f"Webcam resolution set to {self.WEBCAM_WIDTH}x{self.WEBCAM_HEIGHT}.")


        # Hand Detection and Gesture Control Initialization
        self.detector = HandDetector(min_detection_confidence=0.8, max_hands=1) # Detect one hand for simplicity
        self.gesture_controller = GestureController()

        # Drawing Canvas Initialization (Match webcam and target slide dimensions)
        self.SLIDE_WIDTH = 1920
        self.SLIDE_HEIGHT = 1080
        self.drawing_canvas = DrawingCanvas(slide_width=self.SLIDE_WIDTH, slide_height=self.SLIDE_HEIGHT,
                                            webcam_width=self.WEBCAM_WIDTH, webcam_height=self.WEBCAM_HEIGHT)
        self.gui.set_drawing_canvas(self.drawing_canvas) # Link canvas instance to GUI

        # Timing and Control Variables
        self.last_action_time = 0       # For debouncing major actions (slide change, screenshot, etc.)
        self.action_cooldown = 0.7      # Cooldown in seconds for major actions
        self.last_color_change_time = 0 # Specific cooldown for color change
        self.color_change_delay = 0.7   # Cooldown for color change
        self.last_draw_action_time = 0  # Tracks continuity for drawing/erasing
        self.min_draw_interval = 0.02   # Throttling for drawing

        self.last_mode = None           # Track previous mode for logging/state changes
        self.frame_count = 0
        self.frame_skip = 1             # Process every N frames (1 = process all)

        # Main Processing Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.process_frame)
        # Timer interval (milliseconds). Lower value = higher FPS attempt, more CPU. 33ms = ~30fps, 20ms = ~50fps
        self.TIMER_INTERVAL_MS = 30
        self.timer.start(self.TIMER_INTERVAL_MS)

        logging.info("MainApp initialized successfully.")

    def process_frame(self):
        """Process a single webcam frame for gestures and updates."""
        start_time = time.time() # For performance monitoring

        # Skip processing if user is not logged in
        if self.gui.current_user_id is None:
            # Still read frame to keep buffer clear, but don't process
            success, _ = self.cap.read()
            if not success:
                 logging.warning("Cannot read frame while logged out.")
            return # Exit processing for this frame

        self.frame_count += 1
        if self.frame_count % self.frame_skip != 0:
             # Read frame even if skipping to clear buffer
             success, _ = self.cap.read()
             return # Skip frame processing

        # --- Read Webcam Frame ---
        success, img = self.cap.read()
        if not success or img is None:
            logging.error("Cannot read frame from webcam.")
            # Attempt to recover or notify user?
            return

        # --- Process Frame for Hands ---
        img = self.process_webcam_frame(img) # Flip horizontally, find hands, draw landmarks
        lm_list = self.detector.find_position(img, draw=False) # Get landmarks (already scaled to img dimensions)
        fingers = self.detector.fingers_up(lm_list) if lm_list else [0, 0, 0, 0, 0]

        # --- Handle Gestures ---
        self.handle_gestures(fingers, lm_list, img) # Pass landmarks to avoid recalculation

        # --- Update GUI Display ---
        self.update_display(img)

        # Performance Logging (Optional)
        elapsed_time = time.time() - start_time
        # logging.debug(f"Frame processing time: {elapsed_time:.4f} seconds")


    def process_webcam_frame(self, img):
        """Process webcam frame: flip and find hands."""
        # Flip horizontally for intuitive control
        img = cv2.flip(img, 1)
        # Detect hands and draw landmarks directly onto the image
        img = self.detector.find_hands(img, draw=True) # Draw landmarks for visual feedback
        return img

    def handle_gestures(self, fingers, lm_list, img):
        """Handle detected gestures based on the current mode."""
        current_mode = self.gesture_controller.detect_mode(fingers)
        mode_name = self.gesture_controller.get_mode_name()

        # Handle mode change
        if self.last_mode != mode_name:
            logging.info(f"Mode changed to: {mode_name}")
            self.gui.update_mode(mode_name) # Update GUI label first
            self.last_mode = mode_name
            # Reset drawing points when mode changes to prevent artifacts
            self.drawing_canvas.reset_points(mode=self.gui.drawing_mode, blackboard_mode=self.gui.is_blackboard_mode()) # Pass current state
            self.last_draw_action_time = 0
            self.gui.show_toast(f"Mode: {mode_name}") # Announce mode change


        current_time = time.time()
        # Check if cooldown period has passed for major actions
        can_perform_action = (current_time - self.last_action_time) > self.action_cooldown
        can_draw_or_erase = (current_time - self.last_draw_action_time) > self.min_draw_interval

        # --- Presentation Mode Logic ---
        if current_mode == PRESENTATION_MODE:
            self.drawing_canvas.reset_points(mode=self.gui.drawing_mode, blackboard_mode=self.gui.is_blackboard_mode()) # Ensure clean state
            self.last_draw_action_time = 0

            # Next Slide: Index finger up [0, 1, 0, 0, 0]
            if fingers == [0, 1, 0, 0, 0] and can_perform_action:
                if self.gui.navigate_slide(1): # navigate_slide returns True if successful
                   self.last_action_time = current_time
                   logging.info("Gesture: Next slide")
                   # self.gui.show_toast("Next slide") # Optional feedback

            # Previous Slide: Thumb up [1, 0, 0, 0, 0]
            elif fingers == [1, 0, 0, 0, 0] and can_perform_action:
                if self.gui.navigate_slide(-1):
                    self.last_action_time = current_time
                    logging.info("Gesture: Previous slide")
                    # self.gui.show_toast("Previous slide")

            # Screenshot: Thumb, Index, Middle fingers up [1, 1, 1, 0, 0]
            elif fingers == [1, 1, 1, 0, 0] and can_perform_action:
                self.gui.take_screenshot() # Shows its own toast/message
                self.last_action_time = current_time
                logging.info("Gesture: Screenshot taken")

            # Toggle Fullscreen: Middle and Ring fingers up [0, 0, 1, 1, 0]
            elif fingers == [0, 0, 1, 1, 0] and can_perform_action:
                self.gui.toggle_fullscreen() # Shows its own toast
                self.last_action_time = current_time
                logging.info("Gesture: Toggled fullscreen")

        # --- Drawing Mode Logic ---
        elif current_mode == DRAWING_MODE:
            # Set brush properties (could optimize by setting only if changed)
            self.drawing_canvas.set_brush_size(self.gui.brush_size_slider.value())
            # Opacity setting REMOVED
            # self.drawing_canvas.set_opacity(self.gui.opacity_slider.value())

            # Draw with Index finger [X, 1, X, X, X] (check only index finger [1])
            if fingers[1] == 1 and lm_list and len(lm_list) > 8: # Check index finger tip landmark exists
                 if can_draw_or_erase: # Apply throttle
                    x_raw, y_raw = lm_list[8][1], lm_list[8][2] # Raw coords from webcam frame

                    # Normalize coordinates to a virtual space (e.g., 800x600)
                    x_norm = min(max(int(x_raw * 800 / self.WEBCAM_WIDTH), 0), 799)
                    y_norm = min(max(int(y_raw * 600 / self.WEBCAM_HEIGHT), 0), 599)

                    drawing_mode = self.gui.drawing_mode
                    draw_location = self.gui.draw_location
                    blackboard_mode = self.gui.is_blackboard_mode()

                    # --- Perform Drawing ---
                    # draw() and draw_on_webcam() add to current_annotations internally
                    if draw_location in ['slide', 'both']:
                        self.drawing_canvas.draw(x_norm, y_norm, mode=drawing_mode, blackboard_mode=blackboard_mode)
                    if draw_location in ['webcam', 'both']:
                        self.drawing_canvas.draw_on_webcam(x_norm, y_norm, mode=drawing_mode, blackboard_mode=blackboard_mode)

                    self.last_draw_action_time = current_time # Mark that drawing happened

            # If index finger is down, finalize shape drawing
            else:
                # Check if we were drawing recently to finalize
                if self.last_draw_action_time != 0:
                    logging.debug("Index finger down/lost in Drawing Mode, finalizing shape.")
                    drawing_mode = self.gui.drawing_mode
                    blackboard_mode = self.gui.is_blackboard_mode()
                    # reset_points finalizes shapes and clears start/end points
                    # It adds the final shape annotation to current_annotations
                    self.drawing_canvas.reset_points(mode=drawing_mode, blackboard_mode=blackboard_mode)
                    self.last_draw_action_time = 0 # Reset draw timer


            # Change Color: All fingers up [1, 1, 1, 1, 1]
            can_change_color = (current_time - self.last_color_change_time) > self.color_change_delay
            if all(fingers) and can_change_color:
                self.drawing_canvas.change_color()
                self.last_color_change_time = current_time
                color_name = self.drawing_canvas.get_current_color_name(blackboard_mode=self.gui.is_blackboard_mode())
                self.gui.update_color(color_name) # Updates label and shows toast
                logging.info(f"Gesture: Color changed to {color_name}")

        # --- Erasing Mode Logic ---
        elif current_mode == ERASING_MODE:
            # Erase with Index finger [X, 1, X, X, X]
            if fingers[1] == 1 and lm_list and len(lm_list) > 8:
                 if can_draw_or_erase: # Apply throttle
                    x_raw, y_raw = lm_list[8][1], lm_list[8][2]
                    # Normalize coordinates same as drawing
                    x_norm = min(max(int(x_raw * 800 / self.WEBCAM_WIDTH), 0), 799)
                    y_norm = min(max(int(y_raw * 600 / self.WEBCAM_HEIGHT), 0), 599)

                    # erase() acts on both canvases internally and adds annotation
                    self.drawing_canvas.erase(x_norm, y_norm)
                    self.last_draw_action_time = current_time # Mark erase action

            else:
                # Reset points if finger goes down (less critical for erase, but good practice)
                if self.last_draw_action_time != 0:
                     self.drawing_canvas.reset_points(mode="pen") # Reset pen state
                     self.last_draw_action_time = 0

            # Clear Canvas: All fingers up [1, 1, 1, 1, 1]
            if all(fingers) and can_perform_action:
                logging.info("Gesture: Clear canvas detected.")
                # clear_canvas clears visuals and adds annotation
                self.drawing_canvas.clear_canvas()
                self.last_action_time = current_time # Apply cooldown
                logging.info("Canvas cleared visually, 'clear_canvas' annotation added.")
                self.gui.show_toast("Canvas cleared")


    def update_display(self, img_webcam):
        """Update the GUI with the current slide (including drawings) and webcam feed."""
        # --- Prepare Slide Display ---
        slide_img_original = self.gui.get_current_slide() # Get original (e.g., 1920x1080 BGR)

        # Prepare the final image to be displayed on the slide label using the GUI's method
        # This ensures consistent preparation logic (blackboard + masked drawing overlay)
        slide_display_final = self.gui.prepare_display_image(slide_img_original)

        # Update the slide label in the GUI
        self.gui.update_slide(slide_display_final) # Passes the combined image

        # --- Prepare Webcam Display ---
        # Webcam image 'img_webcam' already has landmarks drawn
        webcam_canvas = self.drawing_canvas.webcam_canvas # 1280x720
        webcam_preview = self.drawing_canvas.get_webcam_preview() # 1280x720

        # Make a copy to draw overlay onto
        img_display_final = img_webcam.copy()

        # Combine webcam canvas and preview
        webcam_canvas_combined = cv2.bitwise_or(webcam_canvas, webcam_preview)

        # Overlay drawings using masking if dimensions match and drawing exists
        if img_display_final.shape == webcam_canvas_combined.shape and \
           img_display_final.dtype == webcam_canvas_combined.dtype :
           # Check if there is anything to overlay
           if cv2.countNonZero(cv2.cvtColor(webcam_canvas_combined, cv2.COLOR_BGR2GRAY)) > 0:
                try:
                    # Create mask for webcam drawings/erase
                    img2gray_wc = cv2.cvtColor(webcam_canvas_combined, cv2.COLOR_BGR2GRAY)
                    ret_wc, mask_wc = cv2.threshold(img2gray_wc, 0, 255, cv2.THRESH_BINARY)
                    mask_inv_wc = cv2.bitwise_not(mask_wc)

                    # Black-out area on webcam feed
                    img_bg_wc = cv2.bitwise_and(img_display_final, img_display_final, mask=mask_inv_wc)
                    # Get drawing/erase pixels
                    img_fg_wc = cv2.bitwise_and(webcam_canvas_combined, webcam_canvas_combined, mask=mask_wc)
                    # Combine
                    img_display_final = cv2.add(img_bg_wc, img_fg_wc)

                except cv2.error as e:
                    logging.error(f"OpenCV error combining webcam and canvas (masked): {e}")
                    # img_display_final remains the original 'img_webcam' as fallback
        # else: # Log mismatch if shapes/types are different
        #      if img_display_final.shape != webcam_canvas_combined.shape or \
        #         img_display_final.dtype != webcam_canvas_combined.dtype:
        #           logging.warning(f"Shape/dtype mismatch preventing webcam overlay: Cam={img_webcam.shape}/{img_webcam.dtype}, WC_Canvas_Combined={webcam_canvas_combined.shape}/{webcam_canvas_combined.dtype}")

        # Update the webcam label in the GUI
        self.gui.update_frame(img_display_final)

    def run(self):
        """Initialize and run the application."""
        exit_code = 0 # Default exit code
        try:
            self.gui.show()
            logging.info("GestureTeach Application GUI is now showing.")
            exit_code = self.app.exec_() # Start PyQt event loop
            logging.info(f"Application exited with code {exit_code}.")
        except SystemExit as e:
             logging.info(f"Application exited via SystemExit with code {e.code}.")
             exit_code = e.code if e.code is not None else 0
        except Exception as e:
            logging.critical(f"Unhandled exception in run method: {e}", exc_info=True)
            exit_code = 1 # Indicate error exit
        finally:
            # --- Cleanup Resources ---
            logging.info("Starting resource cleanup...")
            if hasattr(self, 'timer') and self.timer.isActive():
                self.timer.stop()
                logging.info("Processing timer stopped.")
            if hasattr(self, 'cap') and self.cap.isOpened():
                self.cap.release()
                logging.info("Webcam released.")
            cv2.destroyAllWindows() # Close any OpenCV windows
             # Save annotations before closing DB
            if hasattr(self, 'gui') and self.gui.current_user_id:
                 logging.info("Attempting final annotation save during cleanup...")
                 self.gui.save_current_annotations()
            if hasattr(self, 'db'):
                self.db.close() # Close database connection (logs internally)
            logging.info("Cleanup finished.")
            sys.exit(exit_code)

if __name__ == "__main__":
    # Setup logging (configure once at the start)
    log_format = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    # Use os.path.join for cross-platform compatibility
    log_dir = "logs" # Define log directory name
    try:
        os.makedirs(log_dir, exist_ok=True) # Create logs dir if needed
        log_filename = os.path.join(log_dir, 'gesture_teach.log') # Path to log file
    except OSError as e:
         print(f"Error creating log directory '{log_dir}': {e}. Logging disabled.", file=sys.stderr)
         log_filename = None # Disable file logging if dir fails

    log_handlers = [logging.StreamHandler(sys.stdout)] # Always log to console
    if log_filename:
         log_handlers.append(logging.FileHandler(log_filename, mode='a', encoding='utf-8')) # Add file handler if path is valid

    logging.basicConfig(level=logging.INFO, # Or DEBUG for more details
                        format=log_format,
                        handlers=log_handlers)

    # Set console handler level (if needed)
    # for handler in logging.getLogger().handlers:
    #     if isinstance(handler, logging.StreamHandler):
    #         handler.setLevel(logging.INFO)

    logging.info("========================================")
    logging.info("Starting GestureTeach Application")
    logging.info(f"Log file: {log_filename if log_filename else 'Disabled'}")
    logging.info("========================================")

    main_app = MainApp()
    main_app.run()