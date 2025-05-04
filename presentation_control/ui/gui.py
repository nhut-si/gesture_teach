import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QLineEdit, QMessageBox, QListWidget, QListWidgetItem,
                             QFileDialog, QInputDialog, QDialog, QSlider, QComboBox, QTextEdit,
                             QSizePolicy, QStatusBar, QGridLayout, QFrame, QSpacerItem)
from PyQt5.QtCore import Qt, QTimer, QByteArray, QBuffer
from PyQt5.QtGui import QImage, QPixmap, QPainter, QFont
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
        self.current_username_input = None
        self.current_email_input = None
        self.current_password_input = None
        self.auth_form_widget = None # Widget chứa form đăng nhập/đăng ký hiện tại
        self.init_ui()

        # Add a status bar
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready")

    def init_ui(self):
        """Initialize the user interface."""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # === Sidebar ===
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setFixedWidth(250)
        self.sidebar_widget.setStyleSheet("background-color: #F9FAFB; border-right: 1px solid #E5E7EB;")
        self.sidebar_layout = QVBoxLayout(self.sidebar_widget)
        self.sidebar_widget.setVisible(False)

        # Slide Set Management Widgets
        self.slide_set_label = QLabel("Slide Sets:")
        self.slide_set_label.setStyleSheet("color: #374151; font-weight: bold; padding: 10px;")
        self.slide_set_list = QListWidget()
        self.slide_set_list.setStyleSheet("background-color: white; border: 1px solid #E5E7EB; padding: 5px;")
        self.slide_set_list.itemClicked.connect(self.load_slides)  # Click to load set
        self.add_set_button = QPushButton("Add Slide Set")
        self.add_set_button.setFixedHeight(40)
        self.add_set_button.setStyleSheet("background-color: #3B82F6; color: white; border: none; padding: 5px;")
        self.add_set_button.clicked.connect(self.add_slide_set)
        self.edit_set_button = QPushButton("Edit Slide Set")
        self.edit_set_button.setFixedHeight(40)
        self.edit_set_button.setStyleSheet("background-color: #3B82F6; color: white; border: none; padding: 5px;")
        self.edit_set_button.clicked.connect(self.edit_slide_set)
        self.delete_set_button = QPushButton("Delete Slide Set")
        self.delete_set_button.setFixedHeight(40)
        self.delete_set_button.setStyleSheet("background-color: #EF4444; color: white; border: none; padding: 5px;")
        self.delete_set_button.clicked.connect(self.delete_slide_set)

        # Slide List Widgets
        self.slide_list_label = QLabel("Slides in Set:")
        self.slide_list_label.setStyleSheet("color: #374151; font-weight: bold; padding: 10px;")
        self.slide_list = QListWidget()
        self.slide_list.setStyleSheet("background-color: white; border: 1px solid #E5E7EB; padding: 5px;")
        self.slide_list.itemClicked.connect(self.display_selected_slide)  # Click to display slide

        # Drawing Tool Widgets
        self.pen_button = QPushButton("Pen")
        self.pen_button.setFixedHeight(40)
        self.pen_button.setCheckable(True)
        self.pen_button.setChecked(True)
        self.pen_button.setStyleSheet("background-color: #3B82F6; color: white; border: none; padding: 5px;")
        self.pen_button.clicked.connect(lambda: self.set_drawing_mode("pen"))
        self.circle_button = QPushButton("Circle")
        self.circle_button.setFixedHeight(40)
        self.circle_button.setCheckable(True)
        self.circle_button.setStyleSheet("background-color: #3B82F6; color: white; border: none; padding: 5px;")
        self.circle_button.clicked.connect(lambda: self.set_drawing_mode("circle"))
        self.square_button = QPushButton("Square")
        self.square_button.setFixedHeight(40)
        self.square_button.setCheckable(True)
        self.square_button.setStyleSheet("background-color: #3B82F6; color: white; border: none; padding: 5px;")
        self.square_button.clicked.connect(lambda: self.set_drawing_mode("square"))

        # Brush Size Widgets
        self.brush_size_label = QLabel("Brush Size: 5")
        self.brush_size_label.setStyleSheet("color: #374151; padding: 5px;")
        self.brush_size_slider = QSlider(Qt.Horizontal)
        self.brush_size_slider.setMinimum(1)
        self.brush_size_slider.setMaximum(50)
        self.brush_size_slider.setValue(5)
        self.brush_size_slider.setStyleSheet("QSlider::groove:horizontal { background: #E5E7EB; height: 8px; } QSlider::handle:horizontal { background: #3B82F6; width: 18px; margin: -4px 0; border-radius: 9px; }")
        self.brush_size_slider.valueChanged.connect(self.update_brush_size)

        # Draw Location Widgets
        self.draw_location_label = QLabel("Draw On:")
        self.draw_location_label.setStyleSheet("color: #374151; font-weight: bold; padding: 10px;")
        self.draw_location_combo = QComboBox()
        self.draw_location_combo.addItems(["Slide", "Webcam", "Both"])
        self.draw_location_combo.setStyleSheet("background-color: white; border: 1px solid #E5E7EB; padding: 5px;")
        self.draw_location_combo.currentTextChanged.connect(self.update_draw_location)

        # Other Sidebar Widgets
        self.usage_guide_button = QPushButton("Usage Guide")
        self.usage_guide_button.setFixedHeight(40)
        self.usage_guide_button.setStyleSheet("background-color: #3B82F6; color: white; border: none; padding: 5px;")
        self.usage_guide_button.clicked.connect(self.show_usage_guide)
        self.mode_label = QLabel("Mode: Unknown")
        self.mode_label.setStyleSheet("color: #374151; padding: 5px;")
        self.color_label = QLabel("Color: Unknown")
        self.color_label.setStyleSheet("color: #374151; padding: 5px;")

        # Add Widgets to Sidebar Layout
        self.sidebar_layout.addWidget(self.slide_set_label)
        self.sidebar_layout.addWidget(self.slide_set_list)
        self.sidebar_layout.addWidget(self.add_set_button)
        self.sidebar_layout.addWidget(self.edit_set_button)
        self.sidebar_layout.addWidget(self.delete_set_button)
        self.sidebar_layout.addWidget(self.slide_list_label)
        self.sidebar_layout.addWidget(self.slide_list)
        self.sidebar_layout.addStretch(1)
        self.sidebar_layout.addWidget(QLabel("Drawing Tools:"))
        tool_layout = QHBoxLayout()
        tool_layout.addWidget(self.pen_button)
        tool_layout.addWidget(self.circle_button)
        tool_layout.addWidget(self.square_button)
        self.sidebar_layout.addLayout(tool_layout)
        self.sidebar_layout.addWidget(self.brush_size_label)
        self.sidebar_layout.addWidget(self.brush_size_slider)
        self.sidebar_layout.addWidget(self.draw_location_label)
        self.sidebar_layout.addWidget(self.draw_location_combo)
        self.sidebar_layout.addStretch(1)
        self.sidebar_layout.addWidget(self.usage_guide_button)
        self.sidebar_layout.addWidget(self.mode_label)
        self.sidebar_layout.addWidget(self.color_label)

        self.sidebar_widget.setVisible(False)

        # === Main Content Area ===
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setAlignment(Qt.AlignCenter)

        # Sidebar Toggle Button
        self.sidebar_toggle_button = QPushButton("Hide Sidebar")
        self.sidebar_toggle_button.setFixedHeight(30)
        self.sidebar_toggle_button.setStyleSheet("background-color: #3B82F6; color: white; border: none; padding: 5px;")
        self.sidebar_toggle_button.clicked.connect(self.toggle_sidebar)
        self.sidebar_toggle_button.setVisible(False)
        self.content_layout.addWidget(self.sidebar_toggle_button)

        # --- Login Widget ---
        self.login_widget = QWidget()
        self.login_widget.setFixedSize(350, 400)  # Điều chỉnh kích thước phù hợp
        self.login_widget.setStyleSheet("""
            background-color: white;
            border-radius: 12px;
        """)
        self.login_layout = QGridLayout(self.login_widget)
        self.login_layout.setContentsMargins(30, 30, 30, 30)
        self.login_layout.setSpacing(20)  # Tăng khoảng cách giữa các phần tử

        # Login Title
        login_title = QLabel("GestureTeach")
        login_title.setFont(QFont("Arial", 18, QFont.Bold))  # Giảm kích thước font cho phù hợp
        login_title.setStyleSheet("color: #1E293B; margin-bottom: 20px;")
        login_title.setAlignment(Qt.AlignCenter)

        # Username/Email Input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username or Email")
        self.username_input.setFixedWidth(250)  # Kích thước hợp lý dựa trên hình ảnh
        self.username_input.setFixedHeight(40)  # Kích thước hợp lý
        self.username_input.setStyleSheet("""
            background-color: #F9FAFB;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 10px;
            font-size: 14px;
            text-align: left;
        """)

        # Password Input
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedWidth(250)  # Kích thước hợp lý
        self.password_input.setFixedHeight(40)  # Kích thước hợp lý
        self.password_input.setStyleSheet("""
            background-color: #F9FAFB;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 10px;
            font-size: 14px;
            text-align: left;
        """)

        # Login Button
        self.login_button = QPushButton("Sign In")
        self.login_button.setFixedWidth(250)  # Kích thước hợp lý
        self.login_button.setFixedHeight(45)  # Kích thước hợp lý
        self.login_button.setStyleSheet("""
            background-color: #3B82F6;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
        """)
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.clicked.connect(self.handle_login)

        # Register Button
        self.register_button = QPushButton("Create New Account")
        self.register_button.setFixedWidth(250)  # Kích thước hợp lý
        self.register_button.setFixedHeight(40)  # Kích thước hợp lý
        self.register_button.setStyleSheet("""
            background-color: transparent;
            color: #3B82F6;
            border: 1px solid #3B82F6;
            border-radius: 8px;
            font-size: 14px;
        """)
        self.register_button.setCursor(Qt.PointingHandCursor)
        self.register_button.clicked.connect(self.show_register)

        # Add to Login Layout
        self.login_layout.addWidget(login_title, 0, 0, 1, 2, Qt.AlignHCenter)
        self.login_layout.addWidget(self.username_input, 1, 0, 1, 2, Qt.AlignHCenter)
        self.login_layout.addWidget(self.password_input, 2, 0, 1, 2, Qt.AlignHCenter)
        self.login_layout.addWidget(self.login_button, 3, 0, 1, 2, Qt.AlignHCenter)
        self.login_layout.addWidget(self.register_button, 4, 0, 1, 2, Qt.AlignHCenter)
        self.login_layout.setRowStretch(5, 1)

        self.content_layout.addWidget(self.login_widget)

        # --- Main Application Widget ---
        self.main_widget = QWidget()
        self.main_widget_layout = QVBoxLayout(self.main_widget)
        self.main_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.main_widget_layout.setSpacing(5)

        # Top Area: Slide display and vertical buttons
        self.slide_area_layout = QHBoxLayout()
        self.slide_label = QLabel()
        self.slide_label.setMinimumSize(640, 360)
        self.slide_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.slide_label.setAlignment(Qt.AlignCenter)
        self.slide_label.setStyleSheet("background-color: #1E293B; border: 1px solid #E5E7EB;")

        self.button_widget = QWidget()
        self.button_widget.setFixedWidth(150)
        self.button_layout = QVBoxLayout(self.button_widget)
        self.button_layout.setContentsMargins(5, 0, 0, 0)
        self.fullscreen_button = QPushButton("Full Screen")
        self.fullscreen_button.setFixedHeight(40)
        self.fullscreen_button.setStyleSheet("background-color: #3B82F6; color: white; border: none; padding: 5px;")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self.screenshot_button = QPushButton("Take Screenshot")
        self.screenshot_button.setFixedHeight(40)
        self.screenshot_button.setStyleSheet("background-color: #3B82F6; color: white; border: none; padding: 5px;")
        self.screenshot_button.clicked.connect(self.take_screenshot)
        self.blackboard_button = QPushButton("Blackboard: Off")
        self.blackboard_button.setFixedHeight(40)
        self.blackboard_button.setCheckable(True)
        self.blackboard_button.setStyleSheet("background-color: #3B82F6; color: white; border: none; padding: 5px;")
        self.blackboard_button.clicked.connect(self.toggle_blackboard_mode)
        self.button_layout.addWidget(self.fullscreen_button)
        self.button_layout.addWidget(self.screenshot_button)
        self.button_layout.addWidget(self.blackboard_button)
        self.button_layout.addStretch()

        self.slide_area_layout.addWidget(self.slide_label, 1)
        self.slide_area_layout.addWidget(self.button_widget)
        self.main_widget_layout.addLayout(self.slide_area_layout, 1)

        # Bottom Area: Webcam feed and Logout button
        self.bottom_widget = QWidget()
        self.bottom_layout = QHBoxLayout(self.bottom_widget)
        self.bottom_layout.addStretch()
        self.webcam_widget = QWidget()
        self.webcam_layout = QVBoxLayout(self.webcam_widget)
        self.webcam_label = QLabel("Webcam Feed")
        self.webcam_label.setFixedSize(320, 240)
        self.webcam_label.setAlignment(Qt.AlignCenter)
        self.webcam_label.setStyleSheet("background-color: #1E293B; border: 1px solid #E5E7EB;")
        self.logout_button = QPushButton("Logout")
        self.logout_button.setFixedHeight(30)
        self.logout_button.setStyleSheet("background-color: #EF4444; color: white; border: none; padding: 5px;")
        self.logout_button.clicked.connect(self.handle_logout)
        self.webcam_layout.addWidget(self.webcam_label)
        self.webcam_layout.addWidget(self.logout_button, 0, Qt.AlignRight)
        self.bottom_layout.addWidget(self.webcam_widget)

        self.main_widget_layout.addWidget(self.bottom_widget)
        self.content_layout.addWidget(self.main_widget)
        self.main_widget.setVisible(False)

        # Add sidebar and content area to the main horizontal layout
        self.main_layout.addWidget(self.sidebar_widget)
        self.main_layout.addWidget(self.content_widget, 1)

        # --- Toast Notification Labels ---
        self.toast_timer = QTimer()
        self.toast_timer.setSingleShot(True)
        self.toast_label = QLabel(self)
        self.toast_label.setStyleSheet(
            "background-color: rgba(30, 41, 59, 0.9); color: white; padding: 8px 15px; border-radius: 8px; font-size: 12px;"
        )
        self.toast_label.setAlignment(Qt.AlignCenter)
        self.toast_label.setVisible(False)
        self.toast_timer.timeout.connect(self.hide_toast)

        self.screenshot_toast_timer = QTimer()
        self.screenshot_toast_timer.setSingleShot(True)
        self.screenshot_toast_label = QLabel(self)
        self.screenshot_toast_label.setStyleSheet(
            "background-color: #10B981; color: white; padding: 8px 15px; border: 2px solid white; border-radius: 8px; font-size: 14px;"
        )
        self.screenshot_toast_label.setAlignment(Qt.AlignCenter)
        self.screenshot_toast_label.setVisible(False)
        self.screenshot_toast_timer.timeout.connect(self.hide_toast)

    def show_toast(self, message, duration=5000, is_screenshot=False):
        """Show a temporary toast notification at the appropriate position."""
        if is_screenshot:
            toast_label = self.screenshot_toast_label
            toast_timer = self.screenshot_toast_timer
        else:
            toast_label = self.toast_label
            toast_timer = self.toast_timer

        toast_label.setText(message)
        toast_label.adjustSize()

        try:
            parent_width = self.width()
            parent_height = self.height()

            if is_screenshot:
                toast_x = (parent_width - toast_label.width()) // 2
                toast_y = parent_height - toast_label.height() - 20
            else:
                toast_x = parent_width - toast_label.width() - 20
                toast_y = 20

            toast_label.move(toast_x, toast_y)
            toast_label.raise_()
            toast_label.setVisible(True)
            toast_timer.start(duration)
        except Exception as e:
            logging.error(f"Error showing toast: {e}")

    def hide_toast(self):
        """Hide both toast labels."""
        self.toast_label.setVisible(False)
        self.screenshot_toast_label.setVisible(False)

    def resizeEvent(self, event):
        """Handle window resize event to reposition both toasts."""
        super().resizeEvent(event)
        if self.toast_label.isVisible():
            try:
                parent_width = self.width()
                toast_x = parent_width - self.toast_label.width() - 20
                toast_y = 20
                self.toast_label.move(toast_x, toast_y)
            except Exception as e:
                logging.error(f"Error repositioning general toast on resize: {e}")

        if self.screenshot_toast_label.isVisible():
            try:
                parent_width = self.width()
                parent_height = self.height()
                toast_x = (parent_width - self.screenshot_toast_label.width()) // 2
                toast_y = parent_height - self.screenshot_toast_label.height() - 20
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
            if hasattr(self, 'register_widget'):
                self.register_widget.setVisible(False)
            self.main_widget.setVisible(True)
            self.sidebar_widget.setVisible(self.sidebar_visible)
            self.sidebar_toggle_button.setVisible(True)
            self.update_sidebar_toggle_text()
            self.load_slide_sets()
            self.statusBar().showMessage(f"Logged in as user ID: {self.current_user_id}")
            self.show_toast("Login successful")
            self.password_input.clear()
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username/email or password.")
            self.password_input.clear()

    def handle_logout(self):
        """Handle user logout."""
        reply = QMessageBox.question(self, "Logout", "Are you sure you want to logout?\nUnsaved annotations might be lost if auto-save failed.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        self.save_current_annotations()

        user_id = self.current_user_id
        self.current_user_id = None
        self.main_widget.setVisible(False)
        self.sidebar_widget.setVisible(False)
        self.sidebar_toggle_button.setVisible(False)
        self.login_widget.setVisible(True)
        self.username_input.clear()
        self.password_input.clear()

        self.slide_label.clear()
        self.slide_label.setText("Login to view slides")
        self.slide_label.setStyleSheet("background-color: #1E293B; border: 1px solid #E5E7EB;")
        self.webcam_label.clear()
        self.webcam_label.setText("Webcam Feed")
        self.webcam_label.setStyleSheet("background-color: #1E293B; border: 1px solid #E5E7EB;")
        self.slide_set_list.clear()
        self.slide_list.clear()
        self.slides = []
        self.slide_images = []
        self.current_slide_index = -1
        self.original_slide_image = None
        self.current_slide_with_drawings = None
        if self.drawing_canvas:
            self.drawing_canvas.clear_canvas()
            self.drawing_canvas.current_annotations = []

        self.statusBar().showMessage("Logged out. Please log in.")
        self.show_toast("Logged out successfully")

    # --- Registration Handling ---
    def show_register(self):
        """Show registration interface."""
        self.login_widget.setVisible(False)
        if not hasattr(self, 'register_widget'):
            self.register_widget = QWidget()
            self.register_widget.setFixedSize(350, 450)  # Điều chỉnh kích thước phù hợp
            self.register_widget.setStyleSheet("""
                background-color: white;
                border-radius: 12px;
            """)
            self.register_layout = QGridLayout(self.register_widget)
            self.register_layout.setContentsMargins(30, 30, 30, 30)
            self.register_layout.setSpacing(20)  # Tăng khoảng cách giữa các phần tử

            # Register Title
            reg_title = QLabel("Create Your Account")
            reg_title.setFont(QFont("Arial", 18, QFont.Bold))  # Giảm kích thước font cho phù hợp
            reg_title.setStyleSheet("color: #1E293B; margin-bottom: 20px;")
            reg_title.setAlignment(Qt.AlignCenter)

            # Username Input
            self.reg_username = QLineEdit()
            self.reg_username.setPlaceholderText("Username")
            self.reg_username.setFixedWidth(250)  # Kích thước hợp lý
            self.reg_username.setFixedHeight(40)  # Kích thước hợp lý
            self.reg_username.setStyleSheet("""
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                text-align: left;
            """)

            # Email Input
            self.reg_email = QLineEdit()
            self.reg_email.setPlaceholderText("Email")
            self.reg_email.setFixedWidth(250)  # Kích thước hợp lý
            self.reg_email.setFixedHeight(40)  # Kích thước hợp lý
            self.reg_email.setStyleSheet("""
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                text-align: left;
            """)

            # Password Input
            self.reg_password = QLineEdit()
            self.reg_password.setPlaceholderText("Password (8+ chars, mixed)")
            self.reg_password.setEchoMode(QLineEdit.Password)
            self.reg_password.setFixedWidth(250)  # Kích thước hợp lý
            self.reg_password.setFixedHeight(40)  # Kích thước hợp lý
            self.reg_password.setStyleSheet("""
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                text-align: left;
            """)

            # Register Button
            self.reg_button = QPushButton("Create Account")
            self.reg_button.setFixedWidth(250)  # Kích thước hợp lý
            self.reg_button.setFixedHeight(45)  # Kích thước hợp lý
            self.reg_button.setStyleSheet("""
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            """)
            self.reg_button.setCursor(Qt.PointingHandCursor)
            self.reg_button.clicked.connect(self.handle_register)

            # Back Button
            self.back_button = QPushButton("Back to Sign In")
            self.back_button.setFixedWidth(250)  # Kích thước hợp lý
            self.back_button.setFixedHeight(40)  # Kích thước hợp lý
            self.back_button.setStyleSheet("""
                background-color: transparent;
                color: #3B82F6;
                border: 1px solid #3B82F6;
                border-radius: 8px;
                font-size: 14px;
            """)
            self.back_button.setCursor(Qt.PointingHandCursor)
            self.back_button.clicked.connect(self.show_login)

            # Add to Register Layout
            self.register_layout.addWidget(reg_title, 0, 0, 1, 2, Qt.AlignHCenter)
            self.register_layout.addWidget(self.reg_username, 1, 0, 1, 2, Qt.AlignHCenter)
            self.register_layout.addWidget(self.reg_email, 2, 0, 1, 2, Qt.AlignHCenter)
            self.register_layout.addWidget(self.reg_password, 3, 0, 1, 2, Qt.AlignHCenter)
            self.register_layout.addWidget(self.reg_button, 4, 0, 1, 2, Qt.AlignHCenter)
            self.register_layout.addWidget(self.back_button, 5, 0, 1, 2, Qt.AlignHCenter)
            self.register_layout.setRowStretch(6, 1)

            self.content_layout.addWidget(self.register_widget)
            self.register_widget.setVisible(False)

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

        if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            QMessageBox.warning(self, "Registration Error", "Invalid email format.")
            return

        if not (len(password) >= 8 and
                re.search(r"[A-Z]", password) and
                re.search(r"[a-z]", password) and
                re.search(r"[0-9]", password) and
                re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)):
            QMessageBox.warning(self, "Registration Error", "Password does not meet complexity requirements.\n(Min 8 chars, uppercase, lowercase, number, symbol)")
            return

        success, message = self.db.register_user(username, email, password)

        if success:
            QMessageBox.information(self, "Success", "Registration successful! You can now log in.")
            self.show_login()
        else:
            QMessageBox.warning(self, "Registration Failed", f"Registration failed: {message}")

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
                    self.load_slide_sets()
                    self.show_toast(f"Slide set '{name}' added")

    def edit_slide_set(self):
        """Edit slides within an existing slide set."""
        selected_set_item = self.slide_set_list.currentItem()
        if not selected_set_item:
            QMessageBox.warning(self, "Error", "Please select a slide set from the list to edit.")
            return

        set_id = selected_set_item.data(Qt.UserRole)
        set_name = selected_set_item.text()

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Slides in Set: {set_name}")
        dialog.setMinimumSize(400, 300)
        dialog.setStyleSheet("background-color: #F9FAFB; border: 1px solid #E5E7EB;")
        dialog_layout = QVBoxLayout(dialog)

        list_label = QLabel("Current Slides (Drag to Reorder - Future Feature):")
        list_label.setStyleSheet("color: #374151; font-weight: bold; padding: 10px;")
        slide_list_widget = QListWidget()
        slide_list_widget.setStyleSheet("background-color: white; border: 1px solid #E5E7EB; padding: 5px;")

        current_slides = self.db.get_slides(set_id)
        slide_map = {}
        for slide_data in current_slides:
            slide_id_db, file_path, order_index = slide_data
            item_text = f"{order_index + 1}: {os.path.basename(file_path)}"
            list_item = QListWidgetItem(item_text)
            slide_map[item_text] = (slide_id_db, file_path)
            slide_list_widget.addItem(list_item)

        add_button = QPushButton("Add Slides...")
        add_button.setStyleSheet("background-color: #3B82F6; color: white; border: none; padding: 5px;")
        remove_button = QPushButton("Remove Selected Slide")
        remove_button.setStyleSheet("background-color: #EF4444; color: white; border: none; padding: 5px;")

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
                self.load_slide_sets()

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
        self.slide_label.setStyleSheet("background-color: #1E293B; border: 1px solid #E5E7EB;")
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
            self.slide_label.setStyleSheet("background-color: #1E293B; border: 1px solid #E5E7EB;")
            self.current_slide_index = -1
            if self.drawing_canvas:
                self.drawing_canvas.clear_canvas()
                self.drawing_canvas.current_annotations = []
            self.statusBar().showMessage(f"Selected empty set: '{set_name}'.")
            return

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
            self.slide_label.setStyleSheet("background-color: #1E293B; border: 1px solid #E5E7EB;")
            self.current_slide_index = -1
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
            self.slide_label.setStyleSheet("background-color: #1E293B; border: 1px solid #E5E7EB;")
            if self.drawing_canvas:
                self.drawing_canvas.clear_canvas()
                self.drawing_canvas.current_annotations = []
            return

        img_original = self.slide_images[self.current_slide_index]

        if img_original is None:
            self.original_slide_image = None
            slide_path = self.slides[self.current_slide_index][1]
            self.slide_label.setText(f"Error: Cannot load slide\n{os.path.basename(slide_path)}")
            self.slide_label.setStyleSheet("background-color: #1E293B; border: 1px solid #E5E7EB;")
            if self.drawing_canvas:
                self.drawing_canvas.clear_canvas()
                self.drawing_canvas.current_annotations = []
            return

        target_w, target_h = 1920, 1080
        try:
            if img_original.shape[1] != target_w or img_original.shape[0] != target_h:
                self.original_slide_image = cv2.resize(img_original, (target_w, target_h), interpolation=cv2.INTER_AREA)
            else:
                self.original_slide_image = img_original.copy()
        except cv2.error as e:
            self.original_slide_image = None
            self.slide_label.setText("Error processing slide image.")
            self.slide_label.setStyleSheet("background-color: #1E293B; border: 1px solid #E5E7EB;")
            return

        if self.drawing_canvas and self.current_user_id:
            slide_id = self.slides[self.current_slide_index][0]
            if slide_id:
                try:
                    annotations = self.db.load_annotations(slide_id, self.current_user_id)
                    self.drawing_canvas.load_annotations(annotations)
                except Exception as e:
                    QMessageBox.warning(self, "Annotation Error", f"Failed to load annotations for slide {slide_id}.")
                    self.drawing_canvas.clear_canvas()

        display_image = self.prepare_display_image(self.original_slide_image)
        self.update_slide_label(display_image)

    def prepare_display_image(self, base_image):
        """Combines the base slide image with blackboard effect and drawings using masking."""
        if base_image is None or base_image.size == 0:
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

            self.current_slide_with_drawings = img_to_display.copy()
            return img_to_display

        except cv2.error as e:
            return base_image
        except Exception as e:
            return None

    def update_slide_label(self, bgr_image):
        """Updates the slide QLabel with the given BGR image."""
        if bgr_image is None or bgr_image.size == 0:
            self.slide_label.setText("Error displaying slide.")
            self.slide_label.setStyleSheet("background-color: #1E293B; border: 1px solid #E5E7EB;")
            return

        try:
            img_rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
            h, w, ch = img_rgb.shape
            if h <= 0 or w <= 0:
                self.slide_label.setText("Invalid Image.")
                return

            bytes_per_line = ch * w
            q_img = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img)
            scaled_pixmap = pixmap.scaled(self.slide_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.slide_label.setPixmap(scaled_pixmap)
            self.slide_label.setStyleSheet("background-color: transparent; border: 1px solid #E5E7EB;")
        except Exception as e:
            self.slide_label.setText("Slide Display Error.")
            self.slide_label.setStyleSheet("background-color: #1E293B; border: 1px solid #E5E7EB;")

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

    def toggle_blackboard_mode(self):
        """Toggle blackboard mode."""
        self.blackboard_mode = not self.blackboard_mode
        self.blackboard_button.setChecked(self.blackboard_mode)
        self.blackboard_button.setText(f"Blackboard: {'On' if self.blackboard_mode else 'Off'}")
        display_image = self.prepare_display_image(self.original_slide_image)
        self.update_slide_label(display_image)
        self.show_toast(f"Blackboard mode {'enabled' if self.blackboard_mode else 'disabled'}")

    def take_screenshot(self):
        """Capture and save a screenshot of the current slide with drawings to the 'screens' folder."""
        current_time = time.time()
        if current_time - self.last_screenshot_time < 1.0:
            self.show_toast("Chụp màn hình quá nhanh! Vui lòng đợi.", duration=1500, is_screenshot=False)
            return

        image_to_save = self.current_slide_with_drawings

        if image_to_save is None or image_to_save.size == 0:
            QMessageBox.warning(self, "Screenshot Error", "No slide content to capture.")
            return

        screens_dir = "screens"
        try:
            if not os.path.exists(screens_dir):
                os.makedirs(screens_dir)
        except OSError as e:
            QMessageBox.critical(self, "Directory Error", f"Could not create screenshot directory:\n{screens_dir}\nPlease check permissions.")
            return

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(screens_dir, f"screenshot_{timestamp}.png")

        try:
            success = cv2.imwrite(filename, image_to_save)
            if not success:
                raise IOError("cv2.imwrite returned False")
            self.last_screenshot_time = current_time
            self.show_toast("Đã chụp màn hình", duration=3000, is_screenshot=True)
        except Exception as e:
            QMessageBox.warning(self, "Screenshot Error", f"Failed to save screenshot.\nError: {e}")

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
            self.webcam_label.setText("Webcam Error")

    def update_slide(self, img):
        """Update the slide display with the combined image from main loop."""
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
                return

            annotations_to_save = self.drawing_canvas.current_annotations
            if annotations_to_save:
                temp_list = list(annotations_to_save)
                self.drawing_canvas.current_annotations = []
                for annotation in temp_list:
                    if not self.db.save_annotation(slide_id, self.current_user_id, annotation):
                        self.drawing_canvas.current_annotations.append(annotation)

    # --- Usage Guide ---
    def show_usage_guide(self):
        """Show usage guide in a non-modal dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("GestureTeach Usage Guide")
        dialog.setMinimumSize(500, 400)
        dialog.setStyleSheet("background-color: #F9FAFB; border: 1px solid #E5E7EB;")
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
                <li><b>Adjust Size:</b> Use sidebar sliders.</li>
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
        close_button.setStyleSheet("background-color: #3B82F6; color: white; border: none; padding: 5px;")
        close_button.clicked.connect(dialog.accept)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        dialog.show()

    # --- Window Close Event ---
    def closeEvent(self, event):
        """Handle window close event."""
        reply = QMessageBox.question(self, "Exit GestureTeach",
                                     "Are you sure you want to exit?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.save_current_annotations()
            event.accept()
        else:
            event.ignore()

if __name__ == "__main__":
    log_format = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    logging.basicConfig(level=logging.DEBUG,
                        format=log_format,
                        handlers=[logging.StreamHandler(sys.stdout)])

    class MockDatabase:
        def login_user(self, u, p): return 1 if p == "test" else None
        def get_slide_sets(self, uid): return [(1, "Demo Set 1"), (2, "Empty Set")]
        def get_slides(self, sid):
            dummy_dir = "dummy_slides_test_gui"
            os.makedirs(dummy_dir, exist_ok=True)
            dummy_path1 = os.path.join(dummy_dir, "dummy_slide1.png")
            dummy_path2 = os.path.join(dummy_dir, "dummy_slide2.jpg")
            if not os.path.exists(dummy_path1):
                cv2.imwrite(dummy_path1, np.zeros((100, 100, 3), dtype=np.uint8) + 200)
            if not os.path.exists(dummy_path2):
                cv2.imwrite(dummy_path2, np.zeros((100, 100, 3), dtype=np.uint8) + 100)
            if sid == 1:
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
        def close(self): pass

    app = QApplication(sys.argv)
    mock_db = MockDatabase()
    window = AppGUI(mock_db)

    class MockDrawingCanvas:
        def __init__(self):
            self.canvas = np.zeros((1080, 1920, 3), dtype=np.uint8)
            self.current_annotations = [{'type':'mock_initial'}]
        def set_brush_size(self, s): pass
        def clear_canvas(self): self.canvas.fill(0)
        def load_annotations(self, a): self.clear_canvas()
        def get_preview(self): return np.zeros((1080, 1920, 3), dtype=np.uint8)

    mock_canvas = MockDrawingCanvas()
    window.set_drawing_canvas(mock_canvas)
    window.show()
    sys.exit(app.exec_())