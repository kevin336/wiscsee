import os
import time
import sqlite3

class SqliteDB(object):
    def __init__(self, db_path, use_existing_db=False, journal_mode='DELETE'):
        self.db_path = db_path
        self.use_existing_db = use_existing_db
        self.journal_mode = journal_mode

        self.conn = None

    def open(self):
        if self.use_existing_db is False and \
                os.path.exists(self.db_path) is True:
            os.remove(self.db_path)

        self.conn = sqlite3.connect(self.db_path)


        print 'Journal mode', self._get_journal_mode()

        if self.use_existing_db is False:
            self._set_journal_mode()
            print 'After setting journal mode:', self._get_journal_mode()
            schema_text = """
                create table benchtable (
                    name        text primary key,
                    description text
                );
                """
            self.conn.executescript(schema_text)

    def _set_journal_mode(self):
        cmd = "PRAGMA journal_mode={}".format(self.journal_mode.upper())
        print cmd
        ret = self.conn.execute(cmd)
        mode = ret.fetchone()
        print mode
        assert mode[0] == self.journal_mode.lower()

    def _get_journal_mode(self):
        ret = self.conn.execute("PRAGMA journal_mode")
        mode = ret.fetchone()

        return mode[0]

    def initialize(self):
        pass

    def close(self):
        self.conn.close()
        self.conf = None

    def commit(self):
        self.conn.commit()

    def insert(self, key, value):
        self.conn.execute("""
        insert into benchtable (name, description)
        values ('{k}', '{v}')
        """.format(k=key, v=value))

    def update(self, key, value):
        self.conn.execute("""
        update benchtable set description = '{v}' where name = '{k}'
        """.format(k=key, v=value))

    def select_all(self):
        cursor = self.conn.cursor()

        cursor.execute("select * from benchtable")

        table = [row for row in cursor.fetchall()]
        return table

    def get_value(self, key):
        cursor = self.conn.cursor()

        cursor.execute("select name,description from benchtable where name = '{k}'"\
            .format(k=key))

        row = cursor.fetchone()
        if row is None:
            return None
        else:
            k, v = row
            return v


