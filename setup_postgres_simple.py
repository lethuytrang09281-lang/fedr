import psycopg2
import sys
from dotenv import load_dotenv
import os


def check_and_create_db():
    """
    Check PostgreSQL connection and create database if needed
    """
    # Load environment variables
    load_dotenv()

    # Get database settings from environment
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = int(os.getenv('DB_PORT', 5432))
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', 'admin')
    db_name = os.getenv('DB_NAME', 'fedresurs_db')

    print(f"Attempting to connect to PostgreSQL at {db_host}:{db_port}")
    print(f"Using user: {db_user}, database: {db_name}")

    try:
        # Connect to PostgreSQL system database
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database='postgres'
        )

        print("Successfully connected to PostgreSQL!")

        # Create cursor
        cur = conn.cursor()

        # Check if database exists
        cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (db_name,))
        exists = cur.fetchone()

        if not exists:
            # Create database
            # Need to close connection and reconnect with autocommit for database creation
            conn.close()

            # Connect again with autocommit enabled
            conn = psycopg2.connect(
                host=db_host,
                port=db_port,
                user=db_user,
                password=db_password,
                database='postgres'
            )
            conn.autocommit = True

            cur = conn.cursor()
            cur.execute(f"CREATE DATABASE {db_name}")
            cur.close()

            print(f"Database '{db_name}' created successfully!")
        else:
            print(f"Database '{db_name}' already exists.")

        conn.close()
        print("Database setup completed successfully!")
        return True

    except psycopg2.OperationalError as e:
        print(f"Operational error (likely connection issue): {e}")
        print("\nMake sure:")
        print("1. PostgreSQL server is running")
        print("2. Host, port, username, and password are correct")
        print("3. User has privileges to create databases")
        return False
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = check_and_create_db()
    if success:
        print("\nYou can now run table initialization with init_db.py")
    else:
        print("\nError setting up database.")
        sys.exit(1)