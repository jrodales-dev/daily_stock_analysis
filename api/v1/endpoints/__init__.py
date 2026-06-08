# -*- coding: utf-8 -*-
"""
===================================
Inicialização do Módulo de Endpoints da API v1
===================================

Responsabilidades:
1. Declarar todos os módulos de rotas de endpoint
"""

from api.v1.endpoints import (
    health,
    analysis,
    history,
    stocks,
    backtest,
    system_config,
    auth,
    agent,
    usage,
    portfolio,
    alerts,
    alphasift,
)
__all__ = [
    "health",
    "analysis",
    "history",
    "stocks",
    "backtest",
    "system_config",
    "auth",
    "agent",
    "usage",
    "portfolio",
    "alerts",
    "alphasift",
]