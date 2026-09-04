from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for

from app.extensions import db, limiter
from app.models import Usuario
from app.utils import gerar_token, registrar_log

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET"])
def pagina_login():
    if request.args.get("expirada") == "1":
        # O token de API (usado nas chamadas JS, 24h -- JWT_EXPIRATION em
        # config.py) expira bem antes do cookie de sessão do navegador
        # (semanas, padrão do Flask). Sem isso, quem chegava aqui com token
        # expirado mas cookie ainda "válido" era jogado direto de volta pro
        # /home (pelo `elif` abaixo) -- que tentava usar o token velho de
        # novo, tomava 401 de novo, e voltava pra cá: um vaivém instantâneo
        # e confuso em vez de simplesmente pedir login de novo. Limpa a
        # sessão pra garantir que a tela de login realmente apareça.
        session.clear()
    elif session.get("usuario_id"):
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
        # Registra tentativas de login falhas (sem usuário associado, já que
        # não há como saber quem realmente tentou) — ajuda a identificar
        # tentativas de força bruta ou de adivinhação de senha no log de
        # atividade, que hoje só mostra logins bem-sucedidos.
        registrar_log("login_falhou", f"Tentativa de login falhou para o e-mail '{email}'.")
        db.session.commit()
        return jsonify({"erro": "E-mail ou senha incorretos."}), 401

    if not usuario.ativo:
        registrar_log("login_bloqueado", f"Tentativa de login de usuário desativado: {usuario.nome}.", usuario_id=usuario.id)
        db.session.commit()
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
