# -*- coding: utf-8 -*-
"""
===================================
Interface de Análise de Ações
===================================

Responsabilidades:
1. Fornecer POST /api/v1/analysis/analyze para acionar a interface de análise
2. Fornecer GET /api/v1/analysis/status/{task_id} para consultar o status da tarefa
3. Fornecer GET /api/v1/analysis/tasks para obter a lista de tarefas
4. Fornecer GET /api/v1/analysis/tasks/stream para interface de push em tempo real SSE

Características:
- Fila de tarefas assíncronas: as tarefas de análise são executadas assincronamente, sem bloquear as requisições
- Prevenção de envio duplicado: retorna 409 se o mesmo código de ação já estiver sendo analisado
- Push em tempo real SSE: notifica o frontend em tempo real sobre mudanças no status da tarefa
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse, StreamingResponse

from api.deps import get_config_dep
from api.v1.schemas.analysis import (
    AnalyzeRequest,
    AnalysisResultResponse,
    TaskAccepted,
    BatchTaskAcceptedResponse,
    BatchTaskAcceptedItem,
    BatchDuplicateTaskItem,
    TaskStatus,
    TaskInfo,
    TaskListResponse,
    DuplicateTaskErrorResponse,
    MarketReviewRequest,
    MarketReviewAccepted,
)
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.history import (
    AnalysisReport,
    ReportMeta,
    ReportSummary,
    ReportStrategy,
    ReportDetails,
)
from data_provider.base import canonical_stock_code, normalize_stock_code
from src.config import Config
from src.core.market_review_lock import (
    MarketReviewExecutionLock as _MarketReviewExecutionLock,
    market_review_lock_path,
    release_market_review_lock as _release_market_review_lock,
    try_acquire_market_review_lock as _try_acquire_market_review_lock,
)
from src.core.market_review_runtime import (
    build_market_review_runtime as _runtime_build_market_review_runtime,
)
from src.analysis_context_pack_overview import (
    extract_analysis_context_pack_overview,
    sanitize_context_snapshot_for_api,
)
from src.market_phase_summary import extract_market_phase_summary
from src.report_language import get_localized_stock_name, normalize_report_language
from src.services.name_to_code_resolver import resolve_name_to_code
from src.services.stock_code_utils import is_code_like
from src.services.task_queue import (
    get_task_queue,
    DuplicateTaskError,
    TaskStatus as TaskStatusEnum,
)
from src.services.run_diagnostics import build_run_diagnostic_summary
from src.utils.data_processing import (
    normalize_model_used,
    parse_json_field,
    extract_fundamental_detail_fields,
    extract_board_detail_fields,
    extract_realtime_detail_fields,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_SUPPORTED_FREE_TEXT_RE = re.compile(r"^[A-Za-z0-9.*\-+\u3400-\u9fff\s]+$")


def _get_task_trace_id(task: Any) -> Optional[str]:
    trace_id = getattr(task, "trace_id", None)
    if isinstance(trace_id, str) and trace_id.strip():
        return trace_id
    task_id = getattr(task, "task_id", None)
    if isinstance(task_id, str) and task_id.strip():
        return task_id
    return None


def _market_review_lock_path(config: Config) -> Path:
    return market_review_lock_path(config)


def _compute_market_review_override_region(config: Config) -> Optional[str]:
    if not getattr(config, "trading_day_check_enabled", True):
        return None

    try:
        from src.core.trading_calendar import (
            get_open_markets_today,
            compute_effective_region,
        )

        open_markets = get_open_markets_today()
        return compute_effective_region(
            getattr(config, "market_review_region", "cn") or "cn",
            open_markets,
        )
    except Exception as exc:
        logger.warning("A filtragem do dia de negociação da revisão de mercado falhou, continuando conforme configurado: %s", exc)
        return None


def _build_market_review_runtime(config: Config, source_message: Optional[Any] = None) -> tuple[Any, Any, Any]:
    return _runtime_build_market_review_runtime(config, source_message)


def _run_market_review_background(
    send_notification: bool,
    override_region: Optional[str] = None,
    lock_token: Optional[_MarketReviewExecutionLock] = None,
    config: Optional[Config] = None,
    query_id: Optional[str] = None,
) -> None:
    """Run market review after the API response has been accepted."""
    from src.core.market_review import run_market_review

    runtime_config = config or get_config_dep()
    try:
        notifier, analyzer, search_service = _build_market_review_runtime(runtime_config)
        review_kwargs = {
            "notifier": notifier,
            "analyzer": analyzer,
            "search_service": search_service,
            "send_notification": send_notification,
            "override_region": override_region,
        }
        if query_id:
            review_kwargs["query_id"] = query_id
        report = run_market_review(**review_kwargs)
        if not report:
            raise RuntimeError("A revisão de mercado não retornou um relatório persistível")
        return {"result": report}
    finally:
        _release_market_review_lock(lock_token)


def _invalid_analysis_input_error() -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "error": "validation_error",
            "message": "Por favor, insira um código ou nome de ação válido",
        },
    )


def _is_obviously_invalid_analysis_input(text: str) -> bool:
    """Reject mixed alphanumeric noise and unsupported symbols early."""
    if not text or is_code_like(text):
        return False

    if not _SUPPORTED_FREE_TEXT_RE.fullmatch(text):
        return True

    has_letters = any(ch.isalpha() and ch.isascii() for ch in text)
    has_digits = any(ch.isdigit() for ch in text)
    return has_letters and has_digits


def _resolve_and_normalize_input(raw_value: str) -> str:
    """
    Resolve and normalize a stock input for analysis requests.

    Code-like values keep the existing canonical path.
    Non-code inputs must resolve to a known stock code. Obvious garbage
    input is rejected before expensive resolver and task-queue work.
    """
    text = (raw_value or "").strip()
    if not text:
        return ""

    if is_code_like(text):
        return canonical_stock_code(text)

    if _is_obviously_invalid_analysis_input(text):
        raise _invalid_analysis_input_error()

    resolved = resolve_name_to_code(text)
    if resolved:
        return canonical_stock_code(resolved)

    raise _invalid_analysis_input_error()


# ============================================================
# POST /analyze - Acionar Análise de Ações
# ============================================================

@router.post(
    "/analyze",
    response_model=AnalysisResultResponse,
    responses={
        200: {"description": "Análise concluída (modo síncrono)", "model": AnalysisResultResponse},
        202: {
            "description": "Tarefa de análise aceita (modo assíncrono)",
            "model": Union[TaskAccepted, BatchTaskAcceptedResponse],
        },
        400: {"description": "Erro nos parâmetros da requisição", "model": ErrorResponse},
        409: {"description": "A ação já está sendo analisada, envio duplicado rejeitado", "model": DuplicateTaskErrorResponse},
        500: {"description": "Falha na análise", "model": ErrorResponse},
    },
    summary="Acionar análise de ações",
    description="Inicia uma tarefa de análise inteligente de IA, suportando modos síncrono e assíncrono. No modo assíncrono, o mesmo código de ação não pode ser enviado repetidamente."
)
def trigger_analysis(
        request: AnalyzeRequest,
        config: Config = Depends(get_config_dep)
) -> Union[AnalysisResultResponse, JSONResponse]:
    """
    Acionar análise de ações
    
    Inicia uma tarefa de análise inteligente de IA, suportando análise de uma única ação ou em lote
    
    Fluxo:
    1. Valida os parâmetros da requisição
    2. Modo assíncrono: verifica duplicidade -> envia para a fila de tarefas -> retorna 202
    3. Modo síncrono: executa a análise diretamente -> retorna 200
    
    Args:
        request: Parâmetros da requisição de análise
        config: Dependência de configuração
        
    Returns:
        AnalysisResultResponse: Resultado da análise (modo síncrono)
        TaskAccepted | BatchTaskAcceptedResponse: Tarefa aceita (modo assíncrono, retorna 202)
        
    Raises:
        HTTPException: 400 - Erro nos parâmetros da requisição
        HTTPException: 409 - A ação já está sendo analisada
        HTTPException: 500 - Falha na análise
    """
    # Valida os parâmetros da requisição
    stock_codes = []
    if request.stock_code:
        stock_codes.append(request.stock_code)
    if request.stock_codes:
        stock_codes.extend(request.stock_codes)

    if not stock_codes:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": "Deve ser fornecido o parâmetro stock_code ou stock_codes"
            }
        )

    # Normalize and de-duplicate inputs while preserving compatibility.
    resolved = [_resolve_and_normalize_input(c) for c in stock_codes]
    
    seen = set()
    unique_codes = []
    for code in resolved:
        if not code:
            continue
        # Use normalize_stock_code to ensure '600519' and '600519.SH' are merged
        norm = normalize_stock_code(code)
        if norm not in seen:
            seen.add(norm)
            unique_codes.append(code)
    
    stock_codes = unique_codes

    # Limit the number of stocks in a single request to prevent DoS
    MAX_BATCH_SIZE = 50
    if len(stock_codes) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": f"Uma única requisição de análise suporta no máximo {MAX_BATCH_SIZE} ações"
            }
        )

    if not stock_codes:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": "O código da ação não pode ser vazio ou conter apenas espaços em branco"
            }
        )

    # Sync mode only supports single-stock analysis.
    if not request.async_mode:
        if len(stock_codes) > 1:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation_error",
                    "message": "O modo síncrono suporta apenas a análise de uma única ação, por favor, use async_mode=true para análise em lote"
                }
            )
        return _handle_sync_analysis(stock_codes[0], request)

    # Async mode submits one task per stock.
    return _handle_async_analysis_batch(stock_codes, request)


def _handle_async_analysis_batch(
    stock_codes: list,
    request: AnalyzeRequest
) -> JSONResponse:
    """
    Handle asynchronous analysis requests, including batch submission.
    """
    task_queue = get_task_queue()
    
    # Preserve metadata for single-stock requests. For batch requests,
    # only carry through metadata that semantically applies to the whole
    # batch, such as import/image source tracking.
    is_single = len(stock_codes) == 1
    preserve_batch_metadata = request.selection_source in {"import", "image"}

    stock_name = request.stock_name if is_single else None
    original_query = request.original_query if (is_single or preserve_batch_metadata) else None
    selection_source = request.selection_source if (is_single or preserve_batch_metadata) else None
    notify = getattr(request, "notify", None)
    if notify is None:
        config = get_config_dep()
        notify = getattr(config, "web_auto_push_enabled", True)
    skills = getattr(request, "skills", None)

    submit_kwargs = dict(
        stock_codes=stock_codes,
        stock_name=stock_name,
        original_query=original_query,
        selection_source=selection_source,
        report_type=request.report_type,
        force_refresh=request.force_refresh,
        notify=notify,
    )
    if skills is not None:
        submit_kwargs["skills"] = skills

    accepted_tasks, duplicate_errors = task_queue.submit_tasks_batch(**submit_kwargs)

    accepted = [
        BatchTaskAcceptedItem(
            task_id=task.task_id,
            trace_id=_get_task_trace_id(task),
            stock_code=task.stock_code,
            status="pending",
            message=f"Tarefa de análise adicionada à fila: {task.stock_code}",
        )
        for task in accepted_tasks
    ]
    duplicates = [
        BatchDuplicateTaskItem(
            stock_code=dup.stock_code,
            existing_task_id=dup.existing_task_id,
            message=str(dup),
        )
        for dup in duplicate_errors
    ]
    
    # Apenas uma ação e rejeitada: mantém a compatibilidade 409
    if len(stock_codes) == 1 and duplicates:
        dup = duplicates[0]
        error_response = DuplicateTaskErrorResponse(
            error="duplicate_task",
            message=dup.message,
            stock_code=dup.stock_code,
            existing_task_id=dup.existing_task_id,
        )
        return JSONResponse(
            status_code=409,
            content=error_response.model_dump()
        )
    
    # Apenas uma ação e bem-sucedida: mantém a compatibilidade do formato de resposta original
    if len(stock_codes) == 1 and accepted:
        task_accepted = TaskAccepted(
            task_id=accepted[0].task_id,
            trace_id=accepted[0].trace_id,
            status="pending",
            message=accepted[0].message,
        )
        return JSONResponse(
            status_code=202,
            content=task_accepted.model_dump()
        )
    
    # Lote: retorna o resultado consolidado
    batch_response = BatchTaskAcceptedResponse(
        accepted=accepted,
        duplicates=duplicates,
        message=f"Foram enviadas {len(accepted)} tarefas, {len(duplicates)} duplicadas foram ignoradas",
    )
    return JSONResponse(
        status_code=202,
        content=batch_response.model_dump()
    )


def _handle_sync_analysis(
    stock_code: str,
    request: AnalyzeRequest
) -> AnalysisResultResponse:
    """
    Processa requisições de análise síncronas
    
    Executa a análise diretamente e retorna o resultado após a conclusão
    """
    import uuid
    from src.services.analysis_service import AnalysisService
    
    query_id = uuid.uuid4().hex
    
    try:
        service = AnalysisService()
        send_notification = getattr(request, "notify", None)
        if send_notification is None:
            config = get_config_dep()
            send_notification = getattr(config, "web_auto_push_enabled", True)
            
        result = service.analyze_stock(
            stock_code=stock_code,
            report_type=request.report_type,
            force_refresh=request.force_refresh,
            query_id=query_id,
            send_notification=send_notification,
            skills=getattr(request, "skills", None),
        )

        if result is None:
            error_message = service.last_error or f"Falha ao analisar a ação {stock_code}"
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "analysis_failed",
                    "message": error_message,
                }
            )

        # Constrói a estrutura do relatório
        report_data = result.get("report", {})
        context_snapshot, fundamental_snapshot = _load_sync_fundamental_sources(
            query_id=query_id,
            stock_code=result.get("stock_code", stock_code),
        )
        report = _build_analysis_report(
            report_data,
            query_id,
            stock_code,
            result.get("stock_name"),
            context_snapshot=context_snapshot,
            fallback_fundamental_payload=fundamental_snapshot,
        )

        return AnalysisResultResponse(
            query_id=query_id,
            trace_id=result.get("trace_id") or query_id,
            stock_code=result.get("stock_code", stock_code),
            stock_name=result.get("stock_name"),
            report=report.model_dump() if report else None,
            diagnostic_summary=result.get("diagnostic_summary"),
            created_at=datetime.now().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Falha na análise: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Ocorreu um erro durante o processo de análise: {str(e)}"
            }
        )


# ============================================================
# POST /market-review - Acionar Revisão de Mercado
# ============================================================

@router.post(
    "/market-review",
    response_model=MarketReviewAccepted,
    status_code=202,
    responses={
        202: {"description": "Tarefa de revisão de mercado aceita", "model": MarketReviewAccepted},
        409: {"description": "A revisão de mercado está em execução", "model": ErrorResponse},
        500: {"description": "Falha no envio", "model": ErrorResponse},
    },
    summary="Acionar revisão de mercado",
    description="Envia uma tarefa de revisão de mercado em segundo plano, reutilizando o pipeline de revisão de mercado da CLI e salvando o relatório. A interface fornece apenas prevenção de duplicação dentro do processo/máquina única; para implantações de múltiplas instâncias (múltiplos Workers/contêineres), é necessário combinar com um mecanismo de idempotência externo para evitar acionamentos duplicados.",
)
def trigger_market_review(
    request: Optional[MarketReviewRequest] = Body(None),
    config: Config = Depends(get_config_dep),
) -> MarketReviewAccepted:
    """Trigger market review from Web/API without blocking the request."""
    request = request or MarketReviewRequest()

    send_notification = getattr(request, "send_notification", None)
    if send_notification is None:
        send_notification = getattr(config, "web_auto_push_enabled", True)

    override_region = _compute_market_review_override_region(config)
    if override_region == "":
        return MarketReviewAccepted(
            status="accepted",
            message="Todos os mercados relevantes para a revisão de mercado de hoje não são dias de negociação, a revisão de mercado foi ignorada",
            send_notification=send_notification,
            trace_id=None,
        )

    lock_token = _try_acquire_market_review_lock(config)
    if lock_token is None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "duplicate_market_review",
                "message": "A revisão de mercado já está em execução, por favor, tente novamente mais tarde",
            },
        )

    try:
        task_id = uuid.uuid4().hex
        task = get_task_queue().submit_background_task(
            lambda: _run_market_review_background(
                send_notification,
                override_region=override_region,
                lock_token=lock_token,
                config=config,
                query_id=task_id,
            ),
            stock_code="market_review",
            stock_name="Revisão de Mercado",
            message="Tarefa de revisão de mercado enviada",
            task_id=task_id,
        )
    except Exception:
        _release_market_review_lock(lock_token)
        raise

    return MarketReviewAccepted(
        status="accepted",
        message="Tarefa de revisão de mercado enviada, o relatório será salvo e as notificações serão enviadas conforme configurado após a conclusão",
        send_notification=send_notification,
        task_id=task.task_id,
        trace_id=_get_task_trace_id(task),
    )


# ============================================================
# GET /tasks - Obter Lista de Tarefas
# ============================================================

@router.get(
    "/tasks",
    response_model=TaskListResponse,
    responses={
        200: {"description": "Lista de tarefas"},
    },
    summary="Obter lista de tarefas de análise",
    description="Obtém todas as tarefas de análise atuais, podendo filtrar por status"
)
def get_task_list(
    status: Optional[str] = Query(
        None,
        description="Filtrar por status: pending, processing, completed, failed (suporta múltiplos separados por vírgula)"
    ),
    limit: int = Query(20, description="Limite de quantidade de retorno", ge=1, le=100),
) -> TaskListResponse:
    """
    Obter lista de tarefas de análise
    
    Args:
        status: Filtro de status (opcional)
        limit: Limite de quantidade de retorno
        
    Returns:
        TaskListResponse: Resposta da lista de tarefas
    """
    task_queue = get_task_queue()
    
    # Obtém todas as tarefas
    all_tasks = task_queue.list_all_tasks(limit=limit)
    
    # Filtragem por status
    if status:
        status_list = [s.strip().lower() for s in status.split(",")]
        all_tasks = [t for t in all_tasks if t.status.value in status_list]
    
    # Informações estatísticas
    stats = task_queue.get_task_stats()
    
    # Converte para Schema
    task_infos = [
        TaskInfo(
            task_id=t.task_id,
            trace_id=_get_task_trace_id(t),
            stock_code=t.stock_code,
            stock_name=t.stock_name,
            status=t.status.value,
            progress=t.progress,
            message=t.message,
            report_type=t.report_type,
            created_at=t.created_at.isoformat(),
            started_at=t.started_at.isoformat() if t.started_at else None,
            completed_at=t.completed_at.isoformat() if t.completed_at else None,
            error=t.error,
            original_query=t.original_query,
            selection_source=t.selection_source,
        )
        for t in all_tasks
    ]
    
    return TaskListResponse(
        total=stats["total"],
        pending=stats["pending"],
        processing=stats["processing"],
        tasks=task_infos,
    )


# ============================================================
# GET /tasks/stream - Push em Tempo Real SSE
# ============================================================

@router.get(
    "/tasks/stream",
    responses={
        200: {"description": "Fluxo de eventos SSE", "content": {"text/event-stream": {}}},
    },
    summary="Fluxo SSE de status de tarefas",
    description="Envia mudanças de status de tarefas em tempo real via Server-Sent Events"
)
async def task_stream():
    """
    Fluxo SSE de status de tarefas
    
    Tipos de evento:
    - connected: Conexão bem-sucedida
    - task_created: Nova tarefa criada
    - task_started: Tarefa iniciada
    - task_progress: Progresso da fase da tarefa atualizado
    - task_completed: Tarefa concluída
    - task_failed: Tarefa falhou
    - heartbeat: Batimento cardíaco (a cada 30 segundos)
    
    Returns:
        StreamingResponse: Fluxo de eventos SSE
    """
    async def event_generator():
        task_queue = get_task_queue()
        event_queue: asyncio.Queue = asyncio.Queue()
        
        # Envia evento de conexão bem-sucedida
        yield _format_sse_event("connected", {"message": "Conectado ao fluxo de tarefas"})
        
        # Envia tarefas atualmente pendentes
        pending_tasks = task_queue.list_pending_tasks()
        for task in pending_tasks:
            yield _format_sse_event("task_created", task.to_dict())
        
        # Assina eventos de tarefa
        task_queue.subscribe(event_queue)
        
        try:
            while True:
                try:
                    # Espera por eventos, envia batimento cardíaco se houver timeout
                    event = await asyncio.wait_for(event_queue.get(), timeout=30)
                    yield _format_sse_event(event["type"], event["data"])
                except asyncio.TimeoutError:
                    # Batimento cardíaco
                    yield _format_sse_event("heartbeat", {
                        "timestamp": datetime.now().isoformat()
                    })
        except asyncio.CancelledError:
            logger.debug("Cliente SSE desconectado, cancelando gerador de eventos")
            raise
        finally:
            task_queue.unsubscribe(event_queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Desabilita o buffer do Nginx
        }
    )


def _format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """
    Formata um evento SSE
    
    Args:
        event_type: Tipo do evento
        data: Dados do evento
        
    Returns:
        String no formato SSE
    """
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _datetime_to_iso(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        return value
    return None


def _extract_report_created_at(payload: Dict[str, Any]) -> Optional[str]:
    report = payload.get("report")
    if not isinstance(report, dict):
        return None

    meta = report.get("meta")
    if not isinstance(meta, dict):
        return None

    return _datetime_to_iso(meta.get("created_at"))


def _prepare_report_for_task_enrichment(
    report_data: Dict[str, Any],
    created_at: Optional[str],
) -> Dict[str, Any]:
    enriched_report = dict(report_data)
    meta = dict(enriched_report.get("meta") or {})
    if created_at and not _datetime_to_iso(meta.get("created_at")):
        meta["created_at"] = created_at
    enriched_report["meta"] = meta
    return enriched_report


def _build_task_analysis_result(task: Any) -> AnalysisResultResponse:
    """
    Normalize an in-memory completed task result to the public API contract.

    Older AnalysisService payloads contain stock_code/stock_name/report only.
    The status endpoint owns the task metadata, so it can supply the missing
    response fields without waiting for the database fallback path.
    """
    payload = dict(task.result)
    if not payload.get("query_id"):
        payload["query_id"] = task.task_id
    if not payload.get("trace_id"):
        payload["trace_id"] = _get_task_trace_id(task) or task.task_id
    if not payload.get("stock_code"):
        payload["stock_code"] = task.stock_code

    if not payload.get("stock_name") and getattr(task, "stock_name", None):
        payload["stock_name"] = task.stock_name

    if not payload.get("created_at"):
        payload["created_at"] = (
            _extract_report_created_at(payload)
            or _datetime_to_iso(getattr(task, "created_at", None))
            or _datetime_to_iso(getattr(task, "completed_at", None))
            or datetime.now().isoformat()
        )

    report_data = payload.get("report")
    stock_code = payload.get("stock_code")
    query_id = payload.get("query_id")
    if isinstance(report_data, dict) and stock_code and query_id:
        context_snapshot, fundamental_snapshot = _load_sync_fundamental_sources(
            query_id=query_id,
            stock_code=stock_code,
        )
        if context_snapshot is not None or fundamental_snapshot is not None:
            try:
                report = _build_analysis_report(
                    _prepare_report_for_task_enrichment(
                        report_data,
                        payload.get("created_at"),
                    ),
                    query_id,
                    stock_code,
                    payload.get("stock_name") or getattr(task, "stock_name", None),
                    context_snapshot=context_snapshot,
                    fallback_fundamental_payload=fundamental_snapshot,
                )
                payload["report"] = report.model_dump()
            except Exception as e:
                logger.debug(
                    "O enriquecimento do relatório de tarefa em memória falhou (fail-open): task_id=%s err=%s",
                    getattr(task, "task_id", None),
                    e,
                )

    return AnalysisResultResponse.model_validate(payload)


# ============================================================
# GET /status/{task_id} - Consultar Status de Tarefa Única
# ============================================================

@router.get(
    "/status/{task_id}",
    response_model=TaskStatus,
    responses={
        200: {"description": "Status da tarefa"},
        404: {"description": "Tarefa não encontrada", "model": ErrorResponse},
    },
    summary="Consultar status da tarefa de análise",
    description="Consulta o status de uma única tarefa com base no task_id"
)
def get_analysis_status(task_id: str) -> TaskStatus:
    """
    Consultar status da tarefa de análise
    
    Prioriza a consulta na fila de tarefas; se não existir, consulta o histórico no banco de dados
    
    Args:
        task_id: ID da tarefa
        
    Returns:
        TaskStatus: Informações de status da tarefa
        
    Raises:
        HTTPException: 404 - Tarefa não encontrada
    """
    # 1. Primeiro, consulta na fila de tarefas
    task_queue = get_task_queue()
    task = task_queue.get_task(task_id)
    
    if task:
        result: Optional[AnalysisResultResponse] = None
        market_review_report = None

        if task.status == TaskStatusEnum.COMPLETED and isinstance(task.result, dict):
            if task.stock_code == "market_review":
                report_text = task.result.get("result")
                if isinstance(report_text, str) and report_text.strip():
                    market_review_report = report_text
            else:
                try:
                    result = _build_task_analysis_result(task)
                except Exception:
                    logger.warning(
                        "Falha ao analisar o resultado da tarefa, retornando vazio: task_id=%s",
                        task.task_id,
                    )

        return TaskStatus(
            task_id=task.task_id,
            trace_id=_get_task_trace_id(task),
            status=task.status.value,
            progress=task.progress,
            result=result,
            market_review_report=market_review_report,
            error=task.error,
            stock_name=task.stock_name,
            original_query=task.original_query,
            selection_source=task.selection_source,
            skills=getattr(task, "skills", None),
        )
    
    # 2. Consulta registros concluídos no banco de dados
    try:
        from src.storage import DatabaseManager
        db = DatabaseManager.get_instance()
        records = db.get_analysis_history(query_id=task_id, limit=1)

        if records:
            record = records[0]
            raw_result = parse_json_field(record.raw_result)
            if getattr(record, "report_type", None) == "market_review":
                market_review_report = None
                if isinstance(raw_result, dict):
                    report_text = raw_result.get("raw_response") or raw_result.get("market_review_report")
                    if isinstance(report_text, str) and report_text.strip():
                        market_review_report = report_text
                if not market_review_report and record.news_content:
                    market_review_report = record.news_content

                return TaskStatus(
                    task_id=task_id,
                    trace_id=task_id,
                    status="completed",
                    progress=100,
                    result=None,
                    market_review_report=market_review_report,
                    error=None,
                    stock_name=record.name,
                )

            model_used = normalize_model_used(
                (raw_result or {}).get("model_used") if isinstance(raw_result, dict) else None
            )
            report_language = normalize_report_language(
                (raw_result or {}).get("report_language") if isinstance(raw_result, dict) else None
            )
            stock_name = get_localized_stock_name(record.name, record.code, report_language)

            # Extract current_price / change_pct from context_snapshot
            skills = None
            context_snapshot = parse_json_field(getattr(record, 'context_snapshot', None))
            analysis_context_pack_overview = extract_analysis_context_pack_overview(context_snapshot)
            market_phase_summary = extract_market_phase_summary(context_snapshot)
            api_context_snapshot = sanitize_context_snapshot_for_api(context_snapshot)
            if context_snapshot and isinstance(context_snapshot, dict):
                raw_skills = context_snapshot.get("skills")
                if isinstance(raw_skills, list):
                    skills = [str(skill) for skill in raw_skills]
            realtime_fields = extract_realtime_detail_fields(context_snapshot)
            current_price = realtime_fields.get("current_price")
            change_pct = realtime_fields.get("change_pct")
            fallback_fundamental = db.get_latest_fundamental_snapshot(
                query_id=task_id,
                code=record.code,
            )
            extracted_fundamental = extract_fundamental_detail_fields(
                context_snapshot=context_snapshot,
                fallback_fundamental_payload=fallback_fundamental,
            )
            extracted_boards = extract_board_detail_fields(
                context_snapshot=context_snapshot,
                fallback_fundamental_payload=fallback_fundamental,
            )
            has_board_details = bool(extracted_boards.get("belong_boards")) or extracted_boards.get("sector_rankings") is not None
            details = None
            if any(extracted_fundamental.values()) or has_board_details or context_snapshot is not None or analysis_context_pack_overview is not None:
                details = ReportDetails(
                    news_content=getattr(record, "news_content", None),
                    raw_result=raw_result,
                    context_snapshot=api_context_snapshot,
                    analysis_context_pack_overview=analysis_context_pack_overview,
                    financial_report=extracted_fundamental.get("financial_report"),
                    dividend_metrics=extracted_fundamental.get("dividend_metrics"),
                    belong_boards=extracted_boards.get("belong_boards"),
                    sector_rankings=extracted_boards.get("sector_rankings"),
                )

            # Build report from DB record so completed tasks return real data
            report_dict = AnalysisReport(
                meta=ReportMeta(
                    id=record.id,
                    query_id=task_id,
                    stock_code=record.code,
                    stock_name=stock_name,
                    report_type=getattr(record, 'report_type', None),
                    report_language=report_language,
                    created_at=record.created_at.isoformat() if record.created_at else None,
                    model_used=model_used,
                    current_price=current_price,
                    change_pct=change_pct,
                    market_phase_summary=market_phase_summary,
                ),
                summary=ReportSummary(
                    sentiment_score=record.sentiment_score,
                    operation_advice=record.operation_advice,
                    trend_prediction=record.trend_prediction,
                    analysis_summary=record.analysis_summary,
                ),
                strategy=ReportStrategy(
                    ideal_buy=_stringify_report_strategy_value(getattr(record, 'ideal_buy', None)),
                    secondary_buy=_stringify_report_strategy_value(getattr(record, 'secondary_buy', None)),
                    stop_loss=_stringify_report_strategy_value(getattr(record, 'stop_loss', None)),
                    take_profit=_stringify_report_strategy_value(getattr(record, 'take_profit', None)),
                ),
                details=details,
            ).model_dump()
            return TaskStatus(
                task_id=task_id,
                trace_id=task_id,
                status="completed",
                progress=100,
                result=AnalysisResultResponse(
                    query_id=task_id,
                    trace_id=task_id,
                    stock_code=record.code,
                    stock_name=stock_name,
                    report=report_dict,
                    diagnostic_summary=build_run_diagnostic_summary(
                        context_snapshot=context_snapshot,
                        raw_result=raw_result,
                        report_saved=True,
                        query_id=task_id,
                        stock_code=record.code,
                    ),
                    created_at=record.created_at.isoformat() if record.created_at else datetime.now().isoformat()
                ),
                error=None,
                skills=skills,
            )

    except Exception as e:
        logger.error(f"Falha ao consultar o status da tarefa: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Falha ao consultar o status da tarefa: {str(e)}"
            }
        )

    # 3. Tarefa não existe
    raise HTTPException(
        status_code=404,
        detail={
            "error": "not_found",
            "message": f"A tarefa {task_id} não existe ou expirou"
        }
    )


# ============================================================
# Funções Auxiliares
# ============================================================

def _load_sync_fundamental_sources(
    query_id: str,
    stock_code: str,
) -> tuple[Optional[Any], Optional[Dict[str, Any]]]:
    """
    Load context_snapshot and fallback fundamental snapshot for sync analyze response.
    """
    try:
        from src.storage import DatabaseManager

        db = DatabaseManager.get_instance()
        records = db.get_analysis_history(query_id=query_id, code=stock_code, limit=1)
        context_snapshot = None
        if records:
            context_snapshot = parse_json_field(getattr(records[0], "context_snapshot", None))

        fallback_fundamental = db.get_latest_fundamental_snapshot(
            query_id=query_id,
            code=stock_code,
        )
        return context_snapshot, fallback_fundamental
    except Exception as e:
        logger.debug(
            "Falha ao carregar fontes fundamentais síncronas (fail-open): query_id=%s stock_code=%s err=%s",
            query_id,
            stock_code,
            e,
        )
        return None, None


def _stringify_report_strategy_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _build_analysis_report(
        report_data: Dict[str, Any],
        query_id: str,
        stock_code: str,
        stock_name: Optional[str] = None,
        context_snapshot: Optional[Any] = None,
        fallback_fundamental_payload: Optional[Dict[str, Any]] = None,
) -> AnalysisReport:
    """
    Constrói um relatório de análise em conformidade com a especificação da API
    
    Args:
        report_data: Dados brutos do relatório
        query_id: ID da consulta
        stock_code: Código da ação
        stock_name: Nome da ação
        context_snapshot: Snapshot do contexto (opcional)
        fallback_fundamental_payload: Payload do snapshot fundamental (opcional)
        
    Returns:
        AnalysisReport: Relatório de análise estruturado
    """
    meta_data = report_data.get("meta", {})
    summary_data = report_data.get("summary", {})
    strategy_data = report_data.get("strategy", {})
    details_data = report_data.get("details", {})
    report_language = normalize_report_language(
        meta_data.get("report_language")
        or (context_snapshot or {}).get("report_language")
        or getattr(Config.get_instance(), "report_language", "zh")
    )
    localized_stock_name = get_localized_stock_name(
        meta_data.get("stock_name", stock_name),
        meta_data.get("stock_code", stock_code),
        report_language,
    )
    realtime_fields = extract_realtime_detail_fields(context_snapshot)
    current_price = meta_data.get("current_price")
    if current_price is None:
        current_price = realtime_fields.get("current_price")
    change_pct = meta_data.get("change_pct")
    if change_pct is None:
        change_pct = realtime_fields.get("change_pct")
    market_phase_summary = extract_market_phase_summary(context_snapshot)

    meta = ReportMeta(
        query_id=meta_data.get("query_id", query_id),
        stock_code=meta_data.get("stock_code", stock_code),
        stock_name=localized_stock_name,
        report_type=meta_data.get("report_type", "detailed"),
        report_language=report_language,
        created_at=meta_data.get("created_at", datetime.now().isoformat()),
        current_price=current_price,
        change_pct=change_pct,
        model_used=normalize_model_used(meta_data.get("model_used")),
        market_phase_summary=market_phase_summary,
    )

    summary = ReportSummary(
        analysis_summary=summary_data.get("analysis_summary"),
        operation_advice=summary_data.get("operation_advice"),
        trend_prediction=summary_data.get("trend_prediction"),
        sentiment_score=summary_data.get("sentiment_score"),
        sentiment_label=summary_data.get("sentiment_label")
    )

    strategy = None
    if strategy_data:
        strategy = ReportStrategy(
            ideal_buy=_stringify_report_strategy_value(strategy_data.get("ideal_buy")),
            secondary_buy=_stringify_report_strategy_value(strategy_data.get("secondary_buy")),
            stop_loss=_stringify_report_strategy_value(strategy_data.get("stop_loss")),
            take_profit=_stringify_report_strategy_value(strategy_data.get("take_profit"))
        )

    extracted_fundamental = extract_fundamental_detail_fields(
        context_snapshot=context_snapshot,
        fallback_fundamental_payload=fallback_fundamental_payload,
    )
    extracted_boards = extract_board_detail_fields(
        context_snapshot=context_snapshot,
        fallback_fundamental_payload=fallback_fundamental_payload,
    )
    analysis_context_pack_overview = extract_analysis_context_pack_overview(context_snapshot)
    api_context_snapshot = sanitize_context_snapshot_for_api(context_snapshot)
    details = None
    has_board_details = bool(extracted_boards.get("belong_boards")) or extracted_boards.get("sector_rankings") is not None
    if details_data or any(extracted_fundamental.values()) or has_board_details or context_snapshot is not None or analysis_context_pack_overview is not None:
        details = ReportDetails(
            news_content=details_data.get("news_summary") or details_data.get("news_content"),
            raw_result=details_data,
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