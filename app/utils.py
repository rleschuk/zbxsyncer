import datetime, json, re
from app import app

def json_converter(obj):
    if isinstance(obj, datetime.datetime):
        return obj.__str__()
    if isinstance(obj, datetime.timedelta):
        return obj.__str__()
    return obj

def json_loads(obj):
    try: return json.loads(obj)
    except Exception: return obj

def format_data(d):
    #print type(d)
    if type(d) == type([]):
        for i, e in enumerate(d):
            try: d[i] = format_data(e)
            except: pass
    if type(d) == type({}):
        for k in d.keys():
            try: d[k] = format_data(d[k])
            except: pass
    if type(d) == type(''):
        try: d = tonumber(d)
        except: pass
    return d

def is_int(d):
    try:
        d = int(d)
        return True
    except:
        return False
