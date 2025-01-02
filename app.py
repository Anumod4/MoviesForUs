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

# Neon PostgreSQL Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///movies.db')

# Ensure proper PostgreSQL connection string
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

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
            username = request.form.get('username')
            password = request.form.get('password')
            
            logger.info(f"Registration attempt for username: {username}")
            
            # Validate input
            if not username or not password:
                logger.warning("Registration failed: Missing username or password")
                flash('Username and password are required')
                return redirect(url_for('register'))
            
            # Check if user already exists
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
        
        except Exception as e:
            # Rollback in case of error
            db.session.rollback()
            logger.error(f"Registration error: {e}", exc_info=True)
            flash('An error occurred during registration')
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

# Database Initialization Function with Improved Logging
def init_db():
    with app.app_context():
        try:
            logger.info("Initializing database...")
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Database initialization error: {e}", exc_info=True)
            raise

# Call database initialization
init_db()

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

# Optional: Supabase client for additional features
try:
    from supabase import create_client, Client
    supabase: Client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
    logger.info("Supabase client initialized successfully")
except Exception as e:
    logger.warning(f"Supabase client initialization failed: {e}")
    supabase = None

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
