# Early import of Flask-Login patch
import flask_login_patch

# Standard Library Imports
import os
import re
import json
import logging
import tempfile
import mimetypes
import subprocess
import secrets
import sys
import traceback
import inspect  # Add inspect module import
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, unquote, parse_qsl, urlencode

# Flask and Web Framework Imports
from flask import (
    Flask, request, render_template, redirect, url_for, 
    flash, send_file, Response, stream_with_context
)
from werkzeug.utils import secure_filename

# Initialize Flask app first
app = Flask(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Logging Configuration
def configure_logging():
    """
    Configure comprehensive logging for the application
    Ensures detailed logs for debugging and monitoring
    """
    # Ensure logs directory exists
    log_dir = os.path.join(app.root_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,  # Capture all levels of logs
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # File handler for persistent logging
            logging.FileHandler(os.path.join(log_dir, 'app.log'), encoding='utf-8'),
            # Console handler for immediate visibility
            logging.StreamHandler()
        ]
    )

    # Set SQLAlchemy logging to warning to reduce verbosity
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

    # Log application startup
    logging.info("Application logging configured successfully")

# Configure logging early
configure_logging()

# Database Configuration Function
def get_database_uri():
    """
    Determine the most appropriate database URI
    
    Returns:
        str: Database connection URI
    """
    # Check DATABASE_URL first
    database_url = os.getenv('DATABASE_URL')
    
    # If not set, try constructing from individual variables
    if not database_url:
        # Check for individual database configuration variables
        db_host = os.getenv('AIVEN_DB_HOST')
        db_port = os.getenv('AIVEN_DB_PORT')
        db_name = os.getenv('AIVEN_DB_NAME', 'defaultdb')
        db_user = os.getenv('AIVEN_DB_USER')
        db_password = os.getenv('AIVEN_DB_PASSWORD')
        
        if db_host and db_port and db_user and db_password:
            database_url = (
                f"postgresql://{db_user}:{db_password}@"
                f"{db_host}:{db_port}/{db_name}?sslmode=require"
            )
        else:
            # Absolute fallback to SQLite
            logging.warning("No database configuration found. Using SQLite.")
            instance_path = os.path.join(app.root_path, 'instance')
            os.makedirs(instance_path, exist_ok=True)
            database_url = f'sqlite:///{os.path.join(instance_path, "app.db")}'
    
    # Log the selected database URI
    logging.info(f"Selected Database URI: {database_url}")
    
    return database_url

# Set secret key using environment variable or generate a secure random key
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Set database URI before initializing SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)

# Ensure database is configured
def configure_database():
    """
    Validate and test database connection
    """
    try:
        # Test database connection
        with app.app_context():
            # Import text for SQL expression
            from sqlalchemy import text
            
            # Explicitly create tables if they don't exist
            db.create_all()
            logging.info("Database tables created successfully")
            
            # Test connection by checking session using text()
            db.session.execute(text('SELECT 1'))
            logging.info("Database connection successful")
    except Exception as conn_error:
        logging.error(f"Database connection test failed: {conn_error}")
        logging.error(traceback.format_exc())
        raise RuntimeError(f"Unable to connect to database: {conn_error}")

# Validate database configuration
try:
    configure_database()
except Exception as config_error:
    logging.critical(f"Fatal database configuration error: {config_error}")
    logging.critical(traceback.format_exc())
    # In a real-world scenario, you might want to have a fallback or emergency shutdown
    raise

# Configure additional app settings
app.config['SQLALCHEMY_ECHO'] = False  # Disable SQL logging in production

# Increase upload limits
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB max upload size
app.config['UPLOAD_CHUNK_SIZE'] = 1024 * 1024 * 10  # 10MB chunks

# Increase chunk size and add caching
app.config['STREAM_CHUNK_SIZE'] = 1024 * 1024 * 20  # 20MB chunks
app.config['CACHE_TYPE'] = 'FileSystemCache'

# Security and Authentication
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt  # Add Bcrypt import
from werkzeug.security import generate_password_hash, check_password_hash

# Media Processing
import ffmpeg
import cv2
import magic  # MIME type detection

# Initialize extensions
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Initialize Bcrypt
bcrypt = Bcrypt(app)

# User Model with improved error handling
class User(UserMixin, db.Model):
    __tablename__ = 'users'  # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    movies = db.relationship('Movie', backref='uploader', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

