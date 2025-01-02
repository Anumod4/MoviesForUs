import os
import sys
import traceback

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Movie

def reset_database():
    """
    Completely reset the database, dropping and recreating all tables
    """
    try:
        with app.app_context():
            # Drop all existing tables
            db.drop_all()
            
            # Create all tables
            db.create_all()
            
            # Verify table creation
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            print("Database reset. Existing tables:")
            for table in tables:
                print(f"- {table}")
            
            # Optional: Create a test user
            test_user = User(
                username='TestUser', 
                password_hash='$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW'  # hashed 'password'
            )
            
            db.session.add(test_user)
            db.session.commit()
            
            print("Test user 'TestUser' created successfully.")
    
    except Exception as e:
        print(f"Error resetting database: {e}")
        traceback.print_exc()

def print_users():
    """
    Print all users in the database
    """
    try:
        with app.app_context():
            users = User.query.all()
            print("Users in the database:")
            for user in users:
                print(f"- ID: {user.id}, Username: {user.username}")
    except Exception as e:
        print(f"Error retrieving users: {e}")
        traceback.print_exc()

def main():
    print("Database Initialization and Diagnostic Tool")
    print("1. Reset Database")
    print("2. Print Users")
    
    choice = input("Enter your choice (1/2): ")
    
    if choice == '1':
        reset_database()
    elif choice == '2':
        print_users()
    else:
        print("Invalid choice.")

if __name__ == '__main__':
    main()
