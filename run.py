import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Modo de desenvolvimento (com recarregamento automático e depurador).
    # NUNCA use este arquivo para atender a loja no dia a dia — use
    # `iniciar_producao.py` (ou o atalho "Iniciar Sistema.bat"), que roda
    # um servidor adequado para uso real e sem expor detalhes técnicos.
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(debug=debug, host="0.0.0.0", port=5000)
