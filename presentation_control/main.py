import cv2
import numpy as np
import time
from hand_detector import HandDetector
from gesture_control import GestureController, PRESENTATION_MODE, DRAWING_MODE, ERASING_MODE
from drawing_utils import DrawingCanvas
# SlideController is removed
from ui.gui import AppGUI # Ensure 'ui' is the correct package/folder name
from database import Database
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QTimer
import sys
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
             QMessageBox.critical(self.gui, "Webcam Error", "Failed to open default webcam (index 0).\nCheck if it is connected and not used by another application.")
             logging.critical("Failed to open webcam (index 0).")
             sys.exit(1)

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
             # self.WEBCAM_WIDTH = int(actual_width)
             # self.WEBCAM_HEIGHT = int(actual_height)

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
        # self.draw_start_delay = 0.1   # Minimal delay before drawing starts? Maybe not needed.

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
            return # Skip frame processing

        # --- Read Webcam Frame ---
        success, img = self.cap.read()
        if not success or img is None:
            logging.error("Cannot read frame from webcam.")
            # Attempt to recover or notify user?
            # For now, just skip this frame processing.
            # Consider stopping timer if errors persist?
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
        # Dynamically adjust timer interval based on processing time? Advanced.


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
            self.drawing_canvas.reset_points()
            self.last_draw_action_time = 0
            self.gui.show_toast(f"Mode: {mode_name}") # Announce mode change


        current_time = time.time()
        # Check if cooldown period has passed for major actions
        can_perform_action = (current_time - self.last_action_time) > self.action_cooldown

        # --- Presentation Mode Logic ---
        if current_mode == PRESENTATION_MODE:
            self.drawing_canvas.reset_points() # Ensure no drawing state persists
            self.last_draw_action_time = 0

            # Next Slide: Index finger up [0, 1, 0, 0, 0]
            if fingers == [0, 1, 0, 0, 0] and can_perform_action:
                if self.gui.navigate_slide(1): # navigate_slide returns True if successful
                   # self.drawing_canvas.clear_canvas() # Clearing annotations here might be unexpected
                   self.last_action_time = current_time
                   logging.info("Gesture: Next slide")
                   self.gui.show_toast("Next slide") # Use toast for feedback

            # Previous Slide: Thumb up [1, 0, 0, 0, 0]
            elif fingers == [1, 0, 0, 0, 0] and can_perform_action:
                if self.gui.navigate_slide(-1):
                    # self.drawing_canvas.clear_canvas()
                    self.last_action_time = current_time
                    logging.info("Gesture: Previous slide")
                    self.gui.show_toast("Previous slide")

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
            self.drawing_canvas.set_opacity(self.gui.opacity_slider.value())

            # Draw with Index finger [X, 1, X, X, X] (check only index finger [1])
            if fingers[1] == 1 and lm_list and len(lm_list) > 8: # Check index finger tip landmark exists
                x_raw, y_raw = lm_list[8][1], lm_list[8][2] # Raw coords from webcam frame

                # Normalize coordinates to a virtual space (e.g., 800x600)
                # This space matches the expectation of drawing_canvas methods
                # Use webcam dimensions for normalization source
                x_norm = min(max(int(x_raw * 800 / self.WEBCAM_WIDTH), 0), 799)
                y_norm = min(max(int(y_raw * 600 / self.WEBCAM_HEIGHT), 0), 599)

                drawing_mode = self.gui.drawing_mode
                draw_location = self.gui.draw_location
                blackboard_mode = self.gui.is_blackboard_mode()

                annotation = None # Variable to hold the annotation dict to be saved
                # --- Perform Drawing ---
                # Pass normalized coordinates to canvas methods
                if draw_location in ['slide', 'both']:
                    # draw() scales internally from 800x600 to slide dimensions
                    annotation = self.drawing_canvas.draw(x_norm, y_norm, mode=drawing_mode, blackboard_mode=blackboard_mode)
                if draw_location in ['webcam', 'both']:
                    # draw_on_webcam() scales internally from 800x600 to webcam dimensions
                    annotation_webcam = self.drawing_canvas.draw_on_webcam(x_norm, y_norm, mode=drawing_mode, blackboard_mode=blackboard_mode)
                    if draw_location == 'webcam': # Prioritize webcam if only drawing there
                         annotation = annotation_webcam
                         
                # --- Save Annotation ---
                # Save the latest relevant annotation generated
                # Check user ID, valid slide index, and that an annotation was created
                if annotation and self.gui.current_user_id and \
                   self.gui.slides and 0 <= self.gui.current_slide_index < len(self.gui.slides):
                    try:
                        slide_id = self.gui.slides[self.gui.current_slide_index][0]
                        if slide_id:
                             # The draw methods already appended to current_annotations
                             # No need to save 'annotation' directly, save from current_annotations later or immediately?
                             # For immediate feedback, let's save the last one added.
                             last_ann = self.drawing_canvas.current_annotations[-1]
                             if self.db.save_annotation(slide_id, self.gui.current_user_id, last_ann):
                                 # Optional: logging.debug(f"Saved annotation part for slide {slide_id}")
                                 pass # Saved successfully
                             else:
                                 logging.error(f"DB save failed for annotation on slide {slide_id}")
                                 # Consider removing from current_annotations if save fails?
                        else:
                             logging.error("Invalid slide_id, cannot save annotation.")
                    except IndexError:
                         logging.error("Error accessing current_annotations list, possibly empty.")
                    except Exception as e:
                        logging.error(f"Error saving annotation during draw: {e}")

                self.last_draw_action_time = current_time # Mark that drawing happened

            # If index finger is down, finalize shape drawing
            else:
                # Check if we were drawing recently to finalize
                if self.last_draw_action_time != 0:
                    drawing_mode = self.gui.drawing_mode
                    blackboard_mode = self.gui.is_blackboard_mode()
                    # reset_points finalizes shapes and clears start/end points
                    self.drawing_canvas.reset_points(mode=drawing_mode, blackboard_mode=blackboard_mode)
                    # Check if reset_points generated final shape annotations in current_annotations
                    final_annotations = self.drawing_canvas.current_annotations
                    if final_annotations and self.gui.current_user_id and \
                       self.gui.slides and 0 <= self.gui.current_slide_index < len(self.gui.slides):
                        try:
                            slide_id = self.gui.slides[self.gui.current_slide_index][0]
                            if slide_id:
                                saved_final = 0
                                for ann in list(final_annotations): # Iterate copy
                                     if self.db.save_annotation(slide_id, self.gui.current_user_id, ann):
                                          saved_final += 1
                                     else:
                                          logging.error(f"Failed to save final annotation part for slide {slide_id}")
                                if saved_final > 0:
                                     logging.info(f"Saved {saved_final} final annotation parts for slide {slide_id}")
                                     self.gui.show_toast("Shape finalized")
                                # Clear the list after attempting save
                                self.drawing_canvas.current_annotations = []
                            else:
                                logging.error("Invalid slide_id found for final shape.")
                        except Exception as e:
                            logging.error(f"Error saving final shape annotation: {e}")
                            self.drawing_canvas.current_annotations = [] # Clear on error too

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
                x_raw, y_raw = lm_list[8][1], lm_list[8][2]
                # Normalize coordinates same as drawing
                x_norm = min(max(int(x_raw * 800 / self.WEBCAM_WIDTH), 0), 799)
                y_norm = min(max(int(y_raw * 600 / self.WEBCAM_HEIGHT), 0), 599)

                # erase() acts on both canvases internally using normalized coords
                self.drawing_canvas.erase(x_norm, y_norm)

                # Save erase action (erase adds annotation to current_annotations)
                if self.gui.current_user_id and self.gui.slides and \
                   0 <= self.gui.current_slide_index < len(self.gui.slides):
                    try:
                        slide_id = self.gui.slides[self.gui.current_slide_index][0]
                        if slide_id:
                            # Get the erase annotation added by erase()
                            if self.drawing_canvas.current_annotations:
                                erase_annotation = self.drawing_canvas.current_annotations[-1]
                                if erase_annotation.get('type') == 'erase':
                                     if self.db.save_annotation(slide_id, self.gui.current_user_id, erase_annotation):
                                         # logging.debug(f"Saved erase annotation for slide {slide_id}")
                                         pass
                                     else:
                                         logging.error(f"Failed to save erase annotation for slide {slide_id}")
                                     # Remove erase annotation from temp list after attempting save
                                     self.drawing_canvas.current_annotations.pop()
                            else:
                                 logging.warning("Erase action performed but no annotation found in list.")
                        else:
                             logging.error("Invalid slide_id found for erase.")
                    except Exception as e:
                        logging.error(f"Error saving erase annotation: {e}")

                self.last_draw_action_time = current_time # Use same timer as drawing

            else:
                # Reset points if finger goes down (less critical for erase, but good practice)
                if self.last_draw_action_time != 0:
                     self.drawing_canvas.reset_points()
                     self.last_draw_action_time = 0

            # Clear Canvas: All fingers up [1, 1, 1, 1, 1]
            # Use general action cooldown for this less frequent action
            if all(fingers) and can_perform_action:
                self.drawing_canvas.clear_canvas() # Clears visual canvas and current_annotations list
                self.last_action_time = current_time # Apply cooldown
                logging.info("Gesture: Canvas cleared")
                self.gui.show_toast("Canvas cleared")
                # Add a "clear" annotation type to DB? If needed for persistence.
                # Example: clear_ann = {'type': 'clear_canvas', 'timestamp': time.time()}
                # self.db.save_annotation(slide_id, user_id, clear_ann)
                # Then, load_annotations needs to handle 'clear_canvas' type.

    def update_display(self, img):
        """Update the GUI with the current slide (including drawings) and webcam feed."""
        # --- Prepare Slide Display ---
        slide_img_original = self.gui.get_current_slide() # Get original (e.g., 1920x1080 BGR)

        # Prepare the final image to be displayed on the slide label using the GUI's method
        # This ensures consistent preparation logic (blackboard + masked drawing overlay)
        slide_display_final = self.gui.prepare_display_image(slide_img_original)

        # Update the slide label in the GUI
        self.gui.update_slide(slide_display_final) # Passes the combined image

        # --- Prepare Webcam Display ---
        # Webcam image 'img' already has landmarks drawn
        webcam_canvas = self.drawing_canvas.webcam_canvas # 1280x720
        webcam_preview = self.drawing_canvas.get_webcam_preview() # 1280x720

        img_display_final = img.copy() # Start with a copy

        # Combine webcam canvas and preview
        webcam_canvas_combined = cv2.bitwise_or(webcam_canvas, webcam_preview)

        # Overlay drawings using masking if dimensions match
        if img_display_final.shape == webcam_canvas_combined.shape and \
           img_display_final.dtype == webcam_canvas_combined.dtype:
            try:
                # Create mask for webcam drawings/erase
                img2gray_wc = cv2.cvtColor(webcam_canvas_combined, cv2.COLOR_BGR2GRAY)
                ret_wc, mask_wc = cv2.threshold(img2gray_wc, 0, 255, cv2.THRESH_BINARY)

                if cv2.countNonZero(mask_wc) > 0:
                    mask_inv_wc = cv2.bitwise_not(mask_wc)

                    # Black-out area on webcam feed
                    img_bg_wc = cv2.bitwise_and(img_display_final, img_display_final, mask=mask_inv_wc)
                    # Get drawing/erase pixels
                    img_fg_wc = cv2.bitwise_and(webcam_canvas_combined, webcam_canvas_combined, mask=mask_wc)
                    # Combine
                    img_display_final = cv2.add(img_bg_wc, img_fg_wc)

            except cv2.error as e:
                logging.error(f"OpenCV error combining webcam and canvas (masked): {e}")
                # img_display_final remains the original 'img' as fallback
        else:
             logging.warning(f"Shape/dtype mismatch: Webcam={img.shape}/{img.dtype}, WC_Canvas_Combined={webcam_canvas_combined.shape}/{webcam_canvas_combined.dtype}")
             # img_display_final remains the original 'img' as fallback

        # Update the webcam label in the GUI
        self.gui.update_frame(img_display_final)

    def run(self):
        """Initialize and run the application."""
        try:
            self.gui.show()
            logging.info("GestureTeach Application GUI is now showing.")
            exit_code = self.app.exec_() # Start PyQt event loop
            logging.info(f"Application exited with code {exit_code}.")
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
            if hasattr(self, 'db'):
                self.db.close() # Close database connection (logs internally)
            logging.info("Cleanup finished.")
            sys.exit(exit_code)

if __name__ == "__main__":
    # Setup logging (configure once at the start)
    log_format = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    logging.basicConfig(level=logging.INFO, # Or DEBUG for more details
                        filename='gesture_teach.log',
                        format=log_format,
                        filemode='a') # Append to the log file
    # Add a handler to also print logs to console (optional)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO) # Console level can be different
    console_handler.setFormatter(logging.Formatter(log_format))
    logging.getLogger().addHandler(console_handler)

    logging.info("========================================")
    logging.info("Starting GestureTeach Application")
    logging.info("========================================")

    main_app = MainApp()
    main_app.run()