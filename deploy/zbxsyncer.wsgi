PATH = '/home/roman/Scripts/zbxsyncer'

""" /etc/httpd/conf.d/zbxsyncer.conf

#WSGIRestrictStdout Off
#WSGISocketPrefix /var/run/wsgi
Listen 8080
NameVirtualHost *:8080
<VirtualHost *:8080>
    LogLevel info
    ServerName localhost
    WSGIDaemonProcess zbxsyncer threads=5 python-path=/home/roman/Scripts/zbxsyncer
    WSGIScriptAlias / /home/roman/Scripts/zbxsyncer/zbxsyncer.wsgi process-group=zbxsyncer application-group=%{GLOBAL}
    #WSGIPythonPath /home/roman/Scripts/zbxsyncer
    #SetEnv NLS_LANG ".UTF8"
    <Directory /home/roman/Scripts/zbxsyncer>
        <Files "zbxsyncer.wsgi">
            Require all granted
        </Files>
        WSGIScriptReloading On
        Order deny,allow
        Allow from all
    </Directory>
</VirtualHost>

"""

#import sys, os
#sys.path.insert(0, PATH)
#from config import ENV
#for env in ENV: os.environ[env] = ENV[env]
#os.environ['NLS_LANG'] = '.UTF8'

from zbxsyncer import app as application
