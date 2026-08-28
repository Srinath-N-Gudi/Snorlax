import os
import psycopg
class BaseDB: 
    def __init__(self, host, port, dbname, user, password): 
        self.conn = None
        self.cur = None

        self.host = host 
        self.port = port  
        self.dbname = dbname 
        self.user = user 
        self.password = password
    def connect(self):
        conn = psycopg.connect(
        host=self.host,
        port=self.port,
        dbname=self.dbname,
        user=self.user,
        password=self.password 
        )
        self.conn = conn 
        self.cur = conn.cursor()
        return True

    def exec(self, command="SELECT current_database();", params=None):
        try:
            self.cur.execute(command, params)
            self.conn.commit()

            if self.cur.description:
                return self.cur.fetchall()

        except Exception:
            self.conn.rollback()
            raise




