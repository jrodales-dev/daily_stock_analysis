# -*- coding: utf-8 -*-
"""
===================================
Middleware de Tratamento Global de Exceções
===================================

Responsabilidades:
1. Capturar exceções não tratadas
2. Padronizar o formato de resposta de erro
3. Registrar logs de erro
"""

import logging
import traceback
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Middleware de tratamento global de exceções
    
    Captura todas as exceções não tratadas e retorna uma resposta de erro em formato padronizado
    """
    
    async def dispatch(
        self, 
        request: Request, 
        call_next: Callable
    ) -> Response:
        """
        Processa a requisição, capturando exceções
        
        Args:
            request: Objeto da requisição
            call_next: Próximo processador
            
        Returns:
            Response: Objeto de resposta
        """
        try:
            response = await call_next(request)
            return response
            
        except Exception as e:
            # Registra o log de erro
            logger.error(
                f"Exceção não tratada: {e}\n"
                f"Caminho da requisição: {request.url.path}\n"
                f"Método da requisição: {request.method}\n"
                f"Pilha de execução: {traceback.format_exc()}"
            )
            
            # Retorna a resposta de erro em formato padronizado
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_error",
                    "message": "Erro interno do servidor, por favor tente novamente mais tarde",
                    "detail": str(e) if logger.isEnabledFor(logging.DEBUG) else None
                }
            )


def add_error_handlers(app) -> None:
    """
    Adiciona manipuladores de exceção globais
    
    Adiciona manipuladores para vários tipos de exceções ao aplicativo FastAPI
    
    Args:
        app: Instância do aplicativo FastAPI
    """
    from fastapi import HTTPException
    from fastapi.exceptions import RequestValidationError
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Trata exceções HTTP"""
        # Se detail já for um dict no formato ErrorResponse, usa-o diretamente
        if isinstance(exc.detail, dict) and "error" in exc.detail and "message" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail
            )
        # Caso contrário, empacota o detail no formato ErrorResponse
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "http_error",
                "message": str(exc.detail) if exc.detail else "HTTP Error",
                "detail": None
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Trata exceções de validação de requisição"""
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "message": "Falha na validação dos parâmetros da requisição",
                "detail": exc.errors()
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Trata exceções gerais"""
        logger.error(
            f"Exceção não tratada: {exc}\n"
            f"Caminho da requisição: {request.url.path}\n"
            f"Pilha de execução: {traceback.format_exc()}"
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "Erro interno do servidor",
                "detail": None
            }
        )