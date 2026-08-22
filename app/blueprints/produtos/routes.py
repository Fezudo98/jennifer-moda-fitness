import os
import uuid

from flask import Blueprint, render_template, request, jsonify, current_app, send_from_directory
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Produto, ProdutoVariacao, ProdutoImagem, Categoria, VendaItem
from app.utils import (
    token_requerido,
    admin_requerido,
    pagina_login_requerida,
    registrar_log,
    gerar_codigo_barras_imagem,
    proximo_codigo_barras,
    parse_decimal_br,
    ValorInvalidoError,
)

produtos_bp = Blueprint("produtos", __name__, url_prefix="/produtos")

EXTENSOES_PERMITIDAS = {"png", "jpg", "jpeg", "webp", "gif"}


def _extensao_valida(nome_arquivo):
    return "." in nome_arquivo and nome_arquivo.rsplit(".", 1)[1].lower() in EXTENSOES_PERMITIDAS


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

@produtos_bp.route("")
@pagina_login_requerida
def pagina_lista():
    return render_template("produtos/lista.html")


@produtos_bp.route("/novo")
@pagina_login_requerida
def pagina_novo():
    return render_template("produtos/form.html", produto_id=None)


@produtos_bp.route("/<int:produto_id>/editar")
@pagina_login_requerida
def pagina_editar(produto_id):
    return render_template("produtos/form.html", produto_id=produto_id)


# ---------------------------------------------------------------------------
# API - Categorias
# ---------------------------------------------------------------------------

@produtos_bp.route("/api/categorias", methods=["GET"])
@token_requerido
def api_listar_categorias():
    categorias = Categoria.query.order_by(Categoria.nome).all()
    return jsonify([c.to_dict() for c in categorias])


@produtos_bp.route("/api/categorias", methods=["POST"])
@token_requerido
@admin_requerido
def api_criar_categoria():
    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "Informe o nome da categoria."}), 400
    if Categoria.query.filter(db.func.lower(Categoria.nome) == nome.lower()).first():
        return jsonify({"erro": "Já existe uma categoria com esse nome."}), 400

    categoria = Categoria(nome=nome)
    db.session.add(categoria)
    registrar_log("categoria_criada", f"Categoria '{nome}' criada.")
    db.session.commit()
    return jsonify(categoria.to_dict()), 201


@produtos_bp.route("/api/categorias/<int:categoria_id>", methods=["PUT"])
@token_requerido
@admin_requerido
def api_renomear_categoria(categoria_id):
    categoria = db.session.get(Categoria, categoria_id)
    if not categoria:
        return jsonify({"erro": "Categoria não encontrada."}), 404
    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "Informe o nome da categoria."}), 400
    existente = Categoria.query.filter(db.func.lower(Categoria.nome) == nome.lower(), Categoria.id != categoria_id).first()
    if existente:
        return jsonify({"erro": "Já existe uma categoria com esse nome."}), 400

    nome_antigo = categoria.nome
    categoria.nome = nome
    registrar_log("categoria_renomeada", f"Categoria '{nome_antigo}' renomeada para '{nome}' (afeta todos os produtos vinculados).")
    db.session.commit()
    return jsonify(categoria.to_dict())


@produtos_bp.route("/api/categorias/<int:categoria_id>", methods=["DELETE"])
@token_requerido
@admin_requerido
def api_excluir_categoria(categoria_id):
    categoria = db.session.get(Categoria, categoria_id)
    if not categoria:
        return jsonify({"erro": "Categoria não encontrada."}), 404

    migrar_para = request.args.get("migrar_para")
    if migrar_para:
        destino = db.session.get(Categoria, int(migrar_para))
        if not destino:
            return jsonify({"erro": "Categoria de destino não encontrada."}), 404
        Produto.query.filter_by(categoria_id=categoria_id).update({"categoria_id": destino.id})
    else:
        Produto.query.filter_by(categoria_id=categoria_id).update({"categoria_id": None})

    nome = categoria.nome
    db.session.delete(categoria)
    registrar_log("categoria_excluida", f"Categoria '{nome}' excluída.")
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API - Produtos
# ---------------------------------------------------------------------------

