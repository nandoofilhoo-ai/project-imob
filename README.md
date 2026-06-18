# Imobi SDR Backend MVP

Este projeto é um cérebro/backend MVP para um agente de pré-atendimento (SDR) imobiliário automatizado. Ele recebe mensagens recebidas de leads, executa regras de qualificação de leads, gera respostas e integra de forma transparente com a Evolution API (WhatsApp) e o Chatwoot (camada de atendimento humano).

A arquitetura de canais está desacoplada e pré-configurada para suportar a **Meta Cloud API** futuramente sem quebras de regras de negócio.

---

## 🏗️ Estrutura do Projeto

A estrutura foi organizada seguindo as melhores práticas e de forma incremental:

```text
├── src/
│   ├── main.py                     # Inicialização do FastAPI e agregação de rotas
│   ├── core/
│   │   ├── config.py               # Configurações via pydantic-settings
│   │   ├── database.py             # Conexão e injeção do banco SQLAlchemy
│   │   └── logger.py               # Logger estruturado em formato JSON
│   ├── models/
│   │   └── db_models.py            # Modelos do PostgreSQL/SQLite (Tabelas)
│   ├── schemas/
│   │   └── schemas.py              # Esquemas de validação Pydantic
│   ├── repositories/
│   │   └── db_repositories.py      # Operações e abstrações de banco de dados
│   ├── integrations/
│   │   └── whatsapp_provider.py    # Provedores de WhatsApp (Evolution, Meta Stub)
│   ├── services/
│   │   ├── chatwoot_client.py      # Integração/Sincronização com Chatwoot
│   │   ├── qualification_service.py # Heurísticas de extração de intenção do lead
│   │   ├── rule_engine.py          # Decisões de negócio (takeover, handoff, perguntas)
│   │   ├── llm_adapter.py          # Prompt builder e adaptador de LLM (OpenAI / Mock)
│   │   └── inbound_orchestrator.py # Orquestração central de entrada (inbound pipeline)
│   ├── api/
│   │   └── routes/
│   │       ├── health.py           # Endpoint de Health Check do sistema e banco
│   │       ├── webhooks.py         # Endpoints para receber webhooks da Evolution/Meta
│   │       ├── debug.py            # Logs e eventos recentes em memória
│   │       ├── testing.py          # Endpoints para simulação de envios e qualificação
│   │       └── channels.py         # Listagem e status dos canais ativos
│   └── seeds/
│       └── seed_data.py            # Script para povoamento do banco de dados (seeds)
├── tests/
│   ├── conftest.py                 # Fixtures do pytest (banco em memória e mock client)
│   ├── test_health.py              # Testes para health check
│   ├── test_evolution.py           # Testes para webhooks e envio da Evolution API
│   ├── test_brain.py               # Testes de heurísticas, regras de negócio e orquestração
│   └── test_chatwoot.py            # Testes de envio de notas e handoff para o Chatwoot
├── Dockerfile                      # Dockerfile para build do container backend
├── docker-compose.yml              # Configuração do banco PostgreSQL e backend
├── .env.example                    # Modelo das variáveis de ambiente
├── .env                            # Arquivo de configurações locais
├── pytest.ini                      # Configurações de execução de testes do pytest
└── requirements.txt                # Dependências Python do projeto
```

---

## ⚡ Como Rodar o Projeto Localmente

### Opção 1: Via Docker Compose (Recomendado para PostgreSQL)

1. Certifique-se de ter o Docker e Docker Compose instalados.
2. Copie o arquivo `.env.example` para `.env` e configure as credenciais necessárias se for usar chaves reais.
3. Suba o ambiente:
   ```bash
   docker-compose up --build
   ```
   *Isso levantará o banco PostgreSQL na porta `5432` e o backend FastAPI na porta `8000`.*

### Opção 2: Rodar diretamente com Python Local (Out-of-the-box com SQLite)

Ao clonar, o projeto está pré-configurado no `.env` para usar o SQLite local (`sqlite:///./imobi_sdr.db`) e rodar sem necessidade de banco de dados externo ou chaves API (entra em modo LLM Mock e Chatwoot Mock por padrão se as variáveis estiverem vazias).

1. Crie o ambiente virtual:
   ```bash
   python -m venv .venv
   ```
2. Ative o ambiente virtual:
   - **Windows (PowerShell)**: `.\.venv\Scripts\Activate.ps1`
   - **Linux/macOS**: `source .venv/bin/activate`
3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
4. Execute o script de seed para criar as tabelas e povoar a Imobiliária Alfa:
   ```bash
   python src/seeds/seed_data.py
   ```
5. Inicie o servidor FastAPI em modo de recarga automática:
   ```bash
   uvicorn src.main:app --reload
   ```
   *O backend estará rodando em `http://localhost:8000`.*

---

## 🧪 Rodando os Testes

O projeto vem equipado com um conjunto completo de testes de unidade cobrindo todos os fluxos do backend.

Para executar os testes locais usando o banco SQLite isolado em memória e mock de conexões de redes externas:
```bash
pytest
```

---

## 🔌 Configurando Integrações

### 🟢 Evolution API

Para que a Evolution API envie mensagens recebidas no WhatsApp para o seu backend:
1. No seu painel da Evolution API, configure o webhook apontando para:
   `http://<IP_DO_BACKEND>:8000/webhook/evolution`
2. No seu arquivo `.env`, certifique-se de configurar:
   ```env
   EVOLUTION_API_URL=http://localhost:8080
   EVOLUTION_API_KEY=sua-evolution-key
   EVOLUTION_WEBHOOK_URL=http://localhost:8000/webhook/evolution
   ```
3. Registre uma instância da Evolution com o nome correspondente a `provider_instance_id` cadastrado no banco (o padrão do seed é `ImobiliariaAlfa`).

### 💬 Chatwoot

O backend gerencia de forma inteligente a criação e sincronização com o Chatwoot:
1. Obtenha a URL do Chatwoot, seu Token de Acesso de Agente e a ID da Conta.
2. Atualize o arquivo `.env`:
   ```env
   CHATWOOT_URL=https://seu-chatwoot.com
   CHATWOOT_ACCESS_TOKEN=seu-token
   CHATWOOT_ACCOUNT_ID=1
   ```
3. Toda nova conversa iniciada no WhatsApp será sincronizada no Chatwoot. Quando as regras de qualificação forem concluídas ou se o cliente solicitar um humano/corretor, o bot aplicará a tag `sdr-handoff` e registrará uma **Nota Privada** com os dados coletados do lead, sinalizando takeover.

---

## 🛠️ Endpoints Disponíveis

Você pode acessar a documentação OpenAPI gerada automaticamente em `http://localhost:8000/docs`.

### 🫀 Monitoramento e Status
- **`GET /health`**: Valida a resposta do servidor e se a conexão com o banco de dados PostgreSQL/SQLite está saudável.
- **`GET /channels/status`**: Lista todos os canais de comunicação ativos no banco e faz consultas em tempo real para verificar a conectividade do canal na Evolution API.
- **`GET /debug/recent-events`**: Retorna os últimos 50 eventos processados de webhook em tempo real (útil para inspecionar payloads brutos de debug).

### 🧪 Endpoints de Testes Manuais (Simulação)
- **`POST /test/send/evolution`**: Dispara o envio de uma mensagem real via Evolution API para um número e instância informada no JSON.
- **`POST /test/generate`**: Simula a inteligência do bot. Envia um texto, simula o armazenamento da mensagem, a atualização das heurísticas de qualificação e retorna a resposta gerada pelo LLM e a decisão do motor de regras.
