import sqlite3

def create_tables():
    # Establish a connection to SQLite database
    conn = sqlite3.connect('certificates.db')
    cursor = conn.cursor()

    # Create Applications table with the new 'remarks' column
    create_application_table = """
    CREATE TABLE IF NOT EXISTS Applications (
        application_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id VARCHAR(50) REFERENCES users(user_id) ON DELETE CASCADE,
        certificate_type TEXT NOT NULL,
        status VARCHAR(20) DEFAULT 'Pending',
        application_data JSON,
        pdf_file BLOB,
        remarks TEXT DEFAULT NULL
    );
    """

    try:
        cursor.execute(create_application_table)

        # Check if the 'remarks' column exists, and add it if not
        cursor.execute("PRAGMA table_info(Applications)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'remarks' not in columns:
            cursor.execute("ALTER TABLE Applications ADD COLUMN remarks TEXT DEFAULT NULL")

        # Commit changes
        conn.commit()
        print("Success: All tables created/updated successfully!")
    except sqlite3.Error as e:
        print(f"Error: {e}")
    finally:
        # Close the database connection
        conn.close()

if __name__ == "__main__":
    create_tables()
