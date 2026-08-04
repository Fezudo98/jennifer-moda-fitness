import re
import unicodedata
from datetime import datetime, date

from app.extensions import db, bcrypt


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().upper()
    value = re.sub(r"[\s_-]+", "-", value)
    return value


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False, unique=True, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    papel = db.Column(db.String(20), nullable=False, default="vendedor")  # admin | vendedor
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def set_senha(self, senha: str):
        self.senha_hash = bcrypt.generate_password_hash(senha).decode("utf-8")

    def checar_senha(self, senha: str) -> bool:
        return bcrypt.check_password_hash(self.senha_hash, senha)

    @property
    def is_admin(self) -> bool:
        return self.papel == "admin"

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "email": self.email,
            "papel": self.papel,
            "ativo": self.ativo,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
        }


class Categoria(db.Model):
    __tablename__ = "categorias"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False, unique=True)

    produtos = db.relationship("Produto", backref="categoria", lazy="select")

    def to_dict(self):
        return {"id": self.id, "nome": self.nome}


class Produto(db.Model):
    __tablename__ = "produtos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categorias.id"), nullable=True)
    descricao = db.Column(db.Text, nullable=True)
    deletado = db.Column(db.Boolean, nullable=False, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    variacoes = db.relationship(
        "ProdutoVariacao", backref="produto", lazy="select", cascade="all, delete-orphan"
    )
    imagens = db.relationship(
        "ProdutoImagem",
        backref="produto",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="ProdutoImagem.ordem",
    )

    def to_dict(self, incluir_variacoes=True):
        data = {
            "id": self.id,
            "nome": self.nome,
            "categoria_id": self.categoria_id,
            "categoria_nome": self.categoria.nome if self.categoria else None,
            "descricao": self.descricao,
            "deletado": self.deletado,
            "imagem_capa": next(
                (img.caminho for img in self.imagens if img.capa),
                self.imagens[0].caminho if self.imagens else None,
            ),
            "imagens": [img.to_dict() for img in self.imagens],
        }
        if incluir_variacoes:
            data["variacoes"] = [v.to_dict() for v in self.variacoes if not v.deletado]
        return data


class ProdutoVariacao(db.Model):
    __tablename__ = "produto_variacoes"
    __table_args__ = (db.UniqueConstraint("sku", name="uq_variacao_sku"),)

    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)
    cor = db.Column(db.String(60), nullable=False)
    cor_hex = db.Column(db.String(7), nullable=True)
    tamanho = db.Column(db.String(20), nullable=False)
    sku = db.Column(db.String(120), nullable=False)
    codigo_barras = db.Column(db.String(64), nullable=True, unique=True)
    preco_custo = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    preco_venda = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    quantidade = db.Column(db.Integer, nullable=False, default=0)
    estoque_minimo = db.Column(db.Integer, nullable=False, default=5)
    deletado = db.Column(db.Boolean, nullable=False, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def gerar_sku(nome_produto: str, cor: str, tamanho: str) -> str:
        partes = [slugify(nome_produto), slugify(cor), slugify(tamanho)]
        return "-".join(p for p in partes if p)

    @property
    def estoque_baixo(self) -> bool:
        return self.quantidade <= self.estoque_minimo

    def to_dict(self):
        return {
            "id": self.id,
            "produto_id": self.produto_id,
            "produto_nome": self.produto.nome if self.produto else None,
            "categoria_nome": self.produto.categoria.nome if self.produto and self.produto.categoria else None,
            "cor": self.cor,
            "cor_hex": self.cor_hex,
            "tamanho": self.tamanho,
            "sku": self.sku,
            "codigo_barras": self.codigo_barras,
            "preco_custo": float(self.preco_custo),
            "preco_venda": float(self.preco_venda),
            "quantidade": self.quantidade,
            "estoque_minimo": self.estoque_minimo,
            "estoque_baixo": self.estoque_baixo,
            "imagem_capa": next(
                (img.caminho for img in self.produto.imagens if img.capa),
                self.produto.imagens[0].caminho if self.produto and self.produto.imagens else None,
            ) if self.produto else None,
        }


class ProdutoImagem(db.Model):
    __tablename__ = "produto_imagens"

    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)
    caminho = db.Column(db.String(255), nullable=False)
    capa = db.Column(db.Boolean, nullable=False, default=False)
    ordem = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self):
        return {"id": self.id, "caminho": self.caminho, "capa": self.capa, "ordem": self.ordem}


