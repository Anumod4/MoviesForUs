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
from sqlalchemy import inspect, create_engine, text

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

# Initialize extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Safe database initialization function
def safe_init_db():
    try:
        with app.app_context():
            # Ensure all tables are created
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
                # Force recreation of tables
                db.drop_all()
                db.create_all()
                print("Forcibly recreated database tables")
            
            # Commit the session to ensure changes are saved
            db.session.commit()
            
            print("Database tables created successfully.")
    except Exception as e:
        print(f"Critical error initializing database: {e}")
        traceback.print_exc()

# Ensure database is initialized immediately
safe_init_db()

# Flask Configuration and Folder Setup
def configure_app_folders():
    try:
        # Define upload and thumbnail folder paths with Render-specific handling
        base_dir = os.getenv('RENDER_WORKSPACE_DIR', os.path.dirname(os.path.abspath(__file__)))
        
        # Prioritize Render-specific paths
        render_project_dir = '/opt/render/project/src'
        
        # Upload folder configuration with multiple fallback options
        upload_folder_options = [
            os.getenv('UPLOAD_FOLDER'),  # Explicitly set in environment
            os.path.join(render_project_dir, 'static', 'uploads'),  # Render-specific path
            os.path.join(base_dir, 'static', 'uploads'),  # Local development path
            'static/uploads'  # Fallback path
        ]
        
        # Thumbnail folder configuration with multiple fallback options
        thumbnail_folder_options = [
            os.getenv('THUMBNAIL_FOLDER'),  # Explicitly set in environment
            os.path.join(render_project_dir, 'static', 'thumbnails'),  # Render-specific path
            os.path.join(base_dir, 'static', 'thumbnails'),  # Local development path
            'static/thumbnails'  # Fallback path
        ]
        
        # Find first valid upload folder
        upload_folder = next((
            folder for folder in upload_folder_options 
            if folder and os.path.exists(os.path.dirname(folder))
        ), 'static/uploads')
        
        # Find first valid thumbnail folder
        thumbnail_folder = next((
            folder for folder in thumbnail_folder_options 
            if folder and os.path.exists(os.path.dirname(folder))
        ), 'static/thumbnails')
        
        # Ensure folders exist
        os.makedirs(upload_folder, exist_ok=True)
        os.makedirs(thumbnail_folder, exist_ok=True)
        
        # Logging for verification
        print(f"Selected Upload folder: {upload_folder}")
        print(f"Selected Thumbnail folder: {thumbnail_folder}")
        
        return upload_folder, thumbnail_folder
    
    except Exception as e:
        print(f"Error configuring app folders: {e}")
        
        # Absolute fallback
        upload_folder = 'static/uploads'
        thumbnail_folder = 'static/thumbnails'
        
        os.makedirs(upload_folder, exist_ok=True)
        os.makedirs(thumbnail_folder, exist_ok=True)
        
        return upload_folder, thumbnail_folder

# Configure upload and thumbnail folders
UPLOAD_FOLDER, THUMBNAIL_FOLDER = configure_app_folders()

# Flask Configuration
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['THUMBNAIL_FOLDER'] = THUMBNAIL_FOLDER
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback_secret_key')
app.config['MAX_CONTENT_LENGTH'] = None  # Remove file upload size limit

# Logging configuration details
print(f"Upload Folder: {app.config['UPLOAD_FOLDER']}")
print(f"Thumbnail Folder: {app.config['THUMBNAIL_FOLDER']}")

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

# Registration Route with Comprehensive Error Handling
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

# Login Route with Comprehensive Error Handling
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

# Language list for dropdown
LANGUAGES = [
    'English', 'Hindi', 'Tamil', 'Malayalam'
]

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
