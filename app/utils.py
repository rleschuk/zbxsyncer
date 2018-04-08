import datetime, json, re


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
    if isinstance(d, list):
        for i, e in enumerate(d):
            try: d[i] = format_data(e)
            except: pass
    elif isinstance(d, dict):
        for k in d.keys():
            try: d[k] = format_data(d[k])
            except: pass
    elif isinstance(d, str):
        try: d = tonumber(d)
        except: pass
    elif isinstance(d, datetime.datetime):
        d = d.__str__()
    elif isinstance(d, datetime.timedelta):
        d = d.__str__()
    return d


def tonumber(d):
    if '.' in d: return float(d)
    else: return int(d)