class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False)
    telefone = db.Column(db.String(20), nullable=True)
    cpf = db.Column(db.String(14), nullable=True, unique=True)
    rua = db.Column(db.String(160), nullable=True)
    numero = db.Column(db.String(20), nullable=True)
    bairro = db.Column(db.String(100), nullable=True)
    cidade = db.Column(db.String(100), nullable=True)
    estado = db.Column(db.String(2), nullable=True)
    cep = db.Column(db.String(9), nullable=True)
    complemento = db.Column(db.String(160), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    vendas = db.relationship("Venda", backref="cliente", lazy="select")

    def endereco_formatado(self) -> str:
        partes = []
        if self.rua:
            end = self.rua
            if self.numero:
                end += f", {self.numero}"
            partes.append(end)
        if self.complemento:
            partes.append(self.complemento)
        if self.bairro:
            partes.append(self.bairro)
        if self.cidade:
            cidade_estado = self.cidade
            if self.estado:
                cidade_estado += f"/{self.estado}"
            partes.append(cidade_estado)
        if self.cep:
            partes.append(f"CEP {self.cep}")
        return " - ".join(partes)

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "telefone": self.telefone,
            "cpf": self.cpf,
            "rua": self.rua,
            "numero": self.numero,
            "bairro": self.bairro,
            "cidade": self.cidade,
            "estado": self.estado,
            "cep": self.cep,
            "complemento": self.complemento,
            "endereco_formatado": self.endereco_formatado(),
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
        }


class Cupom(db.Model):
    __tablename__ = "cupons"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(40), nullable=False, unique=True)
    tipo = db.Column(db.String(20), nullable=False)  # percentual | fixo
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    aplicacao = db.Column(db.String(20), nullable=False, default="total")  # total | produtos
    produto_ids = db.Column(db.String(255), nullable=True)  # csv de produto ids quando aplicacao=produtos
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def ids_produtos(self):
        if not self.produto_ids:
            return []
        return [int(x) for x in self.produto_ids.split(",") if x.strip()]

    def to_dict(self):
        return {
            "id": self.id,
            "codigo": self.codigo,
            "tipo": self.tipo,
            "valor": float(self.valor),
            "aplicacao": self.aplicacao,
            "produto_ids": self.ids_produtos(),
            "ativo": self.ativo,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
        }


