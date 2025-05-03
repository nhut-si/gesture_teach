# --- START OF FILE drawing_utils.py ---

import cv2
import numpy as np
import json
import logging
import time

class DrawingCanvas:
    """Canvas for drawing on slides and webcam feed."""
    def __init__(self, slide_width=1920, slide_height=1080, webcam_width=1280, webcam_height=720):
        self.slide_width = slide_width
        self.slide_height = slide_height
        self.webcam_width = webcam_width
        self.webcam_height = webcam_height
        # Main drawing canvases (cleared on load)
        self.canvas = np.zeros((slide_height, slide_width, 3), dtype=np.uint8)
        self.webcam_canvas = np.zeros((webcam_height, webcam_width, 3), dtype=np.uint8)
        # Preview canvases for ongoing actions (like drawing shapes)
        self.preview_canvas = np.zeros((slide_height, slide_width, 3), dtype=np.uint8)
        self.webcam_preview_canvas = np.zeros((webcam_height, webcam_width, 3), dtype=np.uint8)
        logging.info(f"DrawingCanvas initialized: Slide({slide_width}x{slide_height}), Webcam({webcam_width}x{webcam_height})")

        # Drawing state variables
        self.slide_prev_x, self.slide_prev_y = None, None
        self.webcam_prev_x, self.webcam_prev_y = None, None
        self.slide_shape_start = None
        self.webcam_shape_start = None

        # Color definitions
        self.colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0), (255, 255, 0)] # BGR: Red, Green, Blue, Yellow
        self.blackboard_colors = [(255, 255, 255), (200, 200, 200), (150, 255, 255), (255, 150, 255)] # White, Gray, Light Cyan, Light Magenta
        self.color_names = ["Red", "Green", "Blue", "Yellow"]
        self.blackboard_color_names = ["White", "Gray", "Lt. Cyan", "Lt. Magenta"]
        self.current_color_index = 0

        # Brush properties
        self.brush_size = 5
        # Opacity REMOVED

        # Temporary storage for annotations within a session or before saving
        self.current_annotations = []

    def _get_current_color(self, blackboard_mode=False):
        """Helper to get the correct color tuple based on mode."""
        colors = self.blackboard_colors if blackboard_mode else self.colors
        names = self.blackboard_color_names if blackboard_mode else self.color_names
        idx = self.current_color_index % len(colors)
        # logging.debug(f"Getting color: Index={idx}, Blackboard={blackboard_mode}, Color={colors[idx]}, Name={names[idx]}")
        return colors[idx]

    def draw(self, x_norm, y_norm, mode="pen", blackboard_mode=False):
        """Draw on the slide canvas based on normalized (e.g., 800x600) coordinates."""
        # Convert normalized coordinates to slide canvas coordinates
        x = min(max(int(x_norm * self.slide_width / 800), 0), self.slide_width - 1)
        y = min(max(int(y_norm * self.slide_height / 600), 0), self.slide_height - 1)
        # logging.debug(f"Draw SLIDE: Norm=({x_norm},{y_norm}), Canvas=({x},{y}), Mode={mode}")

        color = self._get_current_color(blackboard_mode)
        # Create annotation data structure for potential saving
        annotation = {
            'type': mode,
            'coords': (x, y), # Current coordinate
            'color': color,
            'brush_size': self.brush_size,
            'target': 'slide', # Specify target canvas
            'timestamp': time.time() # Add timestamp
        }

        if mode == "pen":
            # If previous point exists, draw a line
            if self.slide_prev_x is not None and self.slide_prev_y is not None:
                cv2.line(self.canvas, (self.slide_prev_x, self.slide_prev_y), (x, y), color, self.brush_size)
                annotation['prev_coords'] = (self.slide_prev_x, self.slide_prev_y) # Store previous point for line drawing on load
            else:
                # If no previous point (start of stroke), draw a small circle
                cv2.circle(self.canvas, (x, y), max(1, self.brush_size // 2), color, -1)
            # Update previous point for the next segment
            self.slide_prev_x, self.slide_prev_y = x, y
        elif mode in ["circle", "square"]:
            # If this is the first point of the shape
            if self.slide_shape_start is None:
                self.slide_shape_start = (x, y)
                annotation['shape_start'] = self.slide_shape_start # Record start in annotation
                logging.debug(f"Slide shape START registered at: {self.slide_shape_start}")
            else:
                # If shape has started, update the preview
                current_shape_end = (x, y)
                self.preview_canvas.fill(0) # Clear previous preview
                # Draw the shape on the temporary preview canvas
                self.draw_shape(self.preview_canvas, self.slide_shape_start, current_shape_end, mode, color, self.brush_size)
                # Update annotation with start and current end (this will be overwritten until finger lifts)
                annotation['shape_start'] = self.slide_shape_start
                annotation['shape_end'] = current_shape_end
                # logging.debug(f"Slide shape PREVIEW updated: Start={self.slide_shape_start}, End={current_shape_end}")


        # Append the annotation (either pen segment or shape update) to the temporary list
        self.current_annotations.append(annotation)
        return annotation # Return the created annotation (optional)

    def draw_on_webcam(self, x_norm, y_norm, mode="pen", blackboard_mode=False):
        """Draw on the webcam canvas based on normalized coordinates."""
        # Convert normalized coordinates to webcam canvas coordinates
        x = min(max(int(x_norm * self.webcam_width / 800), 0), self.webcam_width - 1)
        y = min(max(int(y_norm * self.webcam_height / 600), 0), self.webcam_height - 1)
        # logging.debug(f"Draw WEBCAM: Norm=({x_norm},{y_norm}), Canvas=({x},{y}), Mode={mode}")


        color = self._get_current_color(blackboard_mode)
        # Create annotation data structure
        annotation = {
            'type': mode,
            'coords': (x, y),
            'color': color,
            'brush_size': self.brush_size,
            'target': 'webcam', # Specify target
            'timestamp': time.time()
        }

        if mode == "pen":
            if self.webcam_prev_x is not None and self.webcam_prev_y is not None:
                cv2.line(self.webcam_canvas, (self.webcam_prev_x, self.webcam_prev_y), (x, y), color, self.brush_size)
                annotation['prev_coords'] = (self.webcam_prev_x, self.webcam_prev_y)
            else:
                cv2.circle(self.webcam_canvas, (x, y), max(1, self.brush_size // 2), color, -1)
            self.webcam_prev_x, self.webcam_prev_y = x, y
        elif mode in ["circle", "square"]:
            if self.webcam_shape_start is None:
                self.webcam_shape_start = (x, y)
                annotation['shape_start'] = self.webcam_shape_start
                logging.debug(f"Webcam shape START registered at: {self.webcam_shape_start}")
            else:
                current_shape_end = (x, y)
                self.webcam_preview_canvas.fill(0) # Clear previous preview
                self.draw_shape(self.webcam_preview_canvas, self.webcam_shape_start, current_shape_end, mode, color, self.brush_size)
                annotation['shape_start'] = self.webcam_shape_start
                annotation['shape_end'] = current_shape_end
                # logging.debug(f"Webcam shape PREVIEW updated: Start={self.webcam_shape_start}, End={current_shape_end}")

        # Append annotation to temporary list
        self.current_annotations.append(annotation)
        return annotation

    def draw_shape(self, canvas_to_draw_on, start, end, mode, color, thickness):
        """Helper function to draw a shape on a given canvas."""
        if start is None or end is None:
            logging.warning("draw_shape called with None start or end point.")
            return
        if canvas_to_draw_on is None:
             logging.error("draw_shape called with None canvas_to_draw_on.")
             return

        thickness = max(1, int(thickness)) # Ensure thickness >= 1 and integer
        # Convert coordinates to integers just in case
        start = (int(start[0]), int(start[1]))
        end = (int(end[0]), int(end[1]))

        try:
            if mode == "circle":
                center_x, center_y = start
                radius = int(((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5)
                if radius > 0:
                    cv2.circle(canvas_to_draw_on, (center_x, center_y), radius, color, thickness)
                    # logging.debug(f"Drew circle on canvas {id(canvas_to_draw_on)} at {start} radius {radius}")
            elif mode == "square":
                start_x, start_y = start
                end_x, end_y = end
                pt1 = (min(start_x, end_x), min(start_y, end_y))
                pt2 = (max(start_x, end_x), max(start_y, end_y))
                # Clip coordinates to canvas boundaries to prevent OpenCV errors
                h, w = canvas_to_draw_on.shape[:2]
                pt1 = (max(0, pt1[0]), max(0, pt1[1]))
                pt2 = (min(w - 1, pt2[0]), min(h - 1, pt2[1]))
                # Only draw if the rectangle has valid dimensions (width and height > 0)
                if pt1[0] < pt2[0] and pt1[1] < pt2[1]:
                    cv2.rectangle(canvas_to_draw_on, pt1, pt2, color, thickness)
                    # logging.debug(f"Drew square on canvas {id(canvas_to_draw_on)} from {pt1} to {pt2}")
                else:
                    logging.warning(f"Skipped drawing square with invalid dimensions: pt1={pt1}, pt2={pt2}")
        except cv2.error as e:
             logging.error(f"OpenCV error in draw_shape: {e}. Start: {start}, End: {end}, Mode: {mode}")
        except Exception as e:
             logging.error(f"Unexpected error in draw_shape: {e}", exc_info=True)


    def erase(self, x_norm, y_norm):
        """Erase drawings on both canvases using normalized coordinates."""
        erase_radius = max(5, self.brush_size * 2) # Make eraser size relative to brush size
        x_slide = min(max(int(x_norm * self.slide_width / 800), 0), self.slide_width - 1)
        y_slide = min(max(int(y_norm * self.slide_height / 600), 0), self.slide_height - 1)
        # Erase on slide canvas by drawing black circles
        cv2.circle(self.canvas, (x_slide, y_slide), erase_radius, (0, 0, 0), -1)

        # Erase on webcam canvas
        x_webcam = min(max(int(x_norm * self.webcam_width / 800), 0), self.webcam_width - 1)
        y_webcam = min(max(int(y_norm * self.webcam_height / 600), 0), self.webcam_height - 1)
        cv2.circle(self.webcam_canvas, (x_webcam, y_webcam), erase_radius, (0, 0, 0), -1)

        # Create an annotation for the erase action (mainly for slide canvas)
        annotation = {
            'type': 'erase',
            'coords': (x_slide, y_slide), # Store slide coordinates for potential replay
            'brush_size': erase_radius, # Store erase size
            'target': 'both', # Indicate erase affects both (though only slide coords stored precisely)
            'timestamp': time.time()
        }
        self.current_annotations.append(annotation)
        # logging.debug(f"Erased at Slide:({x_slide},{y_slide}), Webcam:({x_webcam},{y_webcam}) Radius:{erase_radius}")

    def reset_points(self, mode="pen", blackboard_mode=False):
        """Reset drawing points (pen mode) and finalize shapes (circle/square mode)."""
        color = self._get_current_color(blackboard_mode)
        logging.debug(f"Resetting points/finalizing shape. Current drawing mode from GUI: {mode}")

        # --- Finalize Slide Shape ---
        if mode in ["circle", "square"] and self.slide_shape_start:
            logging.debug(f"Attempting to finalize SLIDE shape. Start point: {self.slide_shape_start}")
            # Find the last relevant annotation with shape_end for this start point
            last_shape_end = None
            indices_to_remove = []
            # Search backwards through the temporary annotations list
            for i in range(len(self.current_annotations) - 1, -1, -1):
                ann = self.current_annotations[i]
                # Check if annotation matches the start point, target, and type
                if ann.get('shape_start') == self.slide_shape_start and \
                   ann.get('target') == 'slide' and ann.get('type') == mode:
                    indices_to_remove.append(i) # Mark this temp annotation for removal
                    # If this annotation has an end point, it's our candidate
                    if 'shape_end' in ann and last_shape_end is None:
                        last_shape_end = ann['shape_end']
                        logging.debug(f"Found potential last_shape_end for slide: {last_shape_end} at index {i}")
                    # If we encounter the initial 'shape_start' only annotation, stop searching backwards
                    if 'shape_end' not in ann:
                         logging.debug(f"Found initial start marker for slide at index {i}, stopping search.")
                         break
                # Optimization: Stop searching if annotations are too old (e.g., > 5 seconds)
                # Optional: Adjust time limit as needed
                # elif (time.time() - ann.get('timestamp', 0)) > 5:
                #    logging.debug(f"Stopping backward search for slide shape due to age at index {i}")
                #    break

            # If a valid end point was found
            if last_shape_end:
                # <<< DRAW ON MAIN SLIDE CANVAS >>>
                logging.debug(f"Drawing final SLIDE shape. Start: {self.slide_shape_start}, End: {last_shape_end}, Mode: {mode}, TargetCanvas: self.canvas")
                self.draw_shape(self.canvas, self.slide_shape_start, last_shape_end, mode, color, self.brush_size)
                # <<< TEST POINT >>>
                # cv2.circle(self.canvas, (100, 100), 20, (0, 255, 255), -1) # Draw fixed yellow point
                # logging.debug("Drew TEST yellow circle at (100, 100) on self.canvas")

                # Create the single, final annotation for saving
                final_annotation = {
                    'type': mode,
                    'shape_start': self.slide_shape_start,
                    'shape_end': last_shape_end,
                    'color': color,
                    'brush_size': self.brush_size,
                    'target': 'slide',
                    'timestamp': time.time() # Use current time for final annotation
                }
                # Remove the temporary annotations associated with this shape drawing process
                indices_to_remove.sort(reverse=True) # Sort indices high to low for safe deletion
                logging.debug(f"Removing temporary slide shape annotations at indices: {indices_to_remove}")
                for index in indices_to_remove:
                    try:
                        del self.current_annotations[index]
                    except IndexError:
                         logging.warning(f"Index {index} out of range when removing temp slide annotations.")
                # Add the final, consolidated annotation to the list
                self.current_annotations.append(final_annotation)
                logging.info(f"Finalized SLIDE shape annotation added: Type={mode}, Start={self.slide_shape_start}, End={last_shape_end}")
            else: # No end point found (e.g., user just clicked without dragging)
                 # Just remove the temporary 'start' annotation fragment
                 indices_to_remove.sort(reverse=True)
                 logging.debug(f"No valid end point found for slide shape. Removing indices: {indices_to_remove}")
                 for index in indices_to_remove:
                     try:
                         del self.current_annotations[index]
                     except IndexError:
                          logging.warning(f"Index {index} out of range when removing incomplete slide shape annotation.")
                 logging.info(f"Discarded incomplete slide shape starting at {self.slide_shape_start}")

        # --- Finalize Webcam Shape (Similar Logic - Assuming this works correctly) ---
        if mode in ["circle", "square"] and self.webcam_shape_start:
            logging.debug(f"Attempting to finalize WEBCAM shape. Start point: {self.webcam_shape_start}")
            last_shape_end = None
            indices_to_remove = []
            for i in range(len(self.current_annotations) - 1, -1, -1):
                 ann = self.current_annotations[i]
                 if ann.get('shape_start') == self.webcam_shape_start and \
                    ann.get('target') == 'webcam' and ann.get('type') == mode:
                     indices_to_remove.append(i)
                     if 'shape_end' in ann and last_shape_end is None:
                         last_shape_end = ann['shape_end']
                         # logging.debug(f"Found potential last_shape_end for webcam: {last_shape_end} at index {i}")
                     if 'shape_end' not in ann:
                          # logging.debug(f"Found initial start marker for webcam at index {i}, stopping search.")
                          break
                 # elif (time.time() - ann.get('timestamp', 0)) > 5 :
                 #      break

            if last_shape_end:
                logging.debug(f"Drawing final WEBCAM shape. Start: {self.webcam_shape_start}, End: {last_shape_end}, Mode: {mode}, TargetCanvas: self.webcam_canvas")
                self.draw_shape(self.webcam_canvas, self.webcam_shape_start, last_shape_end, mode, color, self.brush_size)
                final_annotation = {
                    'type': mode,
                    'shape_start': self.webcam_shape_start,
                    'shape_end': last_shape_end,
                    'color': color,
                    'brush_size': self.brush_size,
                    'target': 'webcam',
                    'timestamp': time.time()
                }
                indices_to_remove.sort(reverse=True)
                # logging.debug(f"Removing temporary webcam shape annotations at indices: {indices_to_remove}")
                for index in indices_to_remove:
                    try:
                        del self.current_annotations[index]
                    except IndexError:
                         logging.warning(f"Index {index} out of range when removing temp webcam annotations.")

                self.current_annotations.append(final_annotation)
                logging.info(f"Finalized WEBCAM shape annotation added: Type={mode}, Start={self.webcam_shape_start}, End={last_shape_end}")
            else:
                 indices_to_remove.sort(reverse=True)
                 # logging.debug(f"No valid end point found for webcam shape. Removing indices: {indices_to_remove}")
                 for index in indices_to_remove:
                      try:
                          del self.current_annotations[index]
                      except IndexError:
                          logging.warning(f"Index {index} out of range when removing incomplete webcam shape annotation.")

                 logging.info(f"Discarded incomplete webcam shape starting at {self.webcam_shape_start}")

        # --- Reset States common to all modes or after finalization ---
        # Reset pen drawing points
        self.slide_prev_x, self.slide_prev_y = None, None
        self.webcam_prev_x, self.webcam_prev_y = None, None
        # Reset shape start points
        self.slide_shape_start = None
        self.webcam_shape_start = None
        # Clear preview canvases
        self.preview_canvas.fill(0)
        self.webcam_preview_canvas.fill(0)
        logging.debug("Drawing points and previews reset.")

    def change_color(self):
        """Cycle to the next available drawing color."""
        num_colors = len(self.colors) # Use length of standard colors
        self.current_color_index = (self.current_color_index + 1) % num_colors
        logging.info(f"Color index changed to {self.current_color_index}")

    def clear_canvas(self):
        """Clear both main canvases visually and add a 'clear_canvas' annotation."""
        logging.info("Clearing drawing canvases.")
        self.canvas.fill(0)
        self.webcam_canvas.fill(0)
        self.preview_canvas.fill(0)
        self.webcam_preview_canvas.fill(0)
        # Create the annotation AFTER clearing visually
        clear_annotation = {
            'type': 'clear_canvas',
            'target': 'both', # Indicates this action clears everything
            'timestamp': time.time()
        }
        # Add clear annotation to the list. It will be saved later.
        # load_annotations will process this marker.
        self.current_annotations.append(clear_annotation)
        logging.debug("'clear_canvas' annotation added.")
        # Do NOT clear self.current_annotations here.

    def get_current_color_name(self, blackboard_mode=False):
        """Get the name of the current drawing color."""
        names = self.blackboard_color_names if blackboard_mode else self.color_names
        idx = self.current_color_index % len(names) # Use length of the relevant name list
        return names[idx]

    # --- This method was missing or incorrect in the user's environment ---
    def set_brush_size(self, size):
        """Set the brush size."""
        try:
            self.brush_size = max(1, int(size)) # Ensure size is at least 1 and an integer
            logging.debug(f"Brush size set to: {self.brush_size}")
        except (ValueError, TypeError):
            logging.warning(f"Invalid brush size value received: {size}. Using default {self.brush_size}.")
            # Optionally keep the old value or set to default: self.brush_size = 5

    def get_preview(self):
        """Get the slide preview canvas (for ongoing shape drawing)."""
        return self.preview_canvas

    def get_webcam_preview(self):
        """Get the webcam preview canvas."""
        return self.webcam_preview_canvas

    def load_annotations(self, annotations):
        """Load and render annotations from database onto the canvases."""
        # Start fresh by clearing all visual canvases
        self.canvas.fill(0)
        self.webcam_canvas.fill(0)
        self.preview_canvas.fill(0)
        self.webcam_preview_canvas.fill(0)
        # Clear the list of temporary annotations held by the canvas instance
        self.current_annotations = []
        logging.info(f"Cleared canvases. Loading {len(annotations)} annotation parts from DB.")

        # Find the index of the last 'clear_canvas' event in the loaded data
        last_clear_index = -1
        for i, ann in enumerate(annotations):
            # Ensure it's a dict and has the correct type
            if isinstance(ann, dict) and ann.get('type') == 'clear_canvas':
                last_clear_index = i

        # Determine the list of annotations to actually render (those after the last clear)
        annotations_to_render = annotations[last_clear_index + 1:]
        if last_clear_index != -1:
             logging.info(f"Rendering {len(annotations_to_render)} annotations after last clear event found at original index {last_clear_index}.")
        else:
             logging.info("No 'clear_canvas' event found, rendering all loaded annotations.")


        # --- Render the relevant annotations ---
        rendered_count = {'slide': 0, 'webcam': 0, 'erase': 0, 'pen': 0, 'shape': 0}
        for idx, ann in enumerate(annotations_to_render):
            if not isinstance(ann, dict):
                logging.warning(f"Skipping invalid annotation format during load (Index {idx}): {type(ann)}")
                continue

            try:
                mode = ann.get('type')
                # Default color to Red if missing or invalid format
                color_data = ann.get('color')
                if isinstance(color_data, (list, tuple)) and len(color_data) == 3:
                    color = tuple(int(c) for c in color_data) # Ensure components are int
                else:
                    color = (0, 0, 255) # Default BGR Red
                    if color_data: logging.warning(f"Invalid color format {color_data} in annotation, using default Red.")

                brush_size = ann.get('brush_size', 5) # Use 5 as default if missing
                brush_size = max(1, int(brush_size)) # Ensure valid integer >= 1
                target = ann.get('target', 'slide') # Default to slide if target is missing

                # Determine which canvas(es) to draw on based on target
                draw_on_slide = target in ['slide', 'both']
                draw_on_webcam = target in ['webcam', 'both']

                # --- Render based on annotation type ---
                if mode == "pen":
                    coords_data = ann.get('coords')
                    prev_coords_data = ann.get('prev_coords')
                    if coords_data:
                        coords = (int(coords_data[0]), int(coords_data[1])) # Ensure int tuple
                        if prev_coords_data: # Draw a line segment
                            prev_coords = (int(prev_coords_data[0]), int(prev_coords_data[1]))
                            if draw_on_slide:
                                cv2.line(self.canvas, prev_coords, coords, color, brush_size)
                            if draw_on_webcam:
                                # Need to check if webcam canvas exists and has correct shape
                                # This assumes coords were originally for webcam if target is webcam/both
                                cv2.line(self.webcam_canvas, prev_coords, coords, color, brush_size)
                        else: # Draw the starting point of a pen stroke
                            start_radius = max(1, brush_size // 2)
                            if draw_on_slide:
                                cv2.circle(self.canvas, coords, start_radius, color, -1)
                            if draw_on_webcam:
                                cv2.circle(self.webcam_canvas, coords, start_radius, color, -1)
                        rendered_count['pen'] += 1
                        if draw_on_slide: rendered_count['slide'] += 1
                        if draw_on_webcam: rendered_count['webcam'] += 1
                    else:
                        logging.warning(f"Skipping pen annotation due to missing coords: {ann}")

                elif mode in ["circle", "square"]:
                    start_data = ann.get('shape_start')
                    end_data = ann.get('shape_end')
                    # Only render finalized shapes that have both start and end
                    if start_data and end_data:
                        start = (int(start_data[0]), int(start_data[1]))
                        end = (int(end_data[0]), int(end_data[1]))
                        # Call the helper function to draw the shape on the appropriate canvas
                        if draw_on_slide:
                            # logging.debug(f"Loading shape on slide: Start={start}, End={end}, Mode={mode}")
                            self.draw_shape(self.canvas, start, end, mode, color, brush_size)
                            rendered_count['slide'] += 1
                        if draw_on_webcam:
                            # logging.debug(f"Loading shape on webcam: Start={start}, End={end}, Mode={mode}")
                             self.draw_shape(self.webcam_canvas, start, end, mode, color, brush_size)
                             rendered_count['webcam'] += 1
                        rendered_count['shape'] += 1
                    else:
                         logging.warning(f"Skipping shape annotation due to missing start/end: {ann}")

                elif mode == "erase":
                    coords_data = ann.get('coords')
                    # Use saved erase radius or default based on current brush size
                    erase_radius = ann.get('brush_size', max(5, self.brush_size * 2))
                    erase_radius = max(1, int(erase_radius)) # Ensure valid integer >= 1
                    if coords_data:
                        erase_center_slide = (int(coords_data[0]), int(coords_data[1]))
                        # Always erase on slide canvas using stored slide coords
                        cv2.circle(self.canvas, erase_center_slide, erase_radius, (0, 0, 0), -1)
                        # Approximate erase on webcam canvas
                        x_wc = int(erase_center_slide[0] * self.webcam_width / self.slide_width)
                        y_wc = int(erase_center_slide[1] * self.webcam_height / self.slide_height)
                        erase_center_wc = (x_wc, y_wc)
                        cv2.circle(self.webcam_canvas, erase_center_wc, erase_radius, (0, 0, 0), -1)
                        rendered_count['erase'] += 1
                        # Erase affects both visually
                        rendered_count['slide'] += 1
                        rendered_count['webcam'] += 1
                    else:
                        logging.warning(f"Skipping erase annotation due to missing coords: {ann}")

                elif mode == "clear_canvas":
                    # This case should have been filtered out, but log if encountered
                    logging.warning("Encountered 'clear_canvas' event unexpectedly during rendering loop.")
                else:
                    logging.warning(f"Unknown annotation type during load: '{mode}' in {ann}")

            except (ValueError, TypeError, IndexError, KeyError, cv2.error, Exception) as e:
                logging.error(f"Error processing annotation during load (Index {idx}): {ann}. Error: {e}", exc_info=True)
                continue # Skip to the next annotation if processing fails

        logging.info(f"Finished rendering annotations. Render counts: {rendered_count}")


# --- END OF FILE drawing_utils.py ---