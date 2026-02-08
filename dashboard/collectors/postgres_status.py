import config


def collect():
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=config.PG_HOST,
            port=config.PG_PORT,
            dbname=config.PG_DATABASE,
            user=config.PG_USER,
            password=config.PG_PASSWORD,
            connect_timeout=5,
        )
        cur = conn.cursor()

        # Database size
        cur.execute("SELECT pg_size_pretty(pg_database_size(%s))", (config.PG_DATABASE,))
        db_size = cur.fetchone()[0]

        # Table row counts (approximate, fast)
        cur.execute("""
            SELECT schemaname, relname, n_live_tup
            FROM pg_stat_user_tables
            ORDER BY n_live_tup DESC
            LIMIT 20
        """)
        tables = [
            {"schema": row[0], "table": row[1], "row_count": row[2]}
            for row in cur.fetchall()
        ]

        # PostGIS version
        postgis_version = None
        try:
            cur.execute("SELECT PostGIS_Version()")
            postgis_version = cur.fetchone()[0]
        except Exception:
            conn.rollback()

        cur.close()
        conn.close()

        return {
            "connected": True,
            "host": config.PG_HOST,
            "database": config.PG_DATABASE,
            "db_size": db_size,
            "tables": tables,
            "postgis_version": postgis_version,
            "error": None,
        }
    except ImportError:
        return {
            "connected": False,
            "host": config.PG_HOST,
            "database": config.PG_DATABASE,
            "db_size": None,
            "tables": [],
            "postgis_version": None,
            "error": "psycopg2 not installed",
        }
    except Exception as e:
        return {
            "connected": False,
            "host": config.PG_HOST,
            "database": config.PG_DATABASE,
            "db_size": None,
            "tables": [],
            "postgis_version": None,
            "error": str(e),
        }
