from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=5)

    def initialize(self) -> None:
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.execute(schema)

    @contextmanager
    def transaction(self):
        with self.connect() as conn:
            with conn.transaction():
                yield conn

    def fetchone(self, query: str, params: tuple = ()):
        with self.connect() as conn:
            return conn.execute(query, params).fetchone()

    def fetchall(self, query: str, params: tuple = ()):
        with self.connect() as conn:
            return conn.execute(query, params).fetchall()

    def execute(self, query: str, params: tuple = ()) -> int:
        with self.connect() as conn:
            return conn.execute(query, params).rowcount
