import subprocess
import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
import psycopg2
from src.config import settings


def check_postgres_connection():
    """
    Check PostgreSQL connection
    """
    try:
        # Connect to PostgreSQL using psycopg2
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database='postgres'  # Connect to system database
        )
        conn.close()
        return True
    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return False


def create_database_if_not_exists():
    """
    Create database if it doesn't exist
    """
    try:
        # Connect to PostgreSQL to system database
        engine = create_engine(
            f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/postgres"
        )

        with engine.connect() as conn:
            # Check if database exists
            result = conn.execute(
                text("SELECT 1 FROM pg_catalog.pg_database WHERE datname = :dbname"),
                {"dbname": settings.DB_NAME}
            )

            if not result.fetchone():
                # Create database
                # Need to disable autocommit for database creation
                conn.execute(text("COMMIT"))
                conn.execute(text(f"CREATE DATABASE {settings.DB_NAME}"))
                print(f"Database {settings.DB_NAME} created successfully!")
            else:
                print(f"Database {settings.DB_NAME} already exists.")

        return True
    except Exception as e:
        print(f"Error creating database: {e}")
        return False


def main():
    print("Checking PostgreSQL connection...")

    if not check_postgres_connection():
        print("Could not connect to PostgreSQL. Make sure:")
        print("1. PostgreSQL server is running")
        print("2. Correct credentials in .env file")
        print("3. Port 5432 is open and available")
        return False

    print("PostgreSQL connection successful!")

    print(f"Creating database {settings.DB_NAME}...")
    if create_database_if_not_exists():
        print("Database prepared successfully!")
        return True
    else:
        print("Could not create database.")
        return False


if __name__ == "__main__":
    success = main()
    if success:
        print("\nNow you can run table initialization with init_db.py")
    else:
        print("\nError preparing database.")
        sys.exit(1)