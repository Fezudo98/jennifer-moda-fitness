from datetime import datetime, date, timedelta

from flask import Blueprint, render_template, request, jsonify
from sqlalchemy import func

from app.extensions import db
from app.models import Venda, VendaItem, VendaPagamento, Usuario
from app.utils import token_requerido, admin_requerido, pagina_admin_requerida

relatorios_bp = Blueprint("relatorios", __name__, url_prefix="/relatorios")


@relatorios_bp.route("")
@pagina_admin_requerida
def pagina_dashboard():
    return render_template("relatorios/dashboard.html")


def _periodo():
    hoje = date.today()
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    inicio = datetime.fromisoformat(data_inicio) if data_inicio else datetime.combine(hoje - timedelta(days=29), datetime.min.time())
    fim = datetime.fromisoformat(data_fim + "T23:59:59") if data_fim else datetime.combine(hoje, datetime.max.time())
    return inicio, fim


@relatorios_bp.route("/api/dashboard", methods=["GET"])
@token_requerido
@admin_requerido
def api_dashboard():
    inicio, fim = _periodo()

    vendas_validas = Venda.query.filter(
        Venda.criado_em >= inicio, Venda.criado_em <= fim, Venda.reembolsada == False
    )

    num_vendas = vendas_validas.count()
    receita_total = float(db.session.query(func.coalesce(func.sum(Venda.total), 0)).filter(
        Venda.criado_em >= inicio, Venda.criado_em <= fim, Venda.reembolsada == False
    ).scalar())
    total_descontos = float(db.session.query(func.coalesce(func.sum(Venda.desconto), 0)).filter(
        Venda.criado_em >= inicio, Venda.criado_em <= fim, Venda.reembolsada == False
    ).scalar())
    ticket_medio = receita_total / num_vendas if num_vendas else 0.0

    itens = (
        VendaItem.query.join(Venda)
        .filter(Venda.criado_em >= inicio, Venda.criado_em <= fim, Venda.reembolsada == False)
        .all()
    )
    lucro_bruto = sum(
        float(i.subtotal) - float(i.preco_custo_unit) * i.quantidade for i in itens
    )

    vendas_por_dia = (
        db.session.query(func.date(Venda.criado_em), func.coalesce(func.sum(Venda.total), 0))
        .filter(Venda.criado_em >= inicio, Venda.criado_em <= fim, Venda.reembolsada == False)
        .group_by(func.date(Venda.criado_em))
        .order_by(func.date(Venda.criado_em))
        .all()
    )

    pagamentos_por_forma = (
        db.session.query(VendaPagamento.forma, func.coalesce(func.sum(VendaPagamento.valor), 0))
        .join(Venda)
        .filter(Venda.criado_em >= inicio, Venda.criado_em <= fim, Venda.reembolsada == False)
        .group_by(VendaPagamento.forma)
        .all()
    )

    ranking_produtos = (
        db.session.query(VendaItem.produto_nome, func.sum(VendaItem.quantidade), func.sum(VendaItem.subtotal))
        .join(Venda)
        .filter(Venda.criado_em >= inicio, Venda.criado_em <= fim, Venda.reembolsada == False)
        .group_by(VendaItem.produto_nome)
        .order_by(func.sum(VendaItem.subtotal).desc())
        .limit(10)
        .all()
    )

    ranking_vendedores = (
        db.session.query(Usuario.nome, func.coalesce(func.sum(Venda.total), 0))
        .join(Venda, Venda.vendedor_id == Usuario.id)
        .filter(Venda.criado_em >= inicio, Venda.criado_em <= fim, Venda.reembolsada == False)
        .group_by(Usuario.nome)
        .order_by(func.coalesce(func.sum(Venda.total), 0).desc())
        .all()
    )

    return jsonify({
        "receita_total": receita_total,
        "num_vendas": num_vendas,
        "ticket_medio": ticket_medio,
        "total_descontos": total_descontos,
        "lucro_bruto": lucro_bruto,
        "vendas_por_dia": [{"data": str(d), "total": float(t)} for d, t in vendas_por_dia],
        "pagamentos": [{"forma": f, "total": float(t)} for f, t in pagamentos_por_forma],
        "ranking_produtos": [{"nome": n, "quantidade": int(q), "total": float(t)} for n, q, t in ranking_produtos],
        "ranking_vendedores": [{"nome": n, "total": float(t)} for n, t in ranking_vendedores],
    })
