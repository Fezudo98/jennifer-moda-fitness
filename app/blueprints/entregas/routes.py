from datetime import datetime

from flask import Blueprint, render_template, request, jsonify
from sqlalchemy import func

from app.extensions import db
from app.models import Venda
from app.utils import token_requerido, pagina_login_requerida, registrar_log

entregas_bp = Blueprint("entregas", __name__, url_prefix="/entregas")

STATUS_VALIDOS = ["pendente", "saiu", "entregue"]


@entregas_bp.route("")
@pagina_login_requerida
def pagina_lista():
    return render_template("entregas/lista.html")


@entregas_bp.route("/api", methods=["GET"])
@token_requerido
def api_listar_entregas():
    status = request.args.get("status")
    query = Venda.query.filter_by(entrega_tipo="motoboy")
    if status:
        query = query.filter_by(entrega_status=status)
    vendas = query.order_by(Venda.criado_em.desc()).all()
    return jsonify([v.to_dict(detalhado=False) for v in vendas])


@entregas_bp.route("/api/<int:venda_id>/status", methods=["PUT"])
@token_requerido
def api_atualizar_status(venda_id):
    venda = db.session.get(Venda, venda_id)
    if not venda or venda.entrega_tipo != "motoboy":
        return jsonify({"erro": "Entrega não encontrada."}), 404

    dados = request.get_json(silent=True) or {}
    status = dados.get("status")
    if status not in STATUS_VALIDOS:
        return jsonify({"erro": "Status inválido."}), 400

    venda.entrega_status = status
    registrar_log("entrega_status_atualizado", f"Entrega da venda {venda.numero} atualizada para '{status}'.")
    db.session.commit()
    return jsonify(venda.to_dict(detalhado=False))


@entregas_bp.route("/api/relatorio", methods=["GET"])
@token_requerido
def api_relatorio():
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    query = Venda.query.filter_by(entrega_tipo="motoboy")
    if data_inicio:
        query = query.filter(Venda.criado_em >= datetime.fromisoformat(data_inicio))
    if data_fim:
        query = query.filter(Venda.criado_em <= datetime.fromisoformat(data_fim + "T23:59:59"))

    vendas = query.all()
    return jsonify({
        "quantidade": len(vendas),
        "total_taxas": float(sum((v.entrega_taxa for v in vendas), 0)),
    })
