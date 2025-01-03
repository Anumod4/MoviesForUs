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
import inspect
import uuid
import shutil
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, unquote, parse_qsl, urlencode

# Additional imports for video validation
import os
import logging
import traceback
import mimetypes
from flask import request, jsonify, flash, redirect, url_for
from werkzeug.utils import secure_filename
from moviepy.editor import VideoFileClip

# Flask and Web Framework Imports
from flask import (
    Flask, request, render_template, redirect, url_for, 
    flash, send_file, Response, stream_with_context, jsonify
)
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

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

# Robust Upload Folder Configuration
import os
import logging
import traceback

def configure_upload_folders(app):
    """
    Configure upload folders with comprehensive error handling and logging
    
    Args:
        app (Flask): Flask application instance
    
    Returns:
        tuple: Configured upload and thumbnail folders
    """
    # Potential base directories for uploads
    potential_base_dirs = [
        os.environ.get('RENDER_EXTERNAL_STORAGE', ''),  # Render.com external storage
        '/opt/render/project/src/static/uploads',  # Render.com specific path
        os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'uploads'),  # Project-specific uploads
        os.path.join(os.getcwd(), 'static', 'uploads'),  # Current working directory
        os.path.join(os.path.expanduser('~'), 'movie_uploads'),  # User home directory fallback
        '/tmp/movie_uploads'  # Absolute last resort
    ]
    
    # Logging for debugging
    logging.info("Starting upload folder configuration")
    logging.info("Checking potential upload directories:")
    for potential_dir in potential_base_dirs:
        logging.info(f"  - {potential_dir}")
    
    # Find the first valid directory
    for base_dir in potential_base_dirs:
        if not base_dir:
            continue
        
        try:
            # Create base upload directory
            uploads_base = os.path.join(base_dir)
            movies_upload_dir = os.path.join(uploads_base, 'movies')
            thumbnails_upload_dir = os.path.join(uploads_base, 'thumbnails')
            
            # Ensure directories exist with proper permissions
            os.makedirs(movies_upload_dir, exist_ok=True, mode=0o755)
            os.makedirs(thumbnails_upload_dir, exist_ok=True, mode=0o755)
            
            # Verify directory creation and writability
            if (os.path.exists(movies_upload_dir) and 
                os.path.exists(thumbnails_upload_dir) and 
                os.access(movies_upload_dir, os.W_OK) and 
                os.access(thumbnails_upload_dir, os.W_OK)):
                
                logging.info(f"Using upload directory: {base_dir}")
                logging.info(f"Movies Upload Directory: {movies_upload_dir}")
                logging.info(f"Thumbnails Upload Directory: {thumbnails_upload_dir}")
                
                # Set app configuration
                app.config['UPLOAD_FOLDER'] = movies_upload_dir
                app.config['THUMBNAIL_FOLDER'] = thumbnails_upload_dir
                
                return movies_upload_dir, thumbnails_upload_dir
        
        except Exception as dir_error:
            logging.warning(f"Error with directory {base_dir}: {dir_error}")
            continue
    
    # Absolute last resort - use system temp directory
    fallback_base = '/tmp/movie_uploads'
    fallback_movies = os.path.join(fallback_base, 'movies')
    fallback_thumbnails = os.path.join(fallback_base, 'thumbnails')
    
    try:
        os.makedirs(fallback_movies, exist_ok=True, mode=0o755)
        os.makedirs(fallback_thumbnails, exist_ok=True, mode=0o755)
        
        logging.critical("USING FALLBACK UPLOAD DIRECTORY IN /tmp")
        logging.critical(f"Fallback Movies Directory: {fallback_movies}")
        logging.critical(f"Fallback Thumbnails Directory: {fallback_thumbnails}")
        
        # Set app configuration to fallback
        app.config['UPLOAD_FOLDER'] = fallback_movies
        app.config['THUMBNAIL_FOLDER'] = fallback_thumbnails
        
        return fallback_movies, fallback_thumbnails
    
    except Exception as final_error:
        logging.critical(f"CRITICAL: Cannot create ANY upload directory: {final_error}")
        logging.critical(traceback.format_exc())
        
        # Absolute emergency fallback
        emergency_upload = '/tmp/emergency_uploads'
        os.makedirs(emergency_upload, exist_ok=True, mode=0o755)
        
        app.config['UPLOAD_FOLDER'] = emergency_upload
        app.config['THUMBNAIL_FOLDER'] = emergency_upload
        
        return emergency_upload, emergency_upload

