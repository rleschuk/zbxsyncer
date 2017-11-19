# -*- coding: utf-8 -*-

from sqlalchemy import create_engine
import pandas as pd
from config import *

class Datapi(object):
    def __init__(self):
        self.engine = create_engine('oracle://{0}:{1}@{2}:{3}/{4}'.format(
            ORA_USER, ORA_PASS, ORA_HOST, ORA_PORT, ORA_SID
        ), encoding='utf8', convert_unicode=True)

    def GetDataViaOracle(self, query, chunksize=None):
        if chunksize:
            data = pd.read_sql_query(query, self.engine, chunksize=chunksize)
        else:
            data = pd.read_sql_query(query, self.engine)
        return data

if __name__ == '__main__':
    pass
