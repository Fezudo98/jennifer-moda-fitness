import io
import os
import re
from functools import wraps

import jwt
from flask import current_app, jsonify, request, session

from app.extensions import db


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------

class ValorInvalidoError(ValueError):
    pass


def parse_decimal_br(valor):
    """Converte um valor numérico (str, int, float) em Decimal aceitando tanto
    o formato brasileiro (vírgula decimal, ex: '35,50' ou '1.234,56') quanto o
    formato com ponto (ex: '35.50'). Lança ValorInvalidoError se não for possível
    interpretar o valor."""
    from decimal import Decimal, InvalidOperation

    if valor is None or valor == "":
        raise ValorInvalidoError("Valor não informado.")

    if isinstance(valor, (int, float, Decimal)):
        texto = str(valor)
    else:
        texto = str(valor).strip()

    if not texto:
        raise ValorInvalidoError("Valor não informado.")

    if "," in texto:
        # Formato brasileiro: ponto é separador de milhar, vírgula é decimal.
        texto = texto.replace(".", "").replace(",", ".")

    try:
        return Decimal(texto)
    except InvalidOperation:
        raise ValorInvalidoError(f"Valor numérico inválido: '{valor}'.")


def formatar_moeda(valor) -> str:
    """Formata um número no padrão brasileiro: R$ 1.234,56"""
    valor = float(valor or 0)
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def validar_cpf(cpf: str) -> bool:
    if not cpf:
        return True  # CPF é opcional
    cpf = re.sub(r"\D", "", cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = (soma * 10) % 11
    resto = 0 if resto == 10 else resto
    if resto != int(cpf[9]):
        return False

    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = (soma * 10) % 11
    resto = 0 if resto == 10 else resto
    if resto != int(cpf[10]):
        return False

    return True


def formatar_data_br(valor) -> str:
    """Formata um datetime no padrão brasileiro: 31/12/2026 23:59"""
    if not valor:
        return "-"
    return valor.strftime("%d/%m/%Y %H:%M")


def formatar_cpf(cpf: str) -> str:
    cpf = re.sub(r"\D", "", cpf or "")
    if len(cpf) != 11:
        return cpf
    return f"{cpf[0:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:11]}"


# ---------------------------------------------------------------------------
# Autenticação JWT
# ---------------------------------------------------------------------------

def gerar_token(usuario):
    import datetime as dt

    payload = {
        "usuario_id": usuario.id,
        "papel": usuario.papel,
        "exp": dt.datetime.utcnow() + current_app.config["JWT_EXPIRATION"],
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def token_requerido(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        from app.models import Usuario

        token = request.headers.get("x-access-token")
        if not token:
            return jsonify({"erro": "Token de acesso ausente. Faça login novamente."}), 401
        try:
            dados = jwt.decode(token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
            usuario = db.session.get(Usuario, dados["usuario_id"])
            if not usuario or not usuario.ativo:
                return jsonify({"erro": "Usuário inválido ou desativado."}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({"erro": "Sessão expirada. Faça login novamente."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"erro": "Token inválido. Faça login novamente."}), 401

        request.usuario_atual = usuario
        return f(*args, **kwargs)

    return decorador


def admin_requerido(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        usuario = getattr(request, "usuario_atual", None)
        if not usuario or not usuario.is_admin:
            return jsonify({"erro": "Apenas administradores podem realizar esta ação."}), 403
        return f(*args, **kwargs)

    return decorador


def pagina_login_requerida(f):
    """Protege rotas de página (HTML) verificando a sessão do navegador."""

    @wraps(f)
    def decorador(*args, **kwargs):
        from flask import redirect, url_for

        if not session.get("usuario_id"):
            return redirect(url_for("auth.pagina_login", proximo=request.path))
        return f(*args, **kwargs)

    return decorador


def usuario_da_sessao():
    """Retorna o Usuario logado via sessão de navegador (não JWT). Usado em
    rotas que servem arquivos para download por navegação direta (<a href>),
    onde o cabeçalho x-access-token não é enviado pelo navegador."""
    from app.models import Usuario

    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return None
    return db.session.get(Usuario, usuario_id)


def pagina_admin_requerida(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        from flask import redirect, url_for

        if not session.get("usuario_id"):
            return redirect(url_for("auth.pagina_login", proximo=request.path))
        if session.get("papel") != "admin":
            return redirect(url_for("home.pagina_home"))
        return f(*args, **kwargs)

    return decorador


# ---------------------------------------------------------------------------
# Log de atividades
# ---------------------------------------------------------------------------

def registrar_log(acao: str, detalhes: str = None, usuario_id: int = None):
    from app.models import LogAtividade

    if usuario_id is None:
        usuario_id = getattr(getattr(request, "usuario_atual", None), "id", None) or session.get("usuario_id")

    log = LogAtividade(usuario_id=usuario_id, acao=acao, detalhes=detalhes)
    db.session.add(log)


# ---------------------------------------------------------------------------
# Código de barras
# ---------------------------------------------------------------------------

def gerar_codigo_barras_imagem(codigo: str) -> str:
    """Gera um PNG Code128 para o código informado e retorna o caminho relativo em static/."""
    import barcode
    from barcode.writer import ImageWriter

    pasta = current_app.config["BARCODE_FOLDER"]
    os.makedirs(pasta, exist_ok=True)
    caminho_base = os.path.join(pasta, codigo)

    code128 = barcode.get("code128", codigo, writer=ImageWriter())
    code128.save(caminho_base, options={"write_text": True, "module_height": 10.0, "font_size": 8})

    return f"barcodes/{codigo}.png"


def proximo_codigo_barras() -> str:
    """Gera um código numérico sequencial simples usado como código de barras."""
    import time

    return str(int(time.time() * 1000))[-12:]


def proximo_numero_venda() -> str:
    from app.models import Venda

    ultimo = db.session.query(db.func.max(Venda.id)).scalar() or 0
    return f"V{ultimo + 1:06d}"


# ---------------------------------------------------------------------------
# Comprovante de venda (PDF)
# ---------------------------------------------------------------------------

def caminho_comprovante_venda(venda_id: int) -> str:
    pasta = current_app.config["COMPROVANTES_VENDAS_FOLDER"]
    return os.path.join(pasta, f"venda_{venda_id}.pdf")


ROTULOS_FORMA_PAGAMENTO = {
    "dinheiro": "Dinheiro",
    "pix": "PIX",
    "cartao_credito": "Cartão de Crédito",
    "cartao_debito": "Cartão de Débito",
}


def gerar_comprovante_pdf(venda) -> str:
    """Gera (ou regenera) o PDF do comprovante de uma venda e o guarda em
    disco. Retorna o caminho do arquivo. Falhas aqui nunca devem impedir a
    venda de ser concluída — quem chama deve tratar exceções."""
    from flask import render_template
    from xhtml2pdf import pisa

    caminho_logo = os.path.join(current_app.root_path, "static", "img", "logo.png")
    if not os.path.exists(caminho_logo):
        caminho_logo = None

    html = render_template(
        "vendas/recibo_pdf.html",
        v=venda,
        rotulos_forma=ROTULOS_FORMA_PAGAMENTO,
        caminho_logo=caminho_logo,
    )

    pasta = current_app.config["COMPROVANTES_VENDAS_FOLDER"]
    os.makedirs(pasta, exist_ok=True)
    caminho = caminho_comprovante_venda(venda.id)

    with open(caminho, "wb") as arquivo:
        resultado = pisa.CreatePDF(html, dest=arquivo, encoding="utf-8")

    if resultado.err:
        raise RuntimeError(f"Falha ao gerar PDF do comprovante da venda {venda.numero}.")

    return caminho
