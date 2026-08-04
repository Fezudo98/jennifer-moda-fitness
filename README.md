# Jennifer Moda Fitness — Gestão de Estoque + PDV

Sistema interno (painel administrativo + ponto de venda) para a loja física **Jennifer Moda Fitness**. Não é uma loja virtual — é uma ferramenta de uso exclusivo da equipe da loja.

## Stack

- Python + Flask (Blueprints por domínio)
- SQLAlchemy + SQLite + Flask-Migrate (Alembic)
- Autenticação JWT (`x-access-token`) + sessão de navegador + Flask-Bcrypt
- Flask-Limiter (rate limiting no login)
- Bootstrap 5 + Chart.js + JS puro (sem SPA)

## Instalação no computador da loja (produção)

O sistema roda direto no computador da loja e fica disponível para outros aparelhos (celular, tablet) na mesma rede Wi-Fi. O código vem do repositório público [github.com/Fezudo98/jennifer-moda-fitness](https://github.com/Fezudo98/jennifer-moda-fitness) — assim, atualizações futuras chegam automaticamente sem precisar visitar a loja.

### Instalar

Leve **só o arquivo `Bootstrap-Instalar.bat`** até o computador da cliente — por pendrive, e-mail, WhatsApp etc. O resto do sistema é baixado sozinho, direto do GitHub.

1. Se o computador não tiver **Git**, instale em [git-scm.com/download/win](https://git-scm.com/download/win) (pode deixar tudo no padrão durante a instalação).
2. Se não tiver **Python**, instale em [python.org/downloads](https://www.python.org/downloads/) marcando a opção **"Add Python to PATH"**.
3. Dê **duplo clique em `Bootstrap-Instalar.bat`**. Ele baixa o sistema, prepara tudo, e ao final pede para criar o primeiro usuário administrador (nome, e-mail, senha) — anote essa senha em local seguro.
4. Pronto. Nos dias seguintes, para abrir o sistema, dê **duplo clique em `Iniciar Sistema.bat`** (fica dentro da pasta `Jennifer Moda Fitness` que foi criada na Área de Trabalho).

> **Não feche** a janela preta que abre com `Iniciar Sistema.bat` enquanto o sistema estiver em uso — ela é o "motor" rodando. Fechar essa janela desliga o sistema para todo mundo.

### Como funcionam as atualizações à distância

Toda vez que `Iniciar Sistema.bat` é aberto, ele busca a versão mais recente do repositório automaticamente antes de iniciar. Quando você (desenvolvedor) enviar melhorias com `git push`, elas chegam sozinhas na próxima vez que a loja abrir o sistema — não precisa reinstalar nem visitar o local.

- **Sem internet no momento?** O sistema não trava — ele simplesmente abre com a última versão já instalada e tenta de novo na próxima vez.
- Depois de um `git push` seu, **não é necessário** rodar nenhum comando na máquina da cliente — só reabrir o sistema já atualiza.
- Sempre que enviar uma atualização, crie também uma tag de versão (ex: `git tag -a v1.1.0 -m "..."` seguido de `git push origin v1.1.0`), para manter o histórico rastreável.

### Firewall do Windows

Na primeira vez que rodar `Iniciar Sistema.bat`, o Windows pode perguntar se permite que o Python acesse redes públicas/privadas. Clique em **"Permitir acesso"** — sem isso, outros aparelhos da loja não conseguem se conectar (só funcionará no próprio computador).

### Chaves de segurança

Na primeira vez que o sistema roda, ele gera automaticamente chaves de segurança únicas para aquele computador (guardadas em `instance/.secret_key` e `instance/.jwt_secret_key`) — não é preciso configurar nada manualmente. Não copie esses arquivos para outro computador nem os compartilhe.

### Backup

Todos os dados (produtos, vendas, clientes, caixa) ficam num único arquivo: `instance/jennifer.db`. Os comprovantes de venda em PDF e os anexos de pagamento (foto da maquininha/Pix) ficam em `instance/comprovantes/`. Faça uma cópia periódica de toda a pasta `instance/` (ex: para um pendrive ou nuvem) — é o que garante que nada se perde se o computador tiver problema.

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
migrations/              # histórico de migrações Alembic
seed.py                  # criação do primeiro admin (via terminal)
run.py                   # servidor de desenvolvimento
iniciar_producao.py      # servidor usado no dia a dia da loja (Waitress)
atualizar.py             # busca atualizações do Git antes de iniciar (com fallback offline)
Bootstrap-Instalar.bat   # único arquivo levado manualmente à loja — clona o repositório
Instalar.bat             # prepara o ambiente (chamado pelo Bootstrap)
Iniciar Sistema.bat      # abrir o sistema no dia a dia (atualiza sozinho antes de abrir)
```

## Módulos

- **PDV (Nova Venda)** — busca por nome/SKU/código de barras, múltiplos pagamentos, cupom, cliente, entrega (retirada ou motoboy), recibo imprimível, comprovante em PDF gerado e guardado automaticamente a cada venda, anexo do comprovante da maquininha/Pix por pagamento, reembolso (admin).
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
