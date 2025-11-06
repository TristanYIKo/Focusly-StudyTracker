"""
Reset all study tracker stats by clearing the database.
This will delete all session history and reset stats to 0.
"""

import os
from BackEnd.core.paths import db_path, user_data_dir

def reset_all_stats():
    """Delete the database file to reset all stats."""
    db_file = db_path()
    
    if db_file.exists():
        print(f"Found database at: {db_file}")
        
        # Ask for confirmation
        confirm = input("Are you sure you want to reset all stats? This cannot be undone. (yes/no): ")
        
        if confirm.lower() in ['yes', 'y']:
            try:
                os.remove(db_file)
                print("✓ Database deleted successfully!")
                print("✓ All stats have been reset to 0")
                print("\nNext time you open the app, a fresh database will be created.")
            except Exception as e:
                print(f"✗ Error deleting database: {e}")
        else:
            print("Reset cancelled.")
    else:
        print("No database found. Stats are already at 0.")
    
    # Also delete todo list if it exists
    todos_file = user_data_dir() / "todos.json"
    if todos_file.exists():
        confirm_todos = input("\nAlso delete your To-Do list? (yes/no): ")
        if confirm_todos.lower() in ['yes', 'y']:
            try:
                os.remove(todos_file)
                print("✓ To-Do list deleted successfully!")
            except Exception as e:
                print(f"✗ Error deleting To-Do list: {e}")

if __name__ == "__main__":
    print("=" * 50)
    print("Study Tracker - Reset All Stats")
    print("=" * 50)
    reset_all_stats()
    print("\nPress Enter to exit...")
    input()
