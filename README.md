# Jennifer Moda Fitness — Gestão de Estoque + PDV

Sistema interno (painel administrativo + ponto de venda) para a loja física **Jennifer Moda Fitness**. Não é uma loja virtual — é uma ferramenta de uso exclusivo da equipe da loja.

## Stack

- Python + Flask (Blueprints por domínio)
- SQLAlchemy + SQLite + Flask-Migrate (Alembic)
- Autenticação JWT (`x-access-token`) + sessão de navegador + Flask-Bcrypt
- Flask-Limiter (rate limiting no login)
- Bootstrap 5 + Chart.js + JS puro (sem SPA)

## Instalação no computador da loja (produção)

O sistema roda direto no computador da loja e fica disponível para outros aparelhos (celular, tablet) na mesma rede Wi-Fi — não precisa de internet nem de servidor externo.

1. Copie a pasta inteira do sistema para o computador da loja.
2. Se o computador não tiver Python, instale em [python.org/downloads](https://www.python.org/downloads/) marcando a opção **"Add Python to PATH"** durante a instalação.
3. Dê **duplo clique em `Instalar.bat`**. Ele vai preparar tudo sozinho e, ao final, pedir para criar o primeiro usuário administrador (nome, e-mail e senha) — anote essa senha em local seguro, pois é o acesso principal do sistema.
4. Pronto. Nos dias seguintes, para abrir o sistema, dê **duplo clique em `Iniciar Sistema.bat`** — ele mostra o endereço para acessar do próprio computador e o endereço para acessar de outros aparelhos da loja.

> **Não feche** a janela preta que abre com `Iniciar Sistema.bat` enquanto o sistema estiver em uso — ela é o "motor" rodando. Fechar essa janela desliga o sistema para todo mundo.

### Firewall do Windows

Na primeira vez que rodar `Iniciar Sistema.bat`, o Windows pode perguntar se permite que o Python acesse redes públicas/privadas. Clique em **"Permitir acesso"** — sem isso, outros aparelhos da loja não conseguem se conectar (só funcionará no próprio computador).

### Chaves de segurança

Na primeira vez que o sistema roda, ele gera automaticamente chaves de segurança únicas para aquele computador (guardadas em `instance/.secret_key` e `instance/.jwt_secret_key`) — não é preciso configurar nada manualmente. Não copie esses arquivos para outro computador nem os compartilhe.

### Backup

Todos os dados (produtos, vendas, clientes, caixa) ficam num único arquivo: `instance/jennifer.db`. Faça uma cópia periódica desse arquivo (ex: para um pendrive ou nuvem) — é o que garante que nada se perde se o computador tiver problema.

---

## Instalação manual (desenvolvimento)

Para quem for mexer no código-fonte, sem usar os atalhos `.bat`:

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

set FLASK_APP=run.py
flask db upgrade

python seed.py                 # cria o primeiro usuário (admin)
python run.py                  # servidor de desenvolvimento, com recarregamento automático
```

Acesse `http://localhost:5000`. **Não use `run.py` para atender a loja de verdade** — ele expõe telas de erro técnicas e não foi feito para uso contínuo. Para isso existe `iniciar_producao.py` (é o que os atalhos `.bat` chamam por baixo dos panos).

## Logo

Coloque o arquivo da logo em `app/static/img/logo.png` (círculo, fundo transparente ou rosa). Se o arquivo não existir, o sistema usa automaticamente um logo em texto estilizado como alternativa — nenhuma configuração adicional é necessária.

## Estrutura de pastas

```
app/
  blueprints/       # um pacote por módulo (auth, produtos, vendas, clientes, caixa, cupons, usuarios, relatorios, entregas, logs)
  models.py         # modelos SQLAlchemy
  utils.py          # JWT, moeda BRL, validação de CPF, logs, código de barras
  templates/         # HTML por módulo
  static/            # CSS, JS, uploads de imagens, códigos de barra gerados
migrations/          # histórico de migrações Alembic
seed.py              # criação do primeiro admin (via terminal)
run.py               # servidor de desenvolvimento
iniciar_producao.py  # servidor usado no dia a dia da loja (Waitress)
Instalar.bat         # instalação com um clique (Windows)
Iniciar Sistema.bat  # abrir o sistema no dia a dia (Windows)
```

## Módulos

- **PDV (Nova Venda)** — busca por nome/SKU/código de barras, múltiplos pagamentos, cupom, cliente, entrega (retirada ou motoboy), recibo imprimível, reembolso (admin).
- **Produtos & Estoque** — variações por cor/tamanho, SKU e código de barras automáticos, imagens, edição rápida de preço/estoque, categorias, soft delete.
- **Clientes** — cadastro com validação de CPF, busca rápida, histórico de compras.
- **Cupons** — percentual ou valor fixo, aplicável ao total ou a produtos específicos, ativar/desativar.
- **Entregas** — vendas com motoboy, status (pendente → saiu → entregue), relatório por período.
- **Caixa** *(admin)* — saldo automático, lançamentos manuais (sangria, despesa, ajuste) sempre com observação obrigatória.
- **Usuários** *(admin)* — criação/edição de vendedores, ativar/desativar, redefinir senha.
- **Relatórios** *(admin)* — KPIs, gráficos de vendas e formas de pagamento, ranking de produtos e vendedores, lucro bruto calculado com o custo histórico de cada item vendido.
- **Logs de Atividade** *(admin)* — histórico de ações sensíveis (login, vendas, exclusões, ajustes de caixa etc.).

## Regras de negócio importantes

- Estoque nunca fica negativo em nenhuma operação.
- Produtos são excluídos com soft delete — vendas antigas preservam o histórico.
- O lucro em relatórios usa o preço de custo **no momento da venda**, não o custo atual do produto.
- SKU é gerado de forma determinística a partir de nome + cor + tamanho, com checagem de duplicidade.
- Todo lançamento manual de caixa exige observação.
- Valores monetários são exibidos sempre no padrão brasileiro (`R$ 1.234,56`).
