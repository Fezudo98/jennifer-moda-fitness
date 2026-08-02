from datetime import datetime, date

from flask import Blueprint, render_template
from sqlalchemy import func

from app.extensions import db
from app.models import MovimentacaoCaixa, Venda, ProdutoVariacao
from app.utils import pagina_login_requerida

home_bp = Blueprint("home", __name__)


def calcular_saldo_caixa():
    entradas = db.session.query(func.coalesce(func.sum(MovimentacaoCaixa.valor), 0)).filter_by(tipo="entrada").scalar()
    saidas = db.session.query(func.coalesce(func.sum(MovimentacaoCaixa.valor), 0)).filter_by(tipo="saida").scalar()
    return float(entradas) - float(saidas)


@home_bp.route("/home")
@pagina_login_requerida
def pagina_home():
    hoje = date.today()
    inicio_dia = datetime.combine(hoje, datetime.min.time())

    vendas_hoje = Venda.query.filter(Venda.criado_em >= inicio_dia, Venda.reembolsada == False).count()
    total_hoje = db.session.query(func.coalesce(func.sum(Venda.total), 0)).filter(
        Venda.criado_em >= inicio_dia, Venda.reembolsada == False
    ).scalar()
    estoque_baixo = ProdutoVariacao.query.filter(
        ProdutoVariacao.deletado == False, ProdutoVariacao.quantidade <= ProdutoVariacao.estoque_minimo
    ).count()

    return render_template(
        "home.html",
        saldo_caixa=calcular_saldo_caixa(),
        vendas_hoje=vendas_hoje,
        total_hoje=float(total_hoje),
        estoque_baixo=estoque_baixo,
    )
