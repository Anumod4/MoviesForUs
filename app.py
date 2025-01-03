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
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, unquote, parse_qsl, urlencode

# Flask and Web Framework Imports
from flask import (
    Flask, request, render_template, redirect, url_for, 
    flash, send_file, Response, stream_with_context
)
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

# Security and Authentication
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Database and ORM
from flask_sqlalchemy import SQLAlchemy
import psycopg2

# Environment and Configuration
from dotenv import load_dotenv

# Media Processing
import ffmpeg
import cv2
import magic  # MIME type detection

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Set secret key explicitly
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Ensure the secret key is set before initializing extensions
if not app.config['SECRET_KEY']:
    raise ValueError("No SECRET_KEY set for Flask application. Please set it in .env file.")

# Logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Database Configuration with Enhanced Error Handling
def configure_database():
    try:
        # Validate database configuration
        db_config_keys = [
            'AIVEN_DB_HOST', 
            'AIVEN_DB_PORT', 
            'AIVEN_DB_NAME', 
            'AIVEN_DB_USER', 
            'AIVEN_DB_PASSWORD'
        ]
        
        # Log configuration details safely
        def safe_log_config():
            config_log = {}
            for key in db_config_keys:
                value = os.getenv(key)
                config_log[key] = '*' * len(value) if value else 'Not Set'
            return config_log
        
        # Check if all required keys are present
        missing_keys = [key for key in db_config_keys if not os.getenv(key)]
        if missing_keys:
            print(f"Missing database configuration keys: {missing_keys}")
            return 'sqlite:///movies.db'
        
        # Construct Database URL with SSL support
        database_url = (
            f"postgresql://{os.getenv('AIVEN_DB_USER')}:"
            f"{os.getenv('AIVEN_DB_PASSWORD')}@"
            f"{os.getenv('AIVEN_DB_HOST')}:"
            f"{os.getenv('AIVEN_DB_PORT')}/"
            f"{os.getenv('AIVEN_DB_NAME')}?sslmode=require"
        )
        
        # Additional connection validation
        try:
            # Test database connection using SQLAlchemy
            from sqlalchemy import create_engine, text
            engine = create_engine(database_url, echo=False)
            
            # Attempt to establish a connection and execute a simple query
            with engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                result.fetchone()  # Explicitly fetch the result
            
            print("Database connection successful")
        except Exception as conn_error:
            print(f"Database connection test failed: {conn_error}")
            return 'sqlite:///movies.db'
        
        return database_url
    
    except Exception as e:
        print(f"Error configuring database: {e}")
        return 'sqlite:///movies.db'

# Set Database URL
try:
    DATABASE_URL = configure_database()
except Exception as config_error:
    print(f"Fatal error in database configuration: {config_error}")
    DATABASE_URL = 'sqlite:///movies.db'

# Logging configuration details
print(f"Final Database URL: {DATABASE_URL}")

# Configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False  # Disable SQL logging in production

# Increase upload limits
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB max upload size
app.config['UPLOAD_CHUNK_SIZE'] = 1024 * 1024 * 10  # 10MB chunks

# Increase chunk size and add caching
app.config['STREAM_CHUNK_SIZE'] = 1024 * 1024 * 20  # 20MB chunks
app.config['CACHE_TYPE'] = 'FileSystemCache'

def configure_app_folders():
    """
    Robust configuration of upload and thumbnail folders
    """
    # Base directory for the application
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define upload and thumbnail folders
    upload_folder = os.getenv('UPLOAD_FOLDER', os.path.join(base_dir, 'static', 'uploads'))
    thumbnail_folder = os.getenv('THUMBNAIL_FOLDER', os.path.join(base_dir, 'static', 'thumbnails'))
    
    # Ensure folders exist
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(thumbnail_folder, exist_ok=True)
    
    return upload_folder, thumbnail_folder

# Configure upload and thumbnail folders
UPLOAD_FOLDER, THUMBNAIL_FOLDER = configure_app_folders()

