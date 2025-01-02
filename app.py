from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
import uuid
import os
import cv2

app = Flask(__name__)

# Production Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///movies.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['THUMBNAIL_FOLDER'] = 'static/thumbnails'
app.config['MAX_CONTENT_LENGTH'] = None  # Remove file size limit

# Ensure upload and thumbnail directories exist
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER']), exist_ok=True)
os.makedirs(os.path.join(app.config['THUMBNAIL_FOLDER']), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Language list for dropdown
LANGUAGES = [
    'English', 'Hindi', 'Tamil', 'Malayalam'
]

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    movies = db.relationship('Movie', backref='uploader', lazy=True)

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    thumbnail = db.Column(db.String(200), nullable=True)
    language = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

def generate_thumbnail(video_path, thumbnail_path):
    """Generate a thumbnail for the uploaded video."""
    try:
        video = cv2.VideoCapture(video_path)
        success, image = video.read()
        if success:
            # Resize thumbnail while maintaining aspect ratio
            height, width = image.shape[:2]
            aspect_ratio = width / height
            new_width = 400
            new_height = int(new_width / aspect_ratio)
            resized_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
            
            cv2.imwrite(thumbnail_path, resized_image)
            return True
        return False
    except Exception as e:
        print(f"Thumbnail generation error: {e}")
        return False

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        new_user = User(username=username, password_hash=bcrypt.generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

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
    # Use PORT environment variable for Render
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
