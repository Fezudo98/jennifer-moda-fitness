from flask import Blueprint, render_template, request, jsonify

from app.extensions import db
from app.models import Cupom, Produto
from app.utils import token_requerido, pagina_login_requerida, registrar_log, parse_decimal_br, ValorInvalidoError

cupons_bp = Blueprint("cupons", __name__, url_prefix="/cupons")


@cupons_bp.route("")
@pagina_login_requerida
def pagina_lista():
    return render_template("cupons/lista.html")


@cupons_bp.route("/api", methods=["GET"])
@token_requerido
def api_listar_cupons():
    cupons = Cupom.query.order_by(Cupom.criado_em.desc()).all()
    return jsonify([c.to_dict() for c in cupons])


def _validar_payload_cupom(dados, cupom_id=None):
    codigo = (dados.get("codigo") or "").strip().upper()
    tipo = dados.get("tipo")
    aplicacao = dados.get("aplicacao") or "total"

    if not codigo:
        return None, "Informe o código do cupom."
    if tipo not in ("percentual", "fixo"):
        return None, "Tipo de cupom inválido."
    if aplicacao not in ("total", "produtos"):
        return None, "Aplicação do cupom inválida."

    try:
        valor = float(parse_decimal_br(dados.get("valor")))
    except (TypeError, ValueError, ValorInvalidoError):
        return None, "Informe um valor válido para o cupom."
    if valor <= 0:
        return None, "O valor do cupom deve ser maior que zero."
    if tipo == "percentual" and valor > 100:
        return None, "O percentual de desconto não pode ser maior que 100%."

    existente = Cupom.query.filter(db.func.upper(Cupom.codigo) == codigo, Cupom.id != cupom_id).first()
    if existente:
        return None, "Já existe um cupom com esse código."

    produto_ids = dados.get("produto_ids") or []
    if aplicacao == "produtos":
        if not produto_ids:
            return None, "Selecione ao menos um produto para cupons aplicados a produtos específicos."
        validos = {p.id for p in Produto.query.filter(Produto.id.in_(produto_ids)).all()}
        if len(validos) != len(set(produto_ids)):
            return None, "Um ou mais produtos selecionados não foram encontrados."

    return {
        "codigo": codigo,
        "tipo": tipo,
        "valor": valor,
        "aplicacao": aplicacao,
        "produto_ids": ",".join(str(i) for i in produto_ids) if aplicacao == "produtos" else None,
        "ativo": bool(dados.get("ativo", True)),
    }, None


@cupons_bp.route("/api", methods=["POST"])
@token_requerido
def api_criar_cupom():
    dados = request.get_json(silent=True) or {}
    validado, erro = _validar_payload_cupom(dados)
    if erro:
        return jsonify({"erro": erro}), 400

    cupom = Cupom(**validado)
    db.session.add(cupom)
    registrar_log("cupom_criado", f"Cupom '{cupom.codigo}' criado.")
    db.session.commit()
    return jsonify(cupom.to_dict()), 201


@cupons_bp.route("/api/<int:cupom_id>", methods=["PUT"])
@token_requerido
def api_atualizar_cupom(cupom_id):
    cupom = db.session.get(Cupom, cupom_id)
    if not cupom:
        return jsonify({"erro": "Cupom não encontrado."}), 404

    dados = request.get_json(silent=True) or {}
    validado, erro = _validar_payload_cupom(dados, cupom_id=cupom_id)
    if erro:
        return jsonify({"erro": erro}), 400

    for campo, valor in validado.items():
        setattr(cupom, campo, valor)

    registrar_log("cupom_editado", f"Cupom '{cupom.codigo}' editado.")
    db.session.commit()
    return jsonify(cupom.to_dict())


@cupons_bp.route("/api/<int:cupom_id>/status", methods=["PUT"])
@token_requerido
def api_alternar_status(cupom_id):
    cupom = db.session.get(Cupom, cupom_id)
    if not cupom:
        return jsonify({"erro": "Cupom não encontrado."}), 404

    cupom.ativo = not cupom.ativo
    registrar_log("cupom_status_alterado", f"Cupom '{cupom.codigo}' {'ativado' if cupom.ativo else 'desativado'}.")
    db.session.commit()
    return jsonify(cupom.to_dict())
