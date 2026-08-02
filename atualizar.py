"""
Busca e aplica atualizações do sistema a partir do repositório Git antes de
iniciar. Se não houver internet, o repositório estiver indisponível, ou
qualquer outro problema acontecer, o sistema segue com a versão que já está
instalada — a loja nunca fica impedida de abrir por causa de uma atualização.

Chamado automaticamente por "Iniciar Sistema.bat". Também pode ser rodado
manualmente:
    python atualizar.py
"""
import os
import subprocess
import sys

TIMEOUT_SEGUNDOS = 20


def _rodar(comando, env=None):
    try:
        resultado = subprocess.run(
            comando, capture_output=True, text=True, timeout=TIMEOUT_SEGUNDOS, env=env
        )
        return resultado.returncode == 0, resultado.stdout.strip(), resultado.stderr.strip()
    except Exception as e:
        return False, "", str(e)


def main():
    if not os.path.isdir(".git"):
        print("Este sistema não foi instalado via Git — atualização automática desativada.")
        return

    print("Procurando atualizações...")
    ok_antes, commit_antes, _ = _rodar(["git", "rev-parse", "HEAD"])

    ok_pull, saida_pull, erro_pull = _rodar(["git", "pull", "--ff-only"])
    if not ok_pull:
        print("Não foi possível buscar atualizações agora (sem internet ou repositório indisponível).")
        print("Abrindo o sistema com a versão que já está instalada.")
        return

    ok_depois, commit_depois, _ = _rodar(["git", "rev-parse", "HEAD"])

    if ok_antes and ok_depois and commit_antes == commit_depois:
        print("Sistema já está com a versão mais recente.")
        return

    print("Nova versão encontrada! Atualizando componentes...")
    _rodar([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"])

    env_flask = dict(os.environ, FLASK_APP="run.py")
    ok_db, _, erro_db = _rodar([sys.executable, "-m", "flask", "db", "upgrade"], env=env_flask)
    if not ok_db:
        print("[aviso] Não foi possível atualizar o banco de dados automaticamente:")
        print(erro_db)
        print("Se o sistema não abrir corretamente, avise o suporte técnico.")

    print("Atualização concluída.")


if __name__ == "__main__":
    main()
