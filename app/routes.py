from flask import Blueprint, request, jsonify, current_app
from .models import User
from .extensions import db
import jwt
from datetime import datetime, timedelta, timezone, date
from functools import wraps
from .models import User, Achievement, UserAchievement, Measurement
from sqlalchemy.orm import joinedload
from dateutil import parser

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
    
    new_user = User()
    new_user.nome = data['nome']
    new_user.email = data['email']
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
    

    unlocked_streak_3 = update_achievement_progress(current_user, 'CONSISTENCIA_I', absolute_value=current_user.streak_count)
    unlocked_streak_7 = update_achievement_progress(current_user, 'GUARDAO_DA_SAUDE', absolute_value=current_user.streak_count)
    
    unlocked_now = [ach for ach in [unlocked_streak_3, unlocked_streak_7] if ach]

    return jsonify({
        'streak_count': current_user.streak_count,
        'last_active_date': current_user.last_active_date.isoformat(),
        'unlocked_achievements': unlocked_now
    }), 200

@api.route('/ranking/<int:user_id>', methods=['GET'])
@token_required
def get_ranking(current_user, user_id):
    if current_user.id != user_id:
        return jsonify({'message': 'Não autorizado a ver este ranking.'}), 403

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
@api.route('/achievements', methods=['GET'])
@token_required
def get_user_achievements(current_user):
    all_achievements = Achievement.query.all()
    user_progress = UserAchievement.query.filter_by(user_id=current_user.id).all()

    progress_map = {ua.achievement_id: ua for ua in user_progress}

    result = []
    for ach in all_achievements:
        user_ach = progress_map.get(ach.id)
        if user_ach:
            result.append(user_ach.to_dict(ach.to_dict()))
        else:
            ach_data = ach.to_dict()
            result.append({
                'user_id': current_user.id,
                'achievement_id': ach.id,
                'progress': 0,
                'unlocked': False,
                'unlocked_at': None,
                **ach_data
            })

    result.sort(key=lambda x: x['id']) 

    return jsonify(result), 200

def update_achievement_progress(user, achievement_code, progress_increment=1, absolute_value=None):
    achievement = Achievement.query.filter_by(code=achievement_code).first()
    if not achievement:
        current_app.logger.warning(f"Tentativa de atualizar conquista inexistente: {achievement_code}")
        return None

    user_ach = UserAchievement.query.filter_by(user_id=user.id, achievement_id=achievement.id).first()

    if not user_ach:
        user_ach = UserAchievement()
        user_ach.user_id = user.id
        user_ach.achievement_id = achievement.id
        user_ach.progress = 0
        db.session.add(user_ach)
        try:
            db.session.flush()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao adicionar UserAchievement inicial: {e}")
            return None


    if user_ach.unlocked_at:
        return None

    if absolute_value is not None:
         user_ach.progress = absolute_value
    else:
         user_ach.progress += progress_increment

    unlocked_now = False
    if achievement.goal is not None and user_ach.progress >= achievement.goal:
        user_ach.unlocked_at = datetime.now(timezone.utc)
        user_ach.progress = achievement.goal
        user.pontos += achievement.points_reward
        unlocked_now = True

    try:
       db.session.commit()
       if unlocked_now:
           return user_ach.to_dict(achievement.to_dict())
    except Exception as e:
       db.session.rollback()
       current_app.logger.error(f"Erro ao commitar atualização da conquista {achievement_code}: {e}")

    return None

@api.route('/measurements/sync', methods=['POST'])
@token_required
def sync_measurements(current_user):
    data = request.get_json()
    
    if not isinstance(data, list):
        return jsonify({'message': 'Entrada inválida. Esperava uma lista de medições.'}), 400

    new_measurements_added = 0
    
    # Usamos um set para checar IDs locais já sincronizados e evitar duplicidade
    # (Esta é uma checagem simples, idealmente você usaria o local_id)
    
    for item in data:
        try:
            # Converte a data string (ISO 8601) do frontend para um objeto datetime
            measurement_date = parser.isoparse(item.get('date'))
            value = float(item.get('value'))
            note = item.get('note')
            
            # (Opcional) Você pode adicionar 'local_id' ao seu JSON
            # e verificar se já existe antes de adicionar

            m = Measurement()
            m.user_id = current_user.id
            m.value = value
            m.date = measurement_date
            m.note = note
            db.session.add(m)
            new_measurements_added += 1

        except Exception as e:
            current_app.logger.error(f"Erro ao processar medição: {e}. Item: {item}")
            # Pula este item e continua
            pass

    if new_measurements_added > 0:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao salvar medições no banco: {e}")
            return jsonify({'message': 'Erro interno ao salvar medições.'}), 500

    # --- ATUALIZAÇÃO DAS CONQUISTAS ---
    # Após salvar, recalcula o progresso das conquistas de medição
    try:
        total_measurements = Measurement.query.filter_by(user_id=current_user.id).count()
        
        # Lista de códigos de conquistas de medição (do seu JSON)
        measurement_achievements = [
            'PRIMEIRA_GOTA', 
            'MARATONISTA_I', 
            'MARATONISTA_II', 
            'MARATONISTA_III', 
            'MESTRE_GLICEMICO'
        ]
        
        unlocked_now = []
        for code in measurement_achievements:
            unlocked = update_achievement_progress(current_user, code, absolute_value=total_measurements)
            if unlocked:
                unlocked_now.append(unlocked)
        
        # 'db.session.commit()' já é chamado dentro de update_achievement_progress
        
        return jsonify({
            'message': f'{new_measurements_added} medições sincronizadas com sucesso.',
            'total_measurements_on_server': total_measurements,
            'unlocked_achievements': unlocked_now
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao atualizar conquistas: {e}")
        return jsonify({'message': 'Medições salvas, mas erro ao atualizar conquistas.'}), 500

    return jsonify({'message': 'Nenhuma nova medição válida recebida.'}), 200