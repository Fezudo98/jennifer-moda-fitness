"""
Inicia o sistema Jennifer Moda Fitness para uso real na loja.

Diferente de `run.py` (usado só durante o desenvolvimento), este script:
  - usa um servidor adequado para rodar o dia inteiro (Waitress), em vez do
    servidor de testes do Flask;
  - não expõe telas de erro técnicas para quem estiver usando o sistema;
  - fica acessível para outros aparelhos (celular, tablet) na mesma rede
    Wi-Fi/cabo da loja;
  - abre o navegador sozinho neste computador e mostra o endereço para
    copiar em outros aparelhos.

Uso:
    python iniciar_producao.py
"""
import socket
import threading
import webbrowser

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


def abrir_navegador_local():
    try:
        webbrowser.open(f"http://localhost:{PORTA}")
    except Exception:
        pass  # Se não conseguir abrir sozinho, a lojista pode copiar o endereço mostrado acima.


def main():
    app = create_app()
    ip_local = descobrir_ip_local()
    url_local = f"http://localhost:{PORTA}"
    url_rede = f"http://{ip_local}:{PORTA}"

    print()
    print("=" * 62)
    print("  Jennifer Moda Fitness — Sistema iniciado com sucesso!")
    print("=" * 62)
    print()
    print("  Endereço para usar NESTE computador (vai abrir sozinho):")
    print(f"  {url_local}")
    print()
    print("  Endereço para copiar e usar em CELULAR/TABLET da loja")
    print("  (aparelho precisa estar na mesma rede Wi-Fi):")
    print(f"  {url_rede}")
    print()
    print("  Dica para copiar: selecione o endereço com o mouse e")
    print("  aperte Enter, ou clique com o botão direito nesta janela.")
    print("=" * 62)
    print("  NÃO FECHE esta janela enquanto o sistema estiver em uso.")
    print("  Para desligar o sistema, feche esta janela ou aperte Ctrl+C.")
    print("=" * 62)
    print()

    threading.Timer(1.5, abrir_navegador_local).start()
    serve(app, host="0.0.0.0", port=PORTA, threads=8)


if __name__ == "__main__":
    main()
