#!/usr/bin/env python

import os
from dotenv import load_dotenv
load_dotenv()

config_name = os.getenv('FLASK_CONFIG') or 'default'

from app import create_app
app = create_app(config_name)
