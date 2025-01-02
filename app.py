import os
import sys
import traceback
import logging
import uuid
import urllib.parse
from dotenv import load_dotenv

from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import inspect

# Load environment variables
load_dotenv()

# Optional import for OpenCV
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("OpenCV (cv2) not available. Thumbnail generation will be skipped.")

from PIL import Image

app = Flask(__name__)

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

# Aiven PostgreSQL Configuration
AIVEN_DB_HOST = os.getenv('AIVEN_DB_HOST', 'localhost')
AIVEN_DB_PORT = os.getenv('AIVEN_DB_PORT', '5432')
AIVEN_DB_NAME = os.getenv('AIVEN_DB_NAME', 'defaultdb')
AIVEN_DB_USER = os.getenv('AIVEN_DB_USER')
AIVEN_DB_PASSWORD = os.getenv('AIVEN_DB_PASSWORD')
AIVEN_SSL_CERT_PATH = os.getenv('AIVEN_SSL_CERT_PATH')

# Logging database configuration details
logger.info(f"Aiven DB Configuration:")
logger.info(f"Host: {AIVEN_DB_HOST}")
logger.info(f"Port: {AIVEN_DB_PORT}")
logger.info(f"Name: {AIVEN_DB_NAME}")
logger.info(f"User: {AIVEN_DB_USER}")
logger.info(f"Password: {'*' * len(AIVEN_DB_PASSWORD) if AIVEN_DB_PASSWORD else 'Not Set'}")
logger.info(f"SSL Cert Path: {AIVEN_SSL_CERT_PATH}")

# Construct Database URL with SSL support
DATABASE_URL = os.getenv('DATABASE_URL', 
    f'postgresql://{AIVEN_DB_USER}:{AIVEN_DB_PASSWORD}@{AIVEN_DB_HOST}:{AIVEN_DB_PORT}/{AIVEN_DB_NAME}'
)

# SSL Configuration for Aiven
if AIVEN_SSL_CERT_PATH and os.path.exists(AIVEN_SSL_CERT_PATH):
    DATABASE_URL += '?sslmode=verify-full&sslcert=' + AIVEN_SSL_CERT_PATH
else:
    # Simplified SSL mode
    DATABASE_URL = DATABASE_URL.split('?')[0] + '?sslmode=require'

# Fallback to SQLite if Aiven configuration is incomplete
try:
    if not all([AIVEN_DB_HOST, AIVEN_DB_PORT, AIVEN_DB_NAME, AIVEN_DB_USER, AIVEN_DB_PASSWORD]):
        logger.warning("Incomplete Aiven DB configuration. Attempting to parse DATABASE_URL.")
        parsed_url = urllib.parse.urlparse(DATABASE_URL)
        if not all([parsed_url.hostname, parsed_url.port, parsed_url.path, parsed_url.username, parsed_url.password]):
            logger.error("Both Aiven configuration and DATABASE_URL are incomplete. Falling back to SQLite.")
            DATABASE_URL = 'sqlite:///movies.db'
except Exception as e:
    logger.error(f"Error parsing database configuration: {e}. Falling back to SQLite.")
    DATABASE_URL = 'sqlite:///movies.db'

# Log the final database URL for debugging
logger.info(f"Final Database URL: {DATABASE_URL}")

# Flask Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['THUMBNAIL_FOLDER'] = 'static/thumbnails'
app.config['MAX_CONTENT_LENGTH'] = None

# Create directories
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER']), exist_ok=True)
os.makedirs(os.path.join(app.config['THUMBNAIL_FOLDER']), exist_ok=True)

# Initialize extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Log database configuration
logger.info(f"Database URL: {DATABASE_URL}")

# Error Handler with Detailed Logging
@app.errorhandler(Exception)
def handle_exception(e):
    # Log the error
    logger.error("An error occurred:", exc_info=True)
    
    # Detailed error tracking
    error_id = str(uuid.uuid4())
    error_details = {
        'error_id': error_id,
        'error_type': type(e).__name__,
        'error_message': str(e),
        'traceback': traceback.format_exc()
    }
    
    # Log full traceback
    logger.error(f"Error ID: {error_id}")
    logger.error(f"Full Traceback: {error_details['traceback']}")
    
    # Render error page or return error response
    return render_template('error.html', error_details=error_details), 500

# Database Initialization Function with Robust Error Handling
def init_db():
    try:
        # Ensure all tables are created
        with app.app_context():
            logger.info("Initializing database...")
            
            # Create tables if they don't exist
            db.create_all()
            
            # Log table creation details
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Existing tables in database: {tables}")
            
            # Optional: Check if users table exists and has correct schema
            if 'users' in tables:
                columns = [col['name'] for col in inspector.get_columns('users')]
                logger.info(f"Columns in users table: {columns}")
                
                # Verify required columns
                required_columns = ['id', 'username', 'password_hash']
                missing_columns = [col for col in required_columns if col not in columns]
                
                if missing_columns:
                    logger.error(f"Missing columns in users table: {missing_columns}")
                    raise ValueError(f"Users table is missing critical columns: {missing_columns}")
            
            logger.info("Database initialization complete")
    
    except Exception as e:
        # Comprehensive error logging
        logger.error(f"Database initialization error: {e}", exc_info=True)
        logger.error(f"Full error traceback: {traceback.format_exc()}")
        
        # Attempt to provide more context about the error
        try:
            logger.error(f"Database connection details: {db.engine.url}")
        except Exception as context_error:
            logger.error(f"Could not log database connection details: {context_error}")
        
        # Re-raise the original exception
        raise

