import time
import httpx
from typing import Dict, Any, Optional
from src.core.config import settings
from src.core.logger import get_logger
from src.models.db_models import Tenant, TenantConfig, LeadQualification

logger = get_logger(__name__)

class PromptBuilder:
    @staticmethod
    def build(
        tenant: Tenant,
        tenant_config: Optional[TenantConfig],
        qualification: LeadQualification,
        last_message: str,
        suggested_question: Optional[str] = None
    ) -> str:
        prompt_base = (tenant_config.prompt_base if tenant_config else None) or (
            "Você é um SDR (Sales Development Representative) inteligente e prestativo para a imobiliária "
            f"'{tenant.name}'. Seu objetivo é conduzir um atendimento simpático, rápido e profissional, "
            "coletando os dados necessários para que um corretor possa assumir."
        )

        qualification_summary = (
            f"- Objetivo: {qualification.objetivo or 'Não informado'}\n"
            f"- Tipo de Imóvel: {qualification.tipo_imovel or 'Não informado'}\n"
            f"- Bairro/Região: {qualification.bairro or 'Não informado'}\n"
            f"- Faixa de Preço: {qualification.faixa_preco or 'Não informado'}"
        )

        prompt = f"""{prompt_base}

DIRETRIZES DE ATENDIMENTO:
1. Responda SEMPRE em português do Brasil (pt-BR).
2. Escreva de forma curta e objetiva. Suas respostas devem ter no máximo 2 ou 3 frases curtas.
3. Faça no máximo UMA pergunta por mensagem para não sobrecarregar o cliente.
4. Nunca invente imóveis específicos, preços, condições ou disponibilidades.
5. Se o cliente perguntar sobre opções, diga que vai passar para um corretor especialista encontrar as melhores oportunidades.

ESTADO DA QUALIFICAÇÃO ATUAL:
{qualification_summary}

ÚLTIMA MENSAGEM DO CLIENTE:
"{last_message}"

ORIENTAÇÃO:
Tente dar um retorno simpático e, se apropriado, insira a pergunta para preencher o próximo dado faltante.
Pergunta sugerida para o fluxo atual: "{suggested_question or ''}"

Gere a resposta para o WhatsApp do cliente seguindo as diretrizes acima:"""
        return prompt


def finalize_reply(reply: Optional[str], suggested_question: Optional[str] = None) -> str:
    cleaned_reply = " ".join((reply or "").split()).strip()
    cleaned_question = " ".join((suggested_question or "").split()).strip()

    if not cleaned_reply:
        return f"Entendi! {cleaned_question}".strip() if cleaned_question else "Como posso te ajudar?"

    if cleaned_question:
        if len(cleaned_reply) < 20:
            return f"Entendi! {cleaned_question}".strip()

        if cleaned_question not in cleaned_reply and "?" not in cleaned_reply:
            suffix = cleaned_reply.rstrip(" .!?")
            return f"{suffix}. {cleaned_question}".strip()

    return cleaned_reply


class LlmProvider:
    def generate_reply(self, prompt: str, system_instruction: str = "Você é um assistente de vendas imobiliárias.") -> str:
        pass


class OpenAIProvider(LlmProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = settings.LLM_MODEL or "gpt-4o-mini"
        self.url = "https://api.openai.com/v1/chat/completions"

    def generate_reply(self, prompt: str, system_instruction: str = "Você é um assistente de vendas imobiliárias.") -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5,
            "max_tokens": 150
        }
        
        start_time = time.time()
        logger.info(f"OpenAIProvider: Generating reply using model {self.model}...")
        try:
            with httpx.Client() as client:
                response = client.post(self.url, json=body, headers=headers, timeout=15.0)
                elapsed = time.time() - start_time
                logger.info(f"OpenAI API call took {elapsed:.2f} seconds. Status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    choices = result.get("choices", [])
                    if choices:
                        reply = choices[0].get("message", {}).get("content", "").strip()
                        return reply
                
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                raise Exception(f"OpenAI returned status {response.status_code}")
        except Exception as e:
            logger.error(f"OpenAI call exception: {e}")
            raise e


class GeminiProvider(LlmProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = settings.GEMINI_MODEL or "gemini-1.5-flash"
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

    def generate_reply(self, prompt: str, system_instruction: str = "Você é um assistente de vendas imobiliárias.") -> str:
        headers = {
            "Content-Type": "application/json"
        }
        
        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "systemInstruction": {
                "parts": [
                    {
                        "text": system_instruction
                    }
                ]
            },
            "generationConfig": {
                "temperature": 0.5,
                "maxOutputTokens": 150
            }
        }
        
        start_time = time.time()
        logger.info(f"GeminiProvider: Generating reply using model {self.model}...")
        try:
            with httpx.Client() as client:
                response = client.post(self.url, json=body, headers=headers, timeout=15.0)
                elapsed = time.time() - start_time
                logger.info(f"Gemini API call took {elapsed:.2f} seconds. Status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    candidates = result.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            reply = "".join(
                                part.get("text", "")
                                for part in parts
                                if isinstance(part, dict) and part.get("text")
                            ).strip()
                            if reply:
                                return reply
                
                logger.error(f"Gemini API error: {response.status_code} - {response.text}")
                raise Exception(f"Gemini returned status {response.status_code}")
        except Exception as e:
            logger.error(f"Gemini call exception: {e}")
            raise e


class MockLlmProvider(LlmProvider):
    def __init__(self, suggested_question: Optional[str] = None):
        self.suggested_question = suggested_question

    def generate_reply(self, prompt: str, system_instruction: str = "") -> str:
        logger.info("MockLlmProvider: Generating mock reply...")
        time.sleep(0.5) # Simulate brief processing time
        if self.suggested_question:
            return f"Entendi! {self.suggested_question}"
        return "Olá! Perfeito. Como posso te ajudar na sua busca por imóveis hoje?"


def get_llm_provider(suggested_question: Optional[str] = None) -> LlmProvider:
    if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "sua-gemini-key":
        return GeminiProvider(settings.GEMINI_API_KEY)
    elif settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "sua-openai-key":
        return OpenAIProvider(settings.OPENAI_API_KEY)
    else:
        return MockLlmProvider(suggested_question)

