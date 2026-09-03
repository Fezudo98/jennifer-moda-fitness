from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import os
import uuid

from flask import Blueprint, render_template, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Venda, VendaItem, VendaPagamento, ProdutoVariacao, Cliente, Cupom, MovimentacaoCaixa
from app.utils import (
    token_requerido,
    admin_requerido,
    pagina_login_requerida,
    registrar_log,
    proximo_numero_venda,
    parse_decimal_br,
    ValorInvalidoError,
    gerar_comprovante_pdf,
    caminho_comprovante_venda,
    usuario_da_sessao,
)

vendas_bp = Blueprint("vendas", __name__, url_prefix="/vendas")

FORMAS_PAGAMENTO_VALIDAS = {"dinheiro", "pix", "cartao_credito", "cartao_debito"}


def _d(valor) -> Decimal:
    return parse_decimal_br(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

@vendas_bp.route("/pdv")
@pagina_login_requerida
def pagina_pdv():
    return render_template("vendas/pdv.html")


@vendas_bp.route("")
@pagina_login_requerida
def pagina_lista():
    return render_template("vendas/lista.html")


@vendas_bp.route("/<int:venda_id>")
@pagina_login_requerida
def pagina_detalhe(venda_id):
    return render_template("vendas/detalhe.html", venda_id=venda_id)


@vendas_bp.route("/<int:venda_id>/recibo")
@pagina_login_requerida
def pagina_recibo(venda_id):
    return render_template("vendas/recibo.html", venda_id=venda_id)


@vendas_bp.route("/teste-impressora")
@pagina_login_requerida
def pagina_teste_impressora():
    """Recibo com dados de exemplo (não fica registrado como venda), pra
    calibrar tamanho de papel/margens da impressora térmica sem precisar
    inventar uma venda de verdade."""
    return render_template("vendas/recibo.html", venda_id=None, modo_teste=True)


# ---------------------------------------------------------------------------
# Cálculo de totais (compartilhado entre pré-visualização e criação)
# ---------------------------------------------------------------------------

def _calcular_totais(itens_dados, cupom_codigo, entrega_taxa):
    erros = []
    itens_processados = []
    subtotal = Decimal("0.00")

    for item in itens_dados:
        variacao = db.session.get(ProdutoVariacao, item.get("variacao_id"))
        try:
            quantidade = int(item.get("quantidade") or 0)
        except (TypeError, ValueError):
            quantidade = 0

        if not variacao or variacao.deletado:
            erros.append("Um dos produtos do carrinho não foi encontrado.")
            continue
        if quantidade <= 0:
            erros.append(f"Quantidade inválida para {variacao.sku}.")
            continue
        if variacao.quantidade < quantidade:
            erros.append(f"Estoque insuficiente para {variacao.produto.nome} ({variacao.cor}/{variacao.tamanho}). Disponível: {variacao.quantidade}.")
            continue

        preco_unit = Decimal(str(variacao.preco_venda))
        custo_unit = Decimal(str(variacao.preco_custo))
        item_subtotal = (preco_unit * quantidade).quantize(Decimal("0.01"))
        subtotal += item_subtotal

        itens_processados.append({
            "variacao": variacao,
            "quantidade": quantidade,
            "preco_unit": preco_unit,
            "custo_unit": custo_unit,
            "subtotal": item_subtotal,
        })

    if erros:
        return None, erros

    cupom = None
    desconto = Decimal("0.00")
    if cupom_codigo:
        cupom = Cupom.query.filter_by(codigo=cupom_codigo.strip().upper()).first()
        if not cupom or not cupom.ativo:
            return None, ["Cupom inválido ou inativo."]

        if cupom.aplicacao == "produtos":
            ids_alvo = set(cupom.ids_produtos())
            base = sum(
                (i["subtotal"] for i in itens_processados if i["variacao"].produto_id in ids_alvo),
                Decimal("0.00"),
            )
        else:
            base = subtotal

        if cupom.tipo == "percentual":
            desconto = (base * Decimal(str(cupom.valor)) / Decimal("100")).quantize(Decimal("0.01"))
        else:
            desconto = min(base, Decimal(str(cupom.valor))).quantize(Decimal("0.01"))

    try:
        taxa = _d(entrega_taxa or 0)
    except ValorInvalidoError:
        return None, ["Taxa de entrega inválida."]
    total = subtotal - desconto + taxa
    if total < 0:
        total = Decimal("0.00")

    return {
        "itens": itens_processados,
        "subtotal": subtotal,
        "desconto": desconto,
        "taxa": taxa,
        "total": total,
        "cupom": cupom,
    }, None


@vendas_bp.route("/api/calcular", methods=["POST"])
@token_requerido
def api_calcular():
    dados = request.get_json(silent=True) or {}
    resultado, erros = _calcular_totais(
        dados.get("itens") or [], dados.get("cupom_codigo"), dados.get("entrega_taxa")
    )
    if erros:
        return jsonify({"erro": " | ".join(erros)}), 400

    return jsonify({
        "subtotal": float(resultado["subtotal"]),
        "desconto": float(resultado["desconto"]),
        "taxa": float(resultado["taxa"]),
        "total": float(resultado["total"]),
        "cupom_valido": bool(resultado["cupom"]),
    })


# ---------------------------------------------------------------------------
# API - Vendas
# ---------------------------------------------------------------------------

@vendas_bp.route("/api", methods=["GET"])
@token_requerido
def api_listar_vendas():
    usuario = request.usuario_atual
    query = Venda.query
    if not usuario.is_admin:
        query = query.filter_by(vendedor_id=usuario.id)

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    if data_inicio:
        query = query.filter(Venda.criado_em >= datetime.fromisoformat(data_inicio))
    if data_fim:
        query = query.filter(Venda.criado_em <= datetime.fromisoformat(data_fim + "T23:59:59"))

    vendas = query.order_by(Venda.criado_em.desc()).limit(500).all()
    return jsonify([v.to_dict(detalhado=False) for v in vendas])


@vendas_bp.route("/api/<int:venda_id>", methods=["GET"])
@token_requerido
def api_obter_venda(venda_id):
    usuario = request.usuario_atual
    venda = db.session.get(Venda, venda_id)
    if not venda:
        return jsonify({"erro": "Venda não encontrada."}), 404
    if not usuario.is_admin and venda.vendedor_id != usuario.id:
        return jsonify({"erro": "Você só pode visualizar suas próprias vendas."}), 403
    return jsonify(venda.to_dict())


@vendas_bp.route("/api", methods=["POST"])
@token_requerido
def api_criar_venda():
    usuario = request.usuario_atual
    dados = request.get_json(silent=True) or {}

    itens_dados = dados.get("itens") or []
    if not itens_dados:
        return jsonify({"erro": "Adicione ao menos um produto ao carrinho."}), 400

    pagamentos_dados = dados.get("pagamentos") or []
    if not pagamentos_dados:
        return jsonify({"erro": "Informe ao menos uma forma de pagamento."}), 400

    entrega_tipo = dados.get("entrega_tipo") or "retirada"
    if entrega_tipo not in ("retirada", "motoboy"):
        return jsonify({"erro": "Tipo de entrega inválido."}), 400
    entrega_endereco = (dados.get("entrega_endereco") or "").strip()
    if entrega_tipo == "motoboy" and not entrega_endereco:
        return jsonify({"erro": "Informe o endereço de entrega para vendas com motoboy."}), 400

    resultado, erros = _calcular_totais(itens_dados, dados.get("cupom_codigo"), dados.get("entrega_taxa"))
    if erros:
        return jsonify({"erro": " | ".join(erros)}), 400

    total_pagamentos = Decimal("0.00")
    total_dinheiro = Decimal("0.00")
    for p in pagamentos_dados:
        forma = p.get("forma")
        if forma not in FORMAS_PAGAMENTO_VALIDAS:
            return jsonify({"erro": "Forma de pagamento inválida."}), 400
        try:
            valor = _d(p.get("valor"))
        except Exception:
            return jsonify({"erro": "Valor de pagamento inválido."}), 400
        if valor <= 0:
            return jsonify({"erro": "O valor de cada pagamento deve ser maior que zero."}), 400
        total_pagamentos += valor
        if forma == "dinheiro":
            total_dinheiro += valor

    total_venda = resultado["total"]
    if total_pagamentos < total_venda:
        return jsonify({"erro": f"Valor pago (R$ {total_pagamentos}) é menor que o total da venda (R$ {total_venda})."}), 400

    troco = total_pagamentos - total_venda
    if troco > 0 and total_dinheiro < troco:
        return jsonify({"erro": "O troco só pode ser dado sobre pagamentos em dinheiro."}), 400

    cliente_id = dados.get("cliente_id") or None
    if cliente_id and not db.session.get(Cliente, cliente_id):
        return jsonify({"erro": "Cliente não encontrado."}), 404

    venda = Venda(
        numero=proximo_numero_venda(),
        cliente_id=cliente_id,
        vendedor_id=usuario.id,
        subtotal=resultado["subtotal"],
        desconto=resultado["desconto"],
        total=total_venda,
        cupom_id=resultado["cupom"].id if resultado["cupom"] else None,
        entrega_tipo=entrega_tipo,
        entrega_endereco=entrega_endereco if entrega_tipo == "motoboy" else None,
        entrega_taxa=resultado["taxa"],
        entrega_status="pendente" if entrega_tipo == "motoboy" else None,
    )
    db.session.add(venda)
    db.session.flush()

    for item in resultado["itens"]:
        variacao = item["variacao"]
        # Decremento atômico e condicional no próprio banco (em vez de ler o
        # valor em Python, subtrair e regravar): garante que duas vendas
        # simultâneas do último item em estoque (dois caixas, ou um
        # duplo-clique) nunca derrubem a quantidade abaixo de zero, mesmo
        # que ambas tenham lido o mesmo valor inicial antes de qualquer
        # uma commitar.
        afetadas = ProdutoVariacao.query.filter(
            ProdutoVariacao.id == variacao.id,
            ProdutoVariacao.quantidade >= item["quantidade"],
        ).update(
            {ProdutoVariacao.quantidade: ProdutoVariacao.quantidade - item["quantidade"]},
            synchronize_session=False,
        )
        if afetadas == 0:
            db.session.rollback()
            return jsonify({"erro": f"Estoque insuficiente para {variacao.sku}."}), 400

        db.session.add(VendaItem(
            venda_id=venda.id,
            variacao_id=variacao.id,
            produto_nome=variacao.produto.nome,
            sku=variacao.sku,
            cor=variacao.cor,
            tamanho=variacao.tamanho,
            quantidade=item["quantidade"],
            preco_venda_unit=item["preco_unit"],
            preco_custo_unit=item["custo_unit"],
            subtotal=item["subtotal"],
        ))

    troco_restante = troco
    for p in pagamentos_dados:
        valor = _d(p.get("valor"))
        troco_pagamento = Decimal("0.00")
        if p.get("forma") == "dinheiro" and troco_restante > 0:
            troco_pagamento = min(valor, troco_restante)
            troco_restante -= troco_pagamento

        db.session.add(VendaPagamento(
            venda_id=venda.id,
            forma=p.get("forma"),
            valor=valor,
            parcelas=p.get("parcelas") if p.get("forma") == "cartao_credito" else None,
            troco=troco_pagamento,
        ))

    if total_dinheiro > 0:
        db.session.add(MovimentacaoCaixa(
            tipo="entrada", valor=total_dinheiro, motivo="venda",
            observacao=f"Recebimento em dinheiro da venda {venda.numero}.",
            usuario_id=usuario.id, venda_id=venda.id,
        ))
    if troco > 0:
        db.session.add(MovimentacaoCaixa(
            tipo="saida", valor=troco, motivo="troco",
            observacao=f"Troco entregue na venda {venda.numero}.",
            usuario_id=usuario.id, venda_id=venda.id,
        ))

    registrar_log("venda_registrada", f"Venda {venda.numero} registrada no valor de R$ {total_venda}.", usuario_id=usuario.id)
    db.session.commit()

    try:
        gerar_comprovante_pdf(venda)
    except Exception:
        # A venda já está concluída e salva; a falha em gerar o PDF não pode
        # desfazer a venda. O comprovante pode ser gerado novamente sob
        # demanda ao ser baixado.
        current_app.logger.exception(f"Falha ao gerar comprovante em PDF da venda {venda.numero}.")

    return jsonify(venda.to_dict()), 201


@vendas_bp.route("/api/<int:venda_id>/reembolsar", methods=["POST"])
@token_requerido
@admin_requerido
def api_reembolsar_venda(venda_id):
    venda = db.session.get(Venda, venda_id)
    if not venda:
        return jsonify({"erro": "Venda não encontrada."}), 404
    if venda.reembolsada:
        return jsonify({"erro": "Esta venda já foi reembolsada."}), 400

    for item in venda.itens:
        # Mesmo padrão de expressão SQL atômica do decremento na venda — evita
        # perder incremento de estoque se dois reembolsos/ajustes concorrentes
        # acontecerem sobre a mesma variação ao mesmo tempo.
        ProdutoVariacao.query.filter(ProdutoVariacao.id == item.variacao_id).update(
            {ProdutoVariacao.quantidade: ProdutoVariacao.quantidade + item.quantidade},
            synchronize_session=False,
        )

    venda.reembolsada = True
    venda.reembolsada_em = datetime.utcnow()

    # Só sai do caixa físico a parte que realmente entrou nele em dinheiro —
    # reembolso de pagamento em PIX/cartão não retira nada da gaveta (o
    # estorno é do banco/adquirente para o cliente), então lançar o valor
    # total da venda como saída de caixa distorceria o saldo físico sempre
    # que a venda não foi 100% em dinheiro.
    valor_dinheiro = sum(
        (p.valor for p in venda.pagamentos if p.forma == "dinheiro"), Decimal("0.00")
    )
    if valor_dinheiro > 0:
        db.session.add(MovimentacaoCaixa(
            tipo="saida", valor=valor_dinheiro, motivo="reembolso",
            observacao=f"Reembolso da venda {venda.numero} (parte paga em dinheiro).",
            usuario_id=request.usuario_atual.id, venda_id=venda.id,
        ))

    registrar_log("venda_reembolsada", f"Venda {venda.numero} reembolsada (R$ {venda.total}).")
    db.session.commit()

    try:
        gerar_comprovante_pdf(venda)
    except Exception:
        current_app.logger.exception(f"Falha ao regenerar comprovante em PDF da venda {venda.numero}.")

    return jsonify(venda.to_dict())


# ---------------------------------------------------------------------------
# Comprovantes (PDF da venda + anexos de pagamento)
# ---------------------------------------------------------------------------

EXTENSOES_COMPROVANTE_PERMITIDAS = {"png", "jpg", "jpeg", "webp", "pdf"}


def _verificar_permissao_venda(venda, usuario):
    """Vendedor só acessa comprovantes das próprias vendas; admin acessa tudo."""
    return usuario.is_admin or venda.vendedor_id == usuario.id


@vendas_bp.route("/<int:venda_id>/comprovante")
@pagina_login_requerida
def api_baixar_comprovante_venda(venda_id):
    venda = db.session.get(Venda, venda_id)
    if not venda:
        return jsonify({"erro": "Venda não encontrada."}), 404
    if not _verificar_permissao_venda(venda, usuario_da_sessao()):
        return jsonify({"erro": "Você só pode acessar comprovantes das próprias vendas."}), 403

    caminho = caminho_comprovante_venda(venda.id)
    if not os.path.exists(caminho):
        try:
            gerar_comprovante_pdf(venda)
        except Exception:
            return jsonify({"erro": "Não foi possível gerar o comprovante desta venda."}), 500

    return send_file(caminho, as_attachment=True, download_name=f"comprovante_{venda.numero}.pdf")


@vendas_bp.route("/api/pagamentos/<int:pagamento_id>/comprovante", methods=["POST"])
@token_requerido
def api_anexar_comprovante_pagamento(pagamento_id):
    pagamento = db.session.get(VendaPagamento, pagamento_id)
    if not pagamento:
        return jsonify({"erro": "Pagamento não encontrado."}), 404
    if not _verificar_permissao_venda(pagamento.venda, request.usuario_atual):
        return jsonify({"erro": "Você só pode anexar comprovantes das próprias vendas."}), 403

    arquivo = request.files.get("comprovante")
    if not arquivo or not arquivo.filename:
        return jsonify({"erro": "Nenhum arquivo enviado."}), 400

    extensao = arquivo.filename.rsplit(".", 1)[-1].lower() if "." in arquivo.filename else ""
    if extensao not in EXTENSOES_COMPROVANTE_PERMITIDAS:
        return jsonify({"erro": "Envie uma imagem (PNG, JPG, WEBP) ou PDF."}), 400

    pasta = current_app.config["COMPROVANTES_PAGAMENTOS_FOLDER"]
    os.makedirs(pasta, exist_ok=True)

    # Remove o comprovante anterior, se houver, para não acumular arquivos órfãos.
    if pagamento.comprovante_arquivo:
        caminho_antigo = os.path.join(pasta, pagamento.comprovante_arquivo)
        if os.path.exists(caminho_antigo):
            os.remove(caminho_antigo)

    nome_arquivo = f"pagamento_{pagamento.id}_{uuid.uuid4().hex}.{extensao}"
    arquivo.save(os.path.join(pasta, secure_filename(nome_arquivo)))
    pagamento.comprovante_arquivo = secure_filename(nome_arquivo)

    registrar_log("comprovante_pagamento_anexado", f"Comprovante anexado ao pagamento da venda {pagamento.venda.numero}.")
    db.session.commit()
    return jsonify(pagamento.to_dict()), 201


@vendas_bp.route("/api/pagamentos/<int:pagamento_id>/comprovante", methods=["GET"])
@pagina_login_requerida
def api_baixar_comprovante_pagamento(pagamento_id):
    pagamento = db.session.get(VendaPagamento, pagamento_id)
    if not pagamento or not pagamento.comprovante_arquivo:
        return jsonify({"erro": "Este pagamento não tem comprovante anexado."}), 404
    if not _verificar_permissao_venda(pagamento.venda, usuario_da_sessao()):
        return jsonify({"erro": "Você só pode acessar comprovantes das próprias vendas."}), 403

    pasta = current_app.config["COMPROVANTES_PAGAMENTOS_FOLDER"]
    caminho = os.path.join(pasta, pagamento.comprovante_arquivo)
    if not os.path.exists(caminho):
        return jsonify({"erro": "Arquivo do comprovante não encontrado."}), 404

    return send_file(caminho)


@vendas_bp.route("/api/pagamentos/<int:pagamento_id>/comprovante", methods=["DELETE"])
@token_requerido
def api_remover_comprovante_pagamento(pagamento_id):
    pagamento = db.session.get(VendaPagamento, pagamento_id)
    if not pagamento:
        return jsonify({"erro": "Pagamento não encontrado."}), 404
    if not _verificar_permissao_venda(pagamento.venda, request.usuario_atual):
        return jsonify({"erro": "Você só pode remover comprovantes das próprias vendas."}), 403

    if pagamento.comprovante_arquivo:
        pasta = current_app.config["COMPROVANTES_PAGAMENTOS_FOLDER"]
        caminho = os.path.join(pasta, pagamento.comprovante_arquivo)
        if os.path.exists(caminho):
            os.remove(caminho)
        pagamento.comprovante_arquivo = None
        registrar_log("comprovante_pagamento_removido", f"Comprovante removido do pagamento da venda {pagamento.venda.numero}.")
        db.session.commit()

    return jsonify({"ok": True})
