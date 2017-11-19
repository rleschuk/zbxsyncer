# -*- coding: utf-8 -*-

def is_int(d):
    try:
        d = int(d)
        return True
    except:
        return False
    
def utf8(string):
    try:
        return unicode(string)
    except UnicodeDecodeError:
        string = str(string).decode('utf-8')
        return unicode(string)

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
    if type(d) == type(u''):
        try: d = tonumber(d)
        except: pass
    return d

def tonumber(d):
    if '.' in d: return float(d)
    else:        return int(d)

def getvalue(d, k):
    try:
        return d[k]
    except:
        return None
