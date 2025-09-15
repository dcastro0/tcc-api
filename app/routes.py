from flask import Blueprint, request, jsonify
from .models import User
from .extensions import db
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
import os
from datetime import timedelta as dt_timedelta

api = Blueprint('api', __name__)

meses_pt = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"
}

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            parts = request.headers['Authorization'].split(" ")
            if len(parts) == 2:
                token = parts[1]
        if not token:
            return jsonify({'message': 'Token está faltando!'}), 401
        try:
            data = jwt.decode(token, os.environ.get('SECRET_KEY'), algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
        except Exception as e:
            return jsonify({'message': 'Token é inválido ou expirou!', 'error': str(e)}), 401
        return f(current_user, *args, **kwargs)
    return decorated

@api.route('/register', methods=['POST'])
def register_user():
    data = request.get_json()
    if not data or not 'email' in data or not 'password' in data or not 'nome' in data:
        return jsonify({'message': 'Faltando dados para registro.'}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Usuário com este email já existe.'}), 409
    new_user = User(
        nome=data['nome'],
        email=data['email'],
        pontos=data.get('pontos', 0)
    )
    new_user.set_password(data['password'])
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'Usuário criado com sucesso!'}), 201

@api.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not 'email' in data or not 'password' in data:
        return jsonify({'message': 'Não foi possível verificar'}), 401
    user = User.query.filter_by(email=data['email']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({'message': 'Credenciais inválidas!'}), 401
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.now(timezone.utc) + timedelta(hours=24)
    }, os.environ.get('SECRET_KEY'), algorithm="HS256")
    membro_desde_str = f"{meses_pt[user.created_at.month]} {user.created_at.year}"
    user_data = {
        'id': user.id,
        'token': token,
        'nome': user.nome,
        'email': user.email,
        'pontos': user.pontos,
        'streak_count': user.streak_count,
        'last_active_date': user.last_active_date.isoformat() if user.last_active_date else None,
        'membroDesde': membro_desde_str,
        'avatar': None,
        'totalMedicoes': 0
    }
    return jsonify(user_data)

@api.route('/heartbeat', methods=['POST'])
@token_required
def heartbeat(current_user):
    data = request.get_json() or {}
    local_date_str = data.get('local_date')
    if not local_date_str:
        return jsonify({'message': 'local_date é obrigatório (YYYY-MM-DD).'}), 400
    try:
        local_date = datetime.strptime(local_date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({'message': 'local_date inválido. Use YYYY-MM-DD.'}), 400
    try:
        with db.session.begin():
            user = User.query.get(current_user.id)
            last = user.last_active_date
            if last == local_date:
                pass
            elif last == (local_date - dt_timedelta(days=1)):
                user.streak_count = (user.streak_count or 0) + 1
            else:
                user.streak_count = 1
            user.last_active_date = local_date
            db.session.add(user)
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Erro ao atualizar heartbeat', 'error': str(e)}), 500
    return jsonify({
        'streak_count': user.streak_count,
        'last_active_date': user.last_active_date.isoformat() if user.last_active_date else None
    }), 200

@api.route('/ranking/<int:user_id>', methods=['GET'])
@token_required
def get_ranking(current_user, user_id):
    if current_user.id != user_id:
        return jsonify({'message': 'Não autorizado a ver este ranking.'}), 403
    all_users_ranked = User.query.order_by(User.pontos.desc(), User.created_at.asc()).all()
    if not all_users_ranked:
        return jsonify({'message': 'Nenhum usuário encontrado.'}), 404
    ranked_list = [{
        'rank': i + 1,
        'nome': u.nome,
        'pontos': u.pontos,
        'id': str(u.id),
        'avatar': None
    } for i, u in enumerate(all_users_ranked)]
    user_index = -1
    for i, user_data in enumerate(ranked_list):
        if user_data['id'] == str(user_id):
            user_index = i
            break
    if user_index == -1:
        return jsonify({'message': 'Usuário da requisição não encontrado no ranking.'}), 404
    top_5 = ranked_list[:5]
    start = max(0, user_index - 2)
    end = min(len(ranked_list), user_index + 3)
    user_neighborhood = ranked_list[start:end]
    user_in_top_5 = user_index < 5
    response = {
        'top_5': top_5,
        'user_ranking': {
            'message': 'Você está no Top 5!' if user_in_top_5 else 'Sua posição e usuários próximos.',
            'data': user_neighborhood
        }
    }
    return jsonify(response)
