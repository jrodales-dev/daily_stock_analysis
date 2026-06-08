# -*- coding: utf-8 -*-
"""
===================================
Interface de Verificação de Saúde
===================================

Responsabilidades:
1. Fornecer a interface de verificação de saúde /api/v1/health
2. Usado por balanceadores de carga e sistemas de monitoramento
"""

from datetime import datetime

from fastapi import APIRouter

from api.v1.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Interface de Verificação de Saúde
    
    Usado por balanceadores de carga ou sistemas de monitoramento para verificar o status do serviço
    
    Retorna:
        HealthResponse: Contém o status do serviço e o timestamp
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.now().isoformat()
    )