import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QLineEdit, QMessageBox, QListWidget, QListWidgetItem,
                             QFileDialog, QInputDialog, QDialog, QSlider, QComboBox, QTextEdit,
                             QSizePolicy, QStatusBar, QGridLayout)
from PyQt5.QtCore import Qt, QTimer, QByteArray, QBuffer
from PyQt5.QtGui import QImage, QPixmap, QPainter
from database import Database
import os
import datetime
import re
import logging
import time

class AppGUI(QMainWindow):
    """Main GUI class for the GestureTeach application."""
    def __init__(self, db):
        super().__init__()
        self.setWindowTitle("GestureTeach")
        self.setGeometry(100, 100, 1280, 720)  # Initial size
        self.db = db
        self.current_user_id = None
        self.original_slide_image = None  # Stores the original slide (e.g., 1920x1080 numpy array, BGR)
        self.current_slide_with_drawings = None  # Stores the combined image prepared for display/screenshots
        self.slides = []  # List of tuples from DB: (slide_id, file_path, order_index)
        self.slide_images = []  # Cache of loaded original slide images (numpy arrays, BGR)
        self.current_slide_index = -1  # Start at -1, becomes 0 on first load
        self.current_set_id = None
        self.is_fullscreen = False
        self.blackboard_mode = False
        self.sidebar_visible = True  # Start with sidebar potentially visible after login
        self.drawing_canvas = None  # Will be set by MainApp
        self.drawing_mode = "pen"
        self.draw_location = "slide"
        self.current_gesture = None  # Last processed gesture name
        self.last_screenshot_time = 0  # Track the last screenshot time
        self.init_ui()

        # Add a status bar
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready")

    def init_ui(self):
        """Initialize the user interface."""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)

        # === Sidebar ===
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setFixedWidth(250)
        self.sidebar_layout = QVBoxLayout(self.sidebar_widget)

        # Slide Set Management Widgets
        self.slide_set_label = QLabel("Slide Sets:")
        self.slide_set_list = QListWidget()
        self.slide_set_list.itemClicked.connect(self.load_slides)  # Click to load set
        self.add_set_button = QPushButton("Add Slide Set")
        self.add_set_button.setFixedHeight(40)
        self.add_set_button.clicked.connect(self.add_slide_set)
        self.edit_set_button = QPushButton("Edit Slide Set")
        self.edit_set_button.setFixedHeight(40)
        self.edit_set_button.clicked.connect(self.edit_slide_set)
        self.delete_set_button = QPushButton("Delete Slide Set")
        self.delete_set_button.setFixedHeight(40)
        self.delete_set_button.clicked.connect(self.delete_slide_set)

        # Slide List Widgets
        self.slide_list_label = QLabel("Slides in Set:")
        self.slide_list = QListWidget()
        self.slide_list.itemClicked.connect(self.display_selected_slide)  # Click to display slide

        # Drawing Tool Widgets
        self.pen_button = QPushButton("Pen")
        self.pen_button.setFixedHeight(40)
        self.pen_button.setCheckable(True)  # Make buttons checkable for visual feedback
        self.pen_button.setChecked(True)  # Default tool
        self.pen_button.clicked.connect(lambda: self.set_drawing_mode("pen"))
        self.circle_button = QPushButton("Circle")
        self.circle_button.setFixedHeight(40)
        self.circle_button.setCheckable(True)
        self.circle_button.clicked.connect(lambda: self.set_drawing_mode("circle"))
        self.square_button = QPushButton("Square")
        self.square_button.setFixedHeight(40)
        self.square_button.setCheckable(True)
        self.square_button.clicked.connect(lambda: self.set_drawing_mode("square"))

        # Brush Size Widgets
        self.brush_size_label = QLabel("Brush Size: 5")
        self.brush_size_slider = QSlider(Qt.Horizontal)
        self.brush_size_slider.setMinimum(1)
        self.brush_size_slider.setMaximum(50)
        self.brush_size_slider.setValue(5)
        self.brush_size_slider.valueChanged.connect(self.update_brush_size)

        # Opacity Widgets
        self.opacity_label = QLabel("Opacity: 100%")
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setMinimum(10)  # Min opacity 10%
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self.update_opacity)

        # Draw Location Widgets
        self.draw_location_label = QLabel("Draw On:")
        self.draw_location_combo = QComboBox()
        self.draw_location_combo.addItems(["Slide", "Webcam", "Both"])
        self.draw_location_combo.currentTextChanged.connect(self.update_draw_location)

        # Other Sidebar Widgets
        self.usage_guide_button = QPushButton("Usage Guide")
        self.usage_guide_button.setFixedHeight(40)
        self.usage_guide_button.clicked.connect(self.show_usage_guide)
        self.mode_label = QLabel("Mode: Unknown")  # Status labels
        self.color_label = QLabel("Color: Unknown")

        # Add Widgets to Sidebar Layout (Logical Order)
        self.sidebar_layout.addWidget(self.slide_set_label)
        self.sidebar_layout.addWidget(self.slide_set_list)
        self.sidebar_layout.addWidget(self.add_set_button)
        self.sidebar_layout.addWidget(self.edit_set_button)
        self.sidebar_layout.addWidget(self.delete_set_button)
        self.sidebar_layout.addWidget(self.slide_list_label)
        self.sidebar_layout.addWidget(self.slide_list)
        self.sidebar_layout.addStretch(1)  # Spacer
        self.sidebar_layout.addWidget(QLabel("Drawing Tools:"))
        tool_layout = QHBoxLayout()  # Layout for tool buttons
        tool_layout.addWidget(self.pen_button)
        tool_layout.addWidget(self.circle_button)
        tool_layout.addWidget(self.square_button)
        self.sidebar_layout.addLayout(tool_layout)
        self.sidebar_layout.addWidget(self.brush_size_label)
        self.sidebar_layout.addWidget(self.brush_size_slider)
        self.sidebar_layout.addWidget(self.opacity_label)
        self.sidebar_layout.addWidget(self.opacity_slider)
        self.sidebar_layout.addWidget(self.draw_location_label)
        self.sidebar_layout.addWidget(self.draw_location_combo)
        self.sidebar_layout.addStretch(1)  # Spacer
        self.sidebar_layout.addWidget(self.usage_guide_button)
        self.sidebar_layout.addWidget(self.mode_label)
        self.sidebar_layout.addWidget(self.color_label)

        self.sidebar_widget.setVisible(False)  # Initially hide sidebar

        # === Main Content Area ===
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(5, 5, 5, 5)  # Add some margins

        # Sidebar Toggle Button (Positioned above the main content)
        self.sidebar_toggle_button = QPushButton("Hide Sidebar")
        self.sidebar_toggle_button.setFixedHeight(30)  # Smaller button
        self.sidebar_toggle_button.clicked.connect(self.toggle_sidebar)
        self.sidebar_toggle_button.setVisible(False)  # Hide until logged in
        self.content_layout.addWidget(self.sidebar_toggle_button)

        # --- Login Widget ---
        self.login_widget = QWidget()
        self.login_layout = QVBoxLayout(self.login_widget)
        self.login_layout.setAlignment(Qt.AlignCenter)  # Center login elements
        login_title = QLabel("<h2>GestureTeach Login</h2>")
        login_title.setAlignment(Qt.AlignCenter)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username or Email")
        self.username_input.setFixedWidth(300)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedWidth(300)
        self.login_button = QPushButton("Login")
        self.login_button.setFixedHeight(40)
        self.login_button.setFixedWidth(150)
        self.login_button.clicked.connect(self.handle_login)
        self.register_button = QPushButton("Register New Account")
        self.register_button.setFixedHeight(40)
        self.register_button.setFixedWidth(200)
        self.register_button.clicked.connect(self.show_register)
        self.login_layout.addWidget(login_title)
        self.login_layout.addWidget(self.username_input)
        self.login_layout.addWidget(self.password_input)
        self.login_layout.addWidget(self.login_button)
        self.login_layout.addWidget(self.register_button)
        self.content_layout.addWidget(self.login_widget)  # Add login widget first

        # --- Main Application Widget (contains slide, buttons, webcam) ---
        self.main_widget = QWidget()
        self.main_widget_layout = QVBoxLayout(self.main_widget)
        self.main_widget_layout.setContentsMargins(0, 0, 0, 0)  # No internal margins
        self.main_widget_layout.setSpacing(5)

        # Top Area: Slide display and vertical buttons
        self.slide_area_layout = QHBoxLayout()
        self.slide_label = QLabel()  # No default text
        self.slide_label.setMinimumSize(640, 360)  # Minimum display size
        self.slide_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # Allow expansion
        self.slide_label.setAlignment(Qt.AlignCenter)
        self.slide_label.setStyleSheet("background-color: #333333; border: 1px solid gray;")  # Dark background initially

        # Vertical Button Layout
        self.button_widget = QWidget()
        self.button_widget.setFixedWidth(150)
        self.button_layout = QVBoxLayout(self.button_widget)
        self.button_layout.setContentsMargins(5, 0, 0, 0)  # Margin on the left
        self.fullscreen_button = QPushButton("Full Screen")
        self.fullscreen_button.setFixedHeight(40)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self.screenshot_button = QPushButton("Take Screenshot")
        self.screenshot_button.setFixedHeight(40)
        self.screenshot_button.clicked.connect(self.take_screenshot)
        self.blackboard_button = QPushButton("Blackboard: Off")
        self.blackboard_button.setFixedHeight(40)
        self.blackboard_button.setCheckable(True)  # Make it checkable
        self.blackboard_button.clicked.connect(self.toggle_blackboard_mode)
        self.button_layout.addWidget(self.fullscreen_button)
        self.button_layout.addWidget(self.screenshot_button)
        self.button_layout.addWidget(self.blackboard_button)
        self.button_layout.addStretch()  # Push buttons up

        self.slide_area_layout.addWidget(self.slide_label, 1)  # Slide takes most space
        self.slide_area_layout.addWidget(self.button_widget)
        self.main_widget_layout.addLayout(self.slide_area_layout, 1)  # Slide area stretches vertically

        # Bottom Area: Webcam feed and Logout button
        self.bottom_widget = QWidget()
        self.bottom_layout = QHBoxLayout(self.bottom_widget)
        self.bottom_layout.addStretch()  # Push webcam widget to the right
        self.webcam_widget = QWidget()
        self.webcam_layout = QVBoxLayout(self.webcam_widget)
        self.webcam_label = QLabel("Webcam Feed")
        self.webcam_label.setFixedSize(320, 240)
        self.webcam_label.setAlignment(Qt.AlignCenter)
        self.webcam_label.setStyleSheet("background-color: black; border: 1px solid gray;")
        self.logout_button = QPushButton("Logout")
        self.logout_button.setFixedHeight(30)  # Smaller logout button
        self.logout_button.clicked.connect(self.handle_logout)
        self.webcam_layout.addWidget(self.webcam_label)
        self.webcam_layout.addWidget(self.logout_button, 0, Qt.AlignRight)  # Align button right
        self.bottom_layout.addWidget(self.webcam_widget)

        self.main_widget_layout.addWidget(self.bottom_widget)
        self.content_layout.addWidget(self.main_widget)
        self.main_widget.setVisible(False)  # Hide main widget initially

        # Add sidebar and content area to the main horizontal layout
        self.main_layout.addWidget(self.sidebar_widget)
        self.main_layout.addWidget(self.content_widget, 1)  # Content area takes remaining space

        # --- General Toast Notification Label (for non-screenshot messages) ---
        self.toast_timer = QTimer()
        self.toast_timer.setSingleShot(True)
        self.toast_label = QLabel(self)  # Use a persistent label, parented to main window
        self.toast_label.setStyleSheet(
            "background-color: rgba(50, 50, 50, 220); "  # Original gray background
            "color: white; "
            "padding: 8px 15px; "
            "border-radius: 15px; "
            "font-size: 10pt;"
        )
        self.toast_label.setAlignment(Qt.AlignCenter)
        self.toast_label.setVisible(False)
        self.toast_label.setAttribute(Qt.WA_TranslucentBackground)  # Optional: for better transparency effect
        self.toast_timer.timeout.connect(self.hide_toast)  # Hide on timeout

        # --- Screenshot Toast Notification Label (specific for screenshot) ---
        self.screenshot_toast_timer = QTimer()
        self.screenshot_toast_timer.setSingleShot(True)
        self.screenshot_toast_label = QLabel(self)  # Separate label for screenshot toast
        self.screenshot_toast_label.setStyleSheet(
            "background-color: #28a745; "  # Green background for screenshot toast
            "color: #28a745; "  # Green text to match the theme
            "padding: 8px 15px; "
            "border: 2px solid white; "
            "border-radius: 15px; "
            "font-size: 14pt;"
        )
        self.screenshot_toast_label.setAlignment(Qt.AlignCenter)
        self.screenshot_toast_label.setVisible(False)
        self.screenshot_toast_label.setAttribute(Qt.WA_TranslucentBackground)
        self.screenshot_toast_timer.timeout.connect(self.hide_toast)  # Hide on timeout

    def show_toast(self, message, duration=5000, is_screenshot=False):
        """Show a temporary toast notification at the appropriate position."""
        # Choose the appropriate label and timer based on the message type
        if is_screenshot:
            toast_label = self.screenshot_toast_label
            toast_timer = self.screenshot_toast_timer
        else:
            toast_label = self.toast_label
            toast_timer = self.toast_timer

        toast_label.setText(message)
        toast_label.adjustSize()  # Adjust size to fit text

        # Calculate position based on message type
        try:
            parent_width = self.width()
            parent_height = self.height()

            if is_screenshot:
                # Center horizontally, position at the bottom
                toast_x = (parent_width - toast_label.width()) // 2  # Center horizontally
                toast_y = parent_height - toast_label.height() - 20  # Bottom, with 20px offset
            else:
                # Keep other toasts at the top-right
                toast_x = parent_width - toast_label.width() - 20
                toast_y = 20  # Top-right, offset from top

            toast_label.move(toast_x, toast_y)
            toast_label.raise_()  # Ensure it's on top
            toast_label.setVisible(True)
            toast_timer.start(duration)
        except Exception as e:
            logging.error(f"Error showing toast: {e}")  # Log error if positioning fails

    def hide_toast(self):
        """Hide both toast labels."""
        self.toast_label.setVisible(False)
        self.screenshot_toast_label.setVisible(False)

    def resizeEvent(self, event):
        """Handle window resize event to reposition both toasts."""
        super().resizeEvent(event)
        # Reposition general toast if it's visible (top-right)
        if self.toast_label.isVisible():
            try:
                parent_width = self.width()
                parent_height = self.height()
                toast_x = parent_width - self.toast_label.width() - 20
                toast_y = 20  # Top-right
                self.toast_label.move(toast_x, toast_y)
            except Exception as e:
                logging.error(f"Error repositioning general toast on resize: {e}")

        # Reposition screenshot toast if it's visible (center-bottom)
        if self.screenshot_toast_label.isVisible():
            try:
                parent_width = self.width()
                parent_height = self.height()
                toast_x = (parent_width - self.screenshot_toast_label.width()) // 2  # Center horizontally
                toast_y = parent_height - self.screenshot_toast_label.height() - 20  # Bottom
                self.screenshot_toast_label.move(toast_x, toast_y)
            except Exception as e:
                logging.error(f"Error repositioning screenshot toast on resize: {e}")

    # --- Login/Logout Handling ---
    def handle_login(self):
        """Handle user login."""
        username = self.username_input.text()
        password = self.password_input.text()
        if not username or not password:
            QMessageBox.warning(self, "Login Error", "Please enter username/email and password.")
            return

        user_id = self.db.login_user(username, password)
        if user_id:
            self.current_user_id = user_id
            self.login_widget.setVisible(False)
            if hasattr(self, 'register_widget'):  # Hide register widget if it exists
                self.register_widget.setVisible(False)
            self.main_widget.setVisible(True)
            self.sidebar_widget.setVisible(self.sidebar_visible)  # Show sidebar based on state
            self.sidebar_toggle_button.setVisible(True)  # Show toggle button
            self.update_sidebar_toggle_text()  # Set correct text
            self.load_slide_sets()
            self.statusBar().showMessage(f"Logged in as user ID: {self.current_user_id}")  # Show User ID or username
            self.show_toast("Login successful")
            logging.info(f"User {self.current_user_id} logged in.")
            # Clear password field after successful login
            self.password_input.clear()
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username/email or password.")
            logging.warning(f"Failed login attempt for user: {username}")
            # Clear password field after failed login
            self.password_input.clear()

    def handle_logout(self):
        """Handle user logout."""
        reply = QMessageBox.question(self, "Logout", "Are you sure you want to logout?\nUnsaved annotations might be lost if auto-save failed.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        # Attempt to save annotations before logging out
        self.save_current_annotations()

        user_id = self.current_user_id
        self.current_user_id = None
        self.main_widget.setVisible(False)
        self.sidebar_widget.setVisible(False)
        self.sidebar_toggle_button.setVisible(False)
        self.login_widget.setVisible(True)
        self.username_input.clear()  # Clear username for next login
        # Password already cleared on login success/fail

        # Clear slide display and lists
        self.slide_label.clear()
        self.slide_label.setText("Login to view slides")
        self.slide_label.setStyleSheet("background-color: #333333; border: 1px solid gray;")
        self.webcam_label.clear()
        self.webcam_label.setText("Webcam Feed")
        self.webcam_label.setStyleSheet("background-color: black; border: 1px solid gray;")
        self.slide_set_list.clear()
        self.slide_list.clear()
        self.slides = []
        self.slide_images = []
        self.current_slide_index = -1
        self.original_slide_image = None
        self.current_slide_with_drawings = None
        if self.drawing_canvas:
            self.drawing_canvas.clear_canvas()
            self.drawing_canvas.current_annotations = []  # Clear temp list

        self.statusBar().showMessage("Logged out. Please log in.")
        self.show_toast("Logged out successfully")
        logging.info(f"User {user_id} logged out.")

    # --- Registration Handling ---
    def show_register(self):
        """Show registration interface."""
        self.login_widget.setVisible(False)
        # Create register widget only if it doesn't exist
        if not hasattr(self, 'register_widget'):
            self.register_widget = QWidget()
            self.register_layout = QVBoxLayout(self.register_widget)
            self.register_layout.setAlignment(Qt.AlignCenter)
            reg_title = QLabel("<h2>Register New Account</h2>")
            reg_title.setAlignment(Qt.AlignCenter)
            self.reg_username = QLineEdit()
            self.reg_username.setPlaceholderText("Username")
            self.reg_username.setFixedWidth(300)
            self.reg_email = QLineEdit()
            self.reg_email.setPlaceholderText("Email")
            self.reg_email.setFixedWidth(300)
            self.reg_password = QLineEdit()
            pwd_placeholder = "Password (min 8 chars, A-Z, a-z, 0-9, symbol)"
            self.reg_password.setPlaceholderText(pwd_placeholder)
            self.reg_password.setEchoMode(QLineEdit.Password)
            self.reg_password.setFixedWidth(300)
            self.reg_button = QPushButton("Register")
            self.reg_button.setFixedHeight(40)
            self.reg_button.setFixedWidth(150)
            self.reg_button.clicked.connect(self.handle_register)
            self.back_button = QPushButton("Back to Login")
            self.back_button.setFixedHeight(40)
            self.back_button.setFixedWidth(150)
            self.back_button.clicked.connect(self.show_login)
            self.register_layout.addWidget(reg_title)
            self.register_layout.addWidget(self.reg_username)
            self.register_layout.addWidget(self.reg_email)
            self.register_layout.addWidget(self.reg_password)
            self.register_layout.addWidget(self.reg_button)
            self.register_layout.addWidget(self.back_button)
            # Add register widget to the *content* layout, not directly to main window
            self.content_layout.addWidget(self.register_widget)
            self.register_widget.setVisible(False)  # Start hidden

        # Clear fields before showing
        self.reg_username.clear()
        self.reg_email.clear()
        self.reg_password.clear()
        self.register_widget.setVisible(True)

    def handle_register(self):
        """Handle user registration with validation."""
        username = self.reg_username.text().strip()
        email = self.reg_email.text().strip()
        password = self.reg_password.text()

        if not all([username, email, password]):
            QMessageBox.warning(self, "Registration Error", "All fields are required.")
            return

        # Basic email format validation
        if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):  # Stricter regex
            QMessageBox.warning(self, "Registration Error", "Invalid email format.")
            return

        # Password complexity validation
        if not (len(password) >= 8 and
                re.search(r"[A-Z]", password) and
                re.search(r"[a-z]", password) and
                re.search(r"[0-9]", password) and
                re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)):  # Example symbols
            QMessageBox.warning(self, "Registration Error", "Password does not meet complexity requirements.\n(Min 8 chars, uppercase, lowercase, number, symbol)")
            return

        # Attempt registration
        success, message = self.db.register_user(username, email, password)

        if success:
            QMessageBox.information(self, "Success", "Registration successful! You can now log in.")
            logging.info(f"New user registered: {username}, Email: {email}")
            self.show_login()  # Go back to login screen
        else:
            QMessageBox.warning(self, "Registration Failed", f"Registration failed: {message}")
            logging.error(f"Registration failed for user: {username}. Reason: {message}")

    def show_login(self):
        """Show login interface and hide registration."""
        if hasattr(self, 'register_widget'):
            self.register_widget.setVisible(False)
        self.login_widget.setVisible(True)

    # --- Slide Set Management ---
    def add_slide_set(self):
        """Add a new slide set."""
        if not self.current_user_id:
            self.show_toast("Please log in to add slide sets.")
            return
        name, ok = QInputDialog.getText(self, "Add Slide Set", "Enter New Slide Set Name:")
        if ok and name:
            name = name.strip()
            if not name:
                QMessageBox.warning(self, "Error", "Slide set name cannot be empty.")
                return

            file_paths, _ = QFileDialog.getOpenFileNames(self, f"Select Slides for '{name}'", "", "Images (*.png *.jpg *.jpeg *.bmp)")
            if file_paths:
                set_id = self.db.add_slide_set(self.current_user_id, name)
                if set_id:
                    added_count = 0
                    errors = []
                    for i, path in enumerate(file_paths):
                        if self.db.add_slide(set_id, path, i):
                            added_count += 1
                        else:
                            errors.append(os.path.basename(path))
                    msg = f"Slide set '{name}' added with {added_count} slides."
                    if errors:
                        msg += f"\nCould not add: {', '.join(errors)}"
                    QMessageBox.information(self, "Success", msg)
                    self.load_slide_sets()  # Refresh list
                    self.show_toast(f"Slide set '{name}' added")
                    logging.info(f"User {self.current_user_id} added slide set '{name}' ({set_id}) with {added_count} slides.")
                else:
                    QMessageBox.warning(self, "Error", "Failed to create slide set in database.")
                    logging.error(f"Failed to add slide set '{name}' for user {self.current_user_id}")

    def edit_slide_set(self):
        """Edit slides within an existing slide set."""
        selected_set_item = self.slide_set_list.currentItem()
        if not selected_set_item:
            QMessageBox.warning(self, "Error", "Please select a slide set from the list to edit.")
            return

        set_id = selected_set_item.data(Qt.UserRole)
        set_name = selected_set_item.text()

        # Create a dialog for editing
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Slides in Set: {set_name}")
        dialog.setMinimumSize(400, 300)
        dialog_layout = QVBoxLayout(dialog)

        list_label = QLabel("Current Slides (Drag to Reorder - Future Feature):")
        slide_list_widget = QListWidget()

        # Populate the list
        current_slides = self.db.get_slides(set_id)  # [(id, path, order), ...]
        slide_map = {}  # Map list item text back to slide_id and path for removal
        for slide_data in current_slides:
            slide_id_db, file_path, order_index = slide_data
            item_text = f"{order_index + 1}: {os.path.basename(file_path)}"
            list_item = QListWidgetItem(item_text)
            slide_map[item_text] = (slide_id_db, file_path)  # Store DB ID and full path
            slide_list_widget.addItem(list_item)

        # Buttons for Add/Remove
        add_button = QPushButton("Add Slides...")
        remove_button = QPushButton("Remove Selected Slide")

        def add_new_slides():
            file_paths, _ = QFileDialog.getOpenFileNames(dialog, f"Add Slides to '{set_name}'", "", "Images (*.png *.jpg *.jpeg *.bmp)")
            if file_paths:
                current_max_order = len(current_slides) - 1
                added_count = 0
                errors = []
                for i, path in enumerate(file_paths):
                    if self.db.add_slide(set_id, path, current_max_order + 1 + i):
                        added_count += 1
                    else:
                        errors.append(os.path.basename(path))
                self.show_toast(f"Added {added_count} slides.")
                if errors:
                    QMessageBox.warning(dialog, "Error", f"Could not add: {', '.join(errors)}")
                dialog.accept()
                self.load_slides(selected_set_item)

        def remove_selected_slide():
            selected_list_item = slide_list_widget.currentItem()
            if not selected_list_item:
                QMessageBox.warning(dialog, "Error", "Select a slide to remove.")
                return

            item_text = selected_list_item.text()
            slide_id_to_remove, slide_path_to_remove = slide_map.get(item_text, (None, None))

            if slide_id_to_remove:
                reply = QMessageBox.question(dialog, "Confirm Remove", f"Remove slide '{os.path.basename(slide_path_to_remove)}'?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    if self.db.remove_slide_by_id(slide_id_to_remove):
                        self.show_toast("Slide removed.")
                        dialog.accept()
                        self.load_slides(selected_set_item)
                    else:
                        QMessageBox.warning(dialog, "Error", "Failed to remove slide from database.")
                        logging.error(f"Failed to remove slide ID {slide_id_to_remove}")
            else:
                QMessageBox.warning(dialog, "Error", "Could not identify selected slide for removal.")

        add_button.clicked.connect(add_new_slides)
        remove_button.clicked.connect(remove_selected_slide)

        button_layout = QHBoxLayout()
        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)

        dialog_layout.addWidget(list_label)
        dialog_layout.addWidget(slide_list_widget)
        dialog_layout.addLayout(button_layout)

        dialog.exec_()

    def delete_slide_set(self):
        """Delete the selected slide set and its slides."""
        selected_set_item = self.slide_set_list.currentItem()
        if not selected_set_item:
            QMessageBox.warning(self, "Error", "Please select a slide set to delete.")
            return

        set_id = selected_set_item.data(Qt.UserRole)
        set_name = selected_set_item.text()

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to permanently delete the slide set '{set_name}' and all its slides/annotations?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.db.delete_slide_set(set_id):
                self.show_toast(f"Slide set '{set_name}' deleted.")
                logging.info(f"User {self.current_user_id} deleted slide set '{set_name}' ({set_id})")
                self.load_slide_sets()
            else:
                QMessageBox.warning(self, "Error", f"Failed to delete slide set '{set_name}'.")
                logging.error(f"Failed to delete slide set {set_id} for user {self.current_user_id}")

    # --- Slide Loading and Display ---
    def load_slide_sets(self):
        """Load slide sets for the current user into the list."""
        if not self.current_user_id:
            return
        self.slide_set_list.clear()
        self.slide_list.clear()
        self.slides = []
        self.slide_images = []
        self.current_slide_index = -1
        self.original_slide_image = None
        self.current_set_id = None
        self.slide_label.clear()
        self.slide_label.setText("Select a slide set")
        self.slide_label.setStyleSheet("background-color: #333333; border: 1px solid gray;")
        if self.drawing_canvas:
            self.drawing_canvas.clear_canvas()
            self.drawing_canvas.current_annotations = []

        sets = self.db.get_slide_sets(self.current_user_id)
        if not sets:
            self.statusBar().showMessage("No slide sets found. Click 'Add Slide Set'.")
        else:
            for set_id, name in sets:
                item = QListWidgetItem(name)
                item.setData(Qt.UserRole, set_id)
                self.slide_set_list.addItem(item)
            self.statusBar().showMessage("Select a slide set from the list.")

    def load_slides(self, item):
        """Load slides for the selected slide set."""
        if not item or not self.current_user_id:
            return

        if self.current_set_id is not None and self.current_slide_index != -1:
            self.save_current_annotations()

        set_id = item.data(Qt.UserRole)
        set_name = item.text()

        if set_id == self.current_set_id:
            if self.current_slide_index == -1 and self.slides:
                self.current_slide_index = 0
                self.display_slide()
            return

        self.current_set_id = set_id
        self.slides = self.db.get_slides(set_id)
        self.slide_images = []
        self.slide_list.clear()

        if not self.slides:
            self.original_slide_image = None
            self.slide_label.clear()
            self.slide_label.setText(f"Set '{set_name}' is empty.")
            self.slide_label.setStyleSheet("background-color: #333333; border: 1px solid gray;")
            self.current_slide_index = -1
            if self.drawing_canvas:
                self.drawing_canvas.clear_canvas()
                self.drawing_canvas.current_annotations = []
            self.statusBar().showMessage(f"Selected empty set: '{set_name}'.")
            logging.info(f"Loaded empty slide set '{set_name}' ({set_id}) for user {self.current_user_id}")
            return

        logging.info(f"Loading {len(self.slides)} slides for set '{set_name}' ({set_id})")
        loaded_count = 0
        error_loading = False
        for i, slide_data in enumerate(self.slides):
            slide_id, file_path, order_index = slide_data
            try:
                img = cv2.imread(file_path)
                if img is not None:
                    self.slide_images.append(img)
                    list_text = f"{order_index + 1}: {os.path.basename(file_path)}"
                    slide_item = QListWidgetItem(list_text)
                    slide_item.setData(Qt.UserRole, i)
                    self.slide_list.addItem(slide_item)
                    loaded_count += 1
                else:
                    raise ValueError("cv2.imread returned None")
            except Exception as e:
                self.slide_images.append(None)
                list_text = f"{order_index + 1}: [Load Error] {os.path.basename(file_path)}"
                slide_item = QListWidgetItem(list_text)
                slide_item.setForeground(Qt.red)
                self.slide_list.addItem(slide_item)
                logging.warning(f"Failed to load slide image: {file_path} for set {set_id}. Error: {e}")
                error_loading = True

        if loaded_count > 0:
            self.current_slide_index = 0
            self.slide_list.setCurrentRow(0)
            self.display_slide()
            self.statusBar().showMessage(f"Set '{set_name}'. Slide {self.current_slide_index + 1}/{len(self.slides)}")
            if error_loading:
                self.show_toast("Some slides failed to load.", duration=3000)
        else:
            self.original_slide_image = None
            self.slide_label.clear()
            self.slide_label.setText(f"Error loading all slides in set '{set_name}'.")
            self.slide_label.setStyleSheet("background-color: #FFDDDD; border: 1px solid red;")
            self.current_slide_index = -1
            self.statusBar().showMessage(f"Error loading set '{set_name}'.")
            logging.error(f"Failed to load any slides for set '{set_name}' ({set_id})")
            if self.drawing_canvas:
                self.drawing_canvas.clear_canvas()
                self.drawing_canvas.current_annotations = []

    def display_selected_slide(self, item):
        """Display the slide selected from the slide list."""
        if not item or not self.slides:
            return

        new_index = item.data(Qt.UserRole)

        if 0 <= new_index < len(self.slides):
            if new_index != self.current_slide_index:
                self.save_current_annotations()
                self.current_slide_index = new_index
                self.display_slide()
                self.statusBar().showMessage(f"Slide {self.current_slide_index + 1}/{len(self.slides)}")
        else:
            logging.error(f"Invalid index {new_index} selected from slide list.")

    def display_slide(self):
        """Load, prepare, and display the current slide with annotations."""
        if not (self.slides and 0 <= self.current_slide_index < len(self.slide_images)):
            self.original_slide_image = None
            self.slide_label.clear()
            self.slide_label.setText("No slide selected or available.")
            self.slide_label.setStyleSheet("background-color: #333333; border: 1px solid gray;")
            if self.drawing_canvas:
                self.drawing_canvas.clear_canvas()
                self.drawing_canvas.current_annotations = []
            return

        img_original = self.slide_images[self.current_slide_index]

        if img_original is None:
            self.original_slide_image = None
            slide_path = self.slides[self.current_slide_index][1]
            self.slide_label.setText(f"Error: Cannot load slide\n{os.path.basename(slide_path)}")
            self.slide_label.setStyleSheet("background-color: #FFDDDD; border: 1px solid red;")
            if self.drawing_canvas:
                self.drawing_canvas.clear_canvas()
                self.drawing_canvas.current_annotations = []
            logging.error(f"Attempted to display slide index {self.current_slide_index} which failed to load.")
            return

        target_w, target_h = 1920, 1080
        try:
            if img_original.shape[1] != target_w or img_original.shape[0] != target_h:
                self.original_slide_image = cv2.resize(img_original, (target_w, target_h), interpolation=cv2.INTER_AREA)
            else:
                self.original_slide_image = img_original.copy()
        except cv2.error as e:
            logging.error(f"Error resizing slide {self.current_slide_index}: {e}")
            self.original_slide_image = None
            self.slide_label.setText("Error processing slide image.")
            self.slide_label.setStyleSheet("background-color: #FFDDDD; border: 1px solid red;")
            return

        if self.drawing_canvas and self.current_user_id:
            slide_id = self.slides[self.current_slide_index][0]
            if slide_id:
                try:
                    annotations = self.db.load_annotations(slide_id, self.current_user_id)
                    self.drawing_canvas.load_annotations(annotations)
                    logging.info(f"Loaded {len(annotations)} annotations for slide {slide_id}")
                except Exception as e:
                    logging.error(f"Error loading annotations for slide {slide_id}: {e}")
                    QMessageBox.warning(self, "Annotation Error", f"Failed to load annotations for slide {slide_id}.")
                    self.drawing_canvas.clear_canvas()
            else:
                logging.warning("Cannot load annotations: Invalid slide_id.")
                self.drawing_canvas.clear_canvas()

        display_image = self.prepare_display_image(self.original_slide_image)
        self.update_slide_label(display_image)

    def prepare_display_image(self, base_image):
        """Combines the base slide image with blackboard effect and drawings using masking."""
        if base_image is None or base_image.size == 0:
            logging.warning("prepare_display_image called with invalid base_image.")
            return None

        try:
            img_to_display = base_image.copy()

            if self.blackboard_mode:
                blackboard = np.full_like(img_to_display, (20, 20, 20), dtype=np.uint8)
                img_to_display = cv2.addWeighted(blackboard, 0.7, img_to_display, 0.3, 0.0)

            if self.drawing_canvas:
                canvas = self.drawing_canvas.canvas
                preview = self.drawing_canvas.get_preview()
                canvas_combined = cv2.bitwise_or(canvas, preview)

                if img_to_display.shape == canvas_combined.shape and img_to_display.dtype == canvas_combined.dtype:
                    img2gray = cv2.cvtColor(canvas_combined, cv2.COLOR_BGR2GRAY)
                    ret, mask = cv2.threshold(img2gray, 0, 255, cv2.THRESH_BINARY)
                    if cv2.countNonZero(mask) > 0:
                        mask_inv = cv2.bitwise_not(mask)
                        img_bg = cv2.bitwise_and(img_to_display, img_to_display, mask=mask_inv)
                        img_fg = cv2.bitwise_and(canvas_combined, canvas_combined, mask=mask)
                        img_to_display = cv2.add(img_bg, img_fg)
                else:
                    logging.warning("Dimension/dtype mismatch preventing drawing overlay (masked).")

            return img_to_display

        except cv2.error as e:
            logging.error(f"OpenCV error in prepare_display_image (masked): {e}")
            return base_image
        except Exception as e:
            logging.error(f"Unexpected error in prepare_display_image (masked): {e}")
            return None

    def update_slide_label(self, bgr_image):
        """Updates the slide QLabel with the given BGR image."""
        if bgr_image is None or bgr_image.size == 0:
            self.slide_label.setText("Error displaying slide.")
            self.slide_label.setStyleSheet("background-color: #FFDDDD; border: 1px solid red;")
            return

        try:
            img_rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
            h, w, ch = img_rgb.shape
            if h <= 0 or w <= 0:
                logging.error("Invalid image dimensions for QImage.")
                self.slide_label.setText("Invalid Image.")
                return

            bytes_per_line = ch * w
            q_img = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img)
            scaled_pixmap = pixmap.scaled(self.slide_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.slide_label.setPixmap(scaled_pixmap)
            self.slide_label.setStyleSheet("background-color: transparent; border: 1px solid gray;")

        except Exception as e:
            logging.error(f"Error updating slide label: {e}")
            self.slide_label.setText("Slide Display Error.")
            self.slide_label.setStyleSheet("background-color: #FFDDDD; border: 1px solid red;")

    def navigate_slide(self, direction):
        """Navigate to the next (+1) or previous (-1) slide."""
        if not self.slides:
            return False

        if self.current_slide_index == -1 and direction > 0 and len(self.slides) > 0:
            new_index = 0
        else:
            new_index = self.current_slide_index + direction

        if 0 <= new_index < len(self.slides):
            if self.current_slide_index != -1:
                self.save_current_annotations()
            self.current_slide_index = new_index
            self.slide_list.setCurrentRow(self.current_slide_index)
            self.display_slide()
            self.statusBar().showMessage(f"Slide {self.current_slide_index + 1}/{len(self.slides)}")
            return True
        else:
            current_status = self.statusBar().currentMessage()
            if direction > 0:
                self.statusBar().showMessage("Already on the last slide.", 2000)
            else:
                self.statusBar().showMessage("Already on the first slide.", 2000)
            return False

    # --- Fullscreen, Blackboard, Screenshot ---
    def toggle_fullscreen(self):
        """Toggle between fullscreen and normal mode."""
        if not self.is_fullscreen:
            self.is_fullscreen = True
            self.showFullScreen()
            self.sidebar_widget.setVisible(False)
            self.bottom_widget.setVisible(False)
            self.button_widget.setVisible(False)
            self.sidebar_toggle_button.setVisible(False)
            self.statusBar().setVisible(False)
            self.fullscreen_button.setText("Exit Full Screen")
            self.fullscreen_button.setShortcut("Esc")
        else:
            self.is_fullscreen = False
            self.showNormal()
            if self.current_user_id:
                self.sidebar_widget.setVisible(self.sidebar_visible)
                self.bottom_widget.setVisible(True)
                self.button_widget.setVisible(True)
                self.sidebar_toggle_button.setVisible(True)
                self.statusBar().setVisible(True)
            self.fullscreen_button.setText("Full Screen")
            self.fullscreen_button.setShortcut("")

        QTimer.singleShot(50, self.display_slide)
        self.show_toast("Fullscreen " + ("enabled" if self.is_fullscreen else "disabled"))
        logging.info(f"Fullscreen toggled: {'ON' if self.is_fullscreen else 'OFF'}")

    def toggle_blackboard_mode(self):
        """Toggle blackboard mode."""
        self.blackboard_mode = not self.blackboard_mode
        self.blackboard_button.setChecked(self.blackboard_mode)
        self.blackboard_button.setText(f"Blackboard: {'On' if self.blackboard_mode else 'Off'}")
        display_image = self.prepare_display_image(self.original_slide_image)
        self.update_slide_label(display_image)
        self.show_toast(f"Blackboard mode {'enabled' if self.blackboard_mode else 'disabled'}")
        logging.info(f"Blackboard mode toggled: {'ON' if self.blackboard_mode else 'OFF'}")

    def take_screenshot(self):
        """Capture and save a screenshot of the current slide with drawings to the 'screens' folder."""
        # Check if enough time has passed since the last screenshot (1 second cooldown)
        current_time = time.time()
        if current_time - self.last_screenshot_time < 1.0:
            self.show_toast("Chụp màn hình quá nhanh! Vui lòng đợi 1 giây.", duration=2000, is_screenshot=True)
            logging.info("Screenshot attempt ignored: Cooldown period active.")
            return

        image_to_save = self.current_slide_with_drawings

        if image_to_save is None or image_to_save.size == 0:
            QMessageBox.warning(self, "Screenshot Error", "No slide content to capture.")
            return

        # Create 'screens' directory if it doesn't exist
        if not os.path.exists("screens"):
            os.makedirs("screens")

        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screens/screenshot_{timestamp}.png"

        # Save the image with correct color representation
        try:
            # Ensure the image is in RGB format and colors are preserved
            img_rgb = cv2.cvtColor(image_to_save, cv2.COLOR_BGR2RGB)  # Convert BGR to RGB for consistency
            cv2.imwrite(filename, cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))  # Save as BGR to match OpenCV's default
            self.last_screenshot_time = current_time  # Update the last screenshot time
            logging.info(f"Screenshot saved to {filename}")
            self.show_toast("Đã chụp màn hình", duration=5000, is_screenshot=True)
        except Exception as e:
            logging.error(f"Error saving screenshot to {filename}: {e}")
            QMessageBox.warning(self, "Screenshot Error", "Failed to save screenshot.")

    # --- Sidebar Toggle ---
    def toggle_sidebar(self):
        """Toggle sidebar visibility."""
        self.sidebar_visible = not self.sidebar_visible
        self.sidebar_widget.setVisible(self.sidebar_visible)
        self.update_sidebar_toggle_text()

    def update_sidebar_toggle_text(self):
        """Update the text of the sidebar toggle button."""
        self.sidebar_toggle_button.setText("Hide Sidebar" if self.sidebar_visible else "Show Sidebar")

    # --- Keyboard Shortcuts ---
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        key = event.key()
        modifiers = event.modifiers()

        if modifiers == Qt.NoModifier:
            if key == Qt.Key_F11:
                self.toggle_fullscreen()
            elif key == Qt.Key_Escape and self.is_fullscreen:
                self.toggle_fullscreen()
            if self.current_user_id and not self.is_fullscreen:
                if key == Qt.Key_Right or key == Qt.Key_PageDown:
                    self.navigate_slide(1)
                elif key == Qt.Key_Left or key == Qt.Key_PageUp:
                    self.navigate_slide(-1)
                elif key == Qt.Key_B:
                    self.blackboard_button.click()

    # --- Updates from Main Loop ---
    def update_mode(self, mode):
        """Update the displayed mode label."""
        self.mode_label.setText(f"Mode: {mode}")

    def update_color(self, color_name):
        """Update the displayed color label and show toast."""
        self.color_label.setText(f"Color: {color_name}")
        self.show_toast(f"Color changed to {color_name}")

    def update_frame(self, img):
        """Update the webcam feed display."""
        if img is None or img.size == 0:
            self.webcam_label.setText("No Webcam Feed")
            return
        try:
            h, w, ch = img.shape
            if h <= 0 or w <= 0:
                return
            bytes_per_line = ch * w
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            q_img = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img)
            self.webcam_label.setPixmap(pixmap.scaled(self.webcam_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception as e:
            logging.error(f"Error updating webcam frame: {e}")
            self.webcam_label.setText("Webcam Error")

    def update_slide(self, img):
        """Update the slide display with the combined image from main loop."""
        self.current_slide_with_drawings = img
        self.update_slide_label(img)

    # --- Getters and Setters ---
    def get_current_slide(self):
        """Get the *original* current slide image (numpy array, BGR, 1920x1080)."""
        return self.original_slide_image

    def is_blackboard_mode(self):
        """Check if blackboard mode is enabled."""
        return self.blackboard_mode

    def set_drawing_canvas(self, canvas):
        """Set the drawing canvas instance provided by MainApp."""
        self.drawing_canvas = canvas
        if self.drawing_canvas:
            self.update_brush_size()
            self.update_opacity()

    # --- Drawing Interaction ---
    def set_drawing_mode(self, mode):
        """Set the drawing tool (pen, circle, square)."""
        self.drawing_mode = mode
        self.pen_button.setChecked(mode == "pen")
        self.circle_button.setChecked(mode == "circle")
        self.square_button.setChecked(mode == "square")
        self.show_toast(f"Tool: {mode.capitalize()}")

    def update_brush_size(self):
        """Update brush size in DrawingCanvas and label."""
        size = self.brush_size_slider.value()
        self.brush_size_label.setText(f"Brush Size: {size}")
        if self.drawing_canvas:
            self.drawing_canvas.set_brush_size(size)

    def update_opacity(self):
        """Update opacity in DrawingCanvas and label."""
        opacity_percent = self.opacity_slider.value()
        self.opacity_label.setText(f"Opacity: {opacity_percent}%")
        if self.drawing_canvas:
            self.drawing_canvas.set_opacity(opacity_percent)

    def update_draw_location(self):
        """Update drawing location preference."""
        self.draw_location = self.draw_location_combo.currentText().lower()
        self.show_toast(f"Drawing target: {self.draw_location.capitalize()}")

    # --- Annotation Saving ---
    def save_current_annotations(self):
        """Save current temporary annotations from DrawingCanvas to database."""
        if self.current_user_id and self.drawing_canvas and self.slides and 0 <= self.current_slide_index < len(self.slides):
            slide_id = self.slides[self.current_slide_index][0]
            if not slide_id:
                logging.warning("Cannot save annotations: Invalid slide_id for current index.")
                return

            annotations_to_save = self.drawing_canvas.current_annotations
            if annotations_to_save:
                saved_count = 0
                failed_count = 0
                try:
                    for annotation in list(annotations_to_save):
                        if self.db.save_annotation(slide_id, self.current_user_id, annotation):
                            saved_count += 1
                        else:
                            failed_count += 1
                            logging.error(f"Failed to save one annotation part for slide {slide_id}")
                    if saved_count > 0:
                        logging.info(f"Saved {saved_count} annotation parts for slide {slide_id}.")
                    if failed_count > 0:
                        logging.warning(f"Failed to save {failed_count} annotation parts for slide {slide_id}.")
                    self.drawing_canvas.current_annotations = []
                except Exception as e:
                    logging.error(f"Error during bulk annotation saving for slide {slide_id}: {e}")
                    self.drawing_canvas.current_annotations = []

    # --- Usage Guide ---
    def show_usage_guide(self):
        """Show usage guide in a non-modal dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("GestureTeach Usage Guide")
        dialog.setMinimumSize(500, 400)
        layout = QVBoxLayout(dialog)

        guide_text = QTextEdit()
        guide_text.setReadOnly(True)
        guide_text.setHtml("""
            <h2>GestureTeach Usage Guide</h2>
            <h3>Modes (Select with Gestures)</h3>
            <ul>
                <li><b>Presentation Mode:</b> Thumb + Index fingers up.</li>
                <li><b>Drawing Mode:</b> Index + Middle fingers up.</li>
                <li><b>Erasing Mode:</b> Index + Middle + Ring fingers up.</li>
            </ul>
            <h3>Presentation Mode Actions</h3>
            <ul>
                <li><b>Next Slide:</b> Index finger only.</li>
                <li><b>Previous Slide:</b> Thumb only.</li>
                <li><b>Take Screenshot:</b> Thumb + Index + Middle fingers.</li>
                <li><b>Toggle Fullscreen:</b> Middle + Ring fingers.</li>
            </ul>
            <h3>Drawing Mode Actions</h3>
            <ul>
                <li><b>Draw/Shape Drag:</b> Index finger only (position of tip).</li>
                <li><b>Change Color Cycle:</b> All 5 fingers up.</li>
                <li><b>Select Tool:</b> Use sidebar buttons (Pen, Circle, Square).</li>
                <li><b>Adjust Size/Opacity:</b> Use sidebar sliders.</li>
                <li><b>Change Draw Target:</b> Use sidebar dropdown (Slide, Webcam, Both).</li>
            </ul>
            <h3>Erasing Mode Actions</h3>
            <ul>
                <li><b>Erase Point:</b> Index finger only (position of tip). Eraser size based on brush size.</li>
                <li><b>Clear Entire Canvas:</b> All 5 fingers up.</li>
            </ul>
            <h3>Keyboard Shortcuts</h3>
            <ul>
                <li><b>Left/Right Arrow or PageUp/PageDown:</b> Previous/Next slide.</li>
                <li><b>F11:</b> Toggle fullscreen.</li>
                <li><b>Esc:</b> Exit fullscreen.</li>
                <li><b>B:</b> Toggle Blackboard Mode.</li>
            </ul>
            <p><i>Note: Gestures require a short pause (cooldown) between actions.</i></p>
        """)
        layout.addWidget(guide_text)

        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)

        dialog.show()

    # --- Window Close Event ---
    def closeEvent(self, event):
        """Handle window close event."""
        reply = QMessageBox.question(self, "Exit GestureTeach",
                                     "Are you sure you want to exit?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.save_current_annotations()
            logging.info("GUI closing by user action.")
            event.accept()
        else:
            event.ignore()

# --- Standalone execution for testing GUI ---
if __name__ == "__main__":
    class MockDatabase:
        def login_user(self, u, p): return 1 if p == "test" else None
        def get_slide_sets(self, uid): return [(1, "Demo Set 1"), (2, "Empty Set")]
        def get_slides(self, sid):
            if sid == 1:
                dummy_path1 = "dummy_slide1.png"
                dummy_path2 = "dummy_slide2.jpg"
                if not os.path.exists(dummy_path1):
                    cv2.imwrite(dummy_path1, np.zeros((100, 100, 3), dtype=np.uint8) + 200)
                if not os.path.exists(dummy_path2):
                    cv2.imwrite(dummy_path2, np.zeros((100, 100, 3), dtype=np.uint8) + 100)
                return [(101, dummy_path1, 0), (102, dummy_path2, 1)]
            else:
                return []
        def register_user(self, u, e, p): return True, "Mock registration successful"
        def add_slide_set(self, uid, n): return 3
        def add_slide(self, sid, p, o): return True
        def delete_slide_set(self, sid): return True
        def remove_slide_by_id(self, sid): return True
        def load_annotations(self, sid, uid): return []
        def save_annotation(self, sid, uid, d): return True
        def close(self): print("Mock DB closed")

    app = QApplication(sys.argv)
    mock_db = MockDatabase()
    window = AppGUI(mock_db)

    class MockDrawingCanvas:
        def __init__(self):
            self.canvas = np.zeros((1080, 1920, 3), dtype=np.uint8)
            self.webcam_canvas = np.zeros((720, 1280, 3), dtype=np.uint8)
            self.preview_canvas = np.zeros((1080, 1920, 3), dtype=np.uint8)
            self.webcam_preview_canvas = np.zeros((720, 1280, 3), dtype=np.uint8)
            self.current_annotations = []
        def set_brush_size(self, s): pass
        def set_opacity(self, o): pass
        def clear_canvas(self):
            self.canvas.fill(0)
            self.webcam_canvas.fill(0)
            self.preview_canvas.fill(0)
            self.webcam_preview_canvas.fill(0)
            self.current_annotations = []
        def load_annotations(self, a): self.clear_canvas()
        def get_preview(self): return self.preview_canvas
        def get_webcam_preview(self): return self.webcam_preview_canvas

    mock_canvas = MockDrawingCanvas()
    window.set_drawing_canvas(mock_canvas)
    window.show()
    sys.exit(app.exec_())