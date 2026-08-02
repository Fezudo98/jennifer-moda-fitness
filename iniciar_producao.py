"""
Inicia o sistema Jennifer Moda Fitness para uso real na loja.

Diferente de `run.py` (usado só durante o desenvolvimento), este script:
  - usa um servidor adequado para rodar o dia inteiro (Waitress), em vez do
    servidor de testes do Flask;
  - não expõe telas de erro técnicas para quem estiver usando o sistema;
  - fica acessível para outros aparelhos (celular, tablet) na mesma rede
    Wi-Fi/cabo da loja.

Uso:
    python iniciar_producao.py
"""
import socket

from waitress import serve

from app import create_app

PORTA = 5000


def descobrir_ip_local():
    """Tenta descobrir o IP da máquina na rede local, para exibir o
    endereço que outros aparelhos da loja devem usar."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    app = create_app()
    ip_local = descobrir_ip_local()

    print("=" * 60)
    print("  Jennifer Moda Fitness — Sistema iniciado com sucesso!")
    print("=" * 60)
    print(f"  Neste computador, acesse:      http://localhost:{PORTA}")
    print(f"  De outro aparelho na loja:     http://{ip_local}:{PORTA}")
    print("=" * 60)
    print("  NÃO FECHE esta janela enquanto o sistema estiver em uso.")
    print("  Para desligar o sistema, feche esta janela ou pressione Ctrl+C.")
    print("=" * 60)

    serve(app, host="0.0.0.0", port=PORTA, threads=8)


if __name__ == "__main__":
    main()
