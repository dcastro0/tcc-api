from flask import Blueprint, request, jsonify, current_app
from .models import User
from .extensions import db
import jwt
from datetime import datetime, timedelta, timezone, date
from functools import wraps

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
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]
        if not token:
            return jsonify({'message': 'Token está faltando!'}), 401
        try:
            secret = current_app.config.get('SECRET_KEY')
            data = jwt.decode(token, secret, algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                 return jsonify({'message': 'Usuário do token não encontrado.'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token expirou!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token é inválido!'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

@api.route('/register', methods=['POST'])
def register_user():
    data = request.get_json()
    if not all(k in data for k in ['nome', 'email', 'password']):
        return jsonify({'message': 'Faltando dados para registro.'}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Usuário com este email já existe.'}), 409
    
    new_user = User(nome=data['nome'], email=data['email'])
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
    
    secret = current_app.config.get('SECRET_KEY')
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.now(timezone.utc) + timedelta(hours=24)
    }, secret, algorithm="HS256")
    
    membro_desde_str = "Data Indisponível"
    if user.created_at:
        membro_desde_str = f"{meses_pt[user.created_at.month]} {user.created_at.year}"
    
    user_data = user.to_dict()
    user_data['token'] = token
    user_data['membroDesde'] = membro_desde_str
    user_data['avatar'] = None 
    user_data['totalMedicoes'] = 0

    return jsonify(user_data)

@api.route('/heartbeat', methods=['POST'])
@token_required
def heartbeat(current_user):
    data = request.get_json() or {}
    local_date_str = data.get('local_date')
    if not local_date_str:
        return jsonify({'message': 'local_date é obrigatório (YYYY-MM-DD).'}), 400
    try:
        local_date_obj = date.fromisoformat(local_date_str)
    except (ValueError, TypeError):
        return jsonify({'message': 'local_date inválido. Use YYYY-MM-DD.'}), 400

    last = current_user.last_active_date
    if last == local_date_obj:
        pass
    elif last == (local_date_obj - timedelta(days=1)):
        current_user.streak_count += 1
    else:
        current_user.streak_count = 1
    
    current_user.last_active_date = local_date_obj
    db.session.commit()
    
    return jsonify({
        'streak_count': current_user.streak_count,
        'last_active_date': current_user.last_active_date.isoformat()
    }), 200

@api.route('/ranking/<int:user_id>', methods=['GET'])
@token_required
def get_ranking(current_user, user_id):
    if current_user.id != user_id:
        return jsonify({'message': 'Não autorizado a ver este ranking.'}), 403

    # ATENÇÃO: A lógica abaixo ainda é ineficiente para muitos usuários.
    # O ideal é implementar ranking com Window Functions do SQL.
    # Esta versão é apenas para funcionar, mas deve ser otimizada.
    all_users_ranked = User.query.order_by(User.pontos.desc(), User.created_at.asc()).all()
    
    if not all_users_ranked:
        return jsonify({'message': 'Nenhum usuário encontrado.'}), 404

    ranked_list = []
    user_index = -1
    for i, u in enumerate(all_users_ranked):
        user_data = {
            'rank': i + 1,
            'nome': u.nome,
            'pontos': u.pontos,
            'id': u.id,
            'avatar': None
        }
        ranked_list.append(user_data)
        if u.id == user_id:
            user_index = i

    if user_index == -1:
        return jsonify({'message': 'Usuário da requisição não encontrado no ranking.'}), 404
    
    top_5 = ranked_list[:5]
    start = max(0, user_index - 2)
    end = min(len(ranked_list), user_index + 3)
    user_neighborhood = ranked_list[start:end]
    
    return jsonify({
        'top_5': top_5,
        'user_ranking': {
            'message': 'Sua posição e usuários próximos.',
            'data': user_neighborhood
        }
    })