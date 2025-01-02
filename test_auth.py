import requests
import sys
import os

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, bcrypt

def test_user_registration():
    """
    Test user registration process
    """
    with app.app_context():
        # Check if user already exists
        existing_user = User.query.filter_by(username='TestUser').first()
        if existing_user:
            db.session.delete(existing_user)
            db.session.commit()

        # Create a new user
        hashed_password = bcrypt.generate_password_hash('TestPassword123!').decode('utf-8')
        new_user = User(
            username='TestUser', 
            password_hash=hashed_password
        )
        
        # Add and commit the user
        db.session.add(new_user)
        db.session.commit()

        # Verify user was added
        created_user = User.query.filter_by(username='TestUser').first()
        assert created_user is not None, "User registration failed"
        print("✅ User registration successful")
        
        # Verify password
        assert bcrypt.check_password_hash(created_user.password_hash, 'TestPassword123!'), "Password verification failed"
        print("✅ Password verification successful")

def test_user_login():
    """
    Test user login process
    """
    with app.app_context():
        # Find the test user
        user = User.query.filter_by(username='TestUser').first()
        assert user is not None, "Test user not found"

        # Check password
        is_valid = bcrypt.check_password_hash(user.password_hash, 'TestPassword123!')
        assert is_valid, "Login failed: Incorrect password"
        print("✅ Login successful")

def main():
    try:
        test_user_registration()
        test_user_login()
        print("\n🎉 All authentication tests passed successfully!")
    except AssertionError as e:
        print(f"❌ Test failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == '__main__':
    main()
