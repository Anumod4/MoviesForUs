import os
import sys
import traceback
from sqlalchemy import create_engine, text

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Movie

def test_database_connection():
    """
    Test database connection and print detailed diagnostics
    """
    try:
        # Get the database URL from the app configuration
        database_url = app.config['SQLALCHEMY_DATABASE_URI']
        print(f"Testing connection to: {database_url}")
        
        # Create an engine
        engine = create_engine(database_url, echo=False)
        
        # Attempt to connect and execute a simple query
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            fetched_result = result.fetchone()
            print("Connection successful. Test query result:", fetched_result)
        
        return True
    except Exception as e:
        print(f"Database connection test failed: {e}")
        traceback.print_exc()
        return False

def reset_database():
    """
    Completely reset the database, dropping and recreating all tables
    """
    try:
        with app.app_context():
            # Get the database URL
            database_url = app.config['SQLALCHEMY_DATABASE_URI']
            
            # Drop all existing tables
            db.drop_all()
            
            # Create all tables
            db.create_all()
            
            # If using PostgreSQL, use raw SQL to ensure table creation
            if 'postgresql' in database_url:
                from sqlalchemy import text
                with db.engine.connect() as connection:
                    # Create Users table
                    connection.execute(text("""
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            username VARCHAR(80) UNIQUE NOT NULL,
                            password_hash VARCHAR(255) NOT NULL
                        )
                    """))
                    
                    # Create Movies table
                    connection.execute(text("""
                        CREATE TABLE IF NOT EXISTS movies (
                            id SERIAL PRIMARY KEY,
                            title VARCHAR(100) NOT NULL,
                            filename VARCHAR(200) NOT NULL,
                            thumbnail VARCHAR(200),
                            language VARCHAR(50) NOT NULL,
                            user_id INTEGER NOT NULL REFERENCES users(id)
                        )
                    """))
                    
                    connection.commit()
                    print("Tables created using raw SQL for PostgreSQL")
            
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
    print("1. Test Database Connection")
    print("2. Reset Database")
    print("3. Print Users")
    
    choice = input("Enter your choice (1/2/3): ")
    
    if choice == '1':
        test_database_connection()
    elif choice == '2':
        reset_database()
    elif choice == '3':
        print_users()
    else:
        print("Invalid choice.")

if __name__ == '__main__':
    main()
