import os
import secrets
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")


def _obter_ou_criar_chave(nome_variavel_ambiente, nome_arquivo):
    """Usa a chave definida em variável de ambiente/`.env` se existir; caso
    contrário, gera uma chave aleatória única na primeira execução e a
    guarda em `instance/`, para que a instalação continue segura mesmo sem
    configuração manual por parte de quem for operar a loja."""
    valor_ambiente = os.environ.get(nome_variavel_ambiente)
    if valor_ambiente:
        return valor_ambiente

    os.makedirs(INSTANCE_DIR, exist_ok=True)
    caminho = os.path.join(INSTANCE_DIR, nome_arquivo)
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as arquivo:
            chave = arquivo.read().strip()
            if chave:
                return chave

    chave = secrets.token_hex(32)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(chave)
    return chave


class Config:
    SECRET_KEY = _obter_ou_criar_chave("SECRET_KEY", ".secret_key")
    JWT_SECRET_KEY = _obter_ou_criar_chave("JWT_SECRET_KEY", ".jwt_secret_key")
    JWT_EXPIRATION = timedelta(hours=24)

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(INSTANCE_DIR, "jennifer.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads")
    BARCODE_FOLDER = os.path.join(BASE_DIR, "app", "static", "barcodes")
    # Comprovantes ficam fora de app/static/ (que é servido sem autenticação)
    # porque contêm dados financeiros e do cliente — só saem por rota protegida.
    COMPROVANTES_VENDAS_FOLDER = os.path.join(INSTANCE_DIR, "comprovantes", "vendas")
    COMPROVANTES_PAGAMENTOS_FOLDER = os.path.join(INSTANCE_DIR, "comprovantes", "pagamentos")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    ESTOQUE_BAIXO_PADRAO = 5

    RATELIMIT_STORAGE_URI = "memory://"
