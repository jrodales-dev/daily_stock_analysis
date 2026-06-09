# -*- coding: utf-8 -*-
"""
===================================
Interface de Histórico
===================================

Responsabilidades:
1. Fornecer a interface GET /api/v1/history para consulta de lista de histórico
2. Fornecer a interface GET /api/v1/history/{query_id} para consulta de detalhes do histórico
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends, Body

from api.deps import get_database_manager
from api.v1.schemas.history import (
    HistoryListResponse,
    HistoryItem,
    DeleteHistoryRequest,
    DeleteHistoryResponse,
    NewsIntelItem,
    NewsIntelResponse,
    AnalysisReport,
    ReportMeta,
    ReportSummary,
    ReportStrategy,
    ReportDetails,
    MarkdownReportResponse,
    RunDiagnosticSummaryResponse,
)
from api.v1.schemas.common import ErrorResponse
from src.storage import DatabaseManager
from src.report_language import (
    get_sentiment_label,
    get_localized_stock_name,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)
from src.services.history_service import HistoryService, MarkdownReportGenerationError
from src.utils.data_processing import (
    normalize_model_used,
    extract_fundamental_detail_fields,
    extract_board_detail_fields,
    extract_realtime_detail_fields,
)
from src.analysis_context_pack_overview import (
    extract_analysis_context_pack_overview,
    sanitize_context_snapshot_for_api,
)
from src.market_phase_summary import extract_market_phase_summary

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=HistoryListResponse,
    responses={
        200: {"description": "Lista de registros de histórico"},
        500: {"description": "Erro do servidor", "model": ErrorResponse},
    },
    summary="Obter lista de análises históricas",
    description="Obtém um resumo paginado dos registros de análises históricas, suportando filtragem por código de ação e intervalo de datas"
)
def get_history_list(
    stock_code: Optional[str] = Query(None, description="Filtrar por código de ação"),
    start_date: Optional[str] = Query(None, description="Data de início (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Data de término (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Número da página (começa em 1)"),
    limit: int = Query(20, ge=1, le=100, description="Quantidade por página"),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> HistoryListResponse:
    """
    Obter lista de análises históricas
    
    Obtém um resumo paginado dos registros de análises históricas, suportando filtragem por código de ação e intervalo de datas
    
    Args:
        stock_code: Filtrar por código de ação
        start_date: Data de início
        end_date: Data de término
        page: Número da página
        limit: Quantidade por página
        db_manager: Dependência do gerenciador de banco de dados
        
    Returns:
        HistoryListResponse: Lista de registros de histórico
    """
    try:
        service = HistoryService(db_manager)
        
        # Usar def em vez de async def, FastAPI executa automaticamente em um pool de threads
        result = service.get_history_list(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            page=page,
            limit=limit
        )
        
        # Converter para o modelo de resposta
        items = [
            HistoryItem(
                id=item.get("id"),
                query_id=item.get("query_id", ""),
                stock_code=item.get("stock_code", ""),
                stock_name=item.get("stock_name"),
                report_type=item.get("report_type"),
                trend_prediction=item.get("trend_prediction"),
                analysis_summary=item.get("analysis_summary"),
                sentiment_score=item.get("sentiment_score"),
                operation_advice=item.get("operation_advice"),
                current_price=item.get("current_price"),
                change_pct=item.get("change_pct"),
                volume_ratio=item.get("volume_ratio"),
                turnover_rate=item.get("turnover_rate"),
                model_used=item.get("model_used"),
                created_at=item.get("created_at")
            )
            for item in result.get("items", [])
        ]
        
        return HistoryListResponse(
            total=result.get("total", 0),
            page=page,
            limit=limit,
            items=items
        )
        
    except Exception as e:
        logger.error(f"Falha ao consultar lista de histórico: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Falha ao consultar lista de histórico: {str(e)}"
            }
        )


@router.delete(
    "",
    response_model=DeleteHistoryResponse,
    responses={
        200: {"description": "Excluído com sucesso"},
        400: {"description": "Erro de parâmetro da requisição", "model": ErrorResponse},
        500: {"description": "Erro do servidor", "model": ErrorResponse},
    },
    summary="Excluir registros de análises históricas",
    description="Exclui em massa o histórico de análises por ID de chave primária do registro de histórico"
)
def delete_history_records(
    request: DeleteHistoryRequest = Body(...),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> DeleteHistoryResponse:
    """
    Exclui em massa registros de análises históricas por ID de chave primária.
    """
    record_ids = sorted({record_id for record_id in request.record_ids if record_id is not None})
    if not record_ids:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "message": "record_ids não pode ser vazio"
            }
        )

    try:
        service = HistoryService(db_manager)
        deleted = service.delete_history_records(record_ids)
        return DeleteHistoryResponse(deleted=deleted)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Falha ao excluir registros de histórico: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Falha ao excluir registros de histórico: {str(e)}"
            }
        )


@router.get(
    "/{record_id}",
    response_model=AnalysisReport,
    responses={
        200: {"description": "Detalhes do relatório"},
        404: {"description": "Relatório não encontrado", "model": ErrorResponse},
        500: {"description": "Erro do servidor", "model": ErrorResponse},
    },
    summary="Obter detalhes do relatório histórico",
    description="Obtém o relatório de análise histórica completo com base no ID do registro de histórico de análise ou query_id"
)
def get_history_detail(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> AnalysisReport:
    """
    Obter detalhes do relatório histórico
    
    Obtém o relatório de análise histórica completo com base no ID da chave primária do registro de análise histórica ou query_id.
    Tenta primeiro consultar por ID de chave primária (inteiro), se o parâmetro não for um inteiro válido, consulta por query_id.
    
    Args:
        record_id: ID da chave primária do registro de análise histórica (inteiro) ou query_id (string)
        db_manager: Dependência do gerenciador de banco de dados
        
    Returns:
        AnalysisReport: Relatório de análise completo
        
    Raises:
        HTTPException: 404 - Relatório não encontrado
    """
    try:
        service = HistoryService(db_manager)
        
        # Tenta primeiro o ID inteiro, depois busca por string query_id
        result = service.resolve_and_get_detail(record_id)
        
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"Registro de análise com id/query_id={record_id} não encontrado"
                }
            )
        
        # Extrair informações de preço do context_snapshot
        # Nota: usar `is None` em vez de `or` para evitar confundir 0.0 (preço estável) com valor ausente;
        # e não misturar `change_60d` (mudança acumulada em 60 dias) como fallback para `change_pct` diário.
        context_snapshot = result.get("context_snapshot")
        analysis_context_pack_overview = extract_analysis_context_pack_overview(context_snapshot)
        market_phase_summary = extract_market_phase_summary(context_snapshot)
        api_context_snapshot = sanitize_context_snapshot_for_api(context_snapshot)
        realtime_fields = extract_realtime_detail_fields(context_snapshot)
        current_price = realtime_fields.get("current_price")
        change_pct = realtime_fields.get("change_pct")
        
        raw_result = result.get("raw_result")
        if not isinstance(raw_result, dict):
            raw_result = {}
        report_language = normalize_report_language(
            result.get("report_language")
            or raw_result.get("report_language")
            or (
                context_snapshot.get("report_language")
                if isinstance(context_snapshot, dict)
                else None
            )
        )
        stock_name = get_localized_stock_name(
            result.get("stock_name"),
            result.get("stock_code", ""),
            report_language,
        )

        # Construir modelo de resposta
        meta = ReportMeta(
            id=result.get("id"),
            query_id=result.get("query_id", ""),
            stock_code=result.get("stock_code", ""),
            stock_name=stock_name,
            report_type=result.get("report_type"),
            report_language=report_language,
            created_at=result.get("created_at"),
            current_price=current_price,
            change_pct=change_pct,
            model_used=normalize_model_used(result.get("model_used")),
            market_phase_summary=market_phase_summary,
        )
        
        summary = ReportSummary(
            analysis_summary=result.get("analysis_summary"),
            operation_advice=localize_operation_advice(
                result.get("operation_advice"),
                report_language,
            ),
            trend_prediction=localize_trend_prediction(
                result.get("trend_prediction"),
                report_language,
            ),
            sentiment_score=result.get("sentiment_score"),
            sentiment_label=(
                get_sentiment_label(result.get("sentiment_score"), report_language)
                if result.get("sentiment_score") is not None
                else result.get("sentiment_label")
            )
        )
        
        strategy = ReportStrategy(
            ideal_buy=result.get("ideal_buy"),
            secondary_buy=result.get("secondary_buy"),
            stop_loss=result.get("stop_loss"),
            take_profit=result.get("take_profit")
        )
        
        fallback_fundamental = db_manager.get_latest_fundamental_snapshot(
            query_id=result.get("query_id", ""),
            code=result.get("stock_code", ""),
        )
        extracted_fundamental = extract_fundamental_detail_fields(
            context_snapshot=result.get("context_snapshot"),
            fallback_fundamental_payload=fallback_fundamental,
        )
        extracted_boards = extract_board_detail_fields(
            context_snapshot=result.get("context_snapshot"),
            fallback_fundamental_payload=fallback_fundamental,
        )

        details = ReportDetails(
            news_content=result.get("news_content"),
            raw_result=result.get("raw_result"),
            context_snapshot=api_context_snapshot,
            analysis_context_pack_overview=analysis_context_pack_overview,
            financial_report=extracted_fundamental.get("financial_report"),
            dividend_metrics=extracted_fundamental.get("dividend_metrics"),
            belong_boards=extracted_boards.get("belong_boards"),
            sector_rankings=extracted_boards.get("sector_rankings"),
        )
        
        return AnalysisReport(
            meta=meta,
            summary=summary,
            strategy=strategy,
            details=details
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Falha ao consultar detalhes do histórico: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Falha ao consultar detalhes do histórico: {str(e)}"
            }
        )


@router.get(
    "/{record_id}/diagnostics",
    response_model=RunDiagnosticSummaryResponse,
    responses={
        200: {"description": "Resumo de diagnóstico de execução"},
        404: {"description": "Relatório não encontrado", "model": ErrorResponse},
        500: {"description": "Erro do servidor", "model": ErrorResponse},
    },
    summary="Obter resumo de diagnóstico de execução do relatório histórico",
    description="Obtém um resumo de diagnóstico legível pelo usuário e texto de cópia anonimizado com base no ID do registro de análise histórica ou query_id.",
)
def get_history_diagnostics(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> RunDiagnosticSummaryResponse:
    """
    Obtém o resumo de diagnóstico de execução do relatório histórico.
    """
    try:
        service = HistoryService(db_manager)
        summary = service.resolve_and_get_diagnostics(record_id)
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"Registro de análise com id/query_id={record_id} não encontrado",
                },
            )
        return RunDiagnosticSummaryResponse.model_validate(summary)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Falha ao consultar resumo de diagnóstico de execução: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Falha ao consultar resumo de diagnóstico de execução: {str(e)}",
            },
        )


@router.get(
    "/{record_id}/news",
    response_model=NewsIntelResponse,
    responses={
        200: {"description": "Lista de notícias de inteligência"},
        500: {"description": "Erro do servidor", "model": ErrorResponse},
    },
    summary="Obter notícias associadas ao relatório histórico",
    description="Obtém a lista de notícias de inteligência associadas com base no ID do registro de análise histórica (retorna 200 mesmo se vazio)"
)
def get_history_news(
    record_id: str,
    limit: int = Query(20, ge=1, le=100, description="Limite de quantidade de retorno"),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> NewsIntelResponse:
    """
    Obter notícias associadas ao relatório histórico

    Obtém a lista de notícias de inteligência associadas com base no ID do registro de análise histórica ou query_id.
    A resolução de record_id → query_id é feita internamente.

    Args:
        record_id: ID da chave primária do registro de análise histórica (inteiro) ou query_id (string)
        limit: Limite de quantidade de retorno
        db_manager: Dependência do gerenciador de banco de dados

    Returns:
        NewsIntelResponse: Lista de notícias de inteligência
    """
    try:
        service = HistoryService(db_manager)
        items = service.resolve_and_get_news(record_id=record_id, limit=limit)

        response_items = [
            NewsIntelItem(
                title=item.get("title", ""),
                snippet=item.get("snippet"),
                url=item.get("url", "")
            )
            for item in items
        ]

        return NewsIntelResponse(
            total=len(response_items),
            items=response_items
        )

    except Exception as e:
        logger.error(f"Falha ao consultar notícias de inteligência: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Falha ao consultar notícias de inteligência: {str(e)}"
            }
        )


@router.get(
    "/{record_id}/markdown",
    response_model=MarkdownReportResponse,
    responses={
        200: {"description": "Relatório em formato Markdown"},
        404: {"description": "Relatório não encontrado", "model": ErrorResponse},
        500: {"description": "Erro do servidor", "model": ErrorResponse},
    },
    summary="Obter relatório histórico em formato Markdown",
    description="Obtém o relatório de análise completo em formato Markdown com base no ID do registro de análise histórica"
)
def get_history_markdown(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> MarkdownReportResponse:
    """
    Obtém o conteúdo do relatório histórico em formato Markdown

    Gera um relatório Markdown consistente com o formato de notificação push, com base no ID do registro de análise histórica ou query_id.

    Args:
        record_id: ID da chave primária do registro de análise histórica (inteiro) ou query_id (string)
        db_manager: Dependência do gerenciador de banco de dados

    Returns:
        MarkdownReportResponse: Relatório completo em formato Markdown

    Raises:
        HTTPException: 404 - Relatório não encontrado
        HTTPException: 500 - Falha na geração do relatório (erro interno do servidor)
    """
    service = HistoryService(db_manager)

    try:
        markdown_content = service.get_markdown_report(record_id)
    except MarkdownReportGenerationError as e:
        logger.error(f"Falha na geração do relatório Markdown para {record_id}: {e.message}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "generation_failed",
                "message": f"Falha ao gerar relatório Markdown: {e.message}"
            }
        )
    except Exception as e:
        logger.error(f"Falha ao obter relatório Markdown: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Falha ao obter relatório Markdown: {str(e)}"
            }
        )

    if markdown_content is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"Registro de análise com id/query_id={record_id} não encontrado"
            }
        )

    return MarkdownReportResponse(content=markdown_content)