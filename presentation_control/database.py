import mysql.connector
from mysql.connector import Error
import bcrypt
import os
import re
from dotenv import load_dotenv
import json
import logging

# Thiết lập logging
logging.basicConfig(level=logging.INFO, filename='gesture_teach.log', format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

class Database:
    def __init__(self):
        """Initialize database connection using environment variables."""
        self.config = {
            'host': os.getenv('DB_HOST'),
            'port': int(os.getenv('DB_PORT')),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME')
        }
        self.connection = None
        self.connect()
        if self.connection and self.connection.is_connected():
            self.create_tables()

    def connect(self):
        """Establish connection to MySQL database."""
        try:
            self.connection = mysql.connector.connect(**self.config)
            if self.connection.is_connected():
                logging.info("Connected to MySQL database")
        except Error as e:
            logging.error(f"Error connecting to MySQL: {e}")

    def create_tables(self):
        """Create necessary tables if they don't exist."""
        try:
            cursor = self.connection.cursor()
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password VARBINARY(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create slide_sets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS slide_sets (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)

            # Create slides table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS slides (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    slide_set_id INT,
                    file_path VARCHAR(255) NOT NULL,
                    order_index INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (slide_set_id) REFERENCES slide_sets(id)
                )
            """)

            # Create annotations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS annotations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    slide_id INT,
                    user_id INT,
                    data JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (slide_id) REFERENCES slides(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)

            self.connection.commit()
            logging.info("Database tables created or verified.")
        except Error as e:
            logging.error(f"Error creating tables: {e}")
        finally:
            cursor.close()

    def close(self):
        """Close MySQL database connection."""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logging.info("MySQL connection closed")

    def register_user(self, username, email, password):
        """Register a new user with validated inputs."""
        try:
            if not all([username, email, password]):
                logging.error("Error: Missing required fields")
                return False, "Missing required fields"
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                logging.error("Error: Invalid email format")
                return False, "Invalid email format"
            cursor = self.connection.cursor()
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            query = "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)"
            cursor.execute(query, (username, email, hashed_password))
            self.connection.commit()
            return True, "Registration successful"
        except Error as e:
            logging.error(f"Error registering user: {e}")
            return False, str(e)
        finally:
            cursor.close()

    def login_user(self, username, password):
        """Authenticate a user."""
        try:
            cursor = self.connection.cursor()
            query = "SELECT id, password FROM users WHERE username = %s OR email = %s"
            cursor.execute(query, (username, username))
            user = cursor.fetchone()
            if user:
                hashed_password = user[1].encode('utf-8') if isinstance(user[1], str) else user[1]
                if bcrypt.checkpw(password.encode('utf-8'), hashed_password):
                    return user[0]
            return None
        except Error as e:
            logging.error(f"Error logging in user: {e}")
            return None
        finally:
            cursor.close()

    def add_slide_set(self, user_id, name):
        """Add a new slide set for a user."""
        try:
            cursor = self.connection.cursor()
            query = "INSERT INTO slide_sets (user_id, name) VALUES (%s, %s)"
            cursor.execute(query, (user_id, name.strip()))
            self.connection.commit()
            return cursor.lastrowid
        except Error as e:
            logging.error(f"Error adding slide set: {e}")
            return None
        finally:
            cursor.close()

    def delete_slide_set(self, set_id):
        """Delete a slide set and its associated slides."""
        try:
            cursor = self.connection.cursor()
            # Quan trọng: Xóa các slide con trước
            cursor.execute("DELETE FROM annotations WHERE slide_id IN (SELECT id FROM slides WHERE slide_set_id = %s)", (set_id,)) # <<< THÊM: Xóa annotations liên quan
            cursor.execute("DELETE FROM slides WHERE slide_set_id = %s", (set_id,))
            cursor.execute("DELETE FROM slide_sets WHERE id = %s", (set_id,))
            self.connection.commit() # <<< QUAN TRỌNG: Đảm bảo có commit
            logging.info(f"Successfully deleted slide set with id: {set_id}") # Ghi log thành công
            return True
        except Error as e:
            logging.error(f"Error deleting slide set with id {set_id}: {e}") # Ghi log lỗi
            # Có thể thêm self.connection.rollback() ở đây nếu cần
            return False
        finally:
            # Đảm bảo cursor được đóng ngay cả khi có lỗi
            if 'cursor' in locals() and cursor is not None:
                cursor.close()

    def add_slide(self, slide_set_id, file_path, order_index):
        """Add a slide to a slide set."""
        try:
            cursor = self.connection.cursor()
            query = "INSERT INTO slides (slide_set_id, file_path, order_index) VALUES (%s, %s, %s)"
            cursor.execute(query, (slide_set_id, file_path, order_index))
            self.connection.commit()
            return True
        except Error as e:
            logging.error(f"Error adding slide: {e}")
            return False
        finally:
            cursor.close()

    def remove_slide(self, slide_set_id, file_path):
        """Remove a slide from a slide set."""
        try:
            cursor = self.connection.cursor()
            query = "DELETE FROM slides WHERE slide_set_id = %s AND file_path = %s"
            cursor.execute(query, (slide_set_id, file_path))
            self.connection.commit()
            return True
        except Error as e:
            logging.error(f"Error removing slide: {e}")
            return False
        finally:
            cursor.close()

    def remove_slide_by_id(self, slide_id):
        """Remove a slide by its database ID."""
        try:
            cursor = self.connection.cursor()
            # Quan trọng: Xóa annotations liên quan đến slide này trước
            cursor.execute("DELETE FROM annotations WHERE slide_id = %s", (slide_id,)) # <<< THÊM: Xóa annotations liên quan
            query = "DELETE FROM slides WHERE id = %s"
            cursor.execute(query, (slide_id,))
            self.connection.commit() # <<< QUAN TRỌNG: Đảm bảo có commit
            logging.info(f"Successfully removed slide with id: {slide_id}") # Ghi log thành công
            return True
        except Error as e:
            logging.error(f"Error removing slide by id {slide_id}: {e}") # Ghi log lỗi
            # Có thể thêm self.connection.rollback() ở đây nếu cần
            return False
        finally:
            if 'cursor' in locals() and cursor is not None:
                cursor.close()

    def get_slide_sets(self, user_id):
        """Get all slide sets for a user."""
        try:
            cursor = self.connection.cursor()
            query = "SELECT id, name FROM slide_sets WHERE user_id = %s"
            cursor.execute(query, (user_id,))
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Error fetching slide sets: {e}")
            return []
        finally:
            cursor.close()

    def get_slides(self, slide_set_id):
        """Get all slides in a slide set, ordered by index."""
        try:
            cursor = self.connection.cursor()
            query = "SELECT id, file_path, order_index FROM slides WHERE slide_set_id = %s ORDER BY order_index"
            cursor.execute(query, (slide_set_id,))
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Error fetching slides: {e}")
            return []
        finally:
            cursor.close()

    def save_annotation(self, slide_id, user_id, data):
        """Save annotation data for a slide as JSON."""
        try:
            cursor = self.connection.cursor()
            query = "INSERT INTO annotations (slide_id, user_id, data, created_at) VALUES (%s, %s, %s, NOW())"
            if isinstance(data, dict):
                data = json.dumps(data)
            # Kiểm tra xem data có phải JSON hợp lệ không
            json.loads(data)  # Nếu không hợp lệ, sẽ raise JSONDecodeError
            cursor.execute(query, (slide_id, user_id, data))
            self.connection.commit()
            return True
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON data: {data}, Error: {e}")
            return False
        except Error as e:
            logging.error(f"Error saving annotation: {e}")
            return False
        finally:
            cursor.close()

    def load_annotations(self, slide_id, user_id):
        """Load all annotations for a specific slide and user, expecting JSON data."""
        try:
            cursor = self.connection.cursor()
            query = "SELECT data FROM annotations WHERE slide_id = %s AND user_id = %s ORDER BY created_at"
            cursor.execute(query, (slide_id, user_id))
            annotations = cursor.fetchall()
            result = []
            for annotation in annotations:
                try:
                    data = annotation[0]
                    if isinstance(data, str):
                        parsed_data = json.loads(data)
                        result.append(parsed_data)
                    else:
                        logging.error(f"Unexpected data type for annotation: {type(data)}, value: {data}")
                except json.JSONDecodeError as e:
                    logging.error(f"Error parsing JSON annotation: {data}, Error: {e}")
                except Exception as e:
                    logging.error(f"Error processing annotation: {annotation}, Error: {e}")
            return result
        except Error as e:
            logging.error(f"Error loading annotations: {e}")
            return []
        finally:
            cursor.close()