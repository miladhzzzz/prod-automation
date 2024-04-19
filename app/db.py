import sqlite3
from sqlite3 import Connection, Cursor
from typing import Optional, List, Dict
from queue import Queue
from threading import Lock

# Connection pool
class ConnectionPool:

    DB_FILE = "database/builds.db"

    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self._connections = Queue(max_connections)
        self._lock = Lock()
        
        for _ in range(max_connections):
            connection = sqlite3.connect(self.DB_FILE, check_same_thread=False)
            self._connections.put(connection)

    def execute(self, query: str, args: Optional[tuple] = None) -> Cursor:
        with self.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(query, args)
            return cursor

    def get_connection(self) -> Connection:
        return ConnectionContextManager(self)

    def release_connection(self, connection: Connection):
        self._connections.put(connection)

class ConnectionContextManager:
    def __init__(self, connection_pool: ConnectionPool):
        self.connection_pool = connection_pool
        self.connection = None

    def __enter__(self) -> Connection:
        self.connection = self.connection_pool._connections.get()
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.connection_pool.release_connection(self.connection)