@produtos_bp.route("/api", methods=["GET"])
@token_requerido
def api_listar_produtos():
    busca = (request.args.get("q") or "").strip()
    categoria_id = request.args.get("categoria_id", type=int)
    apenas_estoque_baixo = request.args.get("estoque_baixo") == "1"
    pagina = request.args.get("pagina", type=int)

    query = Produto.query.filter_by(deletado=False)
    if categoria_id:
        query = query.filter_by(categoria_id=categoria_id)
    if busca:
        like = f"%{busca}%"
        query = query.outerjoin(ProdutoVariacao).filter(
            db.or_(Produto.nome.ilike(like), ProdutoVariacao.sku.ilike(like), ProdutoVariacao.codigo_barras.ilike(like))
        ).distinct()

    query = query.order_by(Produto.nome)

    # A filtragem por estoque baixo acontece em memória (depende das variações
    # de cada produto), então não é compatível com paginação no banco — nesse
    # caso retornamos a lista completa já filtrada, sem paginar.
    if pagina and not apenas_estoque_baixo:
        por_pagina = 24
        total = query.count()
        produtos = query.offset((pagina - 1) * por_pagina).limit(por_pagina).all()
        return jsonify({
            "itens": [p.to_dict() for p in produtos],
            "total": total,
            "pagina": pagina,
            "paginas": max(1, (total + por_pagina - 1) // por_pagina),
        })

    produtos = query.all()
    resultado = []
    for p in produtos:
        d = p.to_dict()
        if apenas_estoque_baixo:
            d["variacoes"] = [v for v in d["variacoes"] if v["estoque_baixo"]]
            if not d["variacoes"]:
                continue
        resultado.append(d)
    return jsonify(resultado)


@produtos_bp.route("/api/nomes", methods=["GET"])
@token_requerido
def api_listar_nomes_produtos():
    """Nomes de produtos não excluídos (com o id), para autocomplete no
    cadastro de nova variação — evita criar um produto duplicado por causa
    de um nome digitado com pequena diferença do já cadastrado, e permite
    localizar direto o produto a que a nova variação deve ser anexada."""
    produtos = (
        Produto.query.filter_by(deletado=False)
        .order_by(Produto.nome)
        .all()
    )
    return jsonify([{"id": p.id, "nome": p.nome} for p in produtos])


@produtos_bp.route("/api/stats", methods=["GET"])
@token_requerido
def api_estatisticas_produtos():
    total_pecas = Produto.query.filter_by(deletado=False).count()
    total_variacoes = ProdutoVariacao.query.filter_by(deletado=False).count()
    estoque_baixo = ProdutoVariacao.query.filter(
        ProdutoVariacao.deletado == False,
        ProdutoVariacao.quantidade > 0,
        ProdutoVariacao.quantidade <= ProdutoVariacao.estoque_minimo,
    ).count()
    sem_estoque = ProdutoVariacao.query.filter(
        ProdutoVariacao.deletado == False, ProdutoVariacao.quantidade == 0
    ).count()
    valor_estoque_custo = db.session.query(
        db.func.coalesce(db.func.sum(ProdutoVariacao.preco_custo * ProdutoVariacao.quantidade), 0)
    ).filter(ProdutoVariacao.deletado == False).scalar()

    return jsonify({
        "total_pecas": total_pecas,
        "total_variacoes": total_variacoes,
        "estoque_baixo": estoque_baixo,
        "sem_estoque": sem_estoque,
        "valor_estoque_custo": float(valor_estoque_custo),
    })


@produtos_bp.route("/api/<int:produto_id>", methods=["GET"])
@token_requerido
def api_obter_produto(produto_id):
    produto = db.session.get(Produto, produto_id)
    if not produto or produto.deletado:
        return jsonify({"erro": "Produto não encontrado."}), 404
    return jsonify(produto.to_dict())


def _normalizar_nome(texto):
    """Remove espaços duplicados/nas pontas e padroniza capitalização (Title
    Case). Evita que o mesmo produto/cor apareça cadastrado de formas
    diferentes (' legging basic', 'LEGGING BASIC', 'Legging  Basic') — a
    causa mais comum de catálogo bagunçado e de relatórios que não agrupam
    corretamente a mesma peça."""
    return " ".join((texto or "").split()).title()


def _normalizar_tamanho(texto):
    """Tamanhos ficam em caixa alta (P, M, GG, 42) — nunca em Title Case,
    que deixaria 'Gg' em vez de 'GG'."""
    return " ".join((texto or "").split()).upper()


def _validar_variacao(v, produto_nome):
    cor = _normalizar_nome((v.get("cor") or "").strip())
    tamanho = _normalizar_tamanho((v.get("tamanho") or "").strip())
    if not cor or not tamanho:
        return None, "Cor e tamanho são obrigatórios em cada variação."
    try:
        preco_custo = float(parse_decimal_br(v.get("preco_custo") if v.get("preco_custo") not in (None, "") else 0))
        preco_venda = float(parse_decimal_br(v.get("preco_venda") if v.get("preco_venda") not in (None, "") else 0))
        quantidade = int(v.get("quantidade") or 0)
        estoque_minimo = int(v.get("estoque_minimo") or current_app.config["ESTOQUE_BAIXO_PADRAO"])
    except (TypeError, ValueError, ValorInvalidoError):
        return None, "Valores numéricos inválidos em uma das variações. Use apenas números (ex: 45,90 ou 45.90)."

    if preco_custo < 0 or preco_venda < 0:
        return None, "Preços não podem ser negativos."
    if quantidade < 0:
        return None, "A quantidade em estoque não pode ser negativa."
    if estoque_minimo < 0:
        return None, "O limite de estoque baixo não pode ser negativo."

    sku = ProdutoVariacao.gerar_sku(produto_nome, cor, tamanho)
    return {
        "cor": cor,
        "cor_hex": v.get("cor_hex") or None,
        "tamanho": tamanho,
        "sku": sku,
        "preco_custo": preco_custo,
        "preco_venda": preco_venda,
        "quantidade": quantidade,
        "estoque_minimo": estoque_minimo,
    }, None


def _criar_ou_reativar_variacao(produto_id, validado):
    """Cria uma variação nova para o produto — ou, se já existir uma variação
    excluída (soft delete) com o mesmo SKU determinístico (mesma combinação
    de nome+cor+tamanho de uma peça removida antes), reaproveita esse
    registro em vez de tentar inserir outro com o mesmo SKU, o que violaria
    a restrição de unicidade e derrubaria a requisição com erro 500."""
    existente_deletada = ProdutoVariacao.query.filter_by(sku=validado["sku"], deletado=True).first()
    if existente_deletada:
        existente_deletada.produto_id = produto_id
        existente_deletada.deletado = False
        for campo, valor in validado.items():
            setattr(existente_deletada, campo, valor)
        if not existente_deletada.codigo_barras:
            existente_deletada.codigo_barras = proximo_codigo_barras()
        return existente_deletada, True

    variacao = ProdutoVariacao(produto_id=produto_id, codigo_barras=proximo_codigo_barras(), **validado)
    db.session.add(variacao)
    return variacao, False


@produtos_bp.route("/api", methods=["POST"])
@token_requerido
def api_criar_produto():
    dados = request.get_json(silent=True) or {}
    nome = _normalizar_nome(dados.get("nome"))
    if not nome:
        return jsonify({"erro": "Informe o nome do produto."}), 400

    variacoes_entrada = dados.get("variacoes") or []
    if not variacoes_entrada:
        return jsonify({"erro": "Adicione ao menos uma variação (cor/tamanho) para o produto."}), 400

    produto = Produto(nome=nome, categoria_id=dados.get("categoria_id") or None, descricao=dados.get("descricao"))
    db.session.add(produto)
    db.session.flush()

    skus_usados = set()
    for v in variacoes_entrada:
        validado, erro = _validar_variacao(v, nome)
        if erro:
            db.session.rollback()
            return jsonify({"erro": erro}), 400
        if validado["sku"] in skus_usados:
            db.session.rollback()
            return jsonify({"erro": f"Cor/tamanho duplicado nas variações informadas: {validado['cor']} / {validado['tamanho']}."}), 400
        skus_usados.add(validado["sku"])

        if ProdutoVariacao.query.filter_by(sku=validado["sku"], deletado=False).first():
            db.session.rollback()
            return jsonify({"erro": f"Já existe uma variação com o SKU {validado['sku']}."}), 400

        _criar_ou_reativar_variacao(produto.id, validado)

    registrar_log("produto_criado", f"Produto '{nome}' criado com {len(variacoes_entrada)} variação(ões).")
    db.session.commit()
    return jsonify(produto.to_dict()), 201


@produtos_bp.route("/api/<int:produto_id>", methods=["PUT"])
@token_requerido
def api_atualizar_produto(produto_id):
    produto = db.session.get(Produto, produto_id)
    if not produto or produto.deletado:
        return jsonify({"erro": "Produto não encontrado."}), 404

    dados = request.get_json(silent=True) or {}
    nome = _normalizar_nome(dados.get("nome"))
    if not nome:
        return jsonify({"erro": "Informe o nome do produto."}), 400

    produto.nome = nome
    produto.categoria_id = dados.get("categoria_id") or None
    produto.descricao = dados.get("descricao")

    registrar_log("produto_editado", f"Produto '{nome}' (#{produto.id}) editado.")
    db.session.commit()
    return jsonify(produto.to_dict())


@produtos_bp.route("/api/<int:produto_id>", methods=["DELETE"])
@token_requerido
def api_excluir_produto(produto_id):
    produto = db.session.get(Produto, produto_id)
    if not produto or produto.deletado:
        return jsonify({"erro": "Produto não encontrado."}), 404

    produto.deletado = True
    registrar_log("produto_excluido", f"Produto '{produto.nome}' (#{produto.id}) excluído (soft delete).")
    db.session.commit()
    return jsonify({"ok": True})


@produtos_bp.route("/api/excluir-em-massa", methods=["POST"])
@token_requerido
def api_excluir_em_massa():
    dados = request.get_json(silent=True) or {}
    ids = dados.get("ids") or []
    if not ids:
        return jsonify({"erro": "Nenhum produto selecionado."}), 400

    produtos = Produto.query.filter(Produto.id.in_(ids), Produto.deletado == False).all()
    for p in produtos:
        p.deletado = True

    registrar_log("produtos_excluidos_em_massa", f"{len(produtos)} produto(s) excluído(s) em massa.")
    db.session.commit()
    return jsonify({"ok": True, "excluidos": len(produtos)})


@produtos_bp.route("/api/zerar-estoque-em-massa", methods=["POST"])
@token_requerido
def api_zerar_estoque_em_massa():
    """Zera a quantidade de todas as variações dos produtos selecionados —
    útil para correções de inventário ou fim de coleção, sem excluir o
    cadastro (o produto continua existindo, só sem estoque disponível)."""
    dados = request.get_json(silent=True) or {}
    ids = dados.get("ids") or []
    if not ids:
        return jsonify({"erro": "Nenhum produto selecionado."}), 400

    variacoes = ProdutoVariacao.query.filter(
        ProdutoVariacao.produto_id.in_(ids), ProdutoVariacao.deletado == False
    ).all()
    for v in variacoes:
        v.quantidade = 0

    registrar_log("estoque_zerado_em_massa", f"Estoque zerado para {len(variacoes)} variação(ões) de {len(ids)} produto(s).")
    db.session.commit()
    return jsonify({"ok": True, "variacoes_zeradas": len(variacoes)})


# ---------------------------------------------------------------------------
# API - Variações
# ---------------------------------------------------------------------------

@produtos_bp.route("/api/<int:produto_id>/variacoes", methods=["POST"])
@token_requerido
def api_adicionar_variacao(produto_id):
    produto = db.session.get(Produto, produto_id)
    if not produto or produto.deletado:
        return jsonify({"erro": "Produto não encontrado."}), 404

    dados = request.get_json(silent=True) or {}
    validado, erro = _validar_variacao(dados, produto.nome)
    if erro:
        return jsonify({"erro": erro}), 400

    if ProdutoVariacao.query.filter_by(sku=validado["sku"], deletado=False).first():
        return jsonify({"erro": f"Já existe uma variação com essa cor/tamanho (SKU {validado['sku']})."}), 400

    variacao, reativada = _criar_ou_reativar_variacao(produto.id, validado)
    acao = "variacao_reativada" if reativada else "variacao_criada"
    registrar_log(acao, f"Variação {validado['sku']} adicionada ao produto '{produto.nome}'.")
    db.session.commit()
    return jsonify(variacao.to_dict()), 201


@produtos_bp.route("/api/variacoes/<int:variacao_id>", methods=["PUT"])
@token_requerido
def api_atualizar_variacao(variacao_id):
    variacao = db.session.get(ProdutoVariacao, variacao_id)
    if not variacao or variacao.deletado:
        return jsonify({"erro": "Variação não encontrada."}), 404

    dados = request.get_json(silent=True) or {}
    validado, erro = _validar_variacao(dados, variacao.produto.nome)
    if erro:
        return jsonify({"erro": erro}), 400

    conflito = ProdutoVariacao.query.filter(
        ProdutoVariacao.sku == validado["sku"], ProdutoVariacao.deletado == False, ProdutoVariacao.id != variacao_id
    ).first()
    if conflito:
        return jsonify({"erro": f"Já existe uma variação com essa cor/tamanho (SKU {validado['sku']})."}), 400

    # Se o novo SKU coincide com o de uma variação já excluída (outra peça
    # removida antes com a mesma combinação de nome+cor+tamanho), só é
    # seguro liberar o SKU se essa variação órfã nunca apareceu em nenhuma
    # venda — caso contrário excluí-la de vez quebraria o histórico (regra
    # de nunca fazer hard delete quando há venda associada).
    orfa_deletada = ProdutoVariacao.query.filter(
        ProdutoVariacao.sku == validado["sku"], ProdutoVariacao.deletado == True, ProdutoVariacao.id != variacao_id
    ).first()
    if orfa_deletada:
        tem_historico = VendaItem.query.filter_by(variacao_id=orfa_deletada.id).first() is not None
        if tem_historico:
            return jsonify({
                "erro": "Essa combinação de cor/tamanho já foi usada por uma variação excluída com vendas no histórico. "
                        "Escolha outra cor/tamanho, ou fale com o suporte para reaproveitar o cadastro antigo."
            }), 400
        db.session.delete(orfa_deletada)

    for campo, valor in validado.items():
        setattr(variacao, campo, valor)

    registrar_log("variacao_editada", f"Variação {variacao.sku} editada.")
    db.session.commit()
    return jsonify(variacao.to_dict())


@produtos_bp.route("/api/variacoes/<int:variacao_id>/rapido", methods=["PATCH"])
@token_requerido
def api_editar_variacao_rapido(variacao_id):
    variacao = db.session.get(ProdutoVariacao, variacao_id)
    if not variacao or variacao.deletado:
        return jsonify({"erro": "Variação não encontrada."}), 404

    dados = request.get_json(silent=True) or {}
    if "preco_venda" in dados:
        try:
            preco = float(parse_decimal_br(dados["preco_venda"]))
        except (TypeError, ValueError, ValorInvalidoError):
            return jsonify({"erro": "Preço inválido."}), 400
        if preco < 0:
            return jsonify({"erro": "O preço não pode ser negativo."}), 400
        variacao.preco_venda = preco

    if "quantidade" in dados:
        try:
            quantidade = int(dados["quantidade"])
        except (TypeError, ValueError):
            return jsonify({"erro": "Quantidade inválida."}), 400
        if quantidade < 0:
            return jsonify({"erro": "A quantidade em estoque não pode ser negativa."}), 400

        if dados.get("quantidade_esperada") is not None:
            # Trava otimista: só grava se o estoque no banco ainda for o mesmo
            # valor que a tela mostrava quando o usuário editou. Sem isso, uma
            # venda no PDV que baixe o estoque entre a tela carregar e o
            # admin salvar seria silenciosamente desfeita pela edição rápida.
            try:
                qtd_esperada = int(dados["quantidade_esperada"])
            except (TypeError, ValueError):
                return jsonify({"erro": "Quantidade esperada inválida."}), 400

            afetadas = ProdutoVariacao.query.filter_by(id=variacao_id, quantidade=qtd_esperada).update(
                {"quantidade": quantidade}
            )
            if afetadas == 0:
                db.session.rollback()
                db.session.refresh(variacao)
                return jsonify({
                    "erro": "O estoque dessa variação mudou desde que a tela foi carregada (provavelmente uma venda). "
                            "Atualize a página e tente de novo.",
                    "quantidade_atual": variacao.quantidade,
                }), 409
        else:
            variacao.quantidade = quantidade

    registrar_log("estoque_ajustado", f"Ajuste rápido na variação {variacao.sku}.")
    db.session.commit()
    db.session.refresh(variacao)
    return jsonify(variacao.to_dict())


@produtos_bp.route("/api/variacoes/<int:variacao_id>", methods=["DELETE"])
@token_requerido
def api_excluir_variacao(variacao_id):
    variacao = db.session.get(ProdutoVariacao, variacao_id)
    if not variacao or variacao.deletado:
        return jsonify({"erro": "Variação não encontrada."}), 404

    variacao.deletado = True
    registrar_log("variacao_excluida", f"Variação {variacao.sku} excluída.")
    db.session.commit()
    return jsonify({"ok": True})


@produtos_bp.route("/api/variacoes/busca", methods=["GET"])
@token_requerido
def api_buscar_variacoes():
    """Usado pelo PDV: busca por nome do produto, SKU ou código de barras (leitor)."""
    termo = (request.args.get("q") or "").strip()
    if not termo:
        return jsonify([])

    like = f"%{termo}%"
    variacoes = (
        ProdutoVariacao.query.join(Produto)
        .filter(
            ProdutoVariacao.deletado == False,
            Produto.deletado == False,
            db.or_(
                Produto.nome.ilike(like),
                ProdutoVariacao.sku.ilike(like),
                ProdutoVariacao.codigo_barras == termo,
                ProdutoVariacao.cor.ilike(like),
            ),
        )
        .limit(30)
        .all()
    )
    return jsonify([v.to_dict() for v in variacoes])


@produtos_bp.route("/api/variacoes/<int:variacao_id>/codigo-barras")
@pagina_login_requerida
def api_codigo_barras(variacao_id):
    variacao = db.session.get(ProdutoVariacao, variacao_id)
    if not variacao:
        return jsonify({"erro": "Variação não encontrada."}), 404
    if not variacao.codigo_barras:
        return jsonify({"erro": "Esta variação não possui código de barras."}), 400

    caminho_arquivo = os.path.join(current_app.config["BARCODE_FOLDER"], f"{variacao.codigo_barras}.png")
    if not os.path.exists(caminho_arquivo):
        gerar_codigo_barras_imagem(variacao.codigo_barras)

    return send_from_directory(current_app.config["BARCODE_FOLDER"], f"{variacao.codigo_barras}.png")


# ---------------------------------------------------------------------------
# API - Imagens
# ---------------------------------------------------------------------------

@produtos_bp.route("/api/<int:produto_id>/imagens", methods=["POST"])
@token_requerido
def api_upload_imagens(produto_id):
    produto = db.session.get(Produto, produto_id)
    if not produto or produto.deletado:
        return jsonify({"erro": "Produto não encontrado."}), 404

    arquivos = request.files.getlist("imagens")
    if not arquivos:
        return jsonify({"erro": "Nenhuma imagem enviada."}), 400

    pasta_produto = os.path.join(current_app.config["UPLOAD_FOLDER"], str(produto.id))
    os.makedirs(pasta_produto, exist_ok=True)

    tem_capa = any(img.capa for img in produto.imagens)
    ordem_atual = len(produto.imagens)
    criadas = []
    for arquivo in arquivos:
        if not arquivo or not arquivo.filename or not _extensao_valida(arquivo.filename):
            continue
        nome_seguro = secure_filename(arquivo.filename)
        nome_unico = f"{uuid.uuid4().hex}_{nome_seguro}"
        arquivo.save(os.path.join(pasta_produto, nome_unico))

        imagem = ProdutoImagem(
            produto_id=produto.id,
            caminho=f"uploads/{produto.id}/{nome_unico}",
            capa=not tem_capa,
            ordem=ordem_atual,
        )
        tem_capa = True
        ordem_atual += 1
        db.session.add(imagem)
        criadas.append(imagem)

    if not criadas:
        return jsonify({"erro": "Nenhum arquivo válido enviado. Use PNG, JPG, JPEG, WEBP ou GIF."}), 400

    registrar_log("imagens_adicionadas", f"{len(criadas)} imagem(ns) adicionada(s) ao produto '{produto.nome}'.")
    db.session.commit()
    return jsonify([i.to_dict() for i in criadas]), 201


@produtos_bp.route("/api/imagens/<int:imagem_id>", methods=["DELETE"])
@token_requerido
def api_excluir_imagem(imagem_id):
    imagem = db.session.get(ProdutoImagem, imagem_id)
    if not imagem:
        return jsonify({"erro": "Imagem não encontrada."}), 404

    era_capa = imagem.capa
    produto_id = imagem.produto_id
    caminho_absoluto = os.path.join(current_app.config["UPLOAD_FOLDER"], "..", imagem.caminho)
    db.session.delete(imagem)
    db.session.flush()

    if era_capa:
        proxima = ProdutoImagem.query.filter_by(produto_id=produto_id).order_by(ProdutoImagem.ordem).first()
        if proxima:
            proxima.capa = True

    try:
        caminho_real = os.path.join(current_app.root_path, "static", imagem.caminho)
        if os.path.exists(caminho_real):
            os.remove(caminho_real)
    except OSError:
        pass

    db.session.commit()
    return jsonify({"ok": True})


@produtos_bp.route("/api/imagens/<int:imagem_id>/capa", methods=["PUT"])
@token_requerido
def api_definir_capa(imagem_id):
    imagem = db.session.get(ProdutoImagem, imagem_id)
    if not imagem:
        return jsonify({"erro": "Imagem não encontrada."}), 404

    ProdutoImagem.query.filter_by(produto_id=imagem.produto_id).update({"capa": False})
    imagem.capa = True
    db.session.commit()
    return jsonify({"ok": True})


@produtos_bp.route("/api/imagens/reordenar", methods=["PUT"])
@token_requerido
def api_reordenar_imagens():
    dados = request.get_json(silent=True) or {}
    ids_em_ordem = dados.get("ids") or []
    for posicao, imagem_id in enumerate(ids_em_ordem):
        ProdutoImagem.query.filter_by(id=imagem_id).update({"ordem": posicao})
    db.session.commit()
    return jsonify({"ok": True})
