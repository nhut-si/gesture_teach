GestureTeach
GestureTeach is an innovative application that allows users to control presentations, draw on slides or webcam feed, and manage slide sets using hand gestures. It leverages MediaPipe for hand detection, PyQt5 for the GUI, and MySQL for data management.
Features

Gesture-based control: Navigate slides, switch modes (presentation, drawing, erasing), and capture screenshots using hand gestures.
Drawing tools: Draw on slides or webcam with pen, circle, or square tools, with customizable brush size, opacity, and colors.
Slide management: Create, edit, and delete slide sets with support for PNG/JPG images.
Blackboard mode: Draw on a dark background for enhanced teaching scenarios.
User authentication: Secure login and registration with bcrypt-encrypted passwords.
Database integration: Store user data, slide sets, slides, and annotations in MySQL.

Requirements

Python 3.8+
MySQL Server
Webcam
Required Python packages:pip install opencv-python mediapipe pyqt5 mysql-connector-python bcrypt python-dotenv



Installation

Clone the repository:git clone <repository-url>
cd GestureTeach


Set up MySQL database:
Create a database named gesture_teach.
Run the following SQL to create tables:CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE,
    email VARCHAR(100) UNIQUE,
    password VARCHAR(255)
);
CREATE TABLE slide_sets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    name VARCHAR(100),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE slides (
    id INT AUTO_INCREMENT PRIMARY KEY,
    slide_set_id INT,
    file_path VARCHAR(255),
    order_index INT,
    FOREIGN KEY (slide_set_id) REFERENCES slide_sets(id)
);
CREATE TABLE annotations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    slide_id INT,
    user_id INT,
    data TEXT,
    FOREIGN KEY (slide_id) REFERENCES slides(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);




Configure environment variables:
Create a .env file in the project root with the following content:DB_HOST=localhost
DB_PORT=3306
DB_USER=your_username
DB_PASSWORD=your_password
DB_NAME=gesture_teach




Install dependencies:pip install -r requirements.txt


Run the application:python main.py



Usage

Login/Register: Use the GUI to register a new account or log in with existing credentials.
Create Slide Sets: Add a new slide set and select PNG/JPG images to include.
Gesture Controls:
Presentation Mode: Thumb + index up ([1, 1, 0, 0, 0]) to enter. Use index finger ([0, 1, 0, 0, 0]) for next slide, thumb ([1, 0, 0, 0, 0]) for previous slide.
Drawing Mode: Index + middle fingers up ([0, 1, 1, 0, 0]). Draw with index finger, change colors with all fingers up.
Erasing Mode: Index + middle + ring fingers up ([0, 1, 1, 1, 0]). Erase with index finger, clear canvas with all fingers.
Other Gestures: Thumb + index + middle ([1, 1, 1, 0, 0]) for screenshot, middle + ring ([0, 0, 1, 1, 0]) for fullscreen toggle.


Keyboard Shortcuts:
Left/Right Arrow: Navigate slides.
F: Toggle fullscreen.
Esc: Exit fullscreen.



Project Structure

main.py: Main application logic and integration.
gui.py: PyQt5-based GUI implementation.
hand_detector.py: Hand detection using MediaPipe.
gesture_control.py: Gesture recognition and mode switching.
drawing_utils.py: Canvas for drawing on slides/webcam.
slide_control.py: Slide navigation and display.
database.py: MySQL database operations.
.env: Environment variables for database configuration.

Contributing
Contributions are welcome! Please submit a pull request or open an issue for suggestions.
License
MIT License
