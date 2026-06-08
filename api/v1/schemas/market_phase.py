# -*- coding: utf-8 -*-
"""Market phase summary schemas."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


MarketPhaseValue = Literal[
    "premarket",
    "intraday",
    "lunch_break",
    "closing_auction",
    "postmarket",
    "non_trading",
    "unknown",
]


class MarketPhaseSummary(BaseModel):
    """Low-sensitivity market phase metadata exposed on report meta."""

    market: Optional[str] = Field(None, description="Região do mercado")
    phase: MarketPhaseValue = Field(..., description="Fase do mercado")
    market_local_time: Optional[str] = Field(None, description="Hora local do mercado")
    session_date: Optional[str] = Field(None, description="Data da sessão local do mercado")
    effective_daily_bar_date: Optional[str] = Field(None, description="Data mais recente da barra diária completa utilizável")
    is_trading_day: Optional[bool] = Field(None, description="Se é um dia de negociação")
    is_market_open_now: Optional[bool] = Field(None, description="Se o mercado está aberto atualmente")
    is_partial_bar: Optional[bool] = Field(None, description="Se a barra diária mais recente pode estar incompleta")
    minutes_to_open: Optional[int] = Field(None, description="Minutos restantes para a abertura")
    minutes_to_close: Optional[int] = Field(None, description="Minutos restantes para o fechamento")
    trigger_source: Optional[str] = Field(None, description="Origem do gatilho")
    analysis_intent: Optional[str] = Field(None, description="Intenção de análise")
    warnings: List[str] = Field(default_factory=list, description="Códigos de alerta de degradação da inferência de fase")