# Movie Model
class Movie(db.Model):
    __tablename__ = 'movies'  # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    thumbnail = db.Column(db.String(200), nullable=True)
    language = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    try:
        user = User.query.get(int(user_id))
        print(f"User loaded: {user}")
        return user
    except Exception as e:
        print(f"Error loading user {user_id}: {e}")
        return None

def generate_thumbnail(video_path, output_path, size=(320, 240)):
    """
    Generate a thumbnail for a video with improved error handling
    
    Args:
        video_path (str): Path to the source video
        output_path (str): Path to save the thumbnail
        size (tuple): Thumbnail size, default (320, 240)
    
    Returns:
        str: Thumbnail filename or None if generation fails
    """
    try:
        import cv2
        import numpy as np
        
        # Validate input file
        if not os.path.exists(video_path):
            logging.error(f"Video file not found: {video_path}")
            return None
        
        # Open video capture
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logging.error(f"Could not open video file: {video_path}")
            return None
        
        # Read first frame
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            logging.error(f"Could not read first frame from: {video_path}")
            return None
        
        # Resize frame
        resized_frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
        
        # Generate unique filename
        thumbnail_filename = f"thumb_{uuid.uuid4().hex[:8]}.jpg"
        thumbnail_full_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
        
        # Ensure thumbnail directory exists
        os.makedirs(os.path.dirname(thumbnail_full_path), exist_ok=True)
        
        # Save thumbnail
        cv2.imwrite(thumbnail_full_path, resized_frame)
        
        return thumbnail_filename
    
    except ImportError:
        logging.warning("OpenCV not installed. Skipping thumbnail generation.")
        return None
    except Exception as e:
        logging.error(f"Unexpected error generating thumbnail: {e}")
        return None

