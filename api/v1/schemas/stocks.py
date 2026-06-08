# -*- coding: utf-8 -*-
"""
===================================
Modelos de Dados de Ações
===================================

Responsabilidades:
1. Definir o modelo de cotação em tempo real de ações
2. Definir o modelo de dados históricos de velas (K-line)
"""

from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class StockQuote(BaseModel):
    """Cotação em tempo real de ações"""
    
    stock_code: str = Field(..., description="Código da ação")
    stock_name: Optional[str] = Field(None, description="Nome da ação")
    current_price: float = Field(..., description="Preço atual")
    change: Optional[float] = Field(None, description="Variação (valor)")
    change_percent: Optional[float] = Field(None, description="Variação (%)")
    open: Optional[float] = Field(None, description="Preço de abertura")
    high: Optional[float] = Field(None, description="Preço máximo")
    low: Optional[float] = Field(None, description="Preço mínimo")
    prev_close: Optional[float] = Field(None, description="Fechamento anterior")
    volume: Optional[float] = Field(None, description="Volume de negociação (ações)")
    amount: Optional[float] = Field(None, description="Volume financeiro (Yuan)")
    update_time: Optional[str] = Field(None, description="Hora de atualização")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "stock_name": "Kweichow Moutai",
            "current_price": 1800.00,
            "change": 15.00,
            "change_percent": 0.84,
            "open": 1785.00,
            "high": 1810.00,
            "low": 1780.00,
            "prev_close": 1785.00,
            "volume": 10000000,
            "amount": 18000000000,
            "update_time": "2024-01-01T15:00:00"
        }
    })


class KLineData(BaseModel):
    """Ponto de dados de vela (K-line)"""
    
    date: str = Field(..., description="Data")
    open: float = Field(..., description="Preço de abertura")
    high: float = Field(..., description="Preço máximo")
    low: float = Field(..., description="Preço mínimo")
    close: float = Field(..., description="Preço de fechamento")
    volume: Optional[float] = Field(None, description="Volume de negociação")
    amount: Optional[float] = Field(None, description="Volume financeiro")
    change_percent: Optional[float] = Field(None, description="Variação (%)")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "date": "2024-01-01",
            "open": 1785.00,
            "high": 1810.00,
            "low": 1780.00,
            "close": 1800.00,
            "volume": 10000000,
            "amount": 18000000000,
            "change_percent": 0.84
        }
    })


class ExtractItem(BaseModel):
    """Resultado de extração individual (código, nome, confiança)"""

    code: Optional[str] = Field(None, description="Código da ação, None indica falha na análise")
    name: Optional[str] = Field(None, description="Nome da ação (se houver)")
    confidence: str = Field("medium", description="Nível de confiança: high/medium/low")


class ExtractFromImageResponse(BaseModel):
    """Resposta da extração de código de ação a partir de imagem"""

    codes: List[str] = Field(..., description="Códigos de ações extraídos (sem duplicatas, compatibilidade com versões anteriores)")
    items: List[ExtractItem] = Field(default_factory=list, description="Detalhes do resultado da extração (código + nome + confiança)")
    raw_text: Optional[str] = Field(None, description="Resposta bruta do LLM (para depuração)")


class StockHistoryResponse(BaseModel):
    """Resposta do histórico de cotações da ação"""
    
    stock_code: str = Field(..., description="Código da ação")
    stock_name: Optional[str] = Field(None, description="Nome da ação")
    period: str = Field(..., description="Período da vela (K-line)")
    data: List[KLineData] = Field(default_factory=list, description="Lista de dados de vela (K-line)")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "stock_name": "Kweichow Moutai",
            "period": "daily",
            "data": []
        }
    })