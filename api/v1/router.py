# -*- coding: utf-8 -*-
"""
===================================
Agregação de Rotas da API v1
===================================

Responsabilidades:
1. Agregar todas as rotas de endpoint da versão v1
2. Adicionar o prefixo /api/v1 de forma unificada
"""

from fastapi import APIRouter

from api.v1.endpoints import alerts, analysis, auth, history, stocks, backtest, system_config, agent, usage, portfolio, alphasift

# Cria a rota principal da versão v1
router = APIRouter(prefix="/api/v1")

router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Auth"]
)

router.include_router(
    agent.router,
    prefix="/agent",
    tags=["Agent"]
)

router.include_router(
    analysis.router,
    prefix="/analysis",
    tags=["Analysis"]
)

router.include_router(
    history.router,
    prefix="/history",
    tags=["History"]
)

router.include_router(
    stocks.router,
    prefix="/stocks",
    tags=["Stocks"]
)

router.include_router(
    backtest.router,
    prefix="/backtest",
    tags=["Backtest"]
)

router.include_router(
    system_config.router,
    prefix="/system",
    tags=["SystemConfig"]
)

router.include_router(
    usage.router,
    prefix="/usage",
    tags=["Usage"]
)

router.include_router(
    portfolio.router,
    prefix="/portfolio",
    tags=["Portfolio"]
)

router.include_router(
    alerts.router,
    prefix="/alerts",
    tags=["Alerts"]
)

router.include_router(
    alphasift.router,
    prefix="/alphasift",
    tags=["AlphaSift"]
)