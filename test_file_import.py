import os
import sys
import traceback
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler('test_import.log', encoding='utf-8'),
                        logging.StreamHandler()
                    ])

def test_import():
    try:
        # Add project directory to Python path
        project_dir = os.path.abspath(os.path.dirname(__file__))
        sys.path.insert(0, project_dir)

        # Verbose import logging
        logging.info("Python Path: %s", sys.path)
        logging.info("Current Working Directory: %s", os.getcwd())

        # Import necessary modules
        from app import app, db, Movie, User
        import flask_login

        # Test application context
        with app.app_context():
            # Diagnostic information
            logging.info("Application Context Entered")
            
            # Database diagnostics
            try:
                user_count = User.query.count()
                movie_count = Movie.query.count()
                logging.info(f"Existing Users: {user_count}")
                logging.info(f"Existing Movies: {movie_count}")
            except Exception as db_error:
                logging.error(f"Database Query Error: {db_error}")
                logging.error(traceback.format_exc())
                return False

            # Folder diagnostics
            upload_folder = app.config['UPLOAD_FOLDER']
            thumbnail_folder = app.config['THUMBNAIL_FOLDER']
            
            logging.info(f"Upload Folder: {upload_folder}")
            logging.info(f"Upload Folder Exists: {os.path.exists(upload_folder)}")
            logging.info(f"Thumbnail Folder: {thumbnail_folder}")
            logging.info(f"Thumbnail Folder Exists: {os.path.exists(thumbnail_folder)}")

            # Movie retrieval diagnostics
            try:
                movies = Movie.query.all()
                logging.info(f"Total Movies Retrieved: {len(movies)}")
                
                for movie in movies:
                    logging.info(f"Movie Details:")
                    logging.info(f"  ID: {movie.id}")
                    logging.info(f"  Title: {movie.title}")
                    logging.info(f"  Filename: {movie.filename}")
                    logging.info(f"  Thumbnail: {movie.thumbnail}")
                    logging.info(f"  Language: {movie.language}")
                    logging.info(f"  User ID: {movie.user_id}")
            except Exception as movie_error:
                logging.error(f"Movie Retrieval Error: {movie_error}")
                logging.error(traceback.format_exc())
                return False

        return True

    except Exception as e:
        logging.critical(f"Unexpected Error: {e}")
        logging.critical(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_import()
    sys.exit(0 if success else 1)
