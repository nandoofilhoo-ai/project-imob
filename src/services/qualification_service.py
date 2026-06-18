import re
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from src.repositories.db_repositories import DbRepository
from src.core.logger import get_logger

logger = get_logger(__name__)

class QualificationService:
    @staticmethod
    def extract_keywords_heuristics(text: str) -> Dict[str, Any]:
        """
        Extract key qualification elements using quick regex/keyword heuristics.
        """
        updates = {}
        text_lower = text.lower()

        # 1. Goal (Objetivo)
        if any(w in text_lower for w in ["alugar", "aluguel", "locação", "locacao"]):
            updates["objetivo"] = "aluguel"
        elif any(w in text_lower for w in ["comprar", "compra", "adquirir", "compraria"]):
            updates["objetivo"] = "compra"

        # 2. Property Type (Tipo Imóvel)
        if any(w in text_lower for w in ["apartamento", "apto", "cobertura", "flat"]):
            updates["tipo_imovel"] = "apartamento"
        elif any(w in text_lower for w in ["casa", "sobrado", "residência"]):
            updates["tipo_imovel"] = "casa"
        elif any(w in text_lower for w in ["terreno", "lote"]):
            updates["tipo_imovel"] = "terreno"
        elif any(w in text_lower for w in ["comercial", "sala", "galpão", "galpao"]):
            updates["tipo_imovel"] = "comercial"

        # 3. Urgency (Urgência)
        if any(w in text_lower for w in ["urgente", "o quanto antes", "imediato", "hoje"]):
            updates["urgencia"] = "alta"
        elif any(w in text_lower for w in ["sem pressa", "planejando", "futuro", "pesquisando"]):
            updates["urgencia"] = "baixa"
        elif any(w in text_lower for w in ["mês que vem", "mes que vem", "breve"]):
            updates["urgencia"] = "media"

        # 4. Price range (Faixa de Preço)
        # Match values like "R$ 500mil", "300 mil", "R$ 2.000", "até 3000"
        price_match = re.search(r'(?:até|ate|r\$)?\s*(\d+[\d\.,\s]*(?:mil|milhões|milhoes|k)?)', text_lower)
        if price_match and any(char.isdigit() for char in price_match.group(1)):
            # Capture the match text as a candidate price range
            candidate = price_match.group(0).strip()
            # Basic sanity check (avoid capturing simple short numbers like "2" rooms)
            if len(candidate) > 2:
                updates["faixa_preco"] = candidate

        # 5. Bairro / Neighborhood
        # A simple pattern: "no [Bairro Name]" or "na [Bairro Name]" or "em [Bairro Name]"
        bairro_match = re.search(r'(?:no|na|em|para)\s+([a-zà-ú]+(?:\s+[a-zà-ú]+){0,2})', text_lower)
        if bairro_match:
            bairro_candidate = bairro_match.group(1).strip()
            ignored_words = ["aluguel", "compra", "casa", "apartamento", "terreno", "sala", "um", "uma", "este", "esta", "qualquer", "breve", "urgente"]
            if bairro_candidate not in ignored_words and len(bairro_candidate) > 3:
                updates["bairro"] = bairro_candidate.title()

        return updates

    @classmethod
    def process_incoming_message(cls, db: Session, lead_id: int, text: str) -> Dict[str, Any]:
        """
        Processes an incoming message text, updates the lead qualification state,
        and returns the current state fields.
        """
        # Find current qualification
        qualification = DbRepository.get_qualification(db, lead_id)
        if not qualification:
            qualification = DbRepository.create_qualification(db, lead_id)

        # Apply keyword extraction
        updates = cls.extract_keywords_heuristics(text)
        
        # Check if we should mark for handoff (pronto_para_handoff)
        # We also check in RuleEngine, but let's calculate readiness here too
        # Readiness definition: if goal (objetivo), property type (tipo_imovel), and price range or neighborhood are filled.
        filled_fields = 0
        if qualification.objetivo or updates.get("objetivo"):
            filled_fields += 1
        if qualification.tipo_imovel or updates.get("tipo_imovel"):
            filled_fields += 1
        if qualification.bairro or updates.get("bairro"):
            filled_fields += 1
        if qualification.faixa_preco or updates.get("faixa_preco"):
            filled_fields += 1

        # If at least 3 fields are filled, mark it as ready for human agent review (handoff candidate)
        if filled_fields >= 3:
            updates["pronto_para_handoff"] = True

        # Generate simple summary
        current_objetivo = updates.get("objetivo", qualification.objetivo)
        current_tipo = updates.get("tipo_imovel", qualification.tipo_imovel)
        current_bairro = updates.get("bairro", qualification.bairro)
        current_preco = updates.get("faixa_preco", qualification.faixa_preco)
        
        summary_parts = []
        if current_objetivo: summary_parts.append(f"Objetivo: {current_objetivo}")
        if current_tipo: summary_parts.append(f"Tipo: {current_tipo}")
        if current_bairro: summary_parts.append(f"Bairro: {current_bairro}")
        if current_preco: summary_parts.append(f"Valor: {current_preco}")
        
        updates["resumo_atual"] = " | ".join(summary_parts) if summary_parts else "Nenhuma informação capturada ainda."

        if updates:
            DbRepository.update_qualification(db, qualification.id, updates)
            
        return updates
