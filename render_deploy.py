import os
import sys
import traceback
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Ensure the project directory is in the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Movie, bcrypt

def clear_database():
    """
    Completely clear and reset the database for Render deployment
    """
    print("🔄 Starting Render Deployment Database Reset")
    
    try:
        with app.app_context():
            # Drop all existing tables
            db.drop_all()
            print("✅ Dropped all existing tables")
            
            # Recreate all tables
            db.create_all()
            print("✅ Recreated database tables")
            
            # Create initial admin user
            admin_username = os.getenv('ADMIN_USERNAME', 'admin')
            admin_password = os.getenv('ADMIN_PASSWORD', 'AdminPass123!')
            
            # Hash the admin password
            hashed_password = bcrypt.generate_password_hash(admin_password).decode('utf-8')
            
            # Create admin user
            admin_user = User(
                username=admin_username,
                password_hash=hashed_password
            )
            
            # Add and commit the admin user
            db.session.add(admin_user)
            db.session.commit()
            
            print(f"✅ Created admin user: {admin_username}")
            
            # Optional: Add some initial data or configuration
            print("🏁 Render deployment database reset complete")
    
    except Exception as e:
        print(f"❌ Database reset failed: {e}")
        traceback.print_exc()
        sys.exit(1)

def verify_database_connection():
    """
    Verify database connection and configuration
    """
    print("🔍 Verifying Database Connection")
    
    try:
        # Get database URL
        database_url = app.config['SQLALCHEMY_DATABASE_URI']
        print(f"📡 Connecting to: {database_url}")
        
        # Create engine
        engine = create_engine(database_url)
        
        # Test connection
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            result.fetchone()
        
        print("✅ Database connection successful")
    
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        traceback.print_exc()
        sys.exit(1)

def main():
    print("🚀 Render Deployment Initialization")
    
    # Verify database connection first
    verify_database_connection()
    
    # Clear and reset database
    clear_database()

if __name__ == '__main__':
    main()
