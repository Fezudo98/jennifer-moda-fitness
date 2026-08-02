import re

from flask import Blueprint, render_template, request, jsonify

from app.extensions import db
from app.models import Usuario
from app.utils import token_requerido, admin_requerido, pagina_admin_requerida, registrar_log

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@usuarios_bp.route("")
@pagina_admin_requerida
def pagina_lista():
    return render_template("usuarios/lista.html")


@usuarios_bp.route("/api", methods=["GET"])
@token_requerido
@admin_requerido
def api_listar_usuarios():
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    return jsonify([u.to_dict() for u in usuarios])


@usuarios_bp.route("/api", methods=["POST"])
@token_requerido
@admin_requerido
def api_criar_usuario():
    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""
    papel = dados.get("papel") or "vendedor"

    if not nome:
        return jsonify({"erro": "Informe o nome do usuário."}), 400
    if not EMAIL_REGEX.match(email):
        return jsonify({"erro": "Informe um e-mail válido."}), 400
    if len(senha) < 6:
        return jsonify({"erro": "A senha deve ter ao menos 6 caracteres."}), 400
    if papel not in ("admin", "vendedor"):
        return jsonify({"erro": "Papel inválido."}), 400
    if Usuario.query.filter_by(email=email).first():
        return jsonify({"erro": "Já existe um usuário com esse e-mail."}), 400

    usuario = Usuario(nome=nome, email=email, papel=papel, ativo=True)
    usuario.set_senha(senha)
    db.session.add(usuario)
    registrar_log("usuario_criado", f"Usuário '{nome}' ({papel}) criado.")
    db.session.commit()
    return jsonify(usuario.to_dict()), 201


@usuarios_bp.route("/api/<int:usuario_id>", methods=["PUT"])
@token_requerido
@admin_requerido
def api_atualizar_usuario(usuario_id):
    usuario = db.session.get(Usuario, usuario_id)
    if not usuario:
        return jsonify({"erro": "Usuário não encontrado."}), 404

    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    email = (dados.get("email") or "").strip().lower()
    papel = dados.get("papel") or usuario.papel

    if not nome:
        return jsonify({"erro": "Informe o nome do usuário."}), 400
    if not EMAIL_REGEX.match(email):
        return jsonify({"erro": "Informe um e-mail válido."}), 400
    if papel not in ("admin", "vendedor"):
        return jsonify({"erro": "Papel inválido."}), 400

    existente = Usuario.query.filter(Usuario.email == email, Usuario.id != usuario_id).first()
    if existente:
        return jsonify({"erro": "Já existe um usuário com esse e-mail."}), 400

    if usuario.papel == "admin" and papel != "admin":
        admins_restantes = Usuario.query.filter(Usuario.papel == "admin", Usuario.id != usuario_id, Usuario.ativo == True).count()
        if admins_restantes == 0:
            return jsonify({"erro": "Não é possível remover o último administrador ativo do sistema."}), 400

    usuario.nome = nome
    usuario.email = email
    usuario.papel = papel

    registrar_log("usuario_editado", f"Usuário '{nome}' (#{usuario.id}) editado.")
    db.session.commit()
    return jsonify(usuario.to_dict())


@usuarios_bp.route("/api/<int:usuario_id>/status", methods=["PUT"])
@token_requerido
@admin_requerido
def api_alternar_status(usuario_id):
    usuario = db.session.get(Usuario, usuario_id)
    if not usuario:
        return jsonify({"erro": "Usuário não encontrado."}), 404

    if usuario.id == request.usuario_atual.id:
        return jsonify({"erro": "Você não pode desativar seu próprio usuário."}), 400

    if usuario.papel == "admin" and usuario.ativo:
        admins_restantes = Usuario.query.filter(Usuario.papel == "admin", Usuario.id != usuario_id, Usuario.ativo == True).count()
        if admins_restantes == 0:
            return jsonify({"erro": "Não é possível desativar o último administrador ativo."}), 400

    usuario.ativo = not usuario.ativo
    registrar_log("usuario_status_alterado", f"Usuário '{usuario.nome}' {'ativado' if usuario.ativo else 'desativado'}.")
    db.session.commit()
    return jsonify(usuario.to_dict())


@usuarios_bp.route("/api/<int:usuario_id>/senha", methods=["PUT"])
@token_requerido
@admin_requerido
def api_redefinir_senha(usuario_id):
    usuario = db.session.get(Usuario, usuario_id)
    if not usuario:
        return jsonify({"erro": "Usuário não encontrado."}), 404

    dados = request.get_json(silent=True) or {}
    senha = dados.get("senha") or ""
    if len(senha) < 6:
        return jsonify({"erro": "A senha deve ter ao menos 6 caracteres."}), 400

    usuario.set_senha(senha)
    registrar_log("usuario_senha_redefinida", f"Senha do usuário '{usuario.nome}' redefinida por um administrador.")
    db.session.commit()
    return jsonify({"ok": True})
