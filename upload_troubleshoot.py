import os
import sys
import traceback
import logging
import requests

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('upload_troubleshoot.log', encoding='utf-8')
    ]
)

def test_upload_process():
    """
    Comprehensive upload process troubleshooting
    """
    print("=" * 50)
    print("Upload Process Troubleshooting")
    print("=" * 50)

    # Project directory setup
    project_dir = os.path.abspath(os.path.dirname(__file__))
    sys.path.insert(0, project_dir)

    # Test video file
    test_video_path = os.path.join(project_dir, 'static', 'uploads', 'Manish_wedding.mp4')
    
    if not os.path.exists(test_video_path):
        print(f"✗ Test Video Not Found: {test_video_path}")
        print("Please ensure a test video exists in the specified path.")
        return

    # Prepare multipart form data
    files = {
        'movie': ('Manish_wedding.mp4', open(test_video_path, 'rb'), 'video/mp4')
    }
    
    form_data = {
        'title': 'Test Wedding Video',
        'language': 'English'
    }

    # Authentication check
    try:
        # Attempt to log in first
        login_url = 'http://localhost:5000/login'
        login_data = {
            'username': 'test_user',  # Replace with an actual test user
            'password': 'test_password'  # Replace with actual password
        }

        login_session = requests.Session()
        login_response = login_session.post(login_url, data=login_data)
        
        print("Login Response Details:")
        print(f"Status Code: {login_response.status_code}")
        print(f"Response Headers: {login_response.headers}")
        print(f"Response Content: {login_response.text}")

        if login_response.status_code not in [200, 302]:
            print("✗ Login Failed")
            return

        # Attempt upload
        upload_url = 'http://localhost:5000/upload'
        
        upload_response = login_session.post(
            upload_url, 
            files=files, 
            data=form_data,
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )

        print("\nUpload Response Details:")
        print(f"Status Code: {upload_response.status_code}")
        print(f"Response Headers: {upload_response.headers}")
        print(f"Response Content: {upload_response.text}")

        # Detailed response analysis
        if upload_response.status_code in [200, 302]:
            print("✓ Upload Attempt Successful")
        else:
            print("✗ Upload Failed")
            print(f"Error Details: {upload_response.text}")

    except Exception as upload_error:
        print(f"Upload Error: {upload_error}")
        print(traceback.format_exc())

def main():
    test_upload_process()

if __name__ == "__main__":
    main()
