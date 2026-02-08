"""Shared database connection pool for the explorer and face services."""

import psycopg2
from psycopg2 import pool
import config

_pool = None


def get_pool():
    global _pool
    if _pool is None or _pool.closed:
        _pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=5,
            host=config.PG_HOST,
            port=config.PG_PORT,
            dbname=config.PG_DATABASE,
            user=config.PG_USER,
            password=config.PG_PASSWORD,
        )
    return _pool


def get_conn():
    return get_pool().getconn()


def put_conn(conn):
    try:
        get_pool().putconn(conn)
    except Exception:
        pass


class db_cursor:
    """Context manager for DB queries: auto get/put connection + cursor."""

    def __init__(self):
        self.conn = None
        self.cur = None

    def __enter__(self):
        self.conn = get_conn()
        self.cur = self.conn.cursor()
        return self.cur

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cur:
            self.cur.close()
        if self.conn:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
            put_conn(self.conn)
        return False
