import os
import sys
import traceback

# Add project directory to Python path
project_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_dir)

# Import with error handling
def safe_import(module_name):
    try:
        return __import__(module_name)
    except ImportError:
        print(f"Error importing {module_name}")
        print(traceback.format_exc())
        return None

# Attempt to import Flask and SQLAlchemy modules
flask = safe_import('flask')
flask_login = safe_import('flask_login')
sqlalchemy = safe_import('sqlalchemy')

def print_movie_details():
    try:
        # Import app modules
        from app import app, db, Movie, User

        with app.app_context():
            # Get all movies
            movies = Movie.query.all()
            
            print("\n" + "=" * 50)
            print(f"Total Movies in Database: {len(movies)}")
            print("=" * 50)
            
            if not movies:
                print("No movies found in the database.")
                return
            
            for movie in movies:
                print("\nMovie Details:")
                print(f"ID: {movie.id}")
                print(f"Title: {movie.title}")
                print(f"Filename: {movie.filename}")
                print(f"Thumbnail: {movie.thumbnail}")
                print(f"Language: {movie.language}")
                print(f"User ID: {movie.user_id}")
                
                # Check file existence
                upload_folder = app.config['UPLOAD_FOLDER']
                thumbnail_folder = app.config['THUMBNAIL_FOLDER']
                
                movie_path = os.path.join(upload_folder, movie.filename)
                thumbnail_path = os.path.join(thumbnail_folder, movie.thumbnail) if movie.thumbnail else None
                
                print(f"Movie File Exists: {os.path.exists(movie_path)}")
                print(f"Thumbnail File Exists: {os.path.exists(thumbnail_path) if thumbnail_path else 'No Thumbnail'}")
                print("-" * 50)

    except Exception as e:
        print("Error retrieving movie details:")
        print(traceback.format_exc())

def main():
    print_movie_details()

if __name__ == "__main__":
    main()