# Ensure upload folders are configured immediately
try:
    # Configure upload folders as early as possible
    configure_upload_folders(app)
except Exception as config_error:
    logging.critical(f"FATAL Upload Folder Configuration Error: {config_error}")
    logging.critical(traceback.format_exc())
    # In a real-world scenario, you might want to have a fallback or emergency shutdown
    raise

# Verify configuration at startup
logging.info(f"FINAL UPLOAD_FOLDER: {app.config.get('UPLOAD_FOLDER', 'NOT SET')}")
logging.info(f"FINAL THUMBNAIL_FOLDER: {app.config.get('THUMBNAIL_FOLDER', 'NOT SET')}")

# Thumbnail configuration
THUMBNAIL_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'thumbnails')
app.config['THUMBNAIL_FOLDER'] = THUMBNAIL_FOLDER

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
from flask_bcrypt import Bcrypt
from werkzeug.security import generate_password_hash, check_password_hash

# Media Processing
try:
    import ffmpeg
except ImportError:
    logging.warning("ffmpeg module not installed. Some video conversion features may be limited.")
    ffmpeg = None
import cv2
import magic

# Function to check FFmpeg availability
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

# Log FFmpeg availability
if not FFMPEG_AVAILABLE:
    logging.warning("""
    FFmpeg is not installed or not in system PATH.
    Video thumbnail generation will use fallback methods.
    
    Installation instructions:
    - macOS: brew install ffmpeg
    - Ubuntu/Debian: sudo apt-get install ffmpeg
    - Windows: Download from https://ffmpeg.org/download.html
    """)

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

