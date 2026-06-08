# -*- coding: utf-8 -*-
"""
===================================
Módulo de Injeção de Dependência da API
===================================

Responsabilidades:
1. Fornecer dependência de Session do banco de dados
2. Fornecer dependência de configuração
3. Fornecer dependência da camada de serviço
"""

from typing import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from src.storage import DatabaseManager
from src.config import get_config, Config
from src.services.system_config_service import SystemConfigService


def get_db() -> Generator[Session, None, None]:
    """
    Obtém a dependência de Session do banco de dados
    
    Utiliza o mecanismo de injeção de dependência do FastAPI para garantir que a Session seja fechada automaticamente após o término da requisição
    
    Yields:
        Session: Objeto Session do SQLAlchemy
        
    Exemplo:
        @router.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            ...
    """
    db_manager = DatabaseManager.get_instance()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def get_config_dep() -> Config:
    """
    Obtém a dependência de configuração
    
    Returns:
        Config: Objeto singleton de configuração
    """
    return get_config()


def get_database_manager() -> DatabaseManager:
    """
    Obtém a dependência do gerenciador de banco de dados
    
    Returns:
        DatabaseManager: Objeto singleton do gerenciador de banco de dados
    """
    return DatabaseManager.get_instance()


def get_system_config_service(request: Request) -> SystemConfigService:
    """Obtém a instância compartilhada do SystemConfigService no ciclo de vida da aplicação."""
    service = getattr(request.app.state, "system_config_service", None)
    if service is None:
        service = SystemConfigService()
        request.app.state.system_config_service = service
    return service