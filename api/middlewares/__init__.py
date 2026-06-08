# -*- coding: utf-8 -*-
"""
===================================
Inicialização do Módulo de Middleware da API
===================================

Responsabilidades:
1. Exportar todos os middlewares
"""

from api.middlewares.error_handler import ErrorHandlerMiddleware

__all__ = ["ErrorHandlerMiddleware"]