# -*- coding: utf-8 -*-
"""
===================================
Sistema de Análise Inteligente de Ações - Módulo de Revisão de Mercado (Suporte a Ações A / HK / EUA)
===================================

Responsabilidades:
1. Selecionar região do mercado baseada na configuração MARKET_REVIEW_REGION (cn / hk / us / both)
2. Executar análise e gerar relatório de revisão de mercado
3. Salvar e enviar o relatório de revisão de mercado
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from src.config import get_config
from src.notification import NotificationService
from src.market_analyzer import MarketAnalyzer
from src.report_language import normalize_report_language
from src.search_service import SearchService
from src.analyzer import AnalysisResult, GeminiAnalyzer


logger = logging.getLogger(__name__)

MARKET_REVIEW_HISTORY_CODE = "MARKET"
MARKET_REVIEW_REPORT_TYPE = "market_review"
_MARKET_REVIEW_MARKETS = (
    ('cn', 'cn_title', 'Ações A'),
    ('hk', 'hk_title', 'Ações de HK'),
    ('us', 'us_title', 'Ações dos EUA'),
)
_MARKET_REVIEW_REGION_ORDER = tuple(market for market, _, _ in _MARKET_REVIEW_MARKETS)
_VALID_MARKET_REVIEW_REGIONS = frozenset(_MARKET_REVIEW_REGION_ORDER)


def _get_market_review_text(language: str) -> dict[str, str]:
    normalized = normalize_report_language(language)
    if normalized == "en":
        return {
            "root_title": "# 🎯 Market Review",
            "push_title": "🎯 Market Review",
            "cn_title": "# A-share Market Recap",
            "us_title": "# US Market Recap",
            "hk_title": "# HK Market Recap",
            "separator": "> Next market recap follows",
        }
    if normalized == "pt":
        return {
            "root_title": "# 🎯 Revisão do Mercado",
            "push_title": "🎯 Revisão do Mercado",
            "cn_title": "# Revisão do Mercado de Ações A",
            "us_title": "# Revisão do Mercado Americano",
            "hk_title": "# Revisão do Mercado de Hong Kong",
            "separator": "> A seguir, revisão do próximo mercado",
        }
    return {
        "root_title": "# 🎯 Revisão do Mercado",
        "push_title": "🎯 Revisão do Mercado",
        "cn_title": "# Revisão do Mercado de Ações A",
        "us_title": "# Revisão do Mercado Americano",
        "hk_title": "# Revisão do Mercado de Hong Kong",
        "separator": "> A seguir, revisão do próximo mercado",
    }


def _resolve_market_review_regions(raw_region: Optional[str]) -> list[str]:
    """Normalize MARKET_REVIEW_REGION into an ordered, non-empty region list."""

    region = (raw_region or 'cn').strip().lower()
    if region == 'both':
        return list(_MARKET_REVIEW_REGION_ORDER)
    if ',' in region:
        requested = {
            item.strip().lower()
            for item in region.split(',')
            if item.strip().lower() in _VALID_MARKET_REVIEW_REGIONS
        }
        return [market for market in _MARKET_REVIEW_REGION_ORDER if market in requested] or ['cn']
    if region in _VALID_MARKET_REVIEW_REGIONS:
        return [region]
    return ['cn']


def run_market_review(
    notifier: NotificationService,
    analyzer: Optional[GeminiAnalyzer] = None,
    search_service: Optional[SearchService] = None,
    send_notification: bool = True,
    merge_notification: bool = False,
    override_region: Optional[str] = None,
    query_id: Optional[str] = None,
) -> Optional[str]:
    """
    Executa a análise da revisão de mercado

    Args:
        notifier: Serviço de notificação
        analyzer: Analisador de IA (opcional)
        search_service: Serviço de pesquisa (opcional)
        send_notification: Se deve enviar notificação
        merge_notification: Se deve mesclar notificações (ignorar notificação atual e enviar tudo pela camada principal, Issue #190)
        override_region: Sobrescreve a market_review_region configurada (Issue #373)
        query_id: ID do histórico associado; API fornece task_id, gerado automaticamente para CLI/Bot se vazio

    Returns:
        Texto do relatório da revisão de mercado
    """
    logger.info("Iniciando análise de revisão do mercado...")
    config = get_config()
    review_text = _get_market_review_text(getattr(config, "report_language", "zh"))
    raw_region = (
        override_region
        if override_region is not None
        else (getattr(config, 'market_review_region', 'cn') or 'cn')
    )
    run_markets = _resolve_market_review_regions(raw_region)
    persist_region = ','.join(run_markets) if len(run_markets) > 1 else run_markets[0]

    try:
        if len(run_markets) > 1:
            # Execução sequencial multi-mercado, mesclando relatórios
            parts = []
            market_light_snapshots: Dict[str, Dict[str, Any]] = {}
            for mkt, title_key, label in _MARKET_REVIEW_MARKETS:
                if mkt not in run_markets:
                    continue
                logger.info("Gerando relatório de revisão do mercado para %s...", label)
                mkt_analyzer = MarketAnalyzer(
                    search_service=search_service, analyzer=analyzer, region=mkt
                )
                review_result = mkt_analyzer.run_daily_review_with_snapshot()
                mkt_report = review_result.report
                market_light_snapshots[mkt] = review_result.market_light_snapshot
                if mkt_report:
                    parts.append(f"{review_text[title_key]}\n\n{mkt_report}")
            if parts:
                review_report = f"\n\n---\n\n{review_text['separator']}\n\n".join(parts)
            else:
                review_report = None
        else:
            run_region = run_markets[0]
            market_analyzer = MarketAnalyzer(
                search_service=search_service,
                analyzer=analyzer,
                region=run_region,
            )
            review_result = market_analyzer.run_daily_review_with_snapshot()
            review_report = review_result.report
            market_light_snapshots = {run_region: review_result.market_light_snapshot}
        
        if review_report:
            # Salvar relatório em arquivo
            date_str = datetime.now().strftime('%Y%m%d')
            report_filename = f"market_review_{date_str}.md"
            filepath = notifier.save_report_to_file(
                f"{review_text['root_title']}\n\n{review_report}",
                report_filename
            )
            logger.info(f"Relatório de revisão do mercado salvo: {filepath}")

            _persist_market_review_history(
                review_report=review_report,
                markdown_report=f"{review_text['root_title']}\n\n{review_report}",
                region=persist_region,
                config=config,
                query_id=query_id,
                market_light_snapshots=market_light_snapshots,
            )
            
            # Enviar notificação (ignorado no modo de mesclagem, enviado pela camada main)
            if merge_notification and send_notification:
                logger.info("Modo de mesclagem de notificação: pulando notificação individual da revisão do mercado, será enviada após a revisão da ação+mercado")
            elif send_notification and notifier.is_available():
                # Adicionar título
                report_content = f"{review_text['push_title']}\n\n{review_report}"

                success = notifier.send(report_content, email_send_to_all=True, route_type="report")
                if success:
                    logger.info("Notificação da revisão de mercado enviada com sucesso")
                else:
                    logger.warning("Falha ao enviar notificação da revisão de mercado")
            elif not send_notification:
                logger.info("Notificações puladas (--no-notify)")
            
            return review_report
        
    except Exception as e:
        logger.error(f"Falha na análise da revisão do mercado: {e}")
    
    return None


def _persist_market_review_history(
    *,
    review_report: str,
    markdown_report: str,
    region: str,
    config: object,
    query_id: Optional[str] = None,
    market_light_snapshots: Optional[Dict[str, Dict[str, Any]]] = None,
) -> int:
    """Persist market review output into the existing analysis history table."""
    try:
        from src.storage import DatabaseManager

        report_language = normalize_report_language(getattr(config, "report_language", "zh"))
        summary = _summarize_market_review(review_report, report_language)
        if report_language == "en":
            stock_name = "Market Review"
            operation_advice = "View review"
            trend_prediction = "Market review"
        elif report_language == "pt":
            stock_name = "Revisão do Mercado"
            operation_advice = "Ver revisão"
            trend_prediction = "Revisão do mercado"
        else:
            stock_name = "Revisão do Mercado"
            operation_advice = "Ver revisão"
            trend_prediction = "Revisão do mercado"

        result = AnalysisResult(
            code=MARKET_REVIEW_HISTORY_CODE,
            name=stock_name,
            sentiment_score=50,
            trend_prediction=trend_prediction,
            operation_advice=operation_advice,
            analysis_summary=summary,
            report_language=report_language,
            news_summary=review_report,
            raw_response=markdown_report,
            data_sources="market_review",
        )

        history_query_id = query_id or f"market_review_{uuid.uuid4().hex}"
        context_snapshot: dict[str, Any] = {
            "report_kind": MARKET_REVIEW_REPORT_TYPE,
            "market_review_region": region,
            "report_language": report_language,
        }
        if market_light_snapshots:
            context_snapshot["market_light_snapshots"] = market_light_snapshots

        saved = DatabaseManager.get_instance().save_analysis_history(
            result=result,
            query_id=history_query_id,
            report_type=MARKET_REVIEW_REPORT_TYPE,
            news_content=review_report,
            context_snapshot=context_snapshot,
            save_snapshot=True,
        )
        if saved:
            logger.info("Histórico da revisão de mercado salvo: query_id=%s", history_query_id)
        else:
            logger.warning("Falha ao salvar histórico da revisão de mercado: query_id=%s", history_query_id)
        return saved
    except Exception as exc:
        logger.warning("Exceção ao salvar histórico da revisão de mercado, fluxo do relatório e notificação continuam: %s", exc, exc_info=True)
        return 0


def _summarize_market_review(review_report: str, report_language: str) -> str:
    for line in (review_report or "").splitlines():
        text = line.strip().lstrip("#").strip()
        if text and not text.startswith("---") and not text.startswith(">"):
            return text[:200]
    if report_language == "en":
        return "Market review report generated."
    if report_language == "pt":
        return "Relatório de revisão de mercado gerado."
    return "Relatório de revisão de mercado gerado."
