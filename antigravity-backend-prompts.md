# Prompts para o Antigravity CLI — Backend MVP Imobiliária

Este documento organiza a construção do backend em **rodadas**, para evitar overengineering e facilitar validação incremental.

## Objetivo do projeto

Construir um backend MVP para atendimento SDR imobiliário via WhatsApp com:

- **Evolution API** como provedor principal inicial
- **arquitetura preparada para Meta Cloud API depois**
- **Chatwoot** como camada operacional/humana
- **backend** como cérebro do sistema
- **sem Modal**
- **multi-tenant simples**
- **qualificação de leads**
- **handoff humano**

## Diretriz geral para todas as rodadas

Use sempre esta instrução adicional no final de cada prompt:

> Trabalhe de forma incremental. Implemente primeiro o menor caminho funcional. Evite overengineering. Não crie frontend. Não adicione RAG. Não crie painel admin agora. Foco total em um backend rodável, observável e fácil de testar localmente.

---

# Rodada 1 — Estrutura base + banco + health

## Objetivo

Criar a fundação do projeto, com infraestrutura local rodável.

## Prompt

```txt
Quero que você crie a base de um backend MVP em FastAPI para um agente SDR imobiliário via WhatsApp.

Contexto:
- O backend será o cérebro do sistema.
- O Chatwoot será a camada operacional/humana.
- A Evolution API será o provedor principal inicial.
- A arquitetura deve ficar preparada para Meta Cloud API depois.
- Não usar Modal.

Stack obrigatória:
- Python 3.11+
- FastAPI
- PostgreSQL
- SQLAlchemy
- Pydantic
- Docker Compose
- arquivos .env
- logging estruturado

Quero nesta primeira rodada apenas a fundação do projeto.

Implemente:
1. Estrutura organizada do projeto com pastas como:
   - src/main.py
   - src/core/
   - src/api/routes/
   - src/models/
   - src/schemas/
   - src/repositories/
   - src/services/
   - src/integrations/
   - src/seeds/

2. Configuração base:
   - settings via .env
   - conexão com PostgreSQL
   - inicialização do app FastAPI
   - logging básico estruturado

3. Endpoint GET /health
   - retornar status ok
   - validar conexão com banco
   - retornar informações simples da aplicação

4. Modelagem inicial do banco com tabelas:
   - tenants
   - channel_configs
   - tenant_configs
   - leads
   - conversations
   - messages
   - lead_qualification
   - handoffs
   - audit_logs

5. Criar seeds iniciais para:
   - 1 tenant de exemplo chamado “Imobiliária Alfa”
   - 1 tenant_config inicial
   - 1 channel_config inicial com provider evolution

6. Arquivos de infraestrutura:
   - Dockerfile
   - docker-compose.yml
   - .env.example
   - requirements.txt ou pyproject.toml
   - README.md com instruções para rodar localmente

7. Criar testes mínimos para:
   - health endpoint
   - conexão básica do app

Importante:
- não implemente ainda webhook
- não implemente ainda integração real com Evolution
- não implemente ainda Chatwoot
- não implemente ainda LLM
- foco apenas em base sólida e rodável

Ao final:
- mostre a estrutura criada
- explique como subir o projeto localmente
- explique como rodar seed
- explique como testar o endpoint /health

Trabalhe de forma incremental. Implemente primeiro o menor caminho funcional. Evite overengineering. Não crie frontend. Não adicione RAG. Não crie painel admin agora. Foco total em um backend rodável, observável e fácil de testar localmente.
```

---

# Rodada 2 — Evolution API + webhook + persistência

## Objetivo

Fazer o backend receber mensagens da Evolution, normalizar, persistir e testar envio simples.

## Prompt

