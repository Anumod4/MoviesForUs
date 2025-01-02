import os
import sys
import traceback
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def diagnose_database_connection():
    """
    Comprehensive database connection diagnostic tool
    """
    print("🔍 Database Connection Diagnostic Tool")
    print("=" * 50)

    # Collect database configuration
    db_config = {
        'Host': os.getenv('AIVEN_DB_HOST'),
        'Port': os.getenv('AIVEN_DB_PORT'),
        'Name': os.getenv('AIVEN_DB_NAME'),
        'User': os.getenv('AIVEN_DB_USER'),
        'SSL Mode': 'require'
    }

    print("\n📋 Database Configuration:")
    for key, value in db_config.items():
        print(f"{key}: {value}")

    # Test PostgreSQL connection
    try:
        import psycopg2
        from psycopg2 import sql

        # Construct connection parameters
        conn_params = {
            'host': db_config['Host'],
            'port': db_config['Port'],
            'dbname': db_config['Name'],
            'user': db_config['User'],
            'password': os.getenv('AIVEN_DB_PASSWORD'),
            'sslmode': 'require'
        }

        print("\n🔌 Attempting to connect to PostgreSQL...")
        
        # Establish connection
        with psycopg2.connect(**conn_params) as conn:
            print("✅ Connection successful!")
            
            # Create a cursor
            with conn.cursor() as cur:
                # Test query
                cur.execute("SELECT version()")
                db_version = cur.fetchone()[0]
                print(f"📊 Database Version: {db_version}")

                # Check table existence
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'users'
                    )
                """)
                users_table_exists = cur.fetchone()[0]
                print(f"👥 Users Table Exists: {'Yes' if users_table_exists else 'No'}")

                # If table doesn't exist, create it
                if not users_table_exists:
                    print("🛠 Creating users table...")
                    cur.execute("""
                        CREATE TABLE users (
                            id SERIAL PRIMARY KEY,
                            username VARCHAR(80) UNIQUE NOT NULL,
                            password_hash VARCHAR(255) NOT NULL
                        )
                    """)
                    conn.commit()
                    print("✅ Users table created successfully")

    except psycopg2.Error as e:
        print(f"❌ PostgreSQL Connection Error: {e}")
        traceback.print_exc()
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        traceback.print_exc()

def main():
    diagnose_database_connection()

if __name__ == '__main__':
    main()