def generate_thumbnail(file_path):
    """
    Generate a thumbnail for a given video file
    
    Args:
        file_path (str): Path to the video file
    
    Returns:
        str or None: Absolute path to the thumbnail or None if generation fails
    """
    # Validate and normalize input path
    file_path = os.path.abspath(file_path)
    
    # Validate input
    if not file_path or not os.path.exists(file_path):
        logging.error(f"Invalid file path for thumbnail generation: {file_path}")
        return None
    
    # Generate unique thumbnail filename
    filename = os.path.basename(file_path)
    base_filename = os.path.splitext(filename)[0]
    unique_id = str(uuid.uuid4())[:8]
    thumbnail_filename = f"{base_filename}_thumb_{unique_id}.jpg"
    
    # Ensure thumbnail directory exists
    thumbnail_dir = os.path.join(tempfile.gettempdir(), 'movie_thumbnails')
    os.makedirs(thumbnail_dir, mode=0o755, exist_ok=True)
    
    thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)
    
    # Attempt thumbnail generation
    if FFMPEG_AVAILABLE:
        try:
            # FFmpeg thumbnail generation
            ffmpeg_cmd = [
                'ffmpeg', 
                '-i', file_path,  # Input file
                '-ss', '00:00:01',  # Seek to 1 second
                '-vframes', '1',  # Extract 1 frame
                '-vf', 'scale=320:240',  # Resize
                '-q:v', '2',  # High quality
                '-y',  # Overwrite output file
                thumbnail_path
            ]
            
            # Run FFmpeg command with error capture
            result = subprocess.run(
                ffmpeg_cmd, 
                capture_output=True, 
                text=True,
                timeout=30  # 30-second timeout
            )
            
            # Check if thumbnail was generated
            if result.returncode == 0 and os.path.exists(thumbnail_path):
                # Verify thumbnail file
                thumb_size = os.path.getsize(thumbnail_path)
                if thumb_size > 0:
                    logging.info(f"FFmpeg thumbnail generated: {thumbnail_path}")
                    return thumbnail_path
                else:
                    logging.error("Generated thumbnail is empty")
            else:
                logging.error(f"FFmpeg thumbnail generation failed: {result.stderr}")
        
        except subprocess.TimeoutExpired:
            logging.error("FFmpeg thumbnail generation timed out")
        except Exception as ffmpeg_error:
            logging.error(f"FFmpeg thumbnail error: {ffmpeg_error}")
    
    # Fallback to OpenCV if FFmpeg fails
    try:
        import cv2
        
        # Open video capture
        cap = cv2.VideoCapture(file_path)
        
        if not cap.isOpened():
            logging.error("OpenCV failed to open video file")
            return None
        
        # Seek to 1 second
        cap.set(cv2.CAP_PROP_POS_MSEC, 1000)
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            # Resize frame
            frame = cv2.resize(frame, (320, 240))
            
            # Save thumbnail
            cv2.imwrite(thumbnail_path, frame)
            
            if os.path.exists(thumbnail_path):
                thumb_size = os.path.getsize(thumbnail_path)
                if thumb_size > 0:
                    logging.info(f"OpenCV thumbnail generated: {thumbnail_path}")
                    return thumbnail_path
                else:
                    logging.error("OpenCV generated empty thumbnail")
            else:
                logging.error("OpenCV failed to save thumbnail")
        else:
            logging.error("OpenCV failed to read video frame")
    
    except ImportError:
        logging.error("OpenCV not available")
    except Exception as cv_error:
        logging.error(f"OpenCV thumbnail error: {cv_error}")
    
    # If all methods fail, return None
    logging.error("Failed to generate thumbnail using all methods")
    return None

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
    Comprehensive video file validation
    
    Args:
        file_path (str): Path to the video file to validate
    
    Returns:
        dict: Validation results with 'valid' boolean and optional 'reason'
    """
    try:
        # Check file existence
        if not os.path.exists(file_path):
            return {
                'valid': False, 
                'reason': 'File does not exist'
            }
        
        # Check file size (max 2GB)
        max_file_size = 2 * 1024 * 1024 * 1024  # 2GB
        file_size = os.path.getsize(file_path)
        if file_size > max_file_size:
            return {
                'valid': False, 
                'reason': f'File too large. Max size is 2GB. Current size: {file_size / (1024*1024):.2f} MB'
            }
        
        # Use moviepy to validate video
        try:
            with VideoFileClip(file_path) as video:
                # Check video duration (max 3 hours)
                max_duration = 3 * 60 * 60  # 3 hours in seconds
                if video.duration > max_duration:
                    return {
                        'valid': False, 
                        'reason': f'Video too long. Max duration is 3 hours. Current duration: {video.duration/60:.2f} minutes'
                    }
                
                # Check video resolution
                width, height = video.size
                if width < 640 or height < 360:
                    return {
                        'valid': False, 
                        'reason': f'Low resolution. Minimum 640x360 required. Current: {width}x{height}'
                    }
                
                # Additional metadata
                video_details = {
                    'valid': True,
                    'duration': video.duration,
                    'width': width,
                    'height': height,
                    'fps': video.fps
                }
                
                return video_details
        
        except Exception as video_error:
            logging.error(f"Video processing error: {video_error}")
            logging.error(traceback.format_exc())
            
            return {
                'valid': False, 
                'reason': f'Unable to process video: {str(video_error)}'
            }
    
    except Exception as global_error:
        logging.critical(f"Critical error in video validation: {global_error}")
        logging.critical(traceback.format_exc())
        
        return {
            'valid': False, 
            'reason': f'Unexpected validation error: {str(global_error)}'
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

def allowed_file(filename):
    """
    Check if the uploaded file has an allowed extension.
    
    Args:
        filename (str): Name of the file to validate
    
    Returns:
        bool: True if file extension is allowed, False otherwise
    """
    ALLOWED_EXTENSIONS = {
        'mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv', 
        'webm', 'mpeg', 'mpg', 'm4v', 'divx'
    }
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(error):
    logging.error(f"File upload too large: {error}")
    return jsonify({
        'status': 'error', 
        'message': 'File is too large. Maximum upload size is 500 MB.'
    }), 413

@app.route('/stream/<filename>')
def stream(filename):
    """
    Enhanced video streaming with comprehensive error handling
    """
    try:
        # Secure filename and construct full path
        safe_filename = secure_filename(filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        
        # Validate file existence
        if not os.path.exists(file_path):
            logging.error(f"File not found: {file_path}")
            flash('Video file not found.', 'danger')
            return redirect(url_for('index'))
        
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
        
        # Ensure file is readable
        if not os.access(converted_path, os.R_OK):
            logging.error(f"File not readable: {converted_path}")
            flash('Unable to read video file.', 'danger')
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
    """
    Edit movie details with comprehensive error handling and logging
    """
    try:
        # Find the movie or return 404
        movie = Movie.query.get_or_404(movie_id)
        
        # Logging for debugging
        logging.info(f"Edit Movie Route Accessed")
        logging.info(f"Movie ID: {movie_id}")
        logging.info(f"Current User ID: {current_user.id}")
        logging.info(f"Movie Owner ID: {movie.user_id}")
        
        # Ensure only the uploader can edit
        if movie.user_id != current_user.id:
            logging.warning(f"Unauthorized edit attempt by user {current_user.id} for movie {movie_id}")
            flash('You are not authorized to edit this movie.', 'danger')
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            # Validate input
            title = request.form.get('title', '').strip()
            language = request.form.get('language', '').strip()
            
            # Input validation
            if not title:
                logging.warning("Edit movie: Empty title")
                flash('Movie title cannot be empty.', 'danger')
                return render_template('edit_movie.html', 
                                       movie=movie, 
                                       languages=LANGUAGES)
            
            if not language or language not in LANGUAGES:
                logging.warning(f"Invalid language: {language}")
                flash('Please select a valid language.', 'danger')
                return render_template('edit_movie.html', 
                                       movie=movie, 
                                       languages=LANGUAGES)
            
            # Update movie details
            movie.title = title
            movie.language = language
            
            # Thumbnail upload handling
            try:
                # Check if a thumbnail file is uploaded
                if 'thumbnail' in request.files:
                    thumbnail_file = request.files['thumbnail']
                    
                    # Generate a unique filename for the uploaded thumbnail
                    if thumbnail_file and thumbnail_file.filename:
                        # Secure the filename
                        original_filename = secure_filename(thumbnail_file.filename)
                        base_filename, ext = os.path.splitext(original_filename)
                        
                        # Ensure the extension is an image
                        if ext.lower() not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                            logging.warning(f"Invalid thumbnail file type: {ext}")
                            flash('Invalid thumbnail file type. Please upload an image.', 'danger')
                            continue
                        
                        # Create unique filename
                        unique_id = str(uuid.uuid4())[:8]
                        unique_thumb_filename = f"{base_filename}_{unique_id}{ext}"
                        
                        # Ensure thumbnails directory exists
                        static_thumbnail_dir = os.path.join(app.root_path, 'static', 'thumbnails')
                        os.makedirs(static_thumbnail_dir, exist_ok=True)
                        
                        # Full path for saving
                        static_thumbnail_path = os.path.join(static_thumbnail_dir, unique_thumb_filename)
                        
                        # Save the uploaded thumbnail
                        thumbnail_file.save(static_thumbnail_path)
                        
                        # Verify file was saved and is a valid image
                        try:
                            from PIL import Image
                            with Image.open(static_thumbnail_path) as img:
                                img.verify()  # Verify the image
                        except Exception as img_error:
                            logging.error(f"Invalid image file: {img_error}")
                            # Remove the invalid file
                            os.remove(static_thumbnail_path)
                            flash('Invalid image file. Please upload a valid image.', 'danger')
                            continue
                        
                        # Update movie record with new thumbnail
                        movie.thumbnail = unique_thumb_filename
                        logging.info(f"New thumbnail saved: {static_thumbnail_path}")
            
            except Exception as thumbnail_error:
                logging.error(f"Thumbnail upload error: {thumbnail_error}")
                logging.error(traceback.format_exc())
            
            try:
                # Commit changes
                db.session.commit()
                logging.info(f"Movie {movie_id} updated successfully")
                flash('Movie details updated successfully!', 'success')
                return redirect(url_for('index'))
            
            except Exception as db_error:
                # Rollback in case of database error
                db.session.rollback()
                logging.error(f"Database error during movie update: {db_error}")
                flash('An error occurred while updating the movie. Please try again.', 'danger')
                return render_template('edit_movie.html', 
                                       movie=movie, 
                                       languages=LANGUAGES)
        
        # GET request: render edit page
        return render_template('edit_movie.html', 
                               movie=movie, 
                               languages=LANGUAGES)
    
    except Exception as unexpected_error:
        # Catch any unexpected errors
        logging.critical(f"Unexpected error in edit_movie: {unexpected_error}")
        logging.critical(traceback.format_exc())
        flash('An unexpected error occurred. Please try again.', 'danger')
        return redirect(url_for('index'))

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
    # Enhanced diagnostic logging
    logging.info("=" * 50)
    logging.info("Index Route Accessed")
    logging.info(f"Current User: {current_user.id} ({current_user.username})")
    logging.info(f"User Authentication Status: {current_user.is_authenticated}")

    # Get search and filter parameters
    search_query = request.args.get('search', '').strip()
    language_filter = request.args.get('language', '')

    # Log filter parameters
    logging.info(f"Search Query: '{search_query}'")
    logging.info(f"Language Filter: '{language_filter}'")

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
    logging.info(f"Total Movies Retrieved: {len(movies)}")
    
    # Detailed logging for each movie
    for movie in movies:
        logging.info(f"Movie Details:")
        logging.info(f"  ID: {movie.id}")
        logging.info(f"  Title: {movie.title}")
        logging.info(f"  Filename: {movie.filename}")
        logging.info(f"  Thumbnail: {movie.thumbnail}")
        logging.info(f"  Language: {movie.language}")
        logging.info(f"  User ID: {movie.user_id}")
        
        # Check thumbnail file existence
        if movie.thumbnail:
            thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], movie.thumbnail)
            logging.info(f"  Thumbnail Path: {thumbnail_path}")
            logging.info(f"  Thumbnail Exists: {os.path.exists(thumbnail_path)}")

    # Additional database query logging
    try:
        # Count total movies in the database
        total_movies_count = Movie.query.count()
        logging.info(f"Total Movies in Database: {total_movies_count}")
    except Exception as count_error:
        logging.error(f"Error counting movies: {count_error}")

    # Log rendering details
    logging.info("Rendering Index Template")
    logging.info("=" * 50)

    return render_template('index.html', 
                           movies=movies, 
                           languages=LANGUAGES, 
                           current_search=search_query, 
                           current_language=language_filter)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """
    Enhanced video upload route with comprehensive error handling and logging
    """
    try:
        # Handle different request methods
        if request.method == 'POST':
            # Check if file is present in the request
            if 'movie' not in request.files:
                return jsonify({
                    'status': 'error', 
                    'message': 'No file uploaded.'
                }), 400
            
            file = request.files['movie']
            
            # Check if filename is empty
            if file.filename == '':
                return jsonify({
                    'status': 'error', 
                    'message': 'No selected file.'
                }), 400
            
            # Check file type
            if file and allowed_file(file.filename):
                try:
                    # Secure filename
                    filename = secure_filename(file.filename)
                    
                    # Ensure upload folder exists
                    upload_folder = app.config['UPLOAD_FOLDER']
                    thumbnail_folder = app.config['THUMBNAIL_FOLDER']
                    
                    os.makedirs(upload_folder, exist_ok=True)
                    os.makedirs(thumbnail_folder, exist_ok=True)
                    
                    # Full file paths
                    file_path = os.path.join(upload_folder, filename)
                    
                    # Save the file with a timeout to prevent hanging
                    def save_file_with_timeout():
                        try:
                            file.save(file_path)
                        except Exception as save_error:
                            logging.critical(f"File save error: {save_error}")
                            raise
                    
                    # Use a timeout mechanism
                    from concurrent.futures import ThreadPoolExecutor, TimeoutError
                    
                    try:
                        with ThreadPoolExecutor() as executor:
                            future = executor.submit(save_file_with_timeout)
                            try:
                                future.result(timeout=300)  # 5-minute timeout
                            except TimeoutError:
                                logging.critical("File upload timed out")
                                if os.path.exists(file_path):
                                    os.unlink(file_path)
                                return jsonify({
                                    'status': 'error', 
                                    'message': 'File upload timed out. Please try a smaller file.'
                                }), 408
                    except Exception as thread_error:
                        logging.error(f"Thread execution error: {thread_error}")
                        if os.path.exists(file_path):
                            os.unlink(file_path)
                        return jsonify({
                            'status': 'error', 
                            'message': f'Thread execution error: {thread_error}'
                        }), 500
                    
                    logging.info(f"File saved successfully: {file_path}")
                    
                    # Validate video file
                    video_validation = validate_video_file(file_path)
                    
                    if not video_validation['valid']:
                        # Remove invalid file
                        os.unlink(file_path)
                        logging.error(f"Invalid video file: {video_validation}")
                        return jsonify({
                            'status': 'error', 
                            'message': video_validation.get('reason', 'Invalid video file')
                        }), 400
                    
                    # Prepare movie metadata
                    movie_title = request.form.get('title', filename)
                    movie_language = request.form.get('language', 'English')
                    
                    # Generate thumbnail
                    try:
                        thumbnail_path = generate_thumbnail(file_path)
                        
                        # Ensure thumbnail is saved in the correct directory
                        if thumbnail_path:
                            # Ensure full path for thumbnail
                            if not os.path.isabs(thumbnail_path):
                                thumbnail_path = os.path.join(os.getcwd(), thumbnail_path)
                            
                            # Move thumbnail to the static/thumbnails directory
                            thumbnail_filename = os.path.basename(thumbnail_path)
                            static_thumbnail_dir = os.path.join(app.root_path, 'static', 'thumbnails')
                            os.makedirs(static_thumbnail_dir, exist_ok=True)
                            
                            static_thumbnail_path = os.path.join(static_thumbnail_dir, thumbnail_filename)
                            
                            # Copy instead of move to prevent potential file loss
                            if os.path.exists(thumbnail_path):
                                shutil.copy2(thumbnail_path, static_thumbnail_path)
                                
                                # Optional: remove the original if it's in a temporary location
                                if '/tmp/' in thumbnail_path or '/temp/' in thumbnail_path:
                                    try:
                                        os.remove(thumbnail_path)
                                    except Exception as remove_error:
                                        logging.warning(f"Could not remove temporary thumbnail: {remove_error}")
                            else:
                                logging.error(f"Thumbnail file not found: {thumbnail_path}")
                                thumbnail_filename = None
                            
                            # Use only the filename for database storage
                            thumbnail_filename = os.path.basename(static_thumbnail_path)
                            logging.info(f"Thumbnail saved: {static_thumbnail_path}")
                        else:
                            thumbnail_filename = None
                            logging.warning("Thumbnail generation failed")
                    except Exception as thumbnail_error:
                        logging.error(f"Thumbnail generation error: {thumbnail_error}")
                        logging.error(traceback.format_exc())
                        thumbnail_filename = None
                    
                    # Create movie record
                    new_movie = Movie(
                        title=movie_title,
                        filename=filename,
                        thumbnail=thumbnail_filename,
                        language=movie_language,
                        user_id=current_user.id
                    )
                    
                    # Add and commit to database
                    db.session.add(new_movie)
                    db.session.commit()
                    
                    return jsonify({
                        'status': 'success',
                        'message': 'Movie uploaded successfully',
                        'movie_id': new_movie.id
                    }), 201
                
                except Exception as upload_error:
                    # Rollback database transaction
                    db.session.rollback()
                    
                    # Remove uploaded file if it exists
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                    
                    logging.error(f"Movie upload error: {upload_error}")
                    return jsonify({
                        'status': 'error',
                        'message': f'Upload failed: {str(upload_error)}'
                    }), 500
            
            else:
                # Invalid file type
                return jsonify({
                    'status': 'error', 
                    'message': 'Invalid file type. Please upload a video file.'
                }), 400
        
        elif request.method == 'GET':
            # Render upload page for GET requests
            return render_template('upload.html', languages=LANGUAGES)
        
        # Unexpected method
        logging.warning(f"Unexpected request method: {request.method}")
        return jsonify({
            'status': 'error', 
            'message': 'Invalid request method.'
        }), 405
    
    except Exception as final_error:
        logging.critical(f"Final upload route error: {final_error}")
        logging.critical(traceback.format_exc())
        
        return jsonify({
            'status': 'error', 
            'message': 'A critical error occurred. Please contact support.'
        }), 500

@app.route('/debug_auth')
def debug_auth():
    """
    Diagnostic route to check authentication and session details
    """
    logging.info("=" * 50)
    logging.info("Authentication Debug Route")
    
    # Check current user details
    if current_user.is_authenticated:
        logging.info(f"Authenticated User Details:")
        logging.info(f"  User ID: {current_user.id}")
        logging.info(f"  Username: {current_user.username}")
        return f"Authenticated as {current_user.username}"
    else:
        logging.warning("No authenticated user")
        return "Not authenticated", 401

@app.route('/thumbnails/<filename>')
def serve_thumbnail(filename):
    """
    Serve thumbnails from the thumbnail folder
    
    Args:
        filename (str): Name of the thumbnail file
    
    Returns:
        Flask response with the thumbnail image
    """
    try:
        # Validate filename to prevent directory traversal
        filename = secure_filename(filename)
        
        # Potential thumbnail locations
        thumbnail_locations = [
            os.path.join(app.root_path, 'static', 'thumbnails', filename),
            os.path.join(app.config.get('THUMBNAIL_FOLDER', ''), filename),
            os.path.join(app.root_path, 'static', filename)
        ]
        
        # Find the first existing thumbnail
        thumbnail_path = None
        for potential_path in thumbnail_locations:
            if os.path.exists(potential_path):
                thumbnail_path = potential_path
                break
        
        # Log thumbnail serving details
        logging.info(f"Serving Thumbnail: {filename}")
        logging.info(f"Potential Thumbnail Paths: {thumbnail_locations}")
        
        # If no thumbnail found, serve default
        if not thumbnail_path:
            logging.warning(f"Thumbnail not found: {filename}")
            return send_from_directory(os.path.join(app.root_path, 'static'), 'default_thumbnail.jpg')
        
        # Serve the thumbnail
        return send_file(thumbnail_path, mimetype='image/jpeg')
    
    except Exception as e:
        # Comprehensive error logging
        logging.error(f"Error serving thumbnail {filename}: {e}")
        logging.error(traceback.format_exc())
        
        # Return default thumbnail on error
        return send_from_directory(os.path.join(app.root_path, 'static'), 'default_thumbnail.jpg'), 404

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
