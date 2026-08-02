from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for

from app.extensions import db, limiter
from app.models import Usuario
from app.utils import gerar_token, registrar_log

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET"])
def pagina_login():
    if session.get("usuario_id"):
        return redirect(url_for("home.pagina_home"))
    return render_template("auth/login.html", proximo=request.args.get("proximo") or "")


@auth_bp.route("/api/login", methods=["POST"])
@limiter.limit("8 per minute")
def api_login():
    dados = request.get_json(silent=True) or {}
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""

    if not email or not senha:
        return jsonify({"erro": "Informe e-mail e senha."}), 400

    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario or not usuario.checar_senha(senha):
        return jsonify({"erro": "E-mail ou senha incorretos."}), 401

    if not usuario.ativo:
        return jsonify({"erro": "Este usuário está desativado. Fale com um administrador."}), 403

    token = gerar_token(usuario)

    session["usuario_id"] = usuario.id
    session["nome"] = usuario.nome
    session["papel"] = usuario.papel
    session.permanent = True

    registrar_log("login", f"{usuario.nome} entrou no sistema.", usuario_id=usuario.id)
    db.session.commit()

    return jsonify({"token": token, "usuario": usuario.to_dict()})


@auth_bp.route("/logout")
def pagina_logout():
    if session.get("usuario_id"):
        registrar_log("logout", f"{session.get('nome')} saiu do sistema.", usuario_id=session.get("usuario_id"))
        db.session.commit()
    session.clear()
    return redirect(url_for("auth.pagina_login"))