```txt
Quero que você continue o backend MVP já iniciado e implemente agora a integração inicial com a Evolution API.

Contexto:
- Evolution API é o provedor principal inicial.
- O backend deve receber mensagens da Evolution, persistir os dados e conseguir enviar mensagens de teste.
- Ainda não quero a lógica completa da IA.
- Ainda não quero integração completa com Chatwoot.

Implemente nesta rodada:

1. Arquitetura de provider de WhatsApp
   Criar uma base/interface para provedores com métodos como:
   - provider_name()
   - normalize_inbound(payload)
   - send_text(channel_config, number, text)
   - get_connection_state(channel_config)
   - set_webhook(channel_config, webhook_url)

2. Implementar EvolutionProvider funcional
   - usar header apikey
   - implementar envio de texto
   - implementar consulta de status de conexão
   - implementar suporte para configuração de webhook

3. Criar endpoint POST /webhook/evolution
   - receber payload da Evolution API
   - salvar payload bruto em audit_logs
   - normalizar payload
   - ignorar mensagens fromMe
   - ignorar grupos
   - ignorar mensagens sem texto no MVP
   - extrair:
     - instance_name
     - número do contato
     - nome do contato
     - texto
     - timestamp
   - localizar tenant/canal com base na instance_name
   - criar ou atualizar lead
   - criar conversation
   - salvar message
   - registrar evento recente para debugging
   - por enquanto pode retornar apenas sucesso sem responder automaticamente

4. Criar endpoint GET /debug/recent-events
   - listar eventos recentes em memória ou em leitura simples

5. Criar endpoint POST /test/send/evolution
   - receber number e text
   - usar EvolutionProvider para enviar uma mensagem real
   - retornar resultado da chamada

6. Criar endpoint GET /channels/status
   - listar canais ativos
   - mostrar provider
   - mostrar status da conexão com Evolution quando possível

7. Criar testes mínimos para:
   - normalização do payload da Evolution
   - webhook /webhook/evolution com payload de exemplo
   - endpoint /test/send/evolution com mock

8. Atualizar README com:
   - como preencher credenciais da Evolution no .env
   - como configurar instance_name
   - como testar envio manual
   - como testar webhook com curl

Importante:
- ainda não implementar LLM real
n- ainda não implementar lógica de qualificação completa
- ainda não integrar Chatwoot nesta rodada
- foco em: webhook funcionando, persistência funcionando, teste de envio funcionando

Ao final:
- mostre os endpoints criados
- explique o fluxo da Evolution até o banco
- mostre exemplo de payload esperado
- explique como configurar o webhook da Evolution apontando para o backend

Trabalhe de forma incremental. Implemente primeiro o menor caminho funcional. Evite overengineering. Não crie frontend. Não adicione RAG. Não crie painel admin agora. Foco total em um backend rodável, observável e fácil de testar localmente.
```

> **Observação:** se quiser, você pode corrigir manualmente o pequeno typo `n- ainda não implementar...` antes de colar no Antigravity. O texto correto é `- ainda não implementar LLM real`.

---

# Rodada 3 — Rule engine + qualificação + mock LLM

## Objetivo

Adicionar o cérebro inicial do sistema: regras, estado do lead, qualificação e geração controlada de resposta.

## Prompt