# Ensure cache directory is created within upload folder
CACHE_DIR = os.path.join(UPLOAD_FOLDER, '.video_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

# Flask Configuration
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['THUMBNAIL_FOLDER'] = THUMBNAIL_FOLDER
app.config['CACHE_DIR'] = CACHE_DIR

# Logging configuration details
print(f"Upload Folder: {app.config['UPLOAD_FOLDER']}")
print(f"Thumbnail Folder: {app.config['THUMBNAIL_FOLDER']}")
print(f"Cache Folder: {app.config['CACHE_DIR']}")

# Initialize extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Safe database initialization function
def safe_init_db():
    try:
        with app.app_context():
            # Drop all existing tables first to ensure clean state
            db.drop_all()
            
            # Create all tables
            db.create_all()
            
            # Check if the tables exist
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print("Existing tables:", tables)
            
            # Verify specific tables
            required_tables = ['users', 'movies']
            missing_tables = [table for table in required_tables if table not in tables]
            
            if missing_tables:
                print(f"Warning: Missing tables {missing_tables}")
                
                # If using PostgreSQL, use raw SQL to create tables
                if 'postgresql' in str(db.engine.url):
                    from sqlalchemy import text
                    with db.engine.connect() as connection:
                        # Create Users table
                        connection.execute(text("""
                            CREATE TABLE IF NOT EXISTS users (
                                id SERIAL PRIMARY KEY,
                                username VARCHAR(80) UNIQUE NOT NULL,
                                password_hash VARCHAR(255) NOT NULL
                            )
                        """))
                        
                        # Create Movies table
                        connection.execute(text("""
                            CREATE TABLE IF NOT EXISTS movies (
                                id SERIAL PRIMARY KEY,
                                title VARCHAR(100) NOT NULL,
                                filename VARCHAR(200) NOT NULL,
                                thumbnail VARCHAR(200),
                                language VARCHAR(50) NOT NULL,
                                user_id INTEGER NOT NULL REFERENCES users(id)
                            )
                        """))
                        
                        connection.commit()
                        print("Tables created using raw SQL")
            
            # Commit the session to ensure changes are saved
            db.session.commit()
            
            print("Database tables created successfully.")
    except Exception as e:
        print(f"Critical error initializing database: {e}")
        traceback.print_exc()

# Ensure database is initialized immediately
safe_init_db()

# Import caching libraries
from flask_caching import Cache

# Initialize cache
cache = Cache(app, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': app.config['CACHE_DIR'],
    'CACHE_DEFAULT_TIMEOUT': 86400  # 24-hour cache
})

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

    return render_template('index.html', 
                           movies=movies, 
                           languages=LANGUAGES, 
                           current_search=search_query, 
                           current_language=language_filter)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'movie' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        movie_file = request.files['movie']
        if movie_file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        if movie_file:
            # Generate unique filename for video
            original_filename = secure_filename(movie_file.filename)
            unique_video_filename = f"{uuid.uuid4()}_{original_filename}"
            video_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_video_filename)
            movie_file.save(video_path)
            
            # Handle custom thumbnail
            custom_thumbnail = request.files.get('thumbnail')
            thumbnail_filename = None
            
            if custom_thumbnail and custom_thumbnail.filename:
                # User uploaded a custom thumbnail
                original_thumb_filename = secure_filename(custom_thumbnail.filename)
                unique_thumb_filename = f"{uuid.uuid4()}_{original_thumb_filename}"
                thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], unique_thumb_filename)
                custom_thumbnail.save(thumbnail_path)
                thumbnail_filename = unique_thumb_filename
            else:
                # Generate automatic thumbnail
                thumbnail_filename = f"{uuid.uuid4()}_thumbnail.jpg"
                thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
                
                if not generate_thumbnail(video_path, thumbnail_path):
                    # Fallback if thumbnail generation fails
                    thumbnail_filename = None
            
            # Get language from form
            language = request.form.get('language', 'Other')
            
            # Save movie details
            new_movie = Movie(
                title=request.form.get('title'),
                filename=unique_video_filename,
                thumbnail=thumbnail_filename,
                language=language,
                user_id=current_user.id
            )
            db.session.add(new_movie)
            db.session.commit()
            
            flash('Movie uploaded successfully!', 'success')
            return redirect(url_for('index'))
    
    return render_template('upload.html', languages=LANGUAGES)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
