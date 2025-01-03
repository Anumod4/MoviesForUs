import os
import sys
import requests

# Add project directory to Python path
project_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_dir)

def test_upload_sources():
    """
    Comprehensive test of upload sources and file upload mechanics
    """
    print("=" * 50)
    print("Upload Sources Diagnostic")
    print("=" * 50)

    # Test video file
    test_video_path = os.path.join(project_dir, 'static', 'uploads', 'Manish_wedding.mp4')
    
    if not os.path.exists(test_video_path):
        print(f"✗ Test Video Not Found: {test_video_path}")
        return

    # Simulate multipart/form-data upload
    files = {
        'movie': ('Manish_wedding.mp4', open(test_video_path, 'rb'), 'video/mp4'),
        'title': (None, 'Test Wedding Video'),
        'language': (None, 'English')
    }

    # Attempt upload
    try:
        # Use requests to simulate file upload
        response = requests.post(
            'http://localhost:5000/upload',  # Adjust if different
            files=files,
            allow_redirects=False  # Prevent automatic redirects
        )

        print("Upload Response Details:")
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {response.headers}")
        print(f"Response Content: {response.text}")

        # Check upload status
        if response.status_code in [200, 302]:
            print("✓ Upload Attempt Successful")
        else:
            print("✗ Upload Failed")
            print(f"Error Details: {response.text}")

    except Exception as upload_error:
        print(f"Upload Error: {upload_error}")

def main():
    test_upload_sources()

if __name__ == "__main__":
    main()
