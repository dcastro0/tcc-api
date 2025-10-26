from flask import Flask
from .extensions import db, migrate 
from .routes import api
from config import Config
import os
from flask_cors import CORS 

# --- Imports Adicionados para o Seed ---
import json
import click
from .models import Achievement # Garanta que Achievement está em models.py
# --- Fim dos Imports Adicionados ---


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    CORS(app) 

    # Inicializa as extensões
    db.init_app(app)
    migrate.init_app(app, db) # Sua linha de migrate está mantida

    # Registra o Blueprint
    app.register_blueprint(api, url_prefix='/api')
    
    # --- INÍCIO DO CÓDIGO DE SEED ADICIONADO ---
    # Registra o comando CLI customizado dentro da factory
    @app.cli.command("seed-db")
    def seed_db_command():
        """Popula o banco de dados com conquistas iniciais a partir de um JSON."""
        
        # Constrói o caminho para a pasta 'seeds' que está na raiz do projeto
        # (um nível acima deste arquivo __init__.py)
        basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        json_path = os.path.join(basedir, 'seeds', 'achievements.json')

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                achievements_data = data.get('achievements', [])
        except FileNotFoundError:
            print(f"Erro: Arquivo '{json_path}' não encontrado.")
            print("Certifique-se de criar a pasta 'seeds' e o arquivo 'achievements.json' na raiz do projeto (no mesmo nível de 'app/').")
            return
        except json.JSONDecodeError:
            print(f"Erro: Falha ao decodificar 'seeds/achievements.json'. Verifique o formato.")
            return

        if not achievements_data:
            print("Nenhuma conquista encontrada no arquivo JSON.")
            return

        print("Semeando conquistas a partir do JSON...")
        added_count = 0
        for data in achievements_data:
            required_keys = ['code', 'title', 'description', 'goal', 'points_reward']
            if not all(key in data for key in required_keys):
                print(f"Ignorando item inválido (faltam chaves): {data.get('code', 'SEM_CODIGO')}")
                continue

            ach = Achievement.query.filter_by(code=data['code']).first()
            if not ach:
                ach = Achievement()
                ach.code = data['code']
                ach.description = data['description']
                ach.icon = data.get('icon')
                ach.goal = data['goal']
                ach.points_reward = data['points_reward']
                # Atribui o título ao atributo correto do modelo, com fallback para 'name' ou criação dinâmica
                if hasattr(ach, 'title'):
                    ach.title = data['title']
                elif hasattr(ach, 'name'):
                    setattr(ach, 'name', data['title'])
                else:
                    setattr(ach, 'title', data['title'])
                db.session.add(ach)
                print(f"Adicionando: {getattr(ach, 'title', getattr(ach, 'name', data['title']))}")
                added_count += 1
            else:
                print(f"Ignorando (já existe): {data['title']}")
        
        if added_count > 0:
            db.session.commit()
            print(f"Conquistas semeadas com sucesso ({added_count} novas).")
        else:
            print("Nenhuma nova conquista para semear. Banco já está atualizado.")
    # --- FIM DO CÓDIGO DE SEED ADICIONADO ---
    
    return app