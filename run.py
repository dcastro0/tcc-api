from app import create_app, db
from app.models import User, Achievement # Adicionado Achievement
from flask_migrate import Migrate

app = create_app()
migrate = Migrate(app, db)

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Achievement': Achievement}

