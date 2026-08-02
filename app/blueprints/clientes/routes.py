import re

from flask import Blueprint, render_template, request, jsonify

from app.extensions import db
from app.models import Cliente, Venda
from app.utils import token_requerido, pagina_login_requerida, registrar_log, validar_cpf, formatar_cpf

clientes_bp = Blueprint("clientes", __name__, url_prefix="/clientes")


@clientes_bp.route("")
@pagina_login_requerida
def pagina_lista():
    return render_template("clientes/lista.html")


@clientes_bp.route("/<int:cliente_id>")
@pagina_login_requerida
def pagina_detalhe(cliente_id):
    return render_template("clientes/detalhe.html", cliente_id=cliente_id)


@clientes_bp.route("/api", methods=["GET"])
@token_requerido
def api_listar_clientes():
    termo = (request.args.get("q") or "").strip()
    pagina = request.args.get("pagina", type=int)

    query = Cliente.query
    if termo:
        like = f"%{termo}%"
        cpf_numerico = re.sub(r"\D", "", termo)
        condicoes = [Cliente.nome.ilike(like), Cliente.telefone.ilike(like)]
        if cpf_numerico:
            condicoes.append(Cliente.cpf.ilike(f"%{cpf_numerico}%"))
        query = query.filter(db.or_(*condicoes))
    query = query.order_by(Cliente.nome)

    if pagina:
        por_pagina = 20
        total = query.count()
        clientes = query.offset((pagina - 1) * por_pagina).limit(por_pagina).all()
        return jsonify({
            "itens": [c.to_dict() for c in clientes],
            "total": total,
            "pagina": pagina,
            "paginas": max(1, (total + por_pagina - 1) // por_pagina),
        })

    clientes = query.limit(200).all()
    return jsonify([c.to_dict() for c in clientes])


@clientes_bp.route("/api/<int:cliente_id>", methods=["GET"])
@token_requerido
def api_obter_cliente(cliente_id):
    cliente = db.session.get(Cliente, cliente_id)
    if not cliente:
        return jsonify({"erro": "Cliente não encontrado."}), 404
    data = cliente.to_dict()
    vendas = Venda.query.filter_by(cliente_id=cliente_id).order_by(Venda.criado_em.desc()).all()
    data["historico_compras"] = [v.to_dict(detalhado=False) for v in vendas]
    return jsonify(data)


def _validar_payload_cliente(dados, cliente_id=None):
    nome = (dados.get("nome") or "").strip()
    if not nome:
        return None, "Informe o nome do cliente."

    cpf = re.sub(r"\D", "", dados.get("cpf") or "")
    if cpf and not validar_cpf(cpf):
        return None, "CPF inválido. Verifique os dígitos informados."
    if cpf:
        existente = Cliente.query.filter(Cliente.cpf == cpf, Cliente.id != cliente_id).first()
        if existente:
            return None, "Já existe um cliente cadastrado com esse CPF."

    return {
        "nome": nome,
        "telefone": (dados.get("telefone") or "").strip() or None,
        "cpf": cpf or None,
        "rua": (dados.get("rua") or "").strip() or None,
        "numero": (dados.get("numero") or "").strip() or None,
        "bairro": (dados.get("bairro") or "").strip() or None,
        "cidade": (dados.get("cidade") or "").strip() or None,
        "estado": (dados.get("estado") or "").strip().upper()[:2] or None,
        "cep": (dados.get("cep") or "").strip() or None,
        "complemento": (dados.get("complemento") or "").strip() or None,
    }, None


@clientes_bp.route("/api", methods=["POST"])
@token_requerido
def api_criar_cliente():
    dados = request.get_json(silent=True) or {}
    validado, erro = _validar_payload_cliente(dados)
    if erro:
        return jsonify({"erro": erro}), 400

    cliente = Cliente(**validado)
    db.session.add(cliente)
    registrar_log("cliente_criado", f"Cliente '{cliente.nome}' cadastrado.")
    db.session.commit()
    return jsonify(cliente.to_dict()), 201


@clientes_bp.route("/api/<int:cliente_id>", methods=["PUT"])
@token_requerido
def api_atualizar_cliente(cliente_id):
    cliente = db.session.get(Cliente, cliente_id)
    if not cliente:
        return jsonify({"erro": "Cliente não encontrado."}), 404

    dados = request.get_json(silent=True) or {}
    validado, erro = _validar_payload_cliente(dados, cliente_id=cliente_id)
    if erro:
        return jsonify({"erro": erro}), 400

    for campo, valor in validado.items():
        setattr(cliente, campo, valor)

    registrar_log("cliente_editado", f"Cliente '{cliente.nome}' (#{cliente.id}) editado.")
    db.session.commit()
    return jsonify(cliente.to_dict())


@clientes_bp.route("/api/<int:cliente_id>", methods=["DELETE"])
@token_requerido
def api_excluir_cliente(cliente_id):
    cliente = db.session.get(Cliente, cliente_id)
    if not cliente:
        return jsonify({"erro": "Cliente não encontrado."}), 404

    if Venda.query.filter_by(cliente_id=cliente_id).first():
        return jsonify({"erro": "Este cliente possui vendas registradas e não pode ser excluído."}), 400

    nome = cliente.nome
    db.session.delete(cliente)
    registrar_log("cliente_excluido", f"Cliente '{nome}' excluído.")
    db.session.commit()
    return jsonify({"ok": True})
