# -*- coding: utf-8 -*-
"""
===================================
Interface de Dados de Ações
===================================

Responsabilidades:
1. POST /api/v1/stocks/extract-from-image Extrai códigos de ações de uma imagem
2. POST /api/v1/stocks/parse-import Analisa CSV/Excel/Área de transferência
3. GET /api/v1/stocks/{code}/quote Interface de cotação em tempo real
4. GET /api/v1/stocks/{code}/history Interface de cotação histórica
"""

import logging
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from api.v1.schemas.stocks import (
    ExtractFromImageResponse,
    ExtractItem,
    KLineData,
    StockHistoryResponse,
    StockQuote,
)
from api.v1.schemas.common import ErrorResponse
from src.services.image_stock_extractor import (
    ALLOWED_MIME,
    MAX_SIZE_BYTES,
    extract_stock_codes_from_image,
)
from src.services.import_parser import (
    MAX_FILE_BYTES,
    parse_import_from_bytes,
    parse_import_from_text,
)
from src.services.stock_service import StockService

logger = logging.getLogger(__name__)

router = APIRouter()

# Deve ser definido antes da rota /{stock_code}
ALLOWED_MIME_STR = ", ".join(ALLOWED_MIME)


@router.post(
    "/extract-from-image",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "Códigos de ações extraídos"},
        400: {"description": "Imagem inválida", "model": ErrorResponse},
        500: {"description": "Erro do servidor", "model": ErrorResponse},
    },
    summary="Extrair códigos de ações de uma imagem",
    description="Faz upload de captura de tela/imagem, extrai códigos de ações via Vision LLM. Suporta JPEG, PNG, WebP, GIF, máximo 5MB.",
)
def extract_from_image(
    file: Optional[UploadFile] = File(None, description="Arquivo de imagem (nome do campo do formulário: file)"),
    include_raw: bool = Query(False, description="Se deve incluir a resposta bruta do LLM no resultado"),
) -> ExtractFromImageResponse:
    """
    Extrai códigos de ações de uma imagem carregada (usando Vision LLM).

    Por favor, use o campo do formulário 'file' para carregar a imagem. Prioridade: Gemini / Anthropic / OpenAI (primeiro disponível).
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": "Nenhum arquivo fornecido, por favor, use o campo do formulário 'file' para carregar a imagem"},
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_type",
                "message": f"Tipo não suportado: {content_type}. Permitido: {ALLOWED_MIME_STR}",
            },
        )

    try:
        # Primeiro lê o tamanho limitado, depois verifica se há algo restante (semântica clara: rejeitar se exceder)
        data = file.file.read(MAX_SIZE_BYTES)
        if file.file.read(1):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"A imagem excede o limite de {MAX_SIZE_BYTES // (1024 * 1024)}MB",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Falha ao ler o arquivo carregado: {e}")
        raise HTTPException(
            status_code=400,
            detail={"error": "read_failed", "message": "Falha ao ler o arquivo carregado"},
        )

    try:
        items, raw_text = extract_stock_codes_from_image(data, content_type)
        extract_items = [
            ExtractItem(code=code, name=name, confidence=conf) for code, name, conf in items
        ]
        codes = [i.code for i in extract_items]
        return ExtractFromImageResponse(
            codes=codes,
            items=extract_items,
            raw_text=raw_text if include_raw else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "extract_failed", "message": str(e)})
    except Exception as e:
        logger.error(f"Falha na extração da imagem: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": "Falha na extração da imagem"},
        )


@router.post(
    "/parse-import",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "Resultado da análise"},
        400: {"description": "Dados não fornecidos ou falha na análise", "model": ErrorResponse},
        500: {"description": "Erro do servidor", "model": ErrorResponse},
    },
    summary="Analisar CSV/Excel/Área de transferência",
    description="Faz upload de arquivo CSV/Excel ou cola texto, analisa automaticamente códigos de ações. Limite de arquivo 2MB, limite de texto 100KB.",
)
async def parse_import(request: Request) -> ExtractFromImageResponse:
    """
    Analisa arquivos CSV/Excel ou texto da área de transferência.

    - multipart/form-data + file: Carregar arquivo
    - application/json + {"text": "..."}: Colar texto
    - Prioriza o uso de 'file', se ambos forem fornecidos, 'text' será ignorado.
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as e:
            logger.warning("[parse_import] Falha na análise JSON: %s", e)
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_json", "message": f"Falha na análise JSON: {e}"},
            )
        text = body.get("text") if isinstance(body, dict) else None
        if not text or not isinstance(text, str):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "Texto não fornecido, por favor, use {\"text\": \"...\"}"},
            )
        try:
            items = parse_import_from_text(text)
        except ValueError as e:
            text_bytes = len(text.encode("utf-8"))
            logger.warning(
                "[parse_import] parse_import_from_text falhou: text_bytes=%d, error=%s",
                text_bytes,
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    elif "multipart" in content_type:
        form = await request.form()
        file = form.get("file")
        if not file or not hasattr(file, "read"):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "Nenhum arquivo fornecido, por favor, use o campo do formulário 'file'"},
            )
        file_size = getattr(file, "size", None)
        if isinstance(file_size, int) and file_size > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"O arquivo excede o limite de {MAX_FILE_BYTES // (1024 * 1024)}MB",
                },
            )
        try:
            data = file.file.read(MAX_FILE_BYTES)
            if file.file.read(1):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "file_too_large",
                        "message": f"O arquivo excede o limite de {MAX_FILE_BYTES // (1024 * 1024)}MB",
                    },
                )
        except HTTPException:
            raise
        except Exception as e:
            filename = getattr(file, "filename", None) or ""
            size = getattr(file, "size", None)
            logger.warning(
                "[parse_import] falha na leitura do arquivo: filename=%r, size=%s, error=%s",
                filename,
                size,
                e,
            )
            raise HTTPException(
                status_code=400,
                detail={"error": "read_failed", "message": "Falha ao ler o arquivo"},
            )
        filename = getattr(file, "filename", None) or ""
        try:
            items = parse_import_from_bytes(data, filename=filename)
        except ValueError as e:
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            logger.warning(
                "[parse_import] parse_import_from_bytes falhou: filename=%r, ext=%r, bytes=%d, error=%s",
                filename,
                ext,
                len(data),
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_request",
                "message": "Por favor, use multipart/form-data para carregar um arquivo, ou application/json para enviar {\"text\": \"...\"}",
            },
        )

    extract_items = [
        ExtractItem(code=code, name=name, confidence=conf)
        for code, name, conf in items
    ]
    codes = list(dict.fromkeys(i.code for i in extract_items if i.code))
    return ExtractFromImageResponse(codes=codes, items=extract_items, raw_text=None)


