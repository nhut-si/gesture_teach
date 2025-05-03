import cv2
import numpy as np
import json
import logging

# Thiết lập logging
logging.basicConfig(level=logging.INFO, filename='gesture_teach.log', format='%(asctime)s - %(levelname)s - %(message)s')

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
        self.opacity = 1.0 # Opacity value (0.0 to 1.0)

        # Temporary storage for annotations within a session or before saving
        self.current_annotations = []

    def _get_current_color(self, blackboard_mode=False):
        """Helper to get the correct color tuple based on mode."""
        colors = self.blackboard_colors if blackboard_mode else self.colors
        idx = self.current_color_index % len(colors)
        return colors[idx]

    def draw(self, x_norm, y_norm, mode="pen", blackboard_mode=False):
        """Draw on the slide canvas based on normalized (e.g., 800x600) coordinates."""
        x = min(max(int(x_norm * self.slide_width / 800), 0), self.slide_width - 1)
        y = min(max(int(y_norm * self.slide_height / 600), 0), self.slide_height - 1)

        color = self._get_current_color(blackboard_mode)
        annotation = {
            'type': mode,
            'coords': (x, y),
            'color': color,
            'brush_size': self.brush_size,
            'opacity': self.opacity * 100,
            'target': 'slide'
        }

        if mode == "pen":
            if self.slide_prev_x is not None and self.slide_prev_y is not None:
                cv2.line(self.canvas, (self.slide_prev_x, self.slide_prev_y), (x, y), color, self.brush_size)
                annotation['prev_coords'] = (self.slide_prev_x, self.slide_prev_y)
            else:
                cv2.circle(self.canvas, (x, y), self.brush_size // 2, color, -1)
            self.slide_prev_x, self.slide_prev_y = x, y
        elif mode in ["circle", "square"]:
            if self.slide_shape_start is None:
                self.slide_shape_start = (x, y)
                annotation['shape_start'] = self.slide_shape_start
            else:
                current_shape_end = (x, y)
                self.preview_canvas.fill(0)
                self.draw_shape(self.preview_canvas, self.slide_shape_start, current_shape_end, mode, color, self.brush_size)
                annotation['shape_start'] = self.slide_shape_start
                annotation['shape_end'] = current_shape_end

        self.current_annotations.append(annotation)
        return annotation

    def draw_on_webcam(self, x_norm, y_norm, mode="pen", blackboard_mode=False):
        """Draw on the webcam canvas based on normalized coordinates."""
        x = min(max(int(x_norm * self.webcam_width / 800), 0), self.webcam_width - 1)
        y = min(max(int(y_norm * self.webcam_height / 600), 0), self.webcam_height - 1)

        color = self._get_current_color(blackboard_mode)
        annotation = {
            'type': mode,
            'coords': (x, y),
            'color': color,
            'brush_size': self.brush_size,
            'opacity': self.opacity * 100,
            'target': 'webcam'
        }

        if mode == "pen":
            if self.webcam_prev_x is not None and self.webcam_prev_y is not None:
                cv2.line(self.webcam_canvas, (self.webcam_prev_x, self.webcam_prev_y), (x, y), color, self.brush_size)
                annotation['prev_coords'] = (self.webcam_prev_x, self.webcam_prev_y)
            else:
                cv2.circle(self.webcam_canvas, (x, y), self.brush_size // 2, color, -1)
            self.webcam_prev_x, self.webcam_prev_y = x, y
        elif mode in ["circle", "square"]:
            if self.webcam_shape_start is None:
                self.webcam_shape_start = (x, y)
                annotation['shape_start'] = self.webcam_shape_start
            else:
                current_shape_end = (x, y)
                self.webcam_preview_canvas.fill(0)
                self.draw_shape(self.webcam_preview_canvas, self.webcam_shape_start, current_shape_end, mode, color, self.brush_size)
                annotation['shape_start'] = self.webcam_shape_start
                annotation['shape_end'] = current_shape_end

        self.current_annotations.append(annotation)
        return annotation

    def draw_shape(self, canvas_to_draw_on, start, end, mode, color, thickness):
        """Helper function to draw a shape on a given canvas."""
        if start is None or end is None: return

        if mode == "circle":
            center_x, center_y = start
            radius = int(((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5)
            if radius > 0:
                cv2.circle(canvas_to_draw_on, (center_x, center_y), radius, color, thickness)
        elif mode == "square":
            cv2.rectangle(canvas_to_draw_on, start, end, color, thickness)

    def erase(self, x_norm, y_norm):
        """Erase drawings on both canvases using normalized coordinates."""
        erase_radius = self.brush_size * 2
        x_slide = min(max(int(x_norm * self.slide_width / 800), 0), self.slide_width - 1)
        y_slide = min(max(int(y_norm * self.slide_height / 600), 0), self.slide_height - 1)
        cv2.circle(self.canvas, (x_slide, y_slide), erase_radius, (0, 0, 0), -1)
        x_webcam = min(max(int(x_norm * self.webcam_width / 800), 0), self.webcam_width - 1)
        y_webcam = min(max(int(y_norm * self.webcam_height / 600), 0), self.webcam_height - 1)
        cv2.circle(self.webcam_canvas, (x_webcam, y_webcam), erase_radius, (0, 0, 0), -1)
        annotation = {
            'type': 'erase',
            'coords': (x_slide, y_slide),
            'brush_size': erase_radius
        }
        self.current_annotations.append(annotation)

    def reset_points(self, mode="pen", blackboard_mode=False):
        """Reset drawing points and finalize shapes."""
        color = self._get_current_color(blackboard_mode)
        if mode in ["circle", "square"] and self.slide_shape_start:
            last_shape_annotation = None
            for ann in reversed(self.current_annotations):
                if ann.get('target') == 'slide' and ann.get('shape_start') == self.slide_shape_start and 'shape_end' in ann:
                    last_shape_annotation = ann
                    break
            if last_shape_annotation:
                final_shape_end = last_shape_annotation['shape_end']
                self.draw_shape(self.canvas, self.slide_shape_start, final_shape_end, mode, color, self.brush_size)
                self.current_annotations = [ann for ann in self.current_annotations if ann.get('shape_start') != self.slide_shape_start]
                final_annotation = {
                    'type': mode,
                    'shape_start': self.slide_shape_start,
                    'shape_end': final_shape_end,
                    'color': color,
                    'brush_size': self.brush_size,
                    'opacity': self.opacity * 100,
                    'target': 'slide'
                }
                self.current_annotations.append(final_annotation)
                logging.debug(f"Finalized slide shape: {final_annotation}")

        if mode in ["circle", "square"] and self.webcam_shape_start:
            last_shape_annotation = None
            for ann in reversed(self.current_annotations):
                if ann.get('target') == 'webcam' and ann.get('shape_start') == self.webcam_shape_start and 'shape_end' in ann:
                    last_shape_annotation = ann
                    break
            if last_shape_annotation:
                final_shape_end = last_shape_annotation['shape_end']
                self.draw_shape(self.webcam_canvas, self.webcam_shape_start, final_shape_end, mode, color, self.brush_size)
                self.current_annotations = [ann for ann in self.current_annotations if ann.get('shape_start') != self.webcam_shape_start]
                final_annotation = {
                    'type': mode,
                    'shape_start': self.webcam_shape_start,
                    'shape_end': final_shape_end,
                    'color': color,
                    'brush_size': self.brush_size,
                    'opacity': self.opacity * 100,
                    'target': 'webcam'
                }
                self.current_annotations.append(final_annotation)
                logging.debug(f"Finalized webcam shape: {final_annotation}")

        self.slide_prev_x, self.slide_prev_y = None, None
        self.webcam_prev_x, self.webcam_prev_y = None, None
        self.slide_shape_start = None
        self.webcam_shape_start = None
        self.preview_canvas.fill(0)
        self.webcam_preview_canvas.fill(0)

    def change_color(self):
        """Cycle to the next available drawing color."""
        num_colors = len(self.colors)
        self.current_color_index = (self.current_color_index + 1) % num_colors

    def clear_canvas(self):
        """Clear both canvases visually and add clear_canvas annotation."""
        logging.info("Clearing drawing canvases.")
        self.canvas.fill(0)
        self.webcam_canvas.fill(0)
        self.preview_canvas.fill(0)
        self.webcam_preview_canvas.fill(0)
        clear_annotation = {
            'type': 'clear_canvas',
            'target': 'both'
        }
        self.current_annotations.append(clear_annotation)
        logging.debug("Added clear_canvas annotation to current_annotations.")
        # Do NOT clear current_annotations here; let save_current_annotations handle it after saving

    def get_current_color_name(self, blackboard_mode=False):
        """Get the name of the current drawing color."""
        names = self.blackboard_color_names if blackboard_mode else self.color_names
        idx = self.current_color_index % len(names)
        return names[idx]

    def set_brush_size(self, size):
        """Set the brush size."""
        self.brush_size = max(1, int(size))

    def set_opacity(self, opacity_percent):
        """Set the opacity (takes percentage 0-100)."""
        self.opacity = max(0.0, min(1.0, float(opacity_percent) / 100.0))

    def get_preview(self):
        """Get the slide preview canvas (for ongoing shape drawing)."""
        return self.preview_canvas

    def get_webcam_preview(self):
        """Get the webcam preview canvas."""
        return self.webcam_preview_canvas

    def load_annotations(self, annotations):
        """Load and render annotations from database onto the canvases."""
        self.clear_canvas()  # This adds a clear_canvas annotation, which we remove immediately
        self.current_annotations = []  # Reset annotations to avoid duplicate clear_canvas
        logging.info(f"Loading {len(annotations)} annotation parts onto canvas.")

        # Process annotations until a clear_canvas is found
        valid_annotations = []
        for ann in annotations:
            if not isinstance(ann, dict):
                logging.warning(f"Skipping invalid annotation format: {type(ann)}")
                continue
            if ann.get('type') == 'clear_canvas':
                valid_annotations = []  # Reset all prior annotations
                logging.debug("Encountered clear_canvas annotation, resetting prior annotations.")
            else:
                valid_annotations.append(ann)

        # Separate drawing and erase actions
        drawing_actions = [ann for ann in valid_annotations if ann.get('type') in ['pen', 'circle', 'square']]
        erase_actions = [ann for ann in valid_annotations if ann.get('type') == 'erase']

        # Draw all drawing annotations first
        for ann in drawing_actions:
            try:
                mode = ann.get('type')
                color = tuple(ann.get('color', (255, 0, 0)))
                brush_size = ann.get('brush_size', self.brush_size)
                target = ann.get('target', 'slide')
                canvas_to_draw_on = self.webcam_canvas if target == 'webcam' else self.canvas

                if mode == "pen":
                    coords = ann.get('coords')
                    prev_coords = ann.get('prev_coords')
                    if coords:
                        if prev_coords:
                            cv2.line(canvas_to_draw_on, tuple(prev_coords), tuple(coords), color, brush_size)
                        else:
                            cv2.circle(canvas_to_draw_on, tuple(coords), brush_size // 2, color, -1)
                elif mode in ["circle", "square"]:
                    start = ann.get('shape_start')
                    end = ann.get('shape_end')
                    if start and end:
                        self.draw_shape(canvas_to_draw_on, tuple(start), tuple(end), mode, color, brush_size)
            except Exception as e:
                logging.error(f"Error processing drawing annotation: {ann}. Error: {e}", exc_info=True)
                continue

        # Apply erase actions after drawing
        for ann in erase_actions:
            try:
                coords = ann.get('coords')
                erase_radius = ann.get('brush_size', self.brush_size * 2)
                if coords:
                    x_slide, y_slide = tuple(coords)
                    cv2.circle(self.canvas, (x_slide, y_slide), erase_radius, (0, 0, 0), -1)
                    x_wc = int(x_slide * self.webcam_width / self.slide_width)
                    y_wc = int(y_slide * self.webcam_height / self.slide_height)
                    cv2.circle(self.webcam_canvas, (x_wc, y_wc), erase_radius, (0, 0, 0), -1)
            except Exception as e:
                logging.error(f"Error processing erase annotation: {ann}. Error: {e}", exc_info=True)
                continue