def check_ffmpeg_availability():
    """
    Check if FFmpeg is installed and available in system PATH
    
    Returns:
        bool: True if FFmpeg is available, False otherwise
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False

# Check FFmpeg availability during app initialization
FFMPEG_AVAILABLE = check_ffmpeg_availability()
if not FFMPEG_AVAILABLE:
    logging.warning("""
    FFmpeg is not installed or not in system PATH.
    Video conversion will be disabled.
    
    Installation instructions:
    - macOS: brew install ffmpeg
    - Ubuntu/Debian: sudo apt-get install ffmpeg
    - Windows: Download from https://ffmpeg.org/download.html
    """)

def convert_video_to_mp4(input_path, output_path=None):
    """
    Convert video to MP4 format using FFmpeg
    
    Args:
        input_path (str): Path to the input video file
        output_path (str, optional): Path to save converted video. 
                                     If None, generates a temporary file.
    
    Returns:
        str: Path to the converted MP4 video
    """
    # Check FFmpeg availability before conversion
    if not FFMPEG_AVAILABLE:
        logging.error("FFmpeg is not available. Skipping video conversion.")
        return input_path
    
    try:
        # If no output path specified, create a temporary file
        if output_path is None:
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.mp4', 
                prefix='converted_', 
                delete=False
            )
            output_path = temp_file.name
            temp_file.close()
        
        # FFmpeg conversion command using subprocess for broader compatibility
        subprocess.run(
            [
                'ffmpeg', 
                '-i', input_path, 
                '-c:v', 'libx264',  # H.264 video codec
                '-c:a', 'aac',       # AAC audio codec
                '-loglevel', 'error', # Suppress FFmpeg output
                '-y',                 # Overwrite output file
                output_path
            ],
            check=True,
            capture_output=True
        )
        
        return output_path
    
    except subprocess.CalledProcessError as e:
        logging.error(f"FFmpeg conversion error: {e.stderr.decode()}")
        raise ValueError(f"Video conversion failed: {e.stderr.decode()}")
    except Exception as e:
        logging.error(f"Unexpected error during video conversion: {e}")
        raise

def is_convertible_video(filename):
    """
    Check if the video format is convertible
    
    Args:
        filename (str): Name of the video file
    
    Returns:
        bool: True if convertible, False otherwise
    """
    convertible_extensions = [
        '.mkv', '.avi', '.mov', '.webm', 
        '.flv', '.wmv', '.m4v', '.mpg', 
        '.mpeg', '.mp4'
    ]
    
    file_ext = os.path.splitext(filename)[1].lower()
    return file_ext in convertible_extensions

def validate_video_file(file_path):
    """
    Comprehensive video file validation with multiple detection methods
    
    Args:
        file_path (str): Path to the video file
    
    Returns:
        dict: Validation results with detailed information
    """
    try:
        # Basic file checks
        if not os.path.exists(file_path):
            return {
                'valid': False, 
                'reason': 'File does not exist',
                'details': f'Path: {file_path}'
            }
        
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return {
                'valid': False, 
                'reason': 'Empty file',
                'details': f'Size: {file_size} bytes'
            }
        
        # Multiple MIME type detection methods
        mime_type = None
        
        # Method 1: python-magic
        try:
            import magic
            mime_type = magic.from_file(file_path, mime=True)
        except ImportError:
            logging.warning("python-magic not installed. Falling back to alternative detection.")
        
        # Method 2: mimetypes fallback
        if not mime_type:
            mime_type = mimetypes.guess_type(file_path)[0]
        
        # Method 3: System FFprobe detection
        if not mime_type:
            try:
                # Use subprocess to run ffprobe
                ffprobe_output = subprocess.check_output([
                    'ffprobe', 
                    '-v', 'error', 
                    '-select_streams', 'v:0', 
                    '-count_packets',
                    '-show_entries', 
                    'stream=codec_type,width,height,duration,nb_read_packets', 
                    '-of', 'csv=p=0', 
                    file_path
                ], universal_newlines=True, stderr=subprocess.STDOUT).strip()
                
                # If output is not empty, it's a valid video
                if ffprobe_output:
                    mime_type = 'video/unknown'
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                logging.warning(f"FFprobe detection failed: {e}")
        
        # Supported video MIME types
        supported_mime_types = [
            'video/mp4', 'video/x-matroska', 'video/avi', 
            'video/x-msvideo', 'video/quicktime', 'video/webm',
            'video/x-ms-wmv', 'video/mpeg', 'video/unknown'
        ]
        
        if not mime_type or mime_type not in supported_mime_types:
            return {
                'valid': False, 
                'reason': 'Unsupported video format',
                'details': f'Detected MIME: {mime_type or "Unknown"}'
            }
        
        # Optional: Basic video metadata extraction
        metadata = {}
        try:
            # Use FFprobe for more reliable metadata
            ffprobe_cmd = [
                'ffprobe', 
                '-v', 'quiet', 
                '-print_format', 'json', 
                '-show_format', 
                '-show_streams', 
                file_path
            ]
            
            ffprobe_result = subprocess.check_output(
                ffprobe_cmd, 
                universal_newlines=True, 
                stderr=subprocess.STDOUT
            )
            
            # Parse FFprobe JSON output
            ffprobe_data = json.loads(ffprobe_result)
            video_stream = next(
                (stream for stream in ffprobe_data.get('streams', []) 
                 if stream.get('codec_type') == 'video'), 
                None
            )
            
            if video_stream:
                metadata = {
                    'width': int(video_stream.get('width', 0)),
                    'height': int(video_stream.get('height', 0)),
                    'fps': float(eval(video_stream.get('avg_frame_rate', '0/1'))),
                    'duration': float(ffprobe_data.get('format', {}).get('duration', 0))
                }
        except Exception as metadata_error:
            logging.warning(f"Could not extract video metadata: {metadata_error}")
        
        return {
            'valid': True,
            'mime_type': mime_type,
            'size': file_size,
            'metadata': metadata
        }
    
    except Exception as e:
        logging.error(f"Unexpected error validating video: {e}", exc_info=True)
        return {
            'valid': False,
            'reason': 'Unexpected validation error',
            'details': str(e)
        }

def safe_convert_video(file_path, output_path=None):
    """
    Safe video conversion with multiple fallback methods
    
    Args:
        file_path (str): Path to input video file
        output_path (str, optional): Path to save converted video
    
    Returns:
        str: Path to converted video file
    """
    conversion_methods = [
        # Method 1: FFmpeg conversion
        lambda: convert_video_to_mp4(file_path, output_path),
        
        # Method 2: Subprocess FFmpeg with different settings
        lambda: subprocess.run([
            'ffmpeg', 
            '-i', file_path, 
            '-c:v', 'libx264', 
            '-preset', 'medium', 
            '-crf', '23', 
            '-c:a', 'aac', 
            output_path or (file_path + '.mp4')
        ], check=True),
        
        # Method 3: Fallback to original file
        lambda: file_path
    ]
    
    last_error = None
    for method in conversion_methods:
        try:
            result = method()
            return result if isinstance(result, str) else file_path
        except Exception as e:
            logging.warning(f"Video conversion method failed: {e}")
            last_error = e
    
    logging.error(f"All video conversion methods failed: {last_error}")
    return file_path

def safe_url_decode(query_string, keep_blank_values=True):
    """
    Safely decode URL-encoded query string
    
    Args:
        query_string (str): URL-encoded query string
        keep_blank_values (bool): Whether to keep blank values
    
    Returns:
        dict: Decoded query parameters
    """
    try:
        # Use parse_qs for dictionary with lists
        return dict(parse_qsl(query_string, keep_blank_values=keep_blank_values))
    except Exception as e:
        logging.error(f"URL decoding error: {e}")
        return {}

# Generate a secure random secret key
secret_key = secrets.token_hex(32)

# Generate a secure random token
random_token = secrets.token_urlsafe(16)

# Global Error Handling
@app.errorhandler(500)
def handle_500_error(e):
    """
    Global error handler for 500 Internal Server Errors
    Provides detailed logging and a user-friendly error page
    """
    # Log the full traceback
    logging.critical("500 Internal Server Error")
    logging.critical(f"Error details: {str(e)}")
    logging.critical(traceback.format_exc())

    # Additional context logging
    try:
        logging.critical(f"Current User: {current_user.username if current_user.is_authenticated else 'Not Authenticated'}")
        logging.critical(f"Request Method: {request.method}")
        logging.critical(f"Request URL: {request.url}")
        logging.critical(f"Request Headers: {request.headers}")
        logging.critical(f"Request Form Data: {request.form}")
        logging.critical(f"Request Files: {request.files}")
    except Exception as context_error:
        logging.error(f"Error logging additional context: {context_error}")

    # Render a user-friendly error page
    return render_template('error.html', 
                           error_message="An unexpected error occurred. Our team has been notified.",
                           error_code=500), 500

# Add a custom error template if it doesn't exist
def create_error_template():
    """Create a generic error template if it doesn't exist"""
    error_template_path = os.path.join(app.root_path, 'templates', 'error.html')
    if not os.path.exists(error_template_path):
        error_template_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ error_code }} - Error</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            text-align: center; 
            padding: 50px; 
            background-color: #f4f4f4; 
        }
        .error-container {
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            padding: 30px;
            max-width: 500px;
            margin: 0 auto;
        }
        h1 { color: #e74c3c; }
    </style>
</head>
<body>
    <div class="error-container">
        <h1>Error {{ error_code }}</h1>
        <p>{{ error_message }}</p>
        <p><a href="{{ url_for('index') }}">Return to Home</a></p>
    </div>
</body>
</html>
        """
        with open(error_template_path, 'w') as f:
            f.write(error_template_content)
        logging.info(f"Created error template at {error_template_path}")

# Call the function to ensure error template exists
create_error_template()

@app.route('/stream/<filename>')
def stream(filename):
    """
    Enhanced video streaming with support for large files and range requests
    """
    try:
        # Secure filename and construct full path
        safe_filename = secure_filename(filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        
        # Validate video file
        video_validation = validate_video_file(file_path)
        
        if not video_validation['valid']:
            logging.error(f"Video validation failed: {video_validation}")
            flash(f"Video processing error: {video_validation.get('reason', 'Unknown error')}", 'danger')
            return redirect(url_for('index'))
        
        # Determine conversion strategy
        mime_type = video_validation.get('mime_type', 'video/mp4')
        
        # Convert video if not MP4
        converted_path = file_path
        if mime_type != 'video/mp4':
            try:
                converted_path = safe_convert_video(file_path)
                logging.info(f"Converted {safe_filename} from {mime_type} to MP4")
            except Exception as conv_error:
                logging.error(f"Video conversion failed: {conv_error}")
                flash('Could not convert video format.', 'danger')
                return redirect(url_for('index'))
        
        # Get file size and handle range requests
        file_size = os.path.getsize(converted_path)
        
        # Parse range header
        range_header = request.headers.get('Range', None)
        
        if range_header:
            byte1, byte2 = 0, None
            match = re.search(r'(\d+)-(\d*)', range_header)
            groups = match.groups()

            if groups[0]:
                byte1 = int(groups[0])
            if groups[1]:
                byte2 = int(groups[1])
            
            if byte2 is not None:
                length = byte2 + 1 - byte1
            else:
                length = file_size - byte1
            
            data = None
            with open(converted_path, 'rb') as f:
                f.seek(byte1)
                data = f.read(length)
            
            rv = Response(data, 
                          206,  # Partial Content
                          mimetype='video/mp4', 
                          content_type='video/mp4', 
                          direct_passthrough=True)
            
            rv.headers.add('Content-Range', f'bytes {byte1}-{byte1 + length - 1}/{file_size}')
            rv.headers.add('Accept-Ranges', 'bytes')
            rv.headers.add('Content-Length', str(length))
            
            return rv
        
        # Full file streaming for non-range requests
        def generate():
            with open(converted_path, 'rb') as video_file:
                # Use a larger chunk size for better performance with large files
                chunk_size = app.config.get('STREAM_CHUNK_SIZE', 1024 * 1024 * 10)  # 10MB chunks
                data = video_file.read(chunk_size)
                while data:
                    yield data
                    data = video_file.read(chunk_size)
        
        # Stream response
        response = Response(
            generate(), 
            mimetype='video/mp4',
            content_type='video/mp4',
            headers={
                'Content-Disposition': f'inline; filename="{safe_filename}"',
                'Content-Length': str(file_size),
                'X-Video-Original-Type': mime_type,
                'X-Video-Metadata': json.dumps(video_validation.get('metadata', {})),
                'Accept-Ranges': 'bytes'
            }
        )
        
        # Clean up temporary converted file if different from original
        if converted_path != file_path:
            response.call_on_close(lambda: os.unlink(converted_path))
        
        return response
    
    except Exception as e:
        logging.error(f"Unexpected streaming error: {e}", exc_info=True)
        flash('An unexpected error occurred while streaming the video.', 'danger')
        return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            # Capture all form data for detailed logging
            form_data = dict(request.form)
            print(f"Full registration form data: {form_data}")
            
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            
            print(f"Registration attempt for username: {username}")
            
            # Enhanced input validation
            if not username:
                print("Registration failed: Empty username")
                flash('Username cannot be empty')
                return redirect(url_for('register'))
            
            if len(username) < 3:
                print(f"Registration failed: Username too short - {username}")
                flash('Username must be at least 3 characters long')
                return redirect(url_for('register'))
            
            if len(password) < 6:
                print("Registration failed: Password too short")
                flash('Password must be at least 6 characters long')
                return redirect(url_for('register'))
            
            # Check for special characters in username
            import re
            if not re.match(r'^[a-zA-Z0-9_]+$', username):
                print(f"Registration failed: Invalid username format - {username}")
                flash('Username can only contain letters, numbers, and underscores')
                return redirect(url_for('register'))
            
            # Check if user already exists
            try:
                existing_user = User.query.filter_by(username=username).first()
                if existing_user:
                    print(f"Registration failed: Username {username} already exists")
                    flash('Username already exists')
                    return redirect(url_for('register'))
                
                # Create new user
                hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
                new_user = User(username=username, password_hash=hashed_password)
                
                # Add and commit to database
                db.session.add(new_user)
                db.session.commit()
                
                print(f"User {username} registered successfully")
                flash('Registration successful. Please log in.')
                return redirect(url_for('login'))
            
            except Exception as db_error:
                # More specific database error handling
                db.session.rollback()
                
                # Log full error details
                print(f"Database error during user registration: {db_error}")
                
                # Additional error context
                print(f"Error details: {traceback.format_exc()}")
                
                # Log database session state
                try:
                    print(f"Database session state: {db.session}")
                except Exception as session_error:
                    print(f"Could not log session state: {session_error}")
                
                flash(f'A database error occurred: {str(db_error)}. Please try again.')
                return redirect(url_for('register'))
        
        except Exception as e:
            # Catch-all error handling with maximum information
            print(f"Unexpected registration error: {e}")
            
            # Log full traceback
            print(f"Full error traceback: {traceback.format_exc()}")
            
            # Log request details for debugging
            print(f"Request method: {request.method}")
            print(f"Request form data: {dict(request.form)}")
            
            flash(f'An unexpected error occurred: {str(e)}. Please try again.')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            
            print(f"Login attempt for username: {username}")
            
            # Validate input
            if not username or not password:
                print("Login failed: Missing username or password")
                flash('Username and password are required')
                return redirect(url_for('login'))
            
            # Find user
            user = User.query.filter_by(username=username).first()
            
            # Check password
            if user and bcrypt.check_password_hash(user.password_hash, password):
                login_user(user)
                print(f"User {username} logged in successfully")
                flash('Login successful')
                return redirect(url_for('index'))
            else:
                print(f"Login failed for username: {username}")
                flash('Invalid username or password')
                return redirect(url_for('login'))
        
        except Exception as e:
            print(f"Login error: {e}")
            flash('An error occurred during login')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/play/<int:movie_id>')
@login_required
def play_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    return render_template('stream.html', filename=movie.filename)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/edit_movie/<int:movie_id>', methods=['GET', 'POST'])
@login_required
def edit_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    
    # Ensure only the uploader can edit
    if movie.user_id != current_user.id:
        flash('You are not authorized to edit this movie.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Update movie details
        movie.title = request.form.get('title')
        movie.language = request.form.get('language')
        
        # Handle new thumbnail upload
        new_thumbnail = request.files.get('thumbnail')
        if new_thumbnail and new_thumbnail.filename:
            # Delete old thumbnail if exists
            if movie.thumbnail:
                old_thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], movie.thumbnail)
                if os.path.exists(old_thumbnail_path):
                    os.remove(old_thumbnail_path)
            
            # Save new thumbnail
            original_thumb_filename = secure_filename(new_thumbnail.filename)
            unique_thumb_filename = f"{uuid.uuid4()}_{original_thumb_filename}"
            thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], unique_thumb_filename)
            new_thumbnail.save(thumbnail_path)
            movie.thumbnail = unique_thumb_filename
        
        db.session.commit()
        flash('Movie details updated successfully!', 'success')
        return redirect(url_for('index'))
    
    return render_template('edit_movie.html', 
                           movie=movie, 
                           languages=LANGUAGES)

@app.route('/delete_movie/<int:movie_id>', methods=['POST'])
@login_required
def delete_movie(movie_id):
    try:
        # Find the movie
        movie = Movie.query.get_or_404(movie_id)
        
        # Ensure only the uploader can delete
        if movie.user_id != current_user.id:
            flash('You are not authorized to delete this movie.', 'danger')
            return redirect(url_for('index'))
        
        # Start a transaction to ensure atomic deletion
        try:
            # Delete movie file
            movie_path = os.path.join(app.config['UPLOAD_FOLDER'], movie.filename)
            if os.path.exists(movie_path):
                os.remove(movie_path)
            
            # Delete thumbnail if exists
            if movie.thumbnail:
                thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], movie.thumbnail)
                if os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)
            
            # Remove from database
            db.session.delete(movie)
            db.session.commit()
            
            flash('Movie deleted successfully!', 'success')
        except Exception as delete_error:
            db.session.rollback()
            print(f"Error during movie deletion: {delete_error}")
            flash('Failed to delete movie. Please try again.', 'danger')
        
        return redirect(url_for('index'))
    
    except Exception as e:
        print(f"Unexpected error in delete_movie: {e}")
        flash('An unexpected error occurred.', 'danger')
        return redirect(url_for('index'))

# Language list for dropdown
LANGUAGES = [
    'English', 'Hindi', 'Tamil', 'Malayalam'
]

@app.route('/')
@login_required
def index():
    # Diagnostic logging for database query
    logging.info("Accessing index route")
    logging.info(f"Current User ID: {current_user.id}")
    
    # Get search and filter parameters
    search_query = request.args.get('search', '').strip()
    language_filter = request.args.get('language', '')

    # Start with all movies (not just current user's)
    movies_query = Movie.query

    # Apply search filter
    if search_query:
        movies_query = movies_query.filter(
            Movie.title.ilike(f'%{search_query}%')
        )

    # Apply language filter
    if language_filter:
        movies_query = movies_query.filter(
            Movie.language == language_filter
        )

    # Order by most recent
    movies = movies_query.order_by(Movie.id.desc()).all()

    # Comprehensive logging for debugging
    logging.info(f"Total movies retrieved: {len(movies)}")
    
    # Detailed logging for each movie
    for movie in movies:
        logging.info(f"Movie Details - ID: {movie.id}, Title: {movie.title}, Filename: {movie.filename}, Thumbnail: {movie.thumbnail}, Language: {movie.language}, User ID: {movie.user_id}")
        
        # Check if thumbnail exists
        thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], movie.thumbnail)
        logging.info(f"Thumbnail path: {thumbnail_path}")
        logging.info(f"Thumbnail exists: {os.path.exists(thumbnail_path) if movie.thumbnail else 'No thumbnail'}")

    # Additional database query logging
    try:
        # Count total movies in the database
        total_movies_count = Movie.query.count()
        logging.info(f"Total movies in database: {total_movies_count}")
    except Exception as count_error:
        logging.error(f"Error counting movies: {count_error}")

    return render_template('index.html', 
                           movies=movies, 
                           languages=LANGUAGES, 
                           current_search=search_query, 
                           current_language=language_filter)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """
    Enhanced video upload route with comprehensive error handling
    """
    try:
        # Logging entry point
        logging.info(f"Upload route accessed. Method: {request.method}")
        logging.info(f"Request files: {request.files}")
        logging.info(f"Request form data: {request.form}")

        # Check if user is logged in
        if not current_user.is_authenticated:
            logging.warning("Unauthorized upload attempt")
            flash('Please log in to upload videos.', 'danger')
            return redirect(url_for('login'))

        # Handle POST request
        if request.method == 'POST':
            # Log detailed request information
            logging.info("Processing upload POST request")

            # Check if file is present in the request
            if 'file' not in request.files:
                logging.error("No file part in the request")
                flash('No file part', 'danger')
                return redirect(request.url)

            file = request.files['file']

            # Check if filename is empty
            if file.filename == '':
                logging.error("No selected file")
                flash('No selected file', 'danger')
                return redirect(request.url)

            # Additional logging for file details
            logging.info(f"Uploaded file name: {file.filename}")
            logging.info(f"Uploaded file content type: {file.content_type}")

            # Validate file
            if file and allowed_file(file.filename):
                try:
                    # Secure filename
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

                    # Save the file
                    file.save(file_path)
                    logging.info(f"File saved to: {file_path}")

                    # Validate video file
                    video_validation = validate_video_file(file_path)
                    
                    if not video_validation['valid']:
                        # Remove invalid file
                        os.remove(file_path)
                        logging.error(f"Video validation failed: {video_validation}")
                        flash(f"Video processing error: {video_validation.get('reason', 'Unknown error')}", 'danger')
                        return redirect(request.url)

                    # Generate thumbnail
                    thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], f"{os.path.splitext(filename)[0]}_thumb.jpg")
                    generate_thumbnail(file_path, thumbnail_path)

                    # Save movie metadata to database
                    new_movie = Movie(
                        title=request.form.get('title', filename),
                        filename=filename,
                        thumbnail=os.path.basename(thumbnail_path),
                        language=request.form.get('language', 'Unknown'),
                        user_id=current_user.id
                    )
                    
                    # Log movie details before committing
                    logging.info(f"Preparing to save movie: {new_movie.title}")
                    logging.info(f"Movie details - Filename: {new_movie.filename}, Thumbnail: {new_movie.thumbnail}, Language: {new_movie.language}")
                    
                    # Add and commit in a single transaction
                    db.session.add(new_movie)
                    db.session.commit()
                    
                    # Verify movie was saved
                    saved_movie = Movie.query.filter_by(filename=filename).first()
                    if saved_movie:
                        logging.info(f"Movie saved successfully. Database ID: {saved_movie.id}")
                    else:
                        logging.warning("Movie not found in database after commit")

                    logging.info(f"Movie uploaded successfully: {filename}")
                    flash('Video uploaded successfully!', 'success')
                    return redirect(url_for('index'))

                except Exception as e:
                    # Comprehensive error logging
                    logging.error(f"Upload error: {str(e)}")
                    logging.error(traceback.format_exc())
                    
                    # Rollback database session
                    db.session.rollback()
                    
                    # Remove any partially uploaded files
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    flash(f'Upload failed: {str(e)}', 'danger')
                    return redirect(request.url)

            else:
                logging.warning(f"Invalid file type: {file.filename}")
                flash('Invalid file type. Please upload a valid video.', 'danger')
                return redirect(request.url)

        # Render upload page for GET request
        return render_template('upload.html', languages=LANGUAGES)

    except Exception as e:
        # Global error handling
        logging.critical(f"Critical error in upload route: {str(e)}")
        logging.critical(traceback.format_exc())
        
        flash('An unexpected error occurred. Please try again.', 'danger')
        return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
