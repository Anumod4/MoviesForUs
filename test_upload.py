import os
import sys
import traceback

# Add project directory to Python path
project_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_dir)

def safe_import(module_name):
    """Safely import a module"""
    try:
        return __import__(module_name)
    except ImportError:
        print(f"Could not import {module_name}")
        return None

def test_upload_process():
    """
    Comprehensive test of the upload process
    """
    try:
        # Import necessary modules
        from app import app, db, Movie, User
        from werkzeug.security import generate_password_hash
        from sqlalchemy import text

        # Create an application context
        with app.app_context():
            print("=" * 50)
            print("Upload Process Test")
            print("=" * 50)

            # Check database connection
            try:
                db.session.execute(text('SELECT 1'))
                print("✓ Database Connection: Successful")
            except Exception as db_error:
                print(f"✗ Database Connection Error: {db_error}")
                return

            # Create a test user if not exists
            test_username = 'test_uploader'
            test_password = 'test_password'

            existing_user = User.query.filter_by(username=test_username).first()
            if not existing_user:
                test_user = User(
                    username=test_username,
                    email=f'{test_username}@example.com',
                    password=generate_password_hash(test_password)
                )
                db.session.add(test_user)
                db.session.commit()
                print(f"✓ Test User Created: {test_username}")
            else:
                test_user = existing_user
                print(f"✓ Test User Exists: {test_username}")

            # Test file upload
            test_video_path = os.path.join(project_dir, 'static', 'uploads', 'Manish_wedding.mp4')
            
            if not os.path.exists(test_video_path):
                print(f"✗ Test Video Not Found: {test_video_path}")
                return

            # Validate file
            from app import validate_video_file, generate_thumbnail

            video_validation = validate_video_file(test_video_path)
            if not video_validation['valid']:
                print(f"✗ Video Validation Failed: {video_validation}")
                return

            # Generate thumbnail
            thumbnail_folder = app.config['THUMBNAIL_FOLDER']
            thumbnail_filename = f"test_thumb_{os.path.basename(test_video_path).split('.')[0]}.jpg"
            thumbnail_path = os.path.join(thumbnail_folder, thumbnail_filename)

            generate_thumbnail(test_video_path, thumbnail_path)
            
            if not os.path.exists(thumbnail_path):
                print(f"✗ Thumbnail Generation Failed: {thumbnail_path}")
                return

            print(f"✓ Thumbnail Generated: {thumbnail_path}")

            # Create movie record
            new_movie = Movie(
                title='Test Wedding Video',
                filename=os.path.basename(test_video_path),
                thumbnail=thumbnail_filename,
                language='English',
                user_id=test_user.id
            )

            # Database transaction
            try:
                db.session.add(new_movie)
                db.session.commit()
                print("✓ Movie Record Added to Database")

                # Verify movie record
                saved_movie = Movie.query.filter_by(filename=new_movie.filename).first()
                if saved_movie:
                    print(f"✓ Movie Verified in Database:")
                    print(f"  ID: {saved_movie.id}")
                    print(f"  Title: {saved_movie.title}")
                    print(f"  Filename: {saved_movie.filename}")
                    print(f"  Thumbnail: {saved_movie.thumbnail}")
                else:
                    print("✗ Movie Not Found in Database")

            except Exception as db_save_error:
                db.session.rollback()
                print(f"✗ Database Save Error: {db_save_error}")
                print(traceback.format_exc())

    except Exception as global_error:
        print(f"Critical Error: {global_error}")
        print(traceback.format_exc())

def main():
    test_upload_process()

if __name__ == "__main__":
    main()
