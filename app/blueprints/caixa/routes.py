from datetime import datetime

from flask import Blueprint, render_template, request, jsonify
from sqlalchemy import func

from app.extensions import db
from app.models import MovimentacaoCaixa
from app.utils import token_requerido, admin_requerido, pagina_admin_requerida, registrar_log, parse_decimal_br, ValorInvalidoError

caixa_bp = Blueprint("caixa", __name__, url_prefix="/caixa")

MOTIVOS_MANUAIS = {"sangria", "despesa", "ajuste"}


def calcular_saldo():
    entradas = db.session.query(func.coalesce(func.sum(MovimentacaoCaixa.valor), 0)).filter_by(tipo="entrada").scalar()
    saidas = db.session.query(func.coalesce(func.sum(MovimentacaoCaixa.valor), 0)).filter_by(tipo="saida").scalar()
    return float(entradas) - float(saidas)


@caixa_bp.route("")
@pagina_admin_requerida
def pagina_lista():
    return render_template("caixa/lista.html")


@caixa_bp.route("/api", methods=["GET"])
@token_requerido
@admin_requerido
def api_listar_movimentacoes():
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    query = MovimentacaoCaixa.query
    if data_inicio:
        query = query.filter(MovimentacaoCaixa.criado_em >= datetime.fromisoformat(data_inicio))
    if data_fim:
        query = query.filter(MovimentacaoCaixa.criado_em <= datetime.fromisoformat(data_fim + "T23:59:59"))

    movimentacoes = query.order_by(MovimentacaoCaixa.criado_em.desc()).limit(500).all()
    return jsonify({
        "saldo": calcular_saldo(),
        "movimentacoes": [m.to_dict() for m in movimentacoes],
    })


@caixa_bp.route("/api/movimentacao", methods=["POST"])
@token_requerido
@admin_requerido
def api_criar_movimentacao():
    dados = request.get_json(silent=True) or {}
    tipo = dados.get("tipo")
    motivo = dados.get("motivo")
    observacao = (dados.get("observacao") or "").strip()

    if tipo not in ("entrada", "saida"):
        return jsonify({"erro": "Tipo de movimentação inválido."}), 400
    if motivo not in MOTIVOS_MANUAIS:
        return jsonify({"erro": "Motivo inválido."}), 400
    if not observacao:
        return jsonify({"erro": "A observação é obrigatória para lançamentos manuais de caixa."}), 400

    try:
        valor = float(parse_decimal_br(dados.get("valor")))
    except (TypeError, ValueError, ValorInvalidoError):
        return jsonify({"erro": "Informe um valor válido."}), 400
    if valor <= 0:
        return jsonify({"erro": "O valor deve ser maior que zero."}), 400

    if tipo == "saida" and valor > calcular_saldo():
        return jsonify({"erro": "Saldo insuficiente em caixa para esta saída."}), 400

    movimentacao = MovimentacaoCaixa(
        tipo=tipo, valor=valor, motivo=motivo, observacao=observacao, usuario_id=request.usuario_atual.id
    )
    db.session.add(movimentacao)
    registrar_log("caixa_ajuste_manual", f"{tipo.capitalize()} de R$ {valor} ({motivo}): {observacao}")
    db.session.commit()
    return jsonify(movimentacao.to_dict()), 201