```txt
Quero que você continue o backend MVP e implemente agora o cérebro inicial do agente.

Contexto:
- O backend já recebe mensagens da Evolution e persiste dados.
- Agora quero que ele consiga decidir se responde, o que perguntar e quando fazer handoff.
- Ainda pode usar LLM mock se não houver chave real.

Implemente nesta rodada:

1. Estado de qualificação do lead
   Criar ou completar lógica para manter campos como:
   - objetivo (compra ou aluguel)
   - tipo_imovel
   - bairro
   - faixa_preco
   - urgencia
   - pronto_para_handoff
   - status
   - resumo_atual

2. QualificationService
   - atualizar estado com base na mensagem do lead
   - inferir alguns campos quando possível
   - manter simplicidade no MVP

3. RuleEngine
   Criar motor de regras com comportamento como:
   - se conversa estiver em takeover humano, não responder
   - se mensagem pedir corretor, visita ou atendimento humano, marcar handoff
   - se indicar urgência alta, marcar handoff
   - se for reclamação, marcar handoff
   - se faltarem campos obrigatórios, perguntar apenas o próximo campo faltante
   - limitar toda resposta a 2 ou 3 frases curtas
   - responder sempre em pt-BR
   - nunca inventar imóvel, preço ou disponibilidade
   - no máximo uma pergunta por vez

4. PromptBuilder
   Criar serviço que monte contexto dinâmico com:
   - prompt_base do tenant
   - tenant_config
   - estado atual do lead
   - última mensagem do lead
   - política de resposta curta
   - instrução para atuar como SDR imobiliário

5. Adapter de LLM
   - criar interface de provider LLM
   - implementar OpenAI provider
   - se não houver API key configurada, usar mock automático
   - criar generate_reply(context) -> string
   - logar tempo e falhas

6. InboundOrchestrator
   - centralizar fluxo de entrada
   - receber mensagem normalizada
   - buscar tenant/canal/lead
   - atualizar qualificação
   - aplicar rule engine
   - gerar resposta quando necessário
   - retornar decisão final

7. Atualizar /webhook/evolution
   - usar orchestrator
   - se houver resposta, enviar pela Evolution
   - registrar outbound message no banco
   - salvar motivo da decisão

8. Criar endpoint POST /test/generate
   - receber texto e tenant_id
   - rodar pipeline de geração
   - retornar resposta e decisão

9. Criar testes mínimos para:
   - rule engine
   - qualification service
   - orchestrator com modo mock

10. Atualizar README com:
   - como funciona o rule engine
   - como usar mock LLM
   - como ativar OpenAI real

Importante:
- ainda não integrar Chatwoot nesta rodada
- manter regra simples, sem overengineering
- foco em fluxo funcional de inbound -> decisão -> reply

Ao final:
- explique a arquitetura do cérebro
- mostre como a decisão é tomada
- mostre exemplos de mensagens e respostas esperadas

Trabalhe de forma incremental. Implemente primeiro o menor caminho funcional. Evite overengineering. Não crie frontend. Não adicione RAG. Não crie painel admin agora. Foco total em um backend rodável, observável e fácil de testar localmente.
```

---

# Rodada 4 — Integração com Chatwoot

## Objetivo

Conectar o backend ao Chatwoot como camada operacional/humana.

## Prompt

```txt
Quero que você continue o backend MVP e implemente agora a integração com Chatwoot como camada operacional.

Contexto:
- O backend já recebe mensagens da Evolution, persiste, aplica regras e pode responder.
- Agora quero sincronizar isso com o Chatwoot para operação humana.
- O Chatwoot será usado para histórico, inbox, takeover, notas e organização.

Implemente nesta rodada:

1. Criar ChatwootClient
   com métodos como:
   - find_or_create_contact(...)
   - find_or_create_conversation(...)
   - create_incoming_message(...)
   - create_outgoing_message(...)
   - add_private_note(...)
   - add_label(...)
   - assign_conversation(...) [stub aceitável se necessário]

2. Criar serviço de integração com Chatwoot
   - encapsular regras de sincronização
   - mapear lead/conversation local com registros do Chatwoot

3. Atualizar fluxo principal
   Quando chegar uma mensagem inbound da Evolution:
   - encontrar ou criar contato no Chatwoot
   - encontrar ou criar conversa no Chatwoot
   - registrar a mensagem recebida no Chatwoot
   - se o bot responder, registrar a mensagem do bot também no Chatwoot

4. Implementar handoff humano com Chatwoot
   Quando houver handoff:
   - enviar mensagem curta ao lead
   - registrar motivo do handoff
   - adicionar nota privada no Chatwoot
   - adicionar tag/label no Chatwoot
   - marcar estado local como pronto_para_handoff

5. Criar mecanismo simples de takeover humano
   - permitir que o backend reconheça uma conversa marcada como takeover humano
   - se estiver em takeover, o bot não responde
   - implementar de forma simples via campo local, tag ou status mapeado

6. Atualizar banco/modelos se necessário
   - armazenar ids externos do Chatwoot
   - armazenar mapeamento entre conversation local e Chatwoot

7. Criar testes mínimos para:
   - Chatwoot client com mock
   - fluxo de sincronização
   - handoff com criação de nota/tag

8. Atualizar README com:
   - como configurar Chatwoot URL e token
   - como identificar inbox/account necessários
   - como testar sincronização

Importante:
- não criar frontend
- não criar automações complexas do Chatwoot agora
- apenas a camada mínima de sincronização operacional

Ao final:
- explique como o Chatwoot entra na arquitetura
- mostre o fluxo Evolution -> Backend -> Chatwoot
- explique como funcionará o takeover humano

Trabalhe de forma incremental. Implemente primeiro o menor caminho funcional. Evite overengineering. Não crie frontend. Não adicione RAG. Não crie painel admin agora. Foco total em um backend rodável, observável e fácil de testar localmente.
```

