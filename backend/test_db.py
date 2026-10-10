import os
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError


class DatabaseConfigurationTests(unittest.TestCase):
    def test_database_url_requires_postgresql(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///local.db"}):
            with self.assertRaisesRegex(RuntimeError, "must use PostgreSQL"):
                from backend.db import _database_url

                _database_url()

    def test_postgres_url_uses_psycopg_driver(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:secret@127.0.0.1:5432/shanhe"}):
            from backend.db import _database_url

            url = _database_url()
            self.assertEqual(url.drivername, "postgresql+psycopg")
            self.assertEqual(url.database, "shanhe")


class DatabaseHealthTests(unittest.TestCase):
    def test_database_health_does_not_expose_connection_details(self) -> None:
        from backend import main

        with patch.object(main.engine, "connect") as connect:
            connection = MagicMock()
            connect.return_value.__enter__.return_value = connection
            response = main.database_health()

        self.assertEqual(response, {"status": "ok", "service": "postgresql"})

    def test_database_health_returns_generic_failure(self) -> None:
        from backend import main

        with patch.object(main.engine, "connect", side_effect=OperationalError("secret-url", {}, Exception("failure"))):
            response = main.database_health()

        self.assertEqual(response, {"status": "unavailable", "service": "postgresql"})


if __name__ == "__main__":
    unittest.main()
