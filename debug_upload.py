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

def check_upload_environment():
    """
    Comprehensive check of upload environment and configurations
    """
    print("=" * 50)
    print("Upload Environment Diagnostic")
    print("=" * 50)

    # Check configuration files
    config_files = [
        '.env', 
        'config.py', 
        'app.py'
    ]
    
    for config_file in config_files:
        config_path = os.path.join(project_dir, config_file)
        if os.path.exists(config_path):
            print(f"\nChecking {config_file}:")
            try:
                with open(config_path, 'r') as f:
                    for line_num, line in enumerate(f, 1):
                        if any(keyword in line.lower() for keyword in ['upload', 'folder', 'path', 'config']):
                            print(f"  Line {line_num}: {line.strip()}")
            except Exception as e:
                print(f"  Error reading {config_file}: {e}")
        else:
            print(f"{config_file} not found")

    # Import app safely
    try:
        from app import app
    except Exception as import_error:
        print(f"Could not import app: {import_error}")
        return

    # Check upload and thumbnail folders
    folders = {
        'Upload Folder': 'UPLOAD_FOLDER',
        'Thumbnail Folder': 'THUMBNAIL_FOLDER'
    }

    print("\nFolder Configurations:")
    for folder_name, config_key in folders.items():
        try:
            folder_path = app.config.get(config_key)
            
            print(f"\n{folder_name}:")
            print(f"  Path: {folder_path}")
            
            if folder_path:
                # Ensure absolute path
                folder_path = os.path.abspath(folder_path)
                
                # Check folder existence
                if os.path.exists(folder_path):
                    print(f"  Exists: Yes")
                    print(f"  Permissions: {oct(os.stat(folder_path).st_mode)[-3:]}")
                    
                    # Check contents
                    contents = os.listdir(folder_path)
                    print(f"  Total Files: {len(contents)}")
                    if contents:
                        print("  Sample Files:")
                        for file in contents[:5]:  # Show first 5 files
                            file_path = os.path.join(folder_path, file)
                            print(f"    - {file}")
                else:
                    print(f"  Exists: No (Will be created on first upload)")
            else:
                print(f"  Path: Not configured")
        
        except Exception as folder_error:
            print(f"  Error checking {folder_name}: {folder_error}")

    # Check file upload dependencies
    dependencies = [
        'flask', 
        'werkzeug', 
        'python-magic', 
        'opencv-python'
    ]

    print("\nDependency Check:")
    for dep in dependencies:
        module = safe_import(dep.replace('-', '_'))
        if module:
            print(f"  {dep}: Installed ✓")
        else:
            print(f"  {dep}: NOT INSTALLED ✗")

    # Check database configuration
    try:
        from app import db
        print("\nDatabase Configuration:")
        print(f"  Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured')}")
        print(f"  Track Modifications: {app.config.get('SQLALCHEMY_TRACK_MODIFICATIONS', 'Not configured')}")
    except Exception as db_error:
        print(f"Database configuration error: {db_error}")

def main():
    try:
        check_upload_environment()
    except Exception as e:
        print(f"Critical error in diagnostic: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