---

# Rodada 5 — Preparação para Meta Cloud API

## Objetivo

Deixar a arquitetura pronta para alternar de provedor sem reescrever o sistema.

## Prompt

```txt
Quero que você continue o backend MVP e implemente agora a preparação real para Meta Cloud API, sem quebrar a integração atual com Evolution.

Contexto:
- Evolution continua sendo o provedor principal atual.
- Quero preparar a arquitetura para Meta Cloud API como segundo provider.
- A lógica de negócio do backend não deve depender diretamente do provedor.

Implemente nesta rodada:

1. Revisar a interface/base de providers de WhatsApp
   Garantir que a abstração esteja limpa e realmente reutilizável.

2. Implementar MetaCloudProvider stub mais completo
   - normalize_inbound(payload)
   - send_text(channel_config, number, text) com estrutura preparada
   - get_connection_state(channel_config) stub/documentado
   - set_webhook(channel_config, webhook_url) stub/documentado

3. Criar endpoint POST /webhook/meta
   - receber payload
   - validar estrutura básica
   - normalizar com MetaCloudProvider
   - enviar para o mesmo orchestrator interno
   - suportar modo mock para testes

4. Atualizar channel_configs
   - garantir suporte a evolution ou meta por canal
   - garantir campos genéricos como provider_external_id quando necessário

5. Garantir que outbound use o provider correto
   - a resposta deve sair pelo mesmo canal/provedor correspondente

6. Criar testes mínimos para:
   - normalização do Meta provider
   - roteamento por provider
   - orchestrator independente do provider

7. Atualizar README com:
   - o que já está pronto para Meta
   - o que ainda falta para produção com Meta
   - como trocar provider por canal

Importante:
- não precisa integração completa com a Graph API da Meta nesta rodada
- foco em deixar a arquitetura realmente preparada
- não quebrar Evolution

Ao final:
- explique como alternar provedores
- mostre a arquitetura unificada de providers
- mostre onde configurar um canal evolution ou meta

Trabalhe de forma incremental. Implemente primeiro o menor caminho funcional. Evite overengineering. Não crie frontend. Não adicione RAG. Não crie painel admin agora. Foco total em um backend rodável, observável e fácil de testar localmente.
```

---

# Ordem recomendada de execução

1. **Rodada 1** — base do projeto
2. **Rodada 2** — Evolution + webhook + persistência
3. **Rodada 3** — cérebro inicial
4. **Rodada 4** — Chatwoot
5. **Rodada 5** — preparação para Meta

---

# Meta real do MVP

O MVP está validado quando você conseguir provar este fluxo:

1. Lead manda mensagem no WhatsApp
2. Evolution entrega ao backend
3. Backend identifica o lead
4. Backend aplica regras e responde
5. Backend registra tudo no banco
6. Backend sincroniza a conversa no Chatwoot
7. Se necessário, faz handoff humano

---

# Observação estratégica final

Não tente pular para a rodada 5 antes de validar a rodada 3 ou 4.

O valor do projeto, no começo, não está em “suportar múltiplos provedores com elegância”.
Está em provar que o fluxo **recebe → entende → responde → encaminha** funciona de verdade.