# Call database initialization
init_db()

# Language list for dropdown
LANGUAGES = [
    'English', 'Hindi', 'Tamil', 'Malayalam'
]

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
        logger.info(f"User loaded: {user}")
        return user
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {e}")
        return None

# Registration Route with Comprehensive Error Handling
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            # Capture all form data for detailed logging
            form_data = dict(request.form)
            logger.info(f"Full registration form data: {form_data}")
            
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            
            logger.info(f"Registration attempt for username: {username}")
            
            # Enhanced input validation
            if not username:
                logger.warning("Registration failed: Empty username")
                flash('Username cannot be empty')
                return redirect(url_for('register'))
            
            if len(username) < 3:
                logger.warning(f"Registration failed: Username too short - {username}")
                flash('Username must be at least 3 characters long')
                return redirect(url_for('register'))
            
            if len(password) < 6:
                logger.warning("Registration failed: Password too short")
                flash('Password must be at least 6 characters long')
                return redirect(url_for('register'))
            
            # Check for special characters in username
            import re
            if not re.match(r'^[a-zA-Z0-9_]+$', username):
                logger.warning(f"Registration failed: Invalid username format - {username}")
                flash('Username can only contain letters, numbers, and underscores')
                return redirect(url_for('register'))
            
            # Check if user already exists
            try:
                existing_user = User.query.filter_by(username=username).first()
                if existing_user:
                    logger.warning(f"Registration failed: Username {username} already exists")
                    flash('Username already exists')
                    return redirect(url_for('register'))
                
                # Create new user
                hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
                new_user = User(username=username, password_hash=hashed_password)
                
                # Add and commit to database
                db.session.add(new_user)
                db.session.commit()
                
                logger.info(f"User {username} registered successfully")
                flash('Registration successful. Please log in.')
                return redirect(url_for('login'))
            
            except Exception as db_error:
                # More specific database error handling
                db.session.rollback()
                
                # Log full error details
                logger.error(f"Database error during user registration: {db_error}", exc_info=True)
                
                # Additional error context
                logger.error(f"Error details: {traceback.format_exc()}")
                
                # Log database session state
                try:
                    logger.error(f"Database session state: {db.session}")
                except Exception as session_error:
                    logger.error(f"Could not log session state: {session_error}")
                
                flash(f'A database error occurred: {str(db_error)}. Please try again.')
                return redirect(url_for('register'))
        
        except Exception as e:
            # Catch-all error handling with maximum information
            logger.error(f"Unexpected registration error: {e}", exc_info=True)
            
            # Log full traceback
            logger.error(f"Full error traceback: {traceback.format_exc()}")
            
            # Log request details for debugging
            logger.error(f"Request method: {request.method}")
            logger.error(f"Request form data: {dict(request.form)}")
            
            flash(f'An unexpected error occurred: {str(e)}. Please try again.')
            return redirect(url_for('register'))
    
    return render_template('register.html')

# Login Route with Comprehensive Error Handling
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            
            logger.info(f"Login attempt for username: {username}")
            
            # Validate input
            if not username or not password:
                logger.warning("Login failed: Missing username or password")
                flash('Username and password are required')
                return redirect(url_for('login'))
            
            # Find user
            user = User.query.filter_by(username=username).first()
            
            # Check password
            if user and bcrypt.check_password_hash(user.password_hash, password):
                login_user(user)
                logger.info(f"User {username} logged in successfully")
                flash('Login successful')
                return redirect(url_for('index'))
            else:
                logger.warning(f"Login failed for username: {username}")
                flash('Invalid username or password')
                return redirect(url_for('login'))
        
        except Exception as e:
            logger.error(f"Login error: {e}", exc_info=True)
            flash('An error occurred during login')
            return redirect(url_for('login'))
    
    return render_template('login.html')

def generate_thumbnail(video_path, thumbnail_path):
    """Generate thumbnail for video with fallback to PIL if cv2 is not available."""
    if CV2_AVAILABLE:
        # OpenCV method
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        if ret:
            # Resize thumbnail while maintaining aspect ratio
            height, width = frame.shape[:2]
            aspect_ratio = width / height
            new_width = 400
            new_height = int(new_width / aspect_ratio)
            resized_frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
            cv2.imwrite(thumbnail_path, resized_frame)
            cap.release()
            return True
    
    # Fallback PIL method (less accurate)
    try:
        from PIL import Image
        img = Image.open(video_path)
        img.thumbnail((400, 400)) # Resize to 400x400
        img.save(thumbnail_path)
        return True
    except Exception as e:
        print(f"Thumbnail generation failed: {e}")
        return False

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

@app.route('/stream/<filename>')
@login_required
def stream(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

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
    movie = Movie.query.get_or_404(movie_id)
    
    # Ensure only the uploader can delete
    if movie.user_id != current_user.id:
        flash('You are not authorized to delete this movie.', 'danger')
        return redirect(url_for('index'))
    
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
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
