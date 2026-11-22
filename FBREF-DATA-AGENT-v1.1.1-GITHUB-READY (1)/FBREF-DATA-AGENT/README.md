# FBREF DATA AGENT — MatchEdge Arena

Agente Python + MySQL + API REST + painel web. Configuração selecionada:
- Fontes: FBref + fontes complementares autorizadas (`fbref_plus`)
- Execução: aplicação web e serviço Python (`both`)
- Cobertura: catálogo dinâmico de todas as competições expostas pelos provedores ligados (`all`)

## Aviso essencial sobre FBref
O FBref/Sports Reference proíbe o acesso automatizado sem autorização expressa e restringe a criação de bases de dados/serviços substitutos e o uso dos seus dados para treinar ou orientar modelos de IA. Por isso, este projeto **não faz scraping automático do FBref**. O conector FBref aceita CSVs/ficheiros obtidos legalmente e autorizados por si, e mantém a proveniência dos dados. Para recolha automática, obtenha licença/autorização escrita do fornecedor e implemente a integração aprovada.

Fontes complementares incluídas:
- football-data.org: competições, jogos, equipas, classificações e marcadores, conforme o plano/token e cobertura disponíveis.
- StatsBomb Open Data: competições e dados detalhados de eventos apenas nas competições/épocas que a StatsBomb disponibiliza publicamente para investigação e análise. Respeite a atribuição e os termos do repositório.

"Todas as competições" significa todas as competições que as fontes conectadas disponibilizam, não literalmente todas as ligas do mundo nem todas as métricas de FBref. A disponibilidade varia por fornecedor, plano, época e licença.

## Requisitos
- Docker Desktop + Docker Compose (recomendado) ou Python 3.11+
- Token de football-data.org opcional: https://www.football-data.org/
- Acesso à Internet para sincronizar fontes externas.

## Arranque rápido (Windows 10/11)
1. Descompacte o projeto.
2. Copie `.env.example` para `.env`.
3. (Opcional) preencha `FOOTBALL_DATA_TOKEN`.
4. Abra PowerShell na pasta do projeto e execute:

```powershell
docker compose up --build -d
```

5. Abra:
- Painel: http://localhost:8000
- Documentação API: http://localhost:8000/docs
- Saúde: http://localhost:8000/api/health

Para parar: `docker compose down`
Para apagar também a base de dados: `docker compose down -v` (apaga os dados persistidos).

## Execução sem Docker
```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Configure .env e garanta que existe um MySQL acessível
uvicorn app.main:app --reload
```

## Primeira sincronização
No painel, clique em **Sincronizar fontes** ou use:
```bash
curl -X POST http://localhost:8000/api/admin/sync
```
Os endpoints administrativos exigem `X-API-Key` se `ADMIN_API_KEY` estiver definido:
```bash
curl -X POST http://localhost:8000/api/admin/sync -H "X-API-Key: change-this-key"
```

Importar um CSV FBref obtido com autorização:
```bash
curl -X POST "http://localhost:8000/api/import/fbref?dataset=standard&season=2025-2026&competition=Premier%20League" ^
  -H "X-API-Key: change-this-key" ^
  -F "file=@team_stats.csv"
```
A importação guarda cada linha como registo bruto normalizado, preservando colunas, fonte, época e competição. O formato CSV deve conter cabeçalhos. O sistema não contorna login, paywall, CAPTCHA ou bloqueios.

## API principal
- `GET /api/health`
- `GET /api/overview`
- `GET /api/competitions`
- `GET /api/teams?search=Arsenal`
- `GET /api/players?search=Salah`
- `GET /api/matches?competition=PL&season=2025`
- `GET /api/records?source=statsbomb&dataset=events&limit=100`
- `POST /api/admin/sync`
- `POST /api/import/fbref` (multipart CSV; chave administrativa)
- `GET /api/sources`
- `GET /api/intelligence/teams/compare?home=Arsenal&away=Chelsea` — comparação histórica
- `GET /api/intelligence/players/similar?player=Player%20Name` — similaridade exploratória com CSV FBref importado
- `GET /api/predictions/match?home=Arsenal&away=Chelsea` — probabilidades Poisson (estimativas)

As respostas incluem metadados de origem e atualização. Use paginação `limit`/`offset` nos endpoints de registos.

## Inteligência e previsões (primeira versão)
- Team Intelligence: vitórias, empates, derrotas, golos, diferença de golos e pontos por jogo com base nos jogos concluídos armazenados.
- Player Scouting: encontra jogadores semelhantes por cosseno usando colunas numéricas presentes nos CSVs FBref importados. A comparação é exploratória e ainda não normaliza métricas por posição/90 minutos.
- Prediction Engine: estimativas 1X2, over 1.5/2.5/3.5, BTTS, golos esperados e placares mais prováveis usando distribuição de Poisson e histórico local. Requer jogos suficientes na base; não é garantia.
- Não calcula xG, xA, mapas de calor ou VAEP a partir de CSVs genéricos: essas métricas dependem de colunas específicas ou dados de eventos adequados.

## Arquitetura
- `app/sources/`: adaptadores por fornecedor.
- `app/services/`: orquestração, importação e scheduler.
- `app/models.py`: modelos MySQL.
- `app/api.py`: endpoints REST.
- `web/`: painel administrativo leve.
- `data/`: área de trabalho local (não versionar dados licenciados).

## Produção
Antes de expor na Internet: use HTTPS, segredos fortes, firewall, backups, monitorização, limites de taxa, autenticação de utilizadores/roles, política de retenção e revisão das licenças. `ADMIN_API_KEY` é uma proteção simples para ambiente inicial, não substitui autenticação empresarial.

## Intelligence API (v1.1)

Estes endpoints analisam os dados que já existem na base de dados; não criam estatísticas que a fonte não forneceu:

- `GET /api/intelligence/teams/compare?home=Arsenal&away=Chelsea` — histórico agregado das duas equipas.
- `GET /api/intelligence/players/similar?player=Player%20Name` — similaridade exploratória com base em métricas numéricas de CSVs FBref importados.
- `GET /api/predictions/match?home=Arsenal&away=Chelsea` — estimativa Poisson simples com jogos concluídos disponíveis.

As previsões são experimentais, dependem da qualidade e dimensão da amostra e não são garantias. A similaridade de jogadores ainda não faz normalização por posição, idade ou competição. Métricas como xG, xA, mapas de calor e VAEP só devem ser calculadas quando a fonte fornecer os dados necessários.

## Testes e GitHub Actions

Executar localmente:

```bash
pip install -r requirements.txt pytest
python -m compileall -q app
python -m pytest -q
```

O workflow `.github/workflows/tests.yml` executa compilação e testes automaticamente em cada push e pull request. Para ativá-lo, coloque esta pasta num repositório GitHub e faça push.

## Integração no MatchEdge Arena

O agente é um serviço independente. Execute-o na porta 8000 e configure o MatchEdge Arena para consumir a base URL `http://localhost:8000` (ou o endereço interno do serviço na sua infraestrutura). Não copie credenciais para o frontend. Configure `ADMIN_API_KEY` apenas no backend e mantenha a chave fora do Git.
