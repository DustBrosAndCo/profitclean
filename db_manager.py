import sqlite3
import os
from contextlib import contextmanager
from logger_config import logger

DB_PATH = os.path.join(os.path.dirname(__file__), "profitclean.db")


@contextmanager
def get_db_connection():
    """Context manager for database connections with automatic commit/rollback.
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            results = cursor.fetchall()
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        yield conn
        conn.commit()
        logger.debug("Database transaction committed successfully")
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
            logger.error(f"Database error, transaction rolled back: {e}")
        raise
    except Exception as e:
        if conn:
            conn.rollback()
            logger.error(f"Unexpected error, transaction rolled back: {e}")
        raise
    finally:
        if conn:
            conn.close()
            logger.debug("Database connection closed")


def execute_query(query: str, params: tuple = None, fetch_one: bool = False, fetch_all: bool = False):
    """Execute a database query with parameters.
    
    Args:
        query: SQL query string
        params: Tuple of parameters for parameterized query
        fetch_one: If True, return single row
        fetch_all: If True, return all rows
        
    Returns:
        Query result or None
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        
        if fetch_one:
            return cursor.fetchone()
        elif fetch_all:
            return cursor.fetchall()
        else:
            return cursor.lastrowid


def execute_write(query: str, params: tuple = None) -> int:
    """Execute a write operation (INSERT, UPDATE, DELETE).
    
    Args:
        query: SQL query string
        params: Tuple of parameters for parameterized query
        
    Returns:
        Last row ID for INSERT operations
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        return cursor.lastrowid
