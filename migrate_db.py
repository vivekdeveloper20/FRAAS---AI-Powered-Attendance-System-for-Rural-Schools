import sqlite3
import sys

def migrate():
    try:
        conn = sqlite3.connect("instance/fraas.db")
        cursor = conn.cursor()
        
        # Add the role column
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'Teacher'")
            print("Added 'role' column.")
        except sqlite3.OperationalError as e:
            print("Column might already exist:", e)
            
        # Migrate existing users to Admin
        cursor.execute("UPDATE users SET role = 'Admin'")
        print("Updated existing users to Admin.")
        
        conn.commit()
        conn.close()
        print("Migration successful.")
    except Exception as e:
        print("Migration failed:", e)
        sys.exit(1)

if __name__ == "__main__":
    migrate()
