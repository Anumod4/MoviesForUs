import os
import sys
import sqlite3

def check_sqlite_database(db_path):
    """
    Directly check SQLite database contents
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Tables in database:")
        for table in tables:
            print(f"- {table[0]}")

        # Check movies table
        try:
            cursor.execute("SELECT * FROM movies")
            movies = cursor.fetchall()
            
            print("\nMovies in database:")
            print(f"Total Movies: {len(movies)}")
            
            for movie in movies:
                print("\nMovie Details:")
                print(f"ID: {movie[0]}")
                print(f"Title: {movie[1]}")
                print(f"Filename: {movie[2]}")
                print(f"Thumbnail: {movie[3]}")
                print(f"Language: {movie[4]}")
                print(f"User ID: {movie[5]}")
        
        except sqlite3.OperationalError as table_error:
            print(f"Error accessing movies table: {table_error}")

        conn.close()

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")

def find_database_files(start_path):
    """
    Find all SQLite database files
    """
    print("Searching for database files...")
    for root, dirs, files in os.walk(start_path):
        for file in files:
            if file.endswith('.db'):
                db_path = os.path.join(root, file)
                print(f"\nChecking database: {db_path}")
                check_sqlite_database(db_path)

def main():
    # Project directory
    project_dir = os.path.abspath(os.path.dirname(__file__))
    
    # Check databases in project directory and its subdirectories
    find_database_files(project_dir)

if __name__ == "__main__":
    main()
