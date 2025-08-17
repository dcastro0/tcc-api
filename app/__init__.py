from flask import Flask
from .extensions import db
from .routes import api
from config import Config
import os

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    app.register_blueprint(api, url_prefix='/api')
    
    return app