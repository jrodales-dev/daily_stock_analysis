# -*- coding: utf-8 -*-
"""
===================================
Inicialização do Módulo API v1
===================================

Responsabilidades:
1. Exportar as rotas da API versão v1
"""

from api.v1.router import router as api_v1_router

__all__ = ["api_v1_router"]