class Venda(db.Model):
    __tablename__ = "vendas"

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), nullable=False, unique=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)
    vendedor_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)

    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    desconto = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    cupom_id = db.Column(db.Integer, db.ForeignKey("cupons.id"), nullable=True)

    entrega_tipo = db.Column(db.String(20), nullable=False, default="retirada")  # retirada | motoboy
    entrega_endereco = db.Column(db.String(255), nullable=True)
    entrega_taxa = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    entrega_status = db.Column(db.String(20), nullable=True)  # pendente | saiu | entregue

    reembolsada = db.Column(db.Boolean, nullable=False, default=False)
    reembolsada_em = db.Column(db.DateTime, nullable=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    itens = db.relationship("VendaItem", backref="venda", lazy="select", cascade="all, delete-orphan")
    pagamentos = db.relationship("VendaPagamento", backref="venda", lazy="select", cascade="all, delete-orphan")
    vendedor = db.relationship("Usuario", foreign_keys=[vendedor_id])
    cupom = db.relationship("Cupom", foreign_keys=[cupom_id])

    def to_dict(self, detalhado=True):
        data = {
            "id": self.id,
            "numero": self.numero,
            "cliente_id": self.cliente_id,
            "cliente_nome": self.cliente.nome if self.cliente else "Consumidor Final",
            "vendedor_id": self.vendedor_id,
            "vendedor_nome": self.vendedor.nome if self.vendedor else None,
            "subtotal": float(self.subtotal),
            "desconto": float(self.desconto),
            "total": float(self.total),
            "cupom_codigo": self.cupom.codigo if self.cupom else None,
            "entrega_tipo": self.entrega_tipo,
            "entrega_endereco": self.entrega_endereco,
            "entrega_taxa": float(self.entrega_taxa),
            "entrega_status": self.entrega_status,
            "reembolsada": self.reembolsada,
            "reembolsada_em": self.reembolsada_em.isoformat() if self.reembolsada_em else None,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
        }
        if detalhado:
            data["itens"] = [i.to_dict() for i in self.itens]
            data["pagamentos"] = [p.to_dict() for p in self.pagamentos]
        return data


class VendaItem(db.Model):
    __tablename__ = "venda_itens"

    id = db.Column(db.Integer, primary_key=True)
    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id"), nullable=False)
    variacao_id = db.Column(db.Integer, db.ForeignKey("produto_variacoes.id"), nullable=False)
    produto_nome = db.Column(db.String(160), nullable=False)
    sku = db.Column(db.String(120), nullable=False)
    cor = db.Column(db.String(60), nullable=True)
    tamanho = db.Column(db.String(20), nullable=True)
    quantidade = db.Column(db.Integer, nullable=False)
    preco_venda_unit = db.Column(db.Numeric(10, 2), nullable=False)
    preco_custo_unit = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)

    variacao = db.relationship("ProdutoVariacao", foreign_keys=[variacao_id])

    def to_dict(self):
        return {
            "id": self.id,
            "variacao_id": self.variacao_id,
            "produto_nome": self.produto_nome,
            "sku": self.sku,
            "cor": self.cor,
            "tamanho": self.tamanho,
            "quantidade": self.quantidade,
            "preco_venda_unit": float(self.preco_venda_unit),
            "preco_custo_unit": float(self.preco_custo_unit),
            "subtotal": float(self.subtotal),
        }


class VendaPagamento(db.Model):
    __tablename__ = "venda_pagamentos"

    id = db.Column(db.Integer, primary_key=True)
    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id"), nullable=False)
    forma = db.Column(db.String(20), nullable=False)  # dinheiro | pix | cartao_credito | cartao_debito
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    parcelas = db.Column(db.Integer, nullable=True)
    troco = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    comprovante_arquivo = db.Column(db.String(255), nullable=True)  # comprovante da maquininha/Pix anexado

    def to_dict(self):
        return {
            "id": self.id,
            "forma": self.forma,
            "valor": float(self.valor),
            "parcelas": self.parcelas,
            "troco": float(self.troco),
            "tem_comprovante": bool(self.comprovante_arquivo),
        }


class MovimentacaoCaixa(db.Model):
    __tablename__ = "movimentacoes_caixa"

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(10), nullable=False)  # entrada | saida
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    motivo = db.Column(db.String(60), nullable=False)  # venda | troco | reembolso | sangria | despesa | ajuste
    observacao = db.Column(db.Text, nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id"), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship("Usuario", foreign_keys=[usuario_id])

    def to_dict(self):
        return {
            "id": self.id,
            "tipo": self.tipo,
            "valor": float(self.valor),
            "motivo": self.motivo,
            "observacao": self.observacao,
            "usuario_nome": self.usuario.nome if self.usuario else None,
            "venda_id": self.venda_id,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
        }


class LogAtividade(db.Model):
    __tablename__ = "logs_atividade"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    acao = db.Column(db.String(80), nullable=False)
    detalhes = db.Column(db.Text, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship("Usuario", foreign_keys=[usuario_id])

    def to_dict(self):
        return {
            "id": self.id,
            "usuario_nome": self.usuario.nome if self.usuario else "Sistema",
            "acao": self.acao,
            "detalhes": self.detalhes,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
        }
