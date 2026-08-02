"""
Script para criar o primeiro usuário administrador do sistema.

Uso:
    python seed.py
"""
import getpass
import re

from app import create_app
from app.extensions import db
from app.models import Usuario


def main():
    app = create_app()
    with app.app_context():
        if Usuario.query.count() > 0:
            print("Já existem usuários cadastrados. Use a tela 'Gerenciar Usuários' (login como admin) para criar novos vendedores.")
            return

        print("=== Criação do primeiro usuário administrador — Jennifer Moda Fitness ===")
        nome = input("Nome completo: ").strip()
        while not nome:
            nome = input("Nome completo (obrigatório): ").strip()

        email = input("E-mail: ").strip().lower()
        while not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            email = input("E-mail inválido. Informe novamente: ").strip().lower()

        senha = getpass.getpass("Senha (mín. 6 caracteres): ")
        while len(senha) < 6:
            senha = getpass.getpass("Senha muito curta. Informe uma senha com 6+ caracteres: ")

        usuario = Usuario(nome=nome, email=email, papel="admin", ativo=True)
        usuario.set_senha(senha)
        db.session.add(usuario)
        db.session.commit()

        print(f"\nUsuário administrador '{nome}' criado com sucesso! Já pode fazer login no sistema.")


if __name__ == "__main__":
    main()