@router.get(
    "/{stock_code}/quote",
    response_model=StockQuote,
    responses={
        200: {"description": "Dados de cotação"},
        404: {"description": "Ação não encontrada", "model": ErrorResponse},
        500: {"description": "Erro do servidor", "model": ErrorResponse},
    },
    summary="Obter cotação de ações em tempo real",
    description="Obtém os dados de cotação mais recentes para a ação especificada"
)
def get_stock_quote(stock_code: str) -> StockQuote:
    """
    Obter cotação de ações em tempo real
    
    Obtém os dados de cotação mais recentes para a ação especificada
    
    Args:
        stock_code: Código da ação (ex: 600519, 00700, AAPL)
        
    Returns:
        StockQuote: Dados de cotação em tempo real
        
    Raises:
        HTTPException: 404 - Ação não encontrada
    """
    try:
        service = StockService()
        
        # Usa def em vez de async def, FastAPI executa automaticamente em um pool de threads
        result = service.get_realtime_quote(stock_code)
        
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"Dados de cotação para a ação {stock_code} não encontrados"
                }
            )
        
        return StockQuote(
            stock_code=result.get("stock_code", stock_code),
            stock_name=result.get("stock_name"),
            current_price=result.get("current_price", 0.0),
            change=result.get("change"),
            change_percent=result.get("change_percent"),
            open=result.get("open"),
            high=result.get("high"),
            low=result.get("low"),
            prev_close=result.get("prev_close"),
            volume=result.get("volume"),
            amount=result.get("amount"),
            update_time=result.get("update_time")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Falha ao obter cotação em tempo real: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Falha ao obter cotação em tempo real: {str(e)}"
            }
        )


@router.get(
    "/{stock_code}/history",
    response_model=StockHistoryResponse,
    responses={
        200: {"description": "Dados de cotação histórica"},
        422: {"description": "Parâmetro de período não suportado", "model": ErrorResponse},
        500: {"description": "Erro do servidor", "model": ErrorResponse},
    },
    summary="Obter cotação histórica de ações",
    description="Obtém os dados históricos de K-line para a ação especificada"
)
def get_stock_history(
    stock_code: str,
    period: str = Query("daily", description="Período da K-line", pattern="^(daily|weekly|monthly)$"),
    days: int = Query(30, ge=1, le=365, description="Número de dias para obter")
) -> StockHistoryResponse:
    """
    Obter cotação histórica de ações
    
    Obtém os dados históricos de K-line para a ação especificada
    
    Args:
        stock_code: Código da ação
        period: Período da K-line (daily/weekly/monthly)
        days: Número de dias para obter
        
    Returns:
        StockHistoryResponse: Dados de cotação histórica
    """
    try:
        service = StockService()
        
        # Usa def em vez de async def, FastAPI executa automaticamente em um pool de threads
        result = service.get_history_data(
            stock_code=stock_code,
            period=period,
            days=days
        )
        
        # Converte para o modelo de resposta
        data = [
            KLineData(
                date=item.get("date"),
                open=item.get("open"),
                high=item.get("high"),
                low=item.get("low"),
                close=item.get("close"),
                volume=item.get("volume"),
                amount=item.get("amount"),
                change_percent=item.get("change_percent")
            )
            for item in result.get("data", [])
        ]
        
        return StockHistoryResponse(
            stock_code=stock_code,
            stock_name=result.get("stock_name"),
            period=period,
            data=data
        )
    
    except ValueError as e:
        # Erro de parâmetro 'period' não suportado (ex: weekly/monthly)
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unsupported_period",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Falha ao obter cotação histórica: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Falha ao obter cotação histórica: {str(e)}"
            }
        )