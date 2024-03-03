import sqlite3
from sqlite3 import Connection, Cursor
from typing import Optional, List, Dict
from queue import Queue
from threading import Lock

# Connection pool
class ConnectionPool:
    DB_FILE = "builds.db"

    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self._connections = Queue(max_connections)
        self._lock = Lock()

        for _ in range(max_connections):
            connection = sqlite3.connect(self.DB_FILE, check_same_thread=False)
            self._connections.put(connection)

    def get_connection(self) -> Connection:
        return self._connections.get()

    def release_connection(self, connection: Connection):
        self._connections.put(connection)

    def execute(self, query: str, args: Optional[tuple] = None) -> Cursor:
        connection = self.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(query, args)
            return cursor
        except Exception as e:
            # Handle exceptions appropriately (e.g., log error)
            raise
        finally:
            self.release_connection(connection)

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._lock.release()
