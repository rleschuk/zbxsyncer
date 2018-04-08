import pandas as pd
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
from app import db

def dbexecute(query, app, **kwargs):
    with app.app_context():
        return pd.read_sql_query(query, db.engine, **kwargs)
