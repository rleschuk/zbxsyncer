from flask import jsonify, request, render_template, redirect, url_for
from . import main

@main.errorhandler(404)
def not_found(error):
    return redirect(url_for('main.root'))
