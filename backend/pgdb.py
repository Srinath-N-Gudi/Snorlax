from .basedb import BaseDB
import os
import logging 
from dotenv import load_dotenv
load_dotenv()


logger = logging.getLogger(__name__)


class Table():
    def __init__(self, table_name:str, db:BaseDB):
        self.table_name = table_name 
        self.db = db

    def insert(self, **kwargs):
        keys = ", ".join(kwargs.keys())
        placeholders = ", ".join(["%s"] * len(kwargs))

        query = f"""
            INSERT INTO {self.table_name} ({keys})
            VALUES ({placeholders});
        """

        try:
            self.db.exec(query, tuple(kwargs.values()))
            return True

        except Exception as e:
            logging.error("Insertion failed: %s", e)
            return False
    def select(self, *args, **kwargs):
        if len(args) == 0:
            cols = "*"
        else:
            cols = ", ".join(args)

        if kwargs:
            conditions = " AND ".join(f"{key} = %s" for key in kwargs)
            values = tuple(kwargs.values())
            where = f"WHERE {conditions}"
        else:
            where = ""
            values = ()

        query = f"""
            SELECT {cols}
            FROM {self.table_name}
            {where};
        """

        return self.db.exec(query, values) 
    def clear_all(self):
        query = f"""
            TRUNCATE TABLE {self.table_name}
            RESTART IDENTITY
            CASCADE;
            """

        self.db.exec(query)

    def update(self, where: dict, **kwargs):
        if not kwargs:
            return False

        set_clause = ", ".join(
            f"{key} = %s" for key in kwargs
        )

        where_clause = " AND ".join(
            f"{key} = %s" for key in where
        )

        values = tuple(kwargs.values()) + tuple(where.values())

        query = f"""
            UPDATE {self.table_name}
            SET {set_clause}
            WHERE {where_clause};
        """

        try:
            self.db.exec(query, values)
            return True

        except Exception as e:
            logging.error("Update failed: %s", e)
            return False
    def delete(self, **where):

        if not where:
            return False

        where_clause = " AND ".join(
            f"{key} = %s" for key in where
        )

        values = tuple(where.values())

        query = f"""
            DELETE FROM {self.table_name}
            WHERE {where_clause};
        """

        try:
            self.db.exec(query, values)
            return True
        except Exception as e:
            logging.error("Delete failed: %s", e)
            return False
        
class DB(BaseDB):
    def __init__(self): 
        super().__init__(host=os.getenv('host'),
                         port=os.getenv('port'),
                         dbname=os.getenv('dbname'),
                         user=os.getenv('user'),
                         password=os.getenv('password'))
    def __create_user_table(self): 
        self.exec("""
    CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    user_name VARCHAR(100) NOT NULL UNIQUE,
    user_password VARCHAR(100) NOT NULL,
    date_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

""")
        logging.info("Created `users` table")

    def __create_buckets_table(self):
        self.exec("""
        CREATE TABLE IF NOT EXISTS buckets (
    bucket_id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL,
    bucket_name VARCHAR(200) NOT NULL,
    bucket_password VARCHAR(255) NOT NULL,
    date_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE ); 
""")
        logging.info("Created `buckets` table")

    def __create_objects_table(self):
        self.exec("""
        CREATE TABLE IF NOT EXISTS objects (
    object_id SERIAL PRIMARY KEY,
    object_uuid UUID NOT NULL UNIQUE,

    user_id INTEGER NOT NULL,
    bucket_id UUID NOT NULL,

    object_name VARCHAR(250) NOT NULL,
    object_size BIGINT NOT NULL,
    object_extension VARCHAR(50) NOT NULL,
    object_file_type VARCHAR(50) NOT NULL,

    date_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,

    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (bucket_id) REFERENCES buckets(bucket_id) ON DELETE CASCADE
    );
""")
        logging.info("Created `objects` table")

    def __verify_table(self, table_name):
        return self.exec(f"""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = '{table_name}'
    );
""")[0][0]

    def __check_exists_and_call(self, table_name):
        if not self.__verify_table(table_name): # Check if users table exists
            logging.warning(f"{table_name} was not found, creating {table_name}")
            if table_name == "users":
                self.__create_user_table()
            elif table_name == "buckets":
                self.__create_buckets_table()
            elif table_name == "objects":
                self.__create_objects_table()
        else:
            logging.info(f"✅ {table_name} table exist")



    def check_db_health(self):
        logging.info("Checking database health")
        self.__check_exists_and_call("users")
        self.__check_exists_and_call("buckets")
        self.__check_exists_and_call("objects")

    @property
    def users(self):
        return Table("users", self)
    @property
    def buckets(self):
        return Table("buckets", self)
    @property
    def objects(self):
        return Table("objects", self)
    
