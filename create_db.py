import sqlalchemy
from sqlalchemy import create_engine, text

def create_db():
    # Connect to default 'postgres' database to create the new one
    url = "postgresql://postgres:1234@localhost:5432/postgres"
    engine = create_engine(url)
    
    try:
        with engine.connect() as conn:
            # PostgreSQL doesn't allow CREATE DATABASE inside a transaction block
            conn.execution_options(isolation_level="AUTOCOMMIT").execute(text("CREATE DATABASE safeagent"))
            print("Database 'safeagent' created successfully.")
    except Exception as e:
        if "already exists" in str(e):
            print("Database 'safeagent' already exists.")
        else:
            print(f"Error creating database: {e}")

if __name__ == "__main__":
    create_db()
