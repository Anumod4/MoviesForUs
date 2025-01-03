import os
import sys
import traceback
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('upload_diagnostics.log', encoding='utf-8')
    ]
)

def diagnose_upload_environment():
    """
    Comprehensive diagnostic for upload environment
    """
    print("=" * 50)
    print("Upload Environment Diagnostics")
    print("=" * 50)

    # Check Python environment
    logging.info(f"Python Executable: {sys.executable}")
    logging.info(f"Python Version: {sys.version}")
    logging.info(f"Python Path: {sys.path}")

    # Check project directory
    project_dir = os.path.abspath(os.path.dirname(__file__))
    logging.info(f"Project Directory: {project_dir}")

    # Check upload-related files and configurations
    upload_related_files = [
        'app.py', 
        'templates/upload.html', 
        '.env', 
        'static/js/main.js'
    ]

    for file_path in upload_related_files:
        full_path = os.path.join(project_dir, file_path)
        if os.path.exists(full_path):
            logging.info(f"Checking {file_path}:")
            try:
                with open(full_path, 'r') as f:
                    # Look for upload-related configurations
                    for line_num, line in enumerate(f, 1):
                        if any(keyword in line.lower() for keyword in ['upload', 'file', 'movie', 'form']):
                            logging.debug(f"  Line {line_num}: {line.strip()}")
            except Exception as read_error:
                logging.error(f"Error reading {file_path}: {read_error}")
        else:
            logging.warning(f"{file_path} not found")

    # Check upload and thumbnail folders
    folders = {
        'Upload Folder': os.path.join(project_dir, 'static', 'uploads'),
        'Thumbnail Folder': os.path.join(project_dir, 'static', 'thumbnails')
    }

    for folder_name, folder_path in folders.items():
        logging.info(f"\n{folder_name}:")
        logging.info(f"  Path: {folder_path}")
        
        if os.path.exists(folder_path):
            logging.info(f"  Exists: Yes")
            logging.info(f"  Permissions: {oct(os.stat(folder_path).st_mode)[-3:]}")
            
            # Check contents
            try:
                contents = os.listdir(folder_path)
                logging.info(f"  Total Files: {len(contents)}")
                
                if contents:
                    logging.info("  Sample Files:")
                    for file in contents[:5]:  # Show first 5 files
                        file_path = os.path.join(folder_path, file)
                        logging.info(f"    - {file}")
            except Exception as contents_error:
                logging.error(f"  Error checking folder contents: {contents_error}")
        else:
            logging.warning(f"  Exists: No")

    # Check dependencies
    dependencies = [
        'flask', 
        'werkzeug', 
        'flask_login', 
        'flask_sqlalchemy'
    ]

    logging.info("\nDependency Check:")
    for dep in dependencies:
        try:
            __import__(dep.replace('-', '_'))
            logging.info(f"  {dep}: Installed ✓")
        except ImportError:
            logging.warning(f"  {dep}: NOT INSTALLED ✗")

def main():
    try:
        diagnose_upload_environment()
    except Exception as e:
        logging.critical(f"Critical error in diagnostics: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
