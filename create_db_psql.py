import subprocess
import sys
import os
from dotenv import load_dotenv


def create_db_with_psql():
    """
    Create database using psql command
    """
    # Load environment variables
    load_dotenv()
    
    # Get database settings from environment
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', 'password')
    db_name = os.getenv('DB_NAME', 'fedresurs_db')
    
    print(f"Attempting to create database '{db_name}' using psql...")
    
    # Try to create database using psql command
    try:
        # Command to create database
        cmd = [
            'createdb',
            '-h', db_host,
            '-p', db_port,
            '-U', db_user,
            '-w',  # Disable password prompt (password is in PGPASSWORD environment variable)
            db_name
        ]
        
        # Set password in environment variable
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"Database '{db_name}' created successfully!")
            return True
        else:
            if "already exists" in result.stderr:
                print(f"Database '{db_name}' already exists.")
                return True
            else:
                print(f"Error creating database: {result.stderr}")
                return False
                
    except FileNotFoundError:
        print("psql or createdb command not found. PostgreSQL might not be in PATH.")
        print("You may need to add PostgreSQL bin directory to your system PATH.")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def main():
    print("Trying to create database using PostgreSQL command line tools...")
    success = create_db_with_psql()
    
    if success:
        print("\nDatabase setup completed successfully!")
        print("You can now run table initialization with init_db.py")
    else:
        print("\nError setting up database.")
        print("\nAlternative methods:")
        print("1. Install PostgreSQL command line tools and add to PATH")
        print("2. Use pgAdmin to create database manually")
        print("3. Use Docker to run PostgreSQL container")
        sys.exit(1)


if __name__ == "__main__":
    main()