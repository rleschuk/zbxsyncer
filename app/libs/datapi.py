import pandas as pd
from app import app

def dbexecute(query, **kwargs):
    return pd.read_sql_query(query, app.db.engine, **kwargs)
