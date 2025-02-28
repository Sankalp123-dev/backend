import sqlite3

def delete_data_from_birth_certificate(condition):
    """
    Function to delete data from the Birth_Certificate table based on the given condition.
    The condition should be a valid SQL WHERE condition as a string (e.g. "id=1" or "Full_Name='John Doe'").
    """
    try:
        # Establish a connection to SQLite database
        conn = sqlite3.connect('certificates.db')
        cursor = conn.cursor()

        # Construct the SQL DELETE query
        delete_query = "DROP TABLE complaints;"
        
        # Execute the delete query
        cursor.execute(delete_query)
        conn.commit()  # Commit the transaction
        
        # Check how many rows were affected
        if cursor.rowcount > 0:
            print(f"Successfully dropped")
        else:
            print("No records matched the given condition.")
        
    except sqlite3.Error as e:
        print(f"Error deleting data from Birth_Certificate: {e}")
    
    finally:
        # Close the database connection
        conn.close()

if __name__ == "__main__":
    # Example: Delete records where Full_Name is 'John Doe'
    condition = "Full_Name = 'John Doe'"
    delete_data_from_birth_certificate(condition)
