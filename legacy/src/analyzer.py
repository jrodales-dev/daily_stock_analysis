# -*- coding: utf-8 -*-
"""
===================================
Sistema Inteligente de Análise de Ações - Camada de Análise de IA
===================================

Responsabilidades:
1. Encapsular a lógica de chamada de LLM (chamadas unificadas para Gemini/Anthropic/OpenAI, etc. através do LiteLLM)
2. Gerar relatório de análise combinando análise técnica e de notícias
3. Analisar a resposta do LLM em AnalysisResult estruturado
"""

import json
import logging
import math
import re
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple, Callable

import litellm
from json_repair import repair_json
from litellm import Router

from src.agent.llm_adapter import (
    get_thinking_extra_body,
    resolve_fallback_litellm_wire_models,
    register_fallback_model_pricing,
)
from src.agent.skills.defaults import CORE_TRADING_SKILL_POLICY_ZH
from src.config import (
    Config,
    extra_litellm_params,
    get_api_keys_for_model,
    get_config,
    get_configured_llm_models,
    normalize_litellm_temperature,
    resolve_litellm_wire_model,
    resolve_news_window_days,
)
from src.llm.generation_params import apply_litellm_generation_params
from src.llm.errors import call_litellm_with_param_recovery
from src.storage import persist_llm_usage
from src.data.stock_mapping import STOCK_NAME_MAP
from src.report_language import (
    get_signal_level,
    get_no_data_text,
    get_placeholder_text,
    get_unknown_text,
    get_chip_unavailable_text,
    infer_decision_type_from_advice,
    is_chip_placeholder_value,
    localize_chip_health,
    localize_confidence_level,
    normalize_report_language,
)
from src.schemas.report_schema import AnalysisReportSchema
from src.market_context import get_market_role, get_market_guidelines
from src.market_phase_prompt import format_market_phase_prompt_section

logger = logging.getLogger(__name__)


def _normalize_risk_warning_values(value: Any) -> List[str]:
    """Normalize arbitrary risk_warning values into a flat list of text alerts."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        normalized: List[str] = []
        for item in value:
            normalized.extend(_normalize_risk_warning_values(item))
        return normalized
    if isinstance(value, dict):
        if not value:
            return []
        try:
            dumped = json.dumps(value, ensure_ascii=False)
            text = dumped.strip()
        except (TypeError, ValueError):
            text = str(value).strip()
        return [text] if text else []
    text = str(value).strip()
    return [text] if text else []


def _today_has_realtime_overlay(today: Any) -> bool:
    if not isinstance(today, dict):
        return False
    data_source = today.get("data_source") or today.get("dataSource")
    if isinstance(data_source, str) and data_source.startswith("realtime:"):
        return True
    if today.get("is_partial_bar") is True or today.get("isPartialBar") is True:
        return True
    if today.get("is_estimated") is True or today.get("isEstimated") is True:
        return True
    return bool(today.get("estimated_fields") or today.get("estimatedFields"))


def _today_looks_complete_daily_bar(
    context: Dict[str, Any],
    phase_context: Dict[str, Any],
) -> bool:
    today = context.get("today")
    if (
        not isinstance(today, dict)
        or today.get("close") in (None, "")
        or _today_has_realtime_overlay(today)
    ):
        return False

    effective_date = phase_context.get("effective_daily_bar_date")
    today_date = today.get("date") or today.get("trade_date") or context.get("date")
    if effective_date and today_date and str(today_date) != str(effective_date):
        return False
    return True


def _phase_aware_quote_labels(context: Dict[str, Any]) -> Tuple[str, str]:
    """Choose Chinese quote-table labels that do not conflict with phase context."""
    phase_context = context.get("market_phase_context")
    if not isinstance(phase_context, dict):
        return "Cotação de Hoje", "Preço de Fechamento"

    phase = str(phase_context.get("phase") or "").strip()
    if phase in {"premarket", "non_trading"}:
        today = context.get("today")
        if _today_looks_complete_daily_bar(context, phase_context):
            return "Cotação do Último Dia Útil de Negociação Completo", "Preço de Fechamento do Último Dia Útil de Negociação Completo"
        if _today_has_realtime_overlay(today):
            return "Cotação Mais Recente", "Preço Estimado em Tempo Real"
        if isinstance(today, dict) and today.get("close") not in (None, ""):
            return "Cotação Mais Recente", "Preço Mais Recente"
        return "Cotação de Hoje", "Preço de Fechamento"

    if (
        phase in {"intraday", "lunch_break", "closing_auction"}
        and phase_context.get("is_partial_bar") is True
    ):
        return "Cotação Mais Recente", "Preço Estimado Intradiário"

    return "Cotação de Hoje", "Preço de Fechamento"


def _should_hide_regular_session_ohlc(context: Dict[str, Any]) -> bool:
    phase_context = context.get("market_phase_context")
    if not isinstance(phase_context, dict):
        return False

    phase = str(phase_context.get("phase") or "").strip()
    return phase in {"premarket", "non_trading"} and not _today_looks_complete_daily_bar(
        context,
        phase_context,
    )


class _LiteLLMStreamError(RuntimeError):
    """Internal error wrapper that records whether any text was streamed."""

    def __init__(self, message: str, *, partial_received: bool = False):
        super().__init__(message)
        self.partial_received = partial_received


class _AllModelsFailedError(Exception):
    """Raised when every model in the fallback chain fails.

    This includes both LLM call errors and JSON parse errors (when a
    ``response_validator`` is provided to :meth:`GeminiAnalyzer._call_litellm`).

    The ``last_response_text`` attribute holds the raw text from the last model
    that *did* return a response (but whose JSON could not be validated), so
    callers can still attempt a best-effort text fallback.

    ``last_model`` and ``last_usage`` record the model name and token usage
    from the last attempt so callers can persist usage even on fallback.
    """

    def __init__(
        self,
        message: str,
        *,
        last_response_text: Optional[str] = None,
        last_model: Optional[str] = None,
        last_usage: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.last_response_text = last_response_text
        self.last_model = last_model
        self.last_usage = last_usage or {}


def check_content_integrity(result: "AnalysisResult") -> Tuple[bool, List[str]]:
    """
    Check mandatory fields for report content integrity.
    Returns (pass, missing_fields). Module-level for use by pipeline (agent weak mode).
    """
    missing: List[str] = []

    def _is_blank_text(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        return True

    def _is_invalid_risk_alerts(value: Any) -> bool:
        return not isinstance(value, list)

    def _is_invalid_stop_loss(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, (list, tuple, dict)):
            return True
        if isinstance(value, str):
            return not value.strip()
        return False

    if result.sentiment_score is None:
        missing.append("sentiment_score")
    advice = result.operation_advice
    if not advice or not isinstance(advice, str) or _is_blank_text(advice):
        missing.append("operation_advice")
    summary = result.analysis_summary
    if not summary or not isinstance(summary, str) or _is_blank_text(summary):
        missing.append("analysis_summary")
    dash = result.dashboard if isinstance(result.dashboard, dict) else {}
    core = dash.get("core_conclusion")
    core = core if isinstance(core, dict) else {}
    if _is_blank_text(core.get("one_sentence")):
        missing.append("dashboard.core_conclusion.one_sentence")
    intel = dash.get("intelligence")
    intel = intel if isinstance(intel, dict) else None
    if intel is None or _is_invalid_risk_alerts(intel.get("risk_alerts")):
        missing.append("dashboard.intelligence.risk_alerts")
    if result.decision_type in ("buy", "hold"):
        battle = dash.get("battle_plan")
        battle = battle if isinstance(battle, dict) else {}
        sp = battle.get("sniper_points")
        sp = sp if isinstance(sp, dict) else {}
        stop_loss = sp.get("stop_loss")
        if _is_invalid_stop_loss(stop_loss):
            missing.append("dashboard.battle_plan.sniper_points.stop_loss")
    return len(missing) == 0, missing


def apply_placeholder_fill(result: "AnalysisResult", missing_fields: List[str]) -> None:
    """Fill missing mandatory fields with placeholders (in-place). Module-level for pipeline."""

    def _is_blank_text(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        return True

    def _is_invalid_risk_alerts(value: Any) -> bool:
        return not isinstance(value, list)

    def _is_invalid_stop_loss(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, (list, tuple, dict)):
            return True
        if isinstance(value, str):
            return not value.strip()
        return False

    placeholder = get_placeholder_text(getattr(result, "report_language", "zh"))
    for field in missing_fields:
        if field == "sentiment_score":
            result.sentiment_score = 50
        elif field == "operation_advice":
            if _is_blank_text(result.operation_advice):
                result.operation_advice = placeholder
        elif field == "analysis_summary":
            if _is_blank_text(result.analysis_summary):
                result.analysis_summary = placeholder
        elif field == "dashboard.core_conclusion.one_sentence":
            if not result.dashboard:
                result.dashboard = {}
            core = result.dashboard.get("core_conclusion")
            if not isinstance(core, dict):
                core = {}
                result.dashboard["core_conclusion"] = core
            fallback_sentence = (
                result.analysis_summary
                or result.operation_advice
                or placeholder
            )
            if _is_blank_text(core.get("one_sentence")):
                result.dashboard["core_conclusion"]["one_sentence"] = fallback_sentence
        elif field == "dashboard.intelligence.risk_alerts":
            if not result.dashboard:
                result.dashboard = {}
            intelligence = result.dashboard.get("intelligence")
            if not isinstance(intelligence, dict):
                intelligence = {}
                result.dashboard["intelligence"] = intelligence
            if _is_invalid_risk_alerts(intelligence.get("risk_alerts")):
                risk_warning_values = _normalize_risk_warning_values(result.risk_warning)
                intelligence["risk_alerts"] = risk_warning_values
        elif field == "dashboard.battle_plan.sniper_points.stop_loss":
            if not result.dashboard:
                result.dashboard = {}
            battle_plan = result.dashboard.get("battle_plan")
            if not isinstance(battle_plan, dict):
                battle_plan = {}
                result.dashboard["battle_plan"] = battle_plan
            sniper_points = battle_plan.get("sniper_points")
            if not isinstance(sniper_points, dict):
                sniper_points = {}
                battle_plan["sniper_points"] = sniper_points
            if _is_invalid_stop_loss(sniper_points.get("stop_loss")):
                sniper_points["stop_loss"] = placeholder


# ---------- chip_structure fallback (Issue #589) ----------

_CHIP_KEYS: tuple = ("profit_ratio", "avg_cost", "concentration", "chip_health")


def _is_value_placeholder(v: Any) -> bool:
    """True if value is empty or placeholder (N/A, 数据缺失, etc.)."""
    return is_chip_placeholder_value(v)


_RISK_WARNING_PLACEHOLDER_TEXTS = {
    "",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "tbd",
    "暂无",
    "待补充",
    "数据缺失",
    "未知",
    "无",
    "sem dados",
    "pendente",
    "dados faltantes",
    "desconhecido",
    "nenhum",
}

_STRUCTURAL_RISK_PHRASE_HINTS = (
    "重大利空",
    "重大风险",
    "关键风险",
    "减持",
    "高位减持",
    "退市",
    "退市风险",
    "停牌",
    "重大问询",
    "处罚",
    "限售",
    "违规",
    "违规风险",
    "诉讼",
    "问询",
    "监管",
    "财务",
    "审计",
    "爆雷",
    "暴雷",
    "违约",
    "违约风险",
    "流动性危机",
    "债务",
    "清算",
    "破产",
    "重大变脸",
    "major risk",
    "material adverse",
    "suspension",
    "delisting",
    "regulatory",
    "downgrade",
    "liquidity",
    "default",
    "más notícias significativas",
    "risco significativo",
    "risco chave",
    "redução de participação",
    "deslistagem",
    "risco de deslistagem",
    "suspensão",
    "inquérito importante",
    "penalidade",
    "venda restrita",
    "violação",
    "risco de violação",
    "litígio",
    "regulatório",
    "financeiro",
    "auditoria",
    "estouro",
    "inadimplência",
    "risco de inadimplência",
    "crise de liquidez",
    "dívida",
    "liquidação",
    "falência",
    "mudança significativa",
)

_CAPITAL_FLOW_UNAVAILABLE_STATUS = {
    "not_supported",
    "not supported",
    "unsupported",
    "unavailable",
    "not_available",
    "not available",
    "none",
    "na",
    "n/a",
    "null",
    "missing",
}


def _is_meaningful_text(value: Any) -> bool:
    text = str(value).strip() if value is not None else ""
    if not text:
        return False
    lowered = text.strip().lower()
    return lowered not in _RISK_WARNING_PLACEHOLDER_TEXTS


def _safe_float(v: Any, default: float = 0.0) -> float:
    """Safely convert to float; return default on failure. Private helper for chip fill."""
    if v is None:
        return default
    if isinstance(v, (int, float)):
        try:
            return default if math.isnan(float(v)) else float(v)
        except (ValueError, TypeError):
            return default
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return default


def _coerce_chip_metric(v: Any) -> Optional[float]:
    """Convert chip metrics while preserving the distinction between missing and zero."""
    if v is None:
        return None
    try:
        numeric = float(v)
    except (TypeError, ValueError):
        try:
            numeric = float(str(v).strip())
        except (TypeError, ValueError):
            return None
    return None if math.isnan(numeric) else numeric


_BULLISH_TREND_HINTS: Tuple[str, ...] = (
    "多头排列",
    "持续上涨",
    "趋势向上",
    "上升趋势",
    "向上发散",
    "bullish",
    "uptrend",
    "arranjo de alta",
    "aumento contínuo",
    "tendência de alta",
    "tendência ascendente",
    "divergência ascendente",
)
_WEAK_BULLISH_TREND_HINTS: Tuple[str, ...] = ("弱势多头", "alta fraca")
_BEARISH_TREND_HINTS: Tuple[str, ...] = (
    "空头排列",
    "持续下跌",
    "趋势向下",
    "下降趋势",
    "向下发散",
    "bearish",
    "downtrend",
    "arranjo de baixa",
    "queda contínua",
    "tendência de baixa",
    "tendência descendente",
    "divergência descendente",
)
_WEAK_BEARISH_TREND_HINTS: Tuple[str, ...] = ("弱势空头", "baixa fraca")
_NEGATION_TOKENS: Tuple[str, ...] = (
    "不是",
    "并非",
    "并未",
    "没有",
    "尚不",
    "尚未",
    "未",
    "无",
    "不属",
    "非",
    "not ",
    "no ",
    "não",
    "sem",
    "ainda não",
    "nenhum",
)
_NEGATION_BREAK_CHARS: Tuple[str, ...] = (",", ".", ";", ":", "!", "?", "，", "。", "；", "：", "！", "？", "\n")
_NEGATION_LOOKBACK_CHARS = 16
_NEGATION_MAX_GAP_CHARS = 8
_NEGATION_SCOPE_BREAK_TOKENS: Tuple[str, ...] = (
    "而是",
    "但是",
    "但",
    "反而",
    "反倒",
    "转为",
    "转成",
    "改为",
    "改成",
    " but ",
    " instead ",
    " rather ",
    "mas sim",
    "mas",
    "ao invés",
    "transformou",
    "mudou para",
)
_SINGLE_CHAR_NEGATION_GAP_PREFIXES: Tuple[str, ...] = (
    "形成",
    "出现",
    "进入",
    "转为",
    "转成",
    "构成",
    "呈现",
    "显示",
    "属于",
    "是",
    "有",
    "能",
    "见",
    "站",
    "守",
    "破",
    "formou",
    "apareceu",
    "entrou",
    "transformou",
    "constitui",
    "apresenta",
    "mostra",
    "pertence",
    "é",
    "tem",
    "pode",
    "vê",
    "fica",
    "mantém",
    "quebra",
)


def _normalize_prompt_reason_items(items: Any) -> List[str]:
    """Normalize prompt reason/risk items into a clean string list."""
    if not isinstance(items, list):
        return []
    normalized: List[str] = []
    for item in items:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def _contains_trend_hint(text: str, hints: Tuple[str, ...]) -> bool:
    """Return True when text contains a non-negated strong trend hint."""
    lowered = text.strip().lower()

    def _has_negation_scope_break(gap: str) -> bool:
        normalized_gap = gap.lower()
        for token in _NEGATION_SCOPE_BREAK_TOKENS:
            token_index = normalized_gap.find(token)
            if token_index > 0:
                return True
        return False

    def _is_valid_negation_gap(token: str, gap: str) -> bool:
        if not gap:
            return True
        if token not in {"未", "无", "非"}:
            return True
        return any(gap.startswith(prefix) for prefix in _SINGLE_CHAR_NEGATION_GAP_PREFIXES)

    def _is_negated_match(index: int) -> bool:
        prefix = lowered[max(0, index - _NEGATION_LOOKBACK_CHARS):index]
        for token in _NEGATION_TOKENS:
            token_index = prefix.rfind(token)
            if token_index < 0:
                continue
            gap = prefix[token_index + len(token):]
            if any(char in gap for char in _NEGATION_BREAK_CHARS):
                continue
            stripped_gap = gap.strip()
            if len(stripped_gap) > _NEGATION_MAX_GAP_CHARS:
                continue
            if _has_negation_scope_break(stripped_gap):
                continue
            if not _is_valid_negation_gap(token, stripped_gap):
                continue
            return True
        return False

    for hint in hints:
        keyword = hint.lower()
        start = 0
        while True:
            index = lowered.find(keyword, start)
            if index < 0:
                break
            if not _is_negated_match(index):
                return True
            start = index + len(keyword)
    return False


def _infer_trend_direction(trend: Dict[str, Any]) -> str:
    """Infer the final trend direction from trend_status and ma_alignment."""
    combined = " ".join(
        str(trend.get(key, "")).strip()
        for key in ("trend_status", "ma_alignment")
        if str(trend.get(key, "")).strip()
    )
    if not combined:
        return "neutral"
    lowered = combined.lower()
    normalized = lowered.replace(" ", "")
    has_bullish = (
        _contains_trend_hint(combined, _BULLISH_TREND_HINTS + _WEAK_BULLISH_TREND_HINTS)
        or "ma5>ma10>ma20" in normalized
        or (
            "ma5>ma10" in normalized
            and any(pattern in normalized for pattern in ("ma10≤ma20", "ma10<=ma20"))
        )
    )
    has_bearish = (
        _contains_trend_hint(combined, _BEARISH_TREND_HINTS + _WEAK_BEARISH_TREND_HINTS)
        or "ma5<ma10<ma20" in normalized
        or (
            "ma5<ma10" in normalized
            and any(pattern in normalized for pattern in ("ma10≥ma20", "ma10>=ma20"))
        )
    )
    if has_bullish and not has_bearish:
        return "bullish"
    if has_bearish and not has_bullish:
        return "bearish"
    return "neutral"


def _filter_conflicting_trend_items(items: List[str], conflict_hints: Tuple[str, ...]) -> List[str]:
    """Drop reasons that directly conflict with the final trend direction."""
    return [item for item in items if not _contains_trend_hint(item, conflict_hints)]


def _sanitize_trend_analysis_for_prompt(
    trend: Any,
    *,
    volume_change_ratio: Any = None,
) -> Dict[str, Any]:
    """Clean prompt-only trend hints on a derived copy without touching runtime/provider config."""
    trend_dict = dict(trend) if isinstance(trend, dict) else {}
    signal_reasons = _normalize_prompt_reason_items(trend_dict.get("signal_reasons"))
    risk_factors = _normalize_prompt_reason_items(trend_dict.get("risk_factors"))
    prompt_notes: List[str] = []
    trend_direction = _infer_trend_direction(trend_dict)

    if trend_direction == "bearish":
        filtered_signal_reasons = _filter_conflicting_trend_items(
            signal_reasons,
            _BULLISH_TREND_HINTS + _WEAK_BULLISH_TREND_HINTS,
        )
        if len(filtered_signal_reasons) != len(signal_reasons):
            prompt_notes.append("A estrutura técnica atual é de baixa, foram removidas razões estruturais de alta que conflitam diretamente com o julgamento principal de baixa.")
        signal_reasons = filtered_signal_reasons
        prompt_notes.append(
            "Se as notícias, lucros ou políticas catalisadoras forem de alta, isso só pode ser descrito como 'evento antecipado, técnica a confirmar' ou 'fundamentos de alta, mas técnica ainda não confirmada', sendo estritamente proibido descrever como um ponto de compra definitivo."
        )
    elif trend_direction == "bullish":
        filtered_signal_reasons = _filter_conflicting_trend_items(
            signal_reasons,
            _BEARISH_TREND_HINTS + _WEAK_BEARISH_TREND_HINTS,
        )
        if len(filtered_signal_reasons) != len(signal_reasons):
            prompt_notes.append("A estrutura técnica atual é de alta, foram removidas razões estruturais de baixa que conflitam diretamente com o julgamento principal de alta.")
        signal_reasons = filtered_signal_reasons
        filtered_risk_factors = _filter_conflicting_trend_items(
            risk_factors,
            _BEARISH_TREND_HINTS + _WEAK_BEARISH_TREND_HINTS,
        )
        if len(filtered_risk_factors) != len(risk_factors):
            prompt_notes.append("A estrutura técnica atual é de alta, foram removidas expressões de risco de estrutura de baixa que conflitam diretamente com o julgamento principal de alta.")
        risk_factors = filtered_risk_factors

    parsed_volume_change = _safe_float(volume_change_ratio, default=math.nan)
    if math.isfinite(parsed_volume_change) and parsed_volume_change > 10:
        prompt_notes.append(
            f"O volume de negociação variou cerca de {parsed_volume_change:.2f} vezes em relação a ontem, podem haver dados anormais ou um impulso único; os sinais de volume devem ser interpretados com menor peso e não devem ser vistos mecanicamente como uma forte confirmação."
        )

    trend_dict["signal_reasons"] = signal_reasons
    trend_dict["risk_factors"] = risk_factors
    trend_dict["prompt_consistency_notes"] = prompt_notes
    trend_dict["prompt_trend_direction"] = trend_direction
    return trend_dict


def _derive_chip_health(profit_ratio: float, concentration_90: float, language: str = "pt") -> str:
    """Derive chip_health from profit_ratio and concentration_90."""
    if profit_ratio >= 0.9:
        return localize_chip_health("Alerta", language)  # 获利盘极高
    if concentration_90 >= 0.25:
        return localize_chip_health("Alerta", language)  # 筹码分散
    if concentration_90 < 0.15 and 0.3 <= profit_ratio < 0.9:
        return localize_chip_health("Saudável", language)  # 集中且获利比例适中
    return localize_chip_health("Normal", language)


def _build_chip_structure_from_data(chip_data: Any, language: str = "pt") -> Dict[str, Any]:
    """Build chip_structure dict from ChipDistribution or dict."""
    if hasattr(chip_data, "profit_ratio"):
        pr = _safe_float(chip_data.profit_ratio)
        ac = chip_data.avg_cost
        c90 = _safe_float(chip_data.concentration_90)
    else:
        d = chip_data if isinstance(chip_data, dict) else {}
        pr = _safe_float(d.get("profit_ratio"))
        ac = d.get("avg_cost")
        c90 = _safe_float(d.get("concentration_90"))
    chip_health = _derive_chip_health(pr, c90, language=language)
    return {
        "profit_ratio": f"{pr:.1%}",
        "avg_cost": ac if (ac is not None and _safe_float(ac) != 0.0) else "N/A",
        "concentration": f"{c90:.2%}",
        "chip_health": chip_health,
    }


def _has_meaningful_chip_data(chip_data: Any) -> bool:
    """Return True when chip data has the core metrics required for reporting."""
    if not chip_data:
        return False
    if hasattr(chip_data, "avg_cost"):
        avg_cost = _coerce_chip_metric(getattr(chip_data, "avg_cost", None))
        concentration_90 = _coerce_chip_metric(getattr(chip_data, "concentration_90", None))
        concentration_70 = _coerce_chip_metric(getattr(chip_data, "concentration_70", None))
    else:
        d = chip_data if isinstance(chip_data, dict) else {}
        avg_cost = _coerce_chip_metric(d.get("avg_cost"))
        concentration_90_value = d.get("concentration_90")
        if concentration_90_value is None:
            concentration_90_value = d.get("concentration")
        concentration_90 = _coerce_chip_metric(concentration_90_value)
        concentration_70 = _coerce_chip_metric(d.get("concentration_70"))
    return (
        avg_cost is not None
        and avg_cost > 0
        and (
            (concentration_90 is not None and concentration_90 >= 0)
            or (concentration_70 is not None and concentration_70 >= 0)
        )
    )


def _mark_chip_structure_unavailable(result: "AnalysisResult", language: str) -> None:
    if not result or not isinstance(result.dashboard, dict):
        return
    data_perspective = result.dashboard.get("data_perspective")
    if not isinstance(data_perspective, dict):
        return
    data_perspective["chip_structure"] = {}
    data_perspective["chip_unavailable_reason"] = get_chip_unavailable_text(language)


def normalize_chip_structure_availability(result: "AnalysisResult", chip_data: Any) -> None:
    """Fill valid chip metrics or collapse placeholder-only chip fields to one fallback line."""
    if not result:
        return
    language = getattr(result, "report_language", "zh")
    if _has_meaningful_chip_data(chip_data):
        fill_chip_structure_if_needed(result, chip_data)
        return
    _mark_chip_structure_unavailable(result, language)


def fill_chip_structure_if_needed(result: "AnalysisResult", chip_data: Any) -> None:
    """When chip_data exists, fill chip_structure placeholder fields from chip_data (in-place)."""
    if not result or not _has_meaningful_chip_data(chip_data):
        return
    try:
        if not result.dashboard:
            result.dashboard = {}
        dash = result.dashboard
        # Use `or {}` rather than setdefault so that an explicit `null` from LLM is also replaced
        dp = dash.get("data_perspective") or {}
        dash["data_perspective"] = dp
        cs = dp.get("chip_structure") or {}
        filled = _build_chip_structure_from_data(
            chip_data,
            language=getattr(result, "report_language", "zh"),
        )
        # Start from a copy of cs to preserve any extra keys the LLM may have added
        merged = dict(cs)
        for k in _CHIP_KEYS:
            if _is_value_placeholder(merged.get(k)):
                merged[k] = filled[k]
        if merged != cs:
            dp["chip_structure"] = merged
            logger.info("[chip_structure] Filled placeholder chip fields from data source (Issue #589)")
    except Exception as e:
        logger.warning("[chip_structure] Fill failed, skipping: %s", e)


_PRICE_POS_KEYS = ("ma5", "ma10", "ma20", "bias_ma5", "bias_status", "current_price", "support_level", "resistance_level")


def fill_price_position_if_needed(
    result: "AnalysisResult",
    trend_result: Any = None,
    realtime_quote: Any = None,
) -> None:
    """Fill missing price_position fields from trend_result / realtime data (in-place)."""
    if not result:
        return
    try:
        if not result.dashboard:
            result.dashboard = {}
        dash = result.dashboard
        dp = dash.get("data_perspective") or {}
        dash["data_perspective"] = dp
        pp = dp.get("price_position") or {}

        computed: Dict[str, Any] = {}
        if trend_result:
            tr = trend_result if isinstance(trend_result, dict) else (
                trend_result.__dict__ if hasattr(trend_result, "__dict__") else {}
            )
            computed["ma5"] = tr.get("ma5")
            computed["ma10"] = tr.get("ma10")
            computed["ma20"] = tr.get("ma20")
            computed["bias_ma5"] = tr.get("bias_ma5")
            computed["current_price"] = tr.get("current_price")
            support_levels = tr.get("support_levels") or []
            resistance_levels = tr.get("resistance_levels") or []
            if support_levels:
                computed["support_level"] = support_levels[0]
            if resistance_levels:
                computed["resistance_level"] = resistance_levels[0]
        if realtime_quote:
            rq = realtime_quote if isinstance(realtime_quote, dict) else (
                realtime_quote.to_dict() if hasattr(realtime_quote, "to_dict") else {}
            )
            if _is_value_placeholder(computed.get("current_price")):
                computed["current_price"] = rq.get("price")

        filled = False
        for k in _PRICE_POS_KEYS:
            if _is_value_placeholder(pp.get(k)) and not _is_value_placeholder(computed.get(k)):
                pp[k] = computed[k]
                filled = True
        if filled:
            dp["price_position"] = pp
            logger.info("[price_position] Filled placeholder fields from computed data")
    except Exception as e:
        logger.warning("[price_position] Fill failed, skipping: %s", e)


def stabilize_decision_with_structure(
    result: "AnalysisResult",
    trend_result: Any = None,
    fundamental_context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Calibrate aggressive buy/sell advice with price levels and capital flow.

    The LLM can overreact to one-day price movement.  This guard keeps the
    public `decision_type` enum stable while allowing richer neutral wording
    such as 震荡/洗盘观察 when support, resistance, and fund flow do not confirm
    an immediate buy/sell action.
    """
    if not result:
        return

    try:
        language = normalize_report_language(getattr(result, "report_language", "zh"))
        dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}
        data_perspective = dashboard.get("data_perspective") if isinstance(dashboard, dict) else {}
        if not isinstance(data_perspective, dict):
            data_perspective = {}
        price_position = data_perspective.get("price_position")
        if not isinstance(price_position, dict):
            price_position = {}

        trend_dict = _as_dict_for_decision_guard(trend_result)
        current_price = _first_numeric_value(
            getattr(result, "current_price", None),
            price_position.get("current_price"),
            trend_dict.get("current_price"),
        )
        support = _first_numeric_value(
            price_position.get("support_level"),
            _first_list_value(trend_dict.get("support_levels")),
        )
        resistance = _first_numeric_value(
            price_position.get("resistance_level"),
            _first_list_value(trend_dict.get("resistance_levels")),
        )
        decision_type = infer_decision_type_from_advice(
            getattr(result, "decision_type", ""),
            default=getattr(result, "decision_type", "hold") or "hold",
        )
        decision_type = decision_type if decision_type in {"buy", "hold", "sell"} else "hold"
        advice_decision_type = infer_decision_type_from_advice(
            getattr(result, "operation_advice", ""),
            default="",
        )

        flow_bias, flow_reason = _capital_flow_bias_with_status(fundamental_context)
        if flow_bias == "unavailable":
            if isinstance(fundamental_context, dict) and "capital_flow" in fundamental_context:
                if decision_type == "buy" or advice_decision_type == "buy":
                    _downgrade_buy_without_capital_flow(
                        result,
                        language,
                        current_price=current_price,
                        support=support,
                        resistance=resistance,
                        flow_status=flow_reason,
                    )
                else:
                    _set_decision_stability_unavailable(
                        result,
                        language,
                        current_price=current_price,
                        support=support,
                        resistance=resistance,
                        flow_status=flow_reason,
                    )
            return

        if current_price is None:
            return

        broke_support = support is not None and current_price < support * 0.985
        near_support = support is not None and not broke_support and current_price <= support * 1.03
        breakout = resistance is not None and current_price > resistance * 1.01
        near_resistance = (
            resistance is not None
            and not breakout
            and current_price >= resistance * 0.97
        )
        mid_range = (
            support is not None
            and resistance is not None
            and support * 1.03 < current_price < resistance * 0.97
        )

        has_significant_risk = _has_structural_risk_alert(result)

        if decision_type == "buy":
            if near_resistance and flow_bias != "inflow":
                _downgrade_to_structural_hold(
                    result,
                    language,
                    advice_key="range",
                    reason_key="buy_near_resistance",
                    current_price=current_price,
                    support=support,
                    resistance=resistance,
                    flow_bias=flow_bias,
                )
            elif flow_bias == "outflow" and not breakout:
                _downgrade_to_structural_hold(
                    result,
                    language,
                    advice_key="range",
                    reason_key="buy_with_outflow",
                    current_price=current_price,
                    support=support,
                    resistance=resistance,
                    flow_bias=flow_bias,
                )
            elif mid_range and flow_bias == "neutral":
                _downgrade_to_structural_hold(
                    result,
                    language,
                    advice_key="range",
                    reason_key="hold_mid_range",
                    current_price=current_price,
                    support=support,
                    resistance=resistance,
                    flow_bias=flow_bias,
                )
        elif decision_type == "sell":
            if near_support and (flow_bias != "outflow") and not has_significant_risk:
                _downgrade_to_structural_hold(
                    result,
                    language,
                    advice_key="shakeout",
                    reason_key="sell_near_support",
                    current_price=current_price,
                    support=support,
                    resistance=resistance,
                    flow_bias=flow_bias,
                )
            elif flow_bias == "inflow" and not broke_support and not has_significant_risk:
                _downgrade_to_structural_hold(
                    result,
                    language,
                    advice_key="hold",
                    reason_key="sell_with_inflow",
                    current_price=current_price,
                    support=support,
                    resistance=resistance,
                    flow_bias=flow_bias,
                )
        elif decision_type == "hold":
            change_pct = _first_numeric_value(getattr(result, "change_pct", None))
            if change_pct is not None and change_pct < 0 and near_support and flow_bias != "outflow":
                _set_structural_hold_wording(
                    result,
                    language,
                    advice_key="shakeout",
                    reason_key="hold_shakeout",
                    current_price=current_price,
                    support=support,
                    resistance=resistance,
                    flow_bias=flow_bias,
                )
            elif mid_range and flow_bias == "neutral":
                _set_structural_hold_wording(
                    result,
                    language,
                    advice_key="range",
                    reason_key="hold_mid_range",
                    current_price=current_price,
                    support=support,
                    resistance=resistance,
                    flow_bias=flow_bias,
                )
        _sync_stability_dashboard_fields(result)
    except Exception as exc:
        logger.warning("[decision_stability] skipped: %s", exc)


def _has_structural_risk_alert(result: "AnalysisResult") -> bool:
    dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}

    risk_text = getattr(result, "risk_warning", "")
    if _is_significant_structural_risk(risk_text):
        return True

    intelligence = dashboard.get("intelligence") if isinstance(dashboard, dict) else None
    if isinstance(intelligence, dict):
        risk_alerts = intelligence.get("risk_alerts")
        if isinstance(risk_alerts, str):
            if _is_significant_structural_risk(risk_alerts):
                return True
        elif isinstance(risk_alerts, (list, tuple, set)):
            if any(_is_significant_structural_risk(item) for item in risk_alerts):
                return True

    core_conclusion = dashboard.get("core_conclusion") if isinstance(dashboard, dict) else None
    if isinstance(core_conclusion, dict):
        signal_type = str(core_conclusion.get("signal_type", "")).strip()
        if _is_significant_structural_risk(signal_type):
            return True
    return False


def _is_significant_structural_risk(value: Any) -> bool:
    text = str(value or "").strip()
    if not _is_meaningful_text(text):
        return False

    normalized = text.lower()
    if any(keyword in normalized for keyword in _STRUCTURAL_RISK_PHRASE_HINTS):
        return True

    return "重大" in text and "风险" in normalized


def _sync_stability_dashboard_fields(result: "AnalysisResult") -> None:
    dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}
    result.dashboard = dashboard
    dashboard["sentiment_score"] = getattr(result, "sentiment_score", None)
    dashboard["operation_advice"] = getattr(result, "operation_advice", None)
    dashboard["decision_type"] = getattr(result, "decision_type", None)


def _as_dict_for_decision_guard(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        try:
            converted = value.to_dict()
            return converted if isinstance(converted, dict) else {}
        except Exception:
            return {}
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _first_list_value(value: Any) -> Any:
    if isinstance(value, (list, tuple)) and value:
        return value[0]
    return value


def _coerce_numeric_value(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        if math.isfinite(float(value)):
            return float(value)
        return None
    text = str(value).replace(",", "").replace("，", "").strip()
    if not text or text.upper() in {"N/A", "NA", "NONE", "NULL"}:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _first_numeric_value(*values: Any) -> Optional[float]:
    for value in values:
        if isinstance(value, (list, tuple)):
            nested = _first_numeric_value(*value)
            if nested is not None:
                return nested
            continue
        numeric = _coerce_numeric_value(value)
        if numeric is not None:
            return numeric
    return None


def _capital_flow_bias(fundamental_context: Optional[Dict[str, Any]]) -> str:
    return _capital_flow_bias_with_status(fundamental_context)[0]


def _capital_flow_bias_with_status(
    fundamental_context: Optional[Dict[str, Any]],
) -> tuple[str, str]:
    if not isinstance(fundamental_context, dict):
        return "unavailable", "invalid_context"
    block = fundamental_context.get("capital_flow")
    if not isinstance(block, dict):
        return "unavailable", "capital_flow_block_missing"
    status = str(block.get("status") or "").strip().lower()
    normalized_status = status.replace("-", " ").replace("_", " ").strip()
    if normalized_status in _CAPITAL_FLOW_UNAVAILABLE_STATUS or "not supported" in normalized_status:
        return "unavailable", status or "not_supported"
    data = block.get("data") if isinstance(block.get("data"), dict) else block
    stock_flow = data.get("stock_flow") if isinstance(data, dict) else None
    if not isinstance(stock_flow, dict) or not stock_flow:
        return "unavailable", "empty_stock_flow"

    def _flow_direction(value: Optional[float]) -> Optional[str]:
        if value is None or value == 0:
            return None
        return "inflow" if value > 0 else "outflow"

    numeric_values = [
        _coerce_numeric_value(stock_flow.get("main_net_inflow")),
        _coerce_numeric_value(stock_flow.get("inflow_5d")),
        _coerce_numeric_value(stock_flow.get("inflow_10d")),
    ]
    if all(value is None for value in numeric_values):
        return "unavailable", "missing_or_na_flow_fields"

    ordered_signals = [
        _flow_direction(value) for value in numeric_values
    ]
    directions = {signal for signal in ordered_signals if signal is not None}
    if not directions or len(directions) > 1:
        return "neutral", "conflict_or_missing"
    for signal in ordered_signals:
        if signal is not None:
            return signal, "ok"
    return "neutral", "neutral"


def _capital_flow_status_for_stability(reason: str, language: str) -> str:
    normalized = (reason or "").strip().lower()
    if "not_supported" in normalized or "unsupported" in normalized or "not available" in normalized:
        return "Serviço de fluxo de capital não suportado" if language in ("zh", "pt") else "Capital flow source unsupported"
    if "empty_stock_flow" in normalized or "missing" in normalized:
        return "Dados de fluxo de capital ausentes" if language in ("zh", "pt") else "capital flow data unavailable"
    return "Fluxo de capital indisponível" if language in ("zh", "pt") else "capital flow unavailable"


def _set_decision_stability_unavailable(
    result: "AnalysisResult",
    language: str,
    *,
    current_price: Optional[float],
    support: Optional[float],
    resistance: Optional[float],
    flow_status: str,
) -> None:
    dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}
    result.dashboard = dashboard
    dashboard["decision_stability"] = {
        "applied": False,
        "reason": "Fluxo de capital indisponível, calibração não aplicada" if language in ("zh", "pt") else "Capital flow unavailable; stability calibration not applied",
        "capital_flow_status": _capital_flow_status_for_stability(flow_status, language),
        "current_price": current_price,
        "support": support,
        "resistance": resistance,
        "capital_flow_bias": "unavailable",
    }
    _sync_stability_dashboard_fields(result)


def _bound_hold_watch_sentiment_score(result: "AnalysisResult") -> None:
    try:
        score = int(getattr(result, "sentiment_score", 50))
    except (TypeError, ValueError):
        score = 50
    result.sentiment_score = min(59, max(45, score))


def _apply_hold_watch_dashboard(
    result: "AnalysisResult",
    language: str,
    *,
    advice: str,
    reason: str,
    current_price: Optional[float],
    support: Optional[float],
    resistance: Optional[float],
    flow_bias: str,
    no_position: str,
    has_position: str,
    capital_flow_status: Optional[str] = None,
) -> None:
    result.operation_advice = advice

    dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}
    result.dashboard = dashboard
    core = dashboard.get("core_conclusion")
    if not isinstance(core, dict):
        core = {}
        dashboard["core_conclusion"] = core
    core["signal_type"] = "🟡 Manter / Observar" if language in ("zh", "pt") else "🟡 Hold / Watch"
    core["one_sentence"] = f"{advice}: {reason}" if language in ("zh", "pt") else f"{advice}: {reason}"

    position_advice = core.get("position_advice")
    if not isinstance(position_advice, dict):
        position_advice = {}
        core["position_advice"] = position_advice
    position_advice["no_position"] = no_position
    position_advice["has_position"] = has_position

    stability = {
        "applied": True,
        "reason": reason,
        "current_price": current_price,
        "support": support,
        "resistance": resistance,
        "capital_flow_bias": flow_bias,
    }
    if capital_flow_status is not None:
        stability["capital_flow_status"] = capital_flow_status
    dashboard["decision_stability"] = stability

    if reason and reason not in (result.risk_warning or ""):
        sep = "；" if language in ("zh", "pt") else "; "
        result.risk_warning = f"{result.risk_warning}{sep}{reason}" if result.risk_warning else reason
    result.buy_reason = reason or result.buy_reason


def _downgrade_buy_without_capital_flow(
    result: "AnalysisResult",
    language: str,
    *,
    current_price: Optional[float],
    support: Optional[float],
    resistance: Optional[float],
    flow_status: str,
) -> None:
    status_text = _capital_flow_status_for_stability(flow_status, language)
    if language in ("zh", "pt"):
        advice = "Observar"
        reason = f"{status_text}, o chamado de compra carece de confirmação de fluxo de capital, tratar como apenas observação."
        no_position = "Não persiga a compra; aguarde a recuperação do fluxo de capital, confirmação do suporte ou um rompimento válido."
        has_position = "Use o suporte chave como linha de risco e controle o tamanho da posição até o fluxo de capital se recuperar."
        confidence = "Baixo"
    else:
        advice = "Hold and watch"
        reason = f"{status_text}; the buy call lacks capital-flow confirmation, so treat it as watch-only."
        no_position = "Do not chase; wait for capital-flow recovery, support confirmation, or a valid breakout."
        has_position = "Use key support as the risk line and keep position size controlled until capital flow recovers."
        confidence = "Low"

    result.decision_type = "hold"
    result.confidence_level = confidence
    _bound_hold_watch_sentiment_score(result)
    _apply_hold_watch_dashboard(
        result,
        language,
        advice=advice,
        reason=reason,
        current_price=current_price,
        support=support,
        resistance=resistance,
        flow_bias="unavailable",
        no_position=no_position,
        has_position=has_position,
        capital_flow_status=status_text,
    )
    _sync_stability_dashboard_fields(result)
    logger.info("[decision_stability] Downgraded buy because capital flow is unavailable: %s", flow_status)


def _downgrade_to_structural_hold(
    result: "AnalysisResult",
    language: str,
    *,
    advice_key: str,
    reason_key: str,
    current_price: float,
    support: Optional[float],
    resistance: Optional[float],
    flow_bias: str,
) -> None:
    result.decision_type = "hold"
    _bound_hold_watch_sentiment_score(result)
    _set_structural_hold_wording(
        result,
        language,
        advice_key=advice_key,
        reason_key=reason_key,
        current_price=current_price,
        support=support,
        resistance=resistance,
        flow_bias=flow_bias,
    )


def _set_structural_hold_wording(
    result: "AnalysisResult",
    language: str,
    *,
    advice_key: str,
    reason_key: str,
    current_price: float,
    support: Optional[float],
    resistance: Optional[float],
    flow_bias: str,
) -> None:
    advice = {
        "zh": {
            "range": "Observação em consolidação",
            "shakeout": "Observação de sacudida",
            "hold": "Manter e observar",
        },
        "en": {
            "range": "Range-bound watch",
            "shakeout": "Shakeout watch",
            "hold": "Hold and watch",
        },
        "pt": {
            "range": "Observação em consolidação",
            "shakeout": "Observação de sacudida",
            "hold": "Manter e observar",
        },
    }[language].get(advice_key, "Manter e observar" if language in ("zh", "pt") else "Hold and watch")
    reason_templates = {
        "zh": {
            "buy_near_resistance": "O preço está perto da resistência sem entrada confirmada, não persiga o rebote.",
            "buy_with_outflow": "Saída de capital conflita com a compra; aguarde confirmação de suporte ou entrada de capital.",
            "sell_near_support": "O preço está perto do suporte sem saída sustentada de capital, uma queda diária não justifica venda.",
            "sell_with_inflow": "Entrada de capital conflita com venda; mantenha e observe falha de suporte.",
            "hold_shakeout": "O preço recuou para perto do suporte sem saída confirmada, tratar como observação de sacudida.",
            "hold_mid_range": "O preço está entre suporte e resistência com fluxo neutro, observar consolidação.",
        },
        "en": {
            "buy_near_resistance": "Price is near resistance without confirmed main-force inflow, so chasing the rebound is not actionable.",
            "buy_with_outflow": "Main-force outflow conflicts with a buy call; wait for support confirmation or capital inflow.",
            "sell_near_support": "Price is near support without sustained outflow, so a one-day drop is not enough to sell.",
            "sell_with_inflow": "Main-force inflow conflicts with a sell call; hold and watch for support failure.",
            "hold_shakeout": "Price pulled back near support without confirmed outflow, which is better treated as a shakeout watch.",
            "hold_mid_range": "Price is between support and resistance with neutral fund flow, so range-bound watch is more actionable.",
        },
        "pt": {
            "buy_near_resistance": "O preço está perto da resistência sem entrada confirmada, não persiga o rebote.",
            "buy_with_outflow": "Saída de capital conflita com a compra; aguarde confirmação de suporte ou entrada de capital.",
            "sell_near_support": "O preço está perto do suporte sem saída sustentada de capital, uma queda diária não justifica venda.",
            "sell_with_inflow": "Entrada de capital conflita com venda; mantenha e observe falha de suporte.",
            "hold_shakeout": "O preço recuou para perto do suporte sem saída confirmada, tratar como observação de sacudida.",
            "hold_mid_range": "O preço está entre suporte e resistência com fluxo neutro, observar consolidação.",
        },
    }
    reason = reason_templates[language].get(reason_key, "")
    result.operation_advice = advice
    if language in ("zh", "pt") and "Consolidação" not in (result.trend_prediction or "") and advice_key == "range":
        result.trend_prediction = "Consolidação"
    elif language == "en" and advice_key == "range":
        result.trend_prediction = "Sideways"

    if language in ("zh", "pt"):
        no_position = "Não persiga altas ou baixas; aguarde confirmação de suporte, rompimento ou retorno de capital."
        has_position = "Mantenha o suporte como risco, e observe controlando o tamanho da posição a menos que rompa o suporte."
    else:
        no_position = "Do not chase or panic; wait for support confirmation, breakout, or renewed inflow."
        has_position = "Use key support as the risk line and manage position size unless support fails."
    _apply_hold_watch_dashboard(
        result,
        language,
        advice=advice,
        reason=reason,
        current_price=current_price,
        support=support,
        resistance=resistance,
        flow_bias=flow_bias,
        no_position=no_position,
        has_position=has_position,
    )
    logger.info("[decision_stability] Applied structural hold calibration: %s", reason_key)


def get_stock_name_multi_source(
    stock_code: str,
    context: Optional[Dict] = None,
    data_manager = None
) -> str:
    """
    Obter nome da ação em português de várias fontes

    Estratégia de obtenção (por prioridade):
    1. Obter do context passado (dados em tempo real)
    2. Obter da tabela de mapeamento estática STOCK_NAME_MAP
    3. Obter do DataFetcherManager (várias fontes de dados)
    4. Retornar nome padrão (Ação + Código)

    Args:
        stock_code: Código da ação
        context: Contexto de análise (opcional)
        data_manager: Instância DataFetcherManager (opcional)

    Returns:
        Nome da ação
    """
    # 1. Obter do contexto (dados de mercado em tempo real)
    if context:
        # Priorizar o campo stock_name
        if context.get('stock_name'):
            name = context['stock_name']
            if name and not name.startswith('股票'):
                return name

        # Em seguida, obter dos dados em tempo real
        if 'realtime' in context and context['realtime'].get('name'):
            return context['realtime']['name']

    # 2. Obter da tabela de mapeamento estático
    if stock_code in STOCK_NAME_MAP:
        return STOCK_NAME_MAP[stock_code]

    # 3. Obter da fonte de dados
    if data_manager is None:
        try:
            from data_provider.base import DataFetcherManager
            data_manager = DataFetcherManager()
        except Exception as e:
            logger.debug(f"Não foi possível inicializar DataFetcherManager: {e}")

    if data_manager:
        try:
            name = data_manager.get_stock_name(stock_code)
            if name:
                # Atualizar cache
                STOCK_NAME_MAP[stock_code] = name
                return name
        except Exception as e:
            logger.debug(f"Falha ao obter o nome da ação da fonte de dados: {e}")

    # 4. Retornar nome padrão
    return f'Ação {stock_code}'


@dataclass
class AnalysisResult:
    """
    Classe de dados de resultados de análise de IA - Edição Dashboard de Decisão

    Encapsula os resultados da análise retornados pelo Gemini, incluindo o painel de decisão e a análise detalhada.
    """
    code: str
    name: str

    # ========== 核心指标 ==========
    sentiment_score: int  # 综合评分 0-100 (>70强烈看多, >60看多, 40-60震荡, <40看空)
    trend_prediction: str  # 趋势预测：强烈看多/看多/震荡/看空/强烈看空
    operation_advice: str  # 操作建议：买入/加仓/持有/减仓/卖出/观望
    decision_type: str = "hold"  # 决策类型：buy/hold/sell（用于统计）
    confidence_level: str = "中"  # 置信度：高/中/低
    report_language: str = "zh"  # 报告输出语言：zh/en

    # ========== 决策仪表盘 (新增) ==========
    dashboard: Optional[Dict[str, Any]] = None  # 完整的决策仪表盘数据

    # ========== 走势分析 ==========
    trend_analysis: str = ""  # 走势形态分析（支撑位、压力位、趋势线等）
    short_term_outlook: str = ""  # 短期展望（1-3日）
    medium_term_outlook: str = ""  # 中期展望（1-2周）

    # ========== 技术面分析 ==========
    technical_analysis: str = ""  # 技术指标综合分析
    ma_analysis: str = ""  # 均线分析（多头/空头排列，金叉/死叉等）
    volume_analysis: str = ""  # 量能分析（放量/缩量，主力动向等）
    pattern_analysis: str = ""  # K线形态分析

    # ========== 基本面分析 ==========
    fundamental_analysis: str = ""  # 基本面综合分析
    sector_position: str = ""  # 板块地位和行业趋势
    company_highlights: str = ""  # 公司亮点/风险点

    # ========== 情绪面/消息面分析 ==========
    news_summary: str = ""  # 近期重要新闻/公告摘要
    market_sentiment: str = ""  # 市场情绪分析
    hot_topics: str = ""  # 相关热点话题

    # ========== 综合分析 ==========
    analysis_summary: str = ""  # 综合分析摘要
    key_points: str = ""  # 核心看点（3-5个要点）
    risk_warning: str = ""  # 风险提示
    buy_reason: str = ""  # 买入/卖出理由

    # ========== 元数据 ==========
    market_snapshot: Optional[Dict[str, Any]] = None  # 当日行情快照（展示用）
    raw_response: Optional[str] = None  # 原始响应（调试用）
    search_performed: bool = False  # 是否执行了联网搜索
    data_sources: str = ""  # 数据来源说明
    success: bool = True
    error_message: Optional[str] = None

    # ========== 价格数据（分析时快照）==========
    current_price: Optional[float] = None  # 分析时的股价
    change_pct: Optional[float] = None     # 分析时的涨跌幅(%)

    # ========== 模型标记（Issue #528）==========
    model_used: Optional[str] = None  # 分析使用的 LLM 模型（完整名，如 gemini/gemini-2.0-flash）

    # ========== 历史对比（Report Engine P0）==========
    query_id: Optional[str] = None  # 本次分析 query_id，用于历史对比时排除本次记录

    # ========== 基本面上下文（仅运行时，用于通知拼装；不持久化到 to_dict）==========
    fundamental_context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'name': self.name,
            'sentiment_score': self.sentiment_score,
            'trend_prediction': self.trend_prediction,
            'operation_advice': self.operation_advice,
            'decision_type': self.decision_type,
            'confidence_level': self.confidence_level,
            'report_language': self.report_language,
            'dashboard': self.dashboard,  # 决策仪表盘数据
            'trend_analysis': self.trend_analysis,
            'short_term_outlook': self.short_term_outlook,
            'medium_term_outlook': self.medium_term_outlook,
            'technical_analysis': self.technical_analysis,
            'ma_analysis': self.ma_analysis,
            'volume_analysis': self.volume_analysis,
            'pattern_analysis': self.pattern_analysis,
            'fundamental_analysis': self.fundamental_analysis,
            'sector_position': self.sector_position,
            'company_highlights': self.company_highlights,
            'news_summary': self.news_summary,
            'market_sentiment': self.market_sentiment,
            'hot_topics': self.hot_topics,
            'analysis_summary': self.analysis_summary,
            'key_points': self.key_points,
            'risk_warning': self.risk_warning,
            'buy_reason': self.buy_reason,
            'market_snapshot': self.market_snapshot,
            'search_performed': self.search_performed,
            'success': self.success,
            'error_message': self.error_message,
            'current_price': self.current_price,
            'change_pct': self.change_pct,
            'model_used': self.model_used,
        }

    def get_core_conclusion(self) -> str:
        """获取核心结论（一句话）"""
        if self.dashboard and 'core_conclusion' in self.dashboard:
            return self.dashboard['core_conclusion'].get('one_sentence', self.analysis_summary)
        return self.analysis_summary

    def get_position_advice(self, has_position: bool = False) -> str:
        """获取持仓建议"""
        if self.dashboard and 'core_conclusion' in self.dashboard:
            pos_advice = self.dashboard['core_conclusion'].get('position_advice', {})
            if has_position:
                return pos_advice.get('has_position', self.operation_advice)
            return pos_advice.get('no_position', self.operation_advice)
        return self.operation_advice

    def get_sniper_points(self) -> Dict[str, str]:
        """获取狙击点位"""
        if self.dashboard and 'battle_plan' in self.dashboard:
            return self.dashboard['battle_plan'].get('sniper_points', {})
        return {}

    def get_checklist(self) -> List[str]:
        """获取检查清单"""
        if self.dashboard and 'battle_plan' in self.dashboard:
            return self.dashboard['battle_plan'].get('action_checklist', [])
        return []

    def get_risk_alerts(self) -> List[str]:
        """获取风险警报"""
        if self.dashboard and 'intelligence' in self.dashboard:
            return self.dashboard['intelligence'].get('risk_alerts', [])
        return []

    def get_emoji(self) -> str:
        """根据操作建议返回对应 emoji"""
        _, emoji, _ = get_signal_level(
            self.operation_advice,
            self.sentiment_score,
            self.report_language,
        )
        return emoji

    def get_confidence_stars(self) -> str:
        """返回置信度星级"""
        star_map = {
            "高": "⭐⭐⭐",
            "high": "⭐⭐⭐",
            "中": "⭐⭐",
            "medium": "⭐⭐",
            "低": "⭐",
            "low": "⭐",
        }
        return star_map.get((self.confidence_level or "").strip().lower(), "⭐⭐")


class GeminiAnalyzer:
    """
    Gemini AI 分析器

    职责：
    1. 调用 Google Gemini API 进行股票分析
    2. 结合预先搜索的新闻和技术面数据生成分析报告
    3. 解析 AI 返回的 JSON 格式结果

    使用方式：
        analyzer = GeminiAnalyzer()
        result = analyzer.analyze(context, news_context)
    """

    # ========================================
    # 系统提示词 - 决策仪表盘 v2.0
    # ========================================
    # 输出格式升级：从简单信号升级为决策仪表盘
    # 核心模块：核心结论 + 数据透视 + 舆情情报 + 作战计划
    # ========================================

    LEGACY_DEFAULT_SYSTEM_PROMPT = """Você é um analista de investimentos focado em tendências do mercado {market_placeholder}, responsável por gerar relatórios de análise profissionais do [Dashboard de Decisão].

{guidelines_placeholder}

""" + CORE_TRADING_SKILL_POLICY_ZH + """

## Formato de Saída: Dashboard de Decisão em JSON

Por favor, produza estritamente no seguinte formato JSON, este é um [Dashboard de Decisão] completo:

```json
{
    "stock_name": "Nome da ação",
    "sentiment_score": Número inteiro de 0-100,
    "trend_prediction": "Forte Alta/Alta/Consolidação/Baixa/Forte Baixa",
    "operation_advice": "Comprar/Adicionar/Manter/Reduzir/Vender/Observar",
    "decision_type": "buy/hold/sell",
    "confidence_level": "Alto/Médio/Baixo",

    "dashboard": {
        "core_conclusion": {
            "one_sentence": "Conclusão central em uma frase (menos de 30 palavras, dizendo diretamente ao usuário o que fazer)",
            "signal_type": "🟢Sinal de Compra/🟡Manter e Observar/🔴Sinal de Venda/⚠️Aviso de Risco",
            "time_sensitivity": "Ação Imediata/Hoje/Nesta Semana/Sem Pressa",
            "position_advice": {
                "no_position": "Conselho para quem não tem posição: diretrizes específicas de operação",
                "has_position": "Conselho para quem tem posição: diretrizes específicas de operação"
            }
        },

        "data_perspective": {
            "trend_status": {
                "ma_alignment": "Descrição do estado do alinhamento das médias móveis",
                "is_bullish": true/false,
                "trend_score": 0-100
            },
            "price_position": {
                "current_price": Valor do preço atual,
                "ma5": Valor da MA5,
                "ma10": Valor da MA10,
                "ma20": Valor da MA20,
                "bias_ma5": Porcentagem da taxa de viés,
                "bias_status": "Seguro/Alerta/Perigoso",
                "support_level": Preço do nível de suporte,
                "resistance_level": Preço do nível de resistência
            },
            "volume_analysis": {
                "volume_ratio": Valor da taxa de volume,
                "volume_status": "Aumento/Redução/Estável",
                "turnover_rate": Porcentagem da taxa de rotatividade,
                "volume_meaning": "Interpretação do significado do volume (ex: redução indica menor pressão de venda)"
            },
            "chip_structure": {
                "profit_ratio": Proporção de lucro,
                "avg_cost": Custo médio,
                "concentration": Concentração de fichas,
                "chip_health": "Saudável/Normal/Alerta"
            }
        },

        "intelligence": {
            "latest_news": "[Últimas Notícias] Resumo das notícias importantes recentes",
            "risk_alerts": ["Ponto de risco 1: descrição específica", "Ponto de risco 2: descrição específica"],
            "positive_catalysts": ["Ponto positivo 1: descrição específica", "Ponto positivo 2: descrição específica"],
            "earnings_outlook": "Análise da expectativa de lucros (baseada em relatórios, etc.)",
            "sentiment_summary": "Resumo do sentimento em uma frase"
        },

        "battle_plan": {
            "sniper_points": {
                "ideal_buy": "Ponto de compra ideal: XX (perto da MA5)",
                "secondary_buy": "Ponto de compra secundário: XX (perto da MA10)",
                "stop_loss": "Stop loss: XX (abaixo da MA20 ou X%)",
                "take_profit": "Alvo de lucro: XX (alta anterior/número redondo)"
            },
            "position_strategy": {
                "suggested_position": "Posição sugerida: X/10",
                "entry_plan": "Descrição da estratégia de entrada em lotes",
                "risk_control": "Descrição da estratégia de controle de risco"
            },
            "action_checklist": [
                "✅/⚠️/❌ Item 1: Arranjo de alta",
                "✅/⚠️/❌ Item 2: Taxa de viés razoável",
                "✅/⚠️/❌ Item 3: Suporte de volume",
                "✅/⚠️/❌ Item 4: Sem más notícias significativas",
                "✅/⚠️/❌ Item 5: Fichas saudáveis",
                "✅/⚠️/❌ Item 6: Avaliação de PE razoável"
            ]
        }
    },

    "analysis_summary": "Resumo abrangente de 100 palavras",
    "key_points": "3-5 pontos principais, separados por vírgula",
    "risk_warning": "Aviso de risco",
    "buy_reason": "Razão da operação, citando o conceito de negociação",

    "trend_analysis": "Análise da forma de tendência",
    "short_term_outlook": "Perspectiva de curto prazo (1-3 dias)",
    "medium_term_outlook": "Perspectiva de médio prazo (1-2 semanas)",
    "technical_analysis": "Análise técnica abrangente",
    "ma_analysis": "Análise do sistema de médias móveis",
    "volume_analysis": "Análise de volume",
    "pattern_analysis": "Análise de forma da linha K",
    "fundamental_analysis": "Análise fundamentalista",
    "sector_position": "Análise da indústria do setor",
    "company_highlights": "Destaques/riscos da empresa",
    "news_summary": "Resumo de notícias",
    "market_sentiment": "Sentimento do mercado",
    "hot_topics": "Tópicos relacionados",

    "search_performed": true/false,
    "data_sources": "Descrição das fontes de dados"
}
```

## Critérios de Pontuação

### Compra Forte (80-100 pontos):
- ✅ Arranjo de alta: MA5 > MA10 > MA20
- ✅ Baixo viés: <2%, melhor ponto de compra
- ✅ Retração de volume ou rompimento com volume
- ✅ Fichas concentradas e saudáveis
- ✅ Catalisadores positivos de notícias

### Comprar (60-79 pontos):
- ✅ Arranjo de alta ou alta fraca
- ✅ Viés <5%
- ✅ Volume normal
- ⚪ Permite que uma condição secundária não seja atendida

### Observar (40-59 pontos):
- ⚠️ Viés >5% (risco de perseguição de alta)
- ⚠️ Médias móveis entrelaçadas, tendência obscura
- ⚠️ Eventos de risco presentes

### Vender/Reduzir (0-39 pontos):
- ❌ Arranjo de baixa
- ❌ Abaixo da MA20
- ❌ Queda com volume
- ❌ Más notícias significativas

## Princípios Centrais do Dashboard de Decisão

1. **Conclusão central primeiro**: Esclareça se deve comprar ou vender em uma frase.
2. **Conselhos separados**: Conselhos diferentes para quem tem e quem não tem posições.
3. **Pontos de entrada precisos**: Deve dar preços específicos, não use palavras vagas.
4. **Lista de verificação visual**: Use ✅⚠️❌ para mostrar claramente cada resultado.
5. **Prioridade de risco**: Riscos no sentimento devem ser destacados.

## Restrições de Operabilidade e Estabilidade

- Não mude drasticamente entre 'comprar/vender' apenas devido à alta/baixa de um dia.
- O conselho deve considerar suporte/resistência, volume/fichas, fluxo de capital e riscos.
- Se o preço estiver entre suporte e resistência, e o capital for obscuro, prefira conselhos neutros como 'Manter/Observar'.
- Apenas sugira compra se próximo ao suporte/rompimento com suporte de capital/volume; não persiga em resistências.
- Apenas sugira venda se cair abaixo do suporte, com saída de capital contínua ou risco ampliado."""

    SYSTEM_PROMPT = """Você é um analista de investimentos focado no mercado {market_placeholder}, responsável por gerar relatórios de análise profissionais do [Dashboard de Decisão].

{guidelines_placeholder}

{default_skill_policy_section}
{skills_section}

## Formato de Saída: Dashboard de Decisão em JSON

Por favor, produza estritamente no seguinte formato JSON, este é um [Dashboard de Decisão] completo:

```json
{
    "stock_name": "Nome da ação",
    "sentiment_score": Número inteiro de 0-100,
    "trend_prediction": "Forte Alta/Alta/Consolidação/Baixa/Forte Baixa",
    "operation_advice": "Comprar/Adicionar/Manter/Reduzir/Vender/Observar",
    "decision_type": "buy/hold/sell",
    "confidence_level": "Alto/Médio/Baixo",

    "dashboard": {
        "core_conclusion": {
            "one_sentence": "Conclusão central em uma frase (menos de 30 palavras, dizendo diretamente ao usuário o que fazer)",
            "signal_type": "🟢Sinal de Compra/🟡Manter e Observar/🔴Sinal de Venda/⚠️Aviso de Risco",
            "time_sensitivity": "Ação Imediata/Hoje/Nesta Semana/Sem Pressa",
            "position_advice": {
                "no_position": "Conselho para quem não tem posição: diretrizes específicas de operação",
                "has_position": "Conselho para quem tem posição: diretrizes específicas de operação"
            }
        },

        "data_perspective": {
            "trend_status": {
                "ma_alignment": "Descrição do estado do alinhamento das médias móveis",
                "is_bullish": true/false,
                "trend_score": 0-100
            },
            "price_position": {
                "current_price": Valor do preço atual,
                "ma5": Valor da MA5,
                "ma10": Valor da MA10,
                "ma20": Valor da MA20,
                "bias_ma5": Porcentagem da taxa de viés,
                "bias_status": "Seguro/Alerta/Perigoso",
                "support_level": Preço do nível de suporte,
                "resistance_level": Preço do nível de resistência
            },
            "volume_analysis": {
                "volume_ratio": Valor da taxa de volume,
                "volume_status": "Aumento/Redução/Estável",
                "turnover_rate": Porcentagem da taxa de rotatividade,
                "volume_meaning": "Interpretação do significado do volume (ex: redução indica menor pressão de venda)"
            },
            "chip_structure": {
                "profit_ratio": Proporção de lucro,
                "avg_cost": Custo médio,
                "concentration": Concentração de fichas,
                "chip_health": "Saudável/Normal/Alerta"
            }
        },

        "intelligence": {
            "latest_news": "[Últimas Notícias] Resumo das notícias importantes recentes",
            "risk_alerts": ["Ponto de risco 1: descrição específica", "Ponto de risco 2: descrição específica"],
            "positive_catalysts": ["Ponto positivo 1: descrição específica", "Ponto positivo 2: descrição específica"],
            "earnings_outlook": "Análise da expectativa de lucros (baseada em relatórios, etc.)",
            "sentiment_summary": "Resumo do sentimento em uma frase"
        },

        "battle_plan": {
            "sniper_points": {
                "ideal_buy": "Ponto de entrada ideal: XX (atende às condições principais)",
                "secondary_buy": "Ponto de entrada secundário: XX (mais conservador ou execução após confirmação)",
                "stop_loss": "Stop loss: XX (condição de invalidação ou X% de risco)",
                "take_profit": "Alvo de lucro: XX (baseado na resistência/razão risco-retorno)"
            },
            "position_strategy": {
                "suggested_position": "Posição sugerida: X/10",
                "entry_plan": "Descrição da estratégia de entrada em lotes",
                "risk_control": "Descrição da estratégia de controle de risco"
            },
            "action_checklist": [
                "✅/⚠️/❌ Item 1: A estrutura atual atende às condições de ativação de habilidades",
                "✅/⚠️/❌ Item 2: Posição de entrada e retorno de risco são razoáveis",
                "✅/⚠️/❌ Item 3: Volume/preço/volatilidade/fichas apoiam o julgamento",
                "✅/⚠️/❌ Item 4: Sem grandes pontos negativos",
                "✅/⚠️/❌ Item 5: Posição e plano de stop loss claros",
                "✅/⚠️/❌ Item 6: Avaliação/desempenho/catalisadores correspondem à conclusão"
            ]
        }
    },

    "analysis_summary": "Resumo abrangente de 100 palavras",
    "key_points": "3-5 pontos principais, separados por vírgula",
    "risk_warning": "Aviso de risco",
    "buy_reason": "Razão da operação, citando o conceito de negociação",

    "trend_analysis": "Análise da forma de tendência",
    "short_term_outlook": "Perspectiva de curto prazo (1-3 dias)",
    "medium_term_outlook": "Perspectiva de médio prazo (1-2 semanas)",
    "technical_analysis": "Análise técnica abrangente",
    "ma_analysis": "Análise do sistema de médias móveis",
    "volume_analysis": "Análise de volume",
    "pattern_analysis": "Análise de forma da linha K",
    "fundamental_analysis": "Análise fundamentalista",
    "sector_position": "Análise da indústria do setor",
    "company_highlights": "Destaques/riscos da empresa",
    "news_summary": "Resumo de notícias",
    "market_sentiment": "Sentimento do mercado",
    "hot_topics": "Tópicos relacionados",

    "search_performed": true/false,
    "data_sources": "Descrição das fontes de dados"
}
```

## Critérios de Pontuação

### Compra Forte (80-100 pontos):
- ✅ Várias habilidades de ativação apoiam simultaneamente uma conclusão positiva
- ✅ Espaço de valorização, condições de ativação e risco-retorno claros
- ✅ Riscos chave avaliados, plano de posição e stop loss claros
- ✅ Dados importantes e inteligência coerentes entre si

### Comprar (60-79 pontos):
- ✅ Sinal principal é positivo, mas com algumas confirmações pendentes
- ✅ Riscos controláveis ou pontos de entrada subótimos permitidos
- ✅ Requer especificação clara das condições de observação no relatório

### Observar (40-59 pontos):
- ⚠️ Grande divergência de sinais, ou falta de confirmação suficiente
- ⚠️ Riscos e oportunidades aproximadamente equilibrados
- ⚠️ Mais apropriado para aguardar condições de ativação ou evitar incertezas

### Vender/Reduzir (0-39 pontos):
- ❌ Conclusão principal enfraquece, risco visivelmente superior ao retorno
- ❌ Acionou stop loss, condição de invalidação ou más notícias importantes
- ❌ Posições existentes exigem mais proteção do que ofensiva

## Princípios Centrais do Dashboard de Decisão

1. **Conclusão central primeiro**: Esclareça se deve comprar ou vender em uma frase.
2. **Conselhos separados**: Conselhos diferentes para quem tem e quem não tem posições.
3. **Pontos de entrada precisos**: Deve dar preços específicos, não use palavras vagas.
4. **Lista de verificação visual**: Use ✅⚠️❌ para mostrar claramente cada resultado.
5. **Prioridade de risco**: Riscos no sentimento devem ser destacados.

## Restrições de Operabilidade e Estabilidade

- Não mude drasticamente entre 'comprar/vender' apenas devido à alta/baixa de um dia.
- O conselho deve considerar suporte/resistência, volume/fichas, fluxo de capital e riscos.
- Se o preço estiver entre suporte e resistência, e o capital for obscuro, prefira conselhos neutros como 'Manter/Observar'.
- Apenas sugira compra se próximo ao suporte/rompimento com suporte de capital/volume; não persiga em resistências.
- Apenas sugira venda se cair abaixo do suporte, com saída de capital contínua ou risco ampliado."""

    TEXT_SYSTEM_PROMPT = """Você é um assistente profissional de análise de ações.

- As respostas devem basear-se nos dados e contexto fornecidos pelo usuário.
- Se a informação for insuficiente, você deve apontar claramente a incerteza.
- Não invente preços, relatórios de ganhos ou fatos de notícias.
"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        config: Optional[Config] = None,
        skills: Optional[List[str]] = None,
        skill_instructions: Optional[str] = None,
        default_skill_policy: Optional[str] = None,
        use_legacy_default_prompt: Optional[bool] = None,
    ):
        """Initialize LLM Analyzer via LiteLLM.

        Args:
            api_key: Ignored (kept for backward compatibility). Keys are loaded from config.
        """
        self._config_override = config
        self._requested_skills = list(skills) if skills is not None else None
        self._skill_instructions_override = skill_instructions
        self._default_skill_policy_override = default_skill_policy
        self._use_legacy_default_prompt_override = use_legacy_default_prompt
        self._resolved_prompt_state: Optional[Dict[str, Any]] = None
        self._router = None
        self._legacy_router_model_list: List[Dict[str, Any]] = []
        self._litellm_available = False
        self._init_litellm()
        if not self._litellm_available:
            logger.warning("No LLM configured (LITELLM_MODEL / API keys), AI analysis will be unavailable")

    def _get_runtime_config(self) -> Config:
        """Return the runtime config, honoring injected overrides for tests/pipeline."""
        return getattr(self, "_config_override", None) or get_config()

    def _get_skill_prompt_sections(self) -> tuple[str, str, bool]:
        """Resolve skill instructions + default baseline + prompt mode."""
        skill_instructions = getattr(self, "_skill_instructions_override", None)
        default_skill_policy = getattr(self, "_default_skill_policy_override", None)
        use_legacy_default_prompt = getattr(self, "_use_legacy_default_prompt_override", None)

        if skill_instructions is not None and default_skill_policy is not None:
            return (
                skill_instructions,
                default_skill_policy,
                bool(use_legacy_default_prompt) if use_legacy_default_prompt is not None else False,
            )

        resolved_state = getattr(self, "_resolved_prompt_state", None)
        if resolved_state is None:
            from src.agent.factory import resolve_skill_prompt_state

            prompt_state = resolve_skill_prompt_state(
                self._get_runtime_config(),
                skills=getattr(self, "_requested_skills", None),
            )
            resolved_state = {
                "skill_instructions": prompt_state.skill_instructions,
                "default_skill_policy": prompt_state.default_skill_policy,
                "use_legacy_default_prompt": bool(getattr(prompt_state, "use_legacy_default_prompt", False)),
            }
            self._resolved_prompt_state = resolved_state

        return (
            str(skill_instructions if skill_instructions is not None else resolved_state.get("skill_instructions", "")),
            str(default_skill_policy if default_skill_policy is not None else resolved_state.get("default_skill_policy", "")),
            bool(
                use_legacy_default_prompt
                if use_legacy_default_prompt is not None
                else resolved_state.get("use_legacy_default_prompt", False)
            ),
        )

    def _get_analysis_system_prompt(self, report_language: str, stock_code: str = "") -> str:
        """Build the analyzer system prompt with output-language guidance."""
        lang = normalize_report_language(report_language)
        market_role = get_market_role(stock_code, lang)
        market_guidelines = get_market_guidelines(stock_code, lang)
        skill_instructions, default_skill_policy, use_legacy_default_prompt = self._get_skill_prompt_sections()
        if use_legacy_default_prompt:
            base_prompt = self.LEGACY_DEFAULT_SYSTEM_PROMPT.replace(
                "{market_placeholder}", market_role
            ).replace(
                "{guidelines_placeholder}", market_guidelines
            )
        else:
            skills_section = ""
            if skill_instructions:
                skills_section = f"## Habilidades de negociação ativadas\n\n{skill_instructions}\n"
            default_skill_policy_section = ""
            if default_skill_policy:
                default_skill_policy_section = f"{default_skill_policy}\n"
            base_prompt = (
                self.SYSTEM_PROMPT.replace("{market_placeholder}", market_role)
                .replace("{guidelines_placeholder}", market_guidelines)
                .replace("{default_skill_policy_section}", default_skill_policy_section)
                .replace("{skills_section}", skills_section)
            )
        if lang == "pt":
            return base_prompt + """

## Idioma de Saída (Maior Prioridade)

- Mantenha todas as chaves do JSON inalteradas.
- `decision_type` deve permanecer como `buy|hold|sell`.
- Todos os valores JSON legíveis por humanos DEVEM ser escritos em Português do Brasil (pt-BR).
- Use o nome comum da empresa quando tiver certeza; caso contrário, mantenha o nome original da empresa listada, em vez de inventar um.
- Isso inclui `stock_name`, `trend_prediction`, `operation_advice`, `confidence_level`, texto aninhado no dashboard, itens de checklist, e todos os resumos narrativos.
"""
        if lang == "en":
            return base_prompt + """

## Output Language (highest priority)

- Keep all JSON keys unchanged.
- `decision_type` must remain `buy|hold|sell`.
- All human-readable JSON values must be written in English.
- Use the common English company name when you are confident; otherwise keep the original listed company name instead of inventing one.
- This includes `stock_name`, `trend_prediction`, `operation_advice`, `confidence_level`, nested dashboard text, checklist items, and all narrative summaries.
"""
        return base_prompt + """

## Idioma de Saída (Maior Prioridade)

- Todas as chaves do JSON devem permanecer inalteradas.
- `decision_type` deve permanecer como `buy|hold|sell`.
- Todos os valores de texto legíveis por humanos voltados para o usuário devem usar Português.
"""

    def _has_channel_config(self, config: Config) -> bool:
        """Check if multi-channel config (channels / YAML / legacy model_list) is active."""
        return bool(config.llm_model_list) and not all(
            e.get('model_name', '').startswith('__legacy_') for e in config.llm_model_list
        )

    @staticmethod
    def _legacy_router_provider_alias(model: str) -> str:
        provider = model.split("/", 1)[0] if "/" in model else "openai"
        return f"__legacy_{provider}__"

    @staticmethod
    def _build_legacy_router_model_list_from_config(
        model: str,
        model_list: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build legacy-router candidates from configured legacy llm_model_list entries."""
        if not model:
            return []
        target_model = model
        target_legacy_alias = GeminiAnalyzer._legacy_router_provider_alias(model)
        legacy_entries: List[Dict[str, Any]] = []
        for entry in model_list or []:
            if not isinstance(entry, dict):
                continue
            model_name = str(entry.get("model_name") or "").strip()
            if model_name != target_legacy_alias:
                continue

            params = entry.get("litellm_params")
            if not isinstance(params, dict):
                continue

            api_key = str(params.get("api_key") or "").strip()
            if not api_key or len(api_key) < 8:
                continue

            deployed_params = dict(params)
            deployed_params["model"] = target_model
            deployed_params["api_key"] = api_key
            legacy_entries.append({
                "model_name": target_model,
                "litellm_params": deployed_params,
            })

        return legacy_entries

    def _init_litellm(self) -> None:
        """Initialize litellm Router from channels / YAML / legacy keys."""
        config = self._get_runtime_config()
        litellm_model = config.litellm_model
        if not litellm_model:
            logger.warning("Analyzer LLM: LITELLM_MODEL not configured")
            return

        self._litellm_available = True

        # --- Channel / YAML path: build Router from pre-built model_list ---
        if self._has_channel_config(config):
            model_list = config.llm_model_list
            try:
                self._router = Router(
                    model_list=model_list,
                    routing_strategy="simple-shuffle",
                    num_retries=2,
                )
            except TypeError:
                logger.debug("Analyzer LLM: Router constructor signature not compatible; fallback to direct mode")
                self._router = None
            else:
                unique_models = list(dict.fromkeys(
                    e['litellm_params']['model'] for e in model_list
                ))
                logger.info(
                    f"Analyzer LLM: Router initialized from channels/YAML — "
                    f"{len(model_list)} deployment(s), models: {unique_models}"
                )
                return

        # --- Legacy path: build Router for multi-key, or use single key ---
        keys = get_api_keys_for_model(litellm_model, config)
        legacy_model_list = self._build_legacy_router_model_list_from_config(
            litellm_model,
            config.llm_model_list,
        )
        if len(legacy_model_list) <= 1 and keys:
            extra_params = extra_litellm_params(litellm_model, config)
            configured_model_list = [
                {
                    "model_name": litellm_model,
                    "litellm_params": {
                        "model": litellm_model,
                        "api_key": k,
                        **extra_params,
                    },
                }
                for k in keys
            ]
            if not legacy_model_list:
                legacy_model_list = configured_model_list
            elif len(legacy_model_list) < len(configured_model_list):
                legacy_model_list = configured_model_list

        if len(legacy_model_list) > 1:
            self._legacy_router_model_list = legacy_model_list
            try:
                self._router = Router(
                    model_list=legacy_model_list,
                    routing_strategy="simple-shuffle",
                    num_retries=2,
                )
            except TypeError:
                logger.debug("Analyzer LLM: Legacy Router constructor signature not compatible; using legacy model_list fallback")
                self._router = None
            else:
                logger.info(
                    f"Analyzer LLM: Legacy Router initialized with {len(legacy_model_list)} keys "
                    f"for {litellm_model}"
                )
                return

        if keys:
            logger.info(f"Analyzer LLM: litellm initialized (model={litellm_model})")
        else:
            logger.info(
                f"Analyzer LLM: litellm initialized (model={litellm_model}, "
                f"API key from environment)"
            )

    def is_available(self) -> bool:
        """Check if LiteLLM is properly configured with at least one API key."""
        return self._router is not None or self._litellm_available

    def _dispatch_litellm_completion(
        self,
        model: str,
        call_kwargs: Dict[str, Any],
        *,
        config: Config,
        use_channel_router: bool,
        router_model_names: set[str],
    ) -> Any:
        """Dispatch a LiteLLM completion through router or direct fallback."""
        wire_models = resolve_fallback_litellm_wire_models(model, config.llm_model_list)
        register_fallback_model_pricing(wire_models)
        effective_kwargs = dict(call_kwargs)
        if use_channel_router and self._router and model in router_model_names:
            return self._router.completion(**effective_kwargs)
        if self._router and model == config.litellm_model and not use_channel_router:
            return self._router.completion(**effective_kwargs)

        keys = get_api_keys_for_model(model, config)
        if keys:
            effective_kwargs["api_key"] = keys[0]
        effective_kwargs.update(extra_litellm_params(model, config))
        return litellm.completion(**effective_kwargs)

    def _normalize_usage(self, usage_obj: Any) -> Dict[str, Any]:
        """Normalize usage objects from LiteLLM responses/chunks."""
        if not usage_obj:
            return {}

        def _get_value(key: str) -> int:
            if isinstance(usage_obj, dict):
                return int(usage_obj.get(key) or 0)
            return int(getattr(usage_obj, key, 0) or 0)

        return {
            "prompt_tokens": _get_value("prompt_tokens"),
            "completion_tokens": _get_value("completion_tokens"),
            "total_tokens": _get_value("total_tokens"),
        }

    @staticmethod
    def _get_response_field(obj: Any, key: str) -> Any:
        """Read a field from dict-like or object-like LiteLLM payloads."""
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    def _extract_text_blocks(self, blocks: Any) -> str:
        """Extract text from OpenAI-compatible content block lists."""
        if not blocks:
            return ""

        parts: List[str] = []
        for block in blocks:
            if isinstance(block, str):
                parts.append(block)
                continue

            text = None
            if isinstance(block, dict):
                text = block.get("text")
                if text is None:
                    text = block.get("content")
            else:
                text = getattr(block, "text", None)
                if text is None:
                    text = getattr(block, "content", None)

            if isinstance(text, str) and text:
                parts.append(text)

        return "".join(parts).strip()

    def _extract_completion_text(self, response: Any) -> str:
        """Extract text from non-stream LiteLLM completion responses."""
        choices = self._get_response_field(response, "choices")
        if not choices:
            return ""

        choice = choices[0]
        message = self._get_response_field(choice, "message")

        content_blocks = self._get_response_field(choice, "content_blocks")
        if content_blocks is None and message is not None:
            content_blocks = self._get_response_field(message, "content_blocks")
        block_text = self._extract_text_blocks(content_blocks)
        if block_text:
            return block_text

        content = None
        if message is not None:
            content = self._get_response_field(message, "content")
        if content is None:
            content = self._get_response_field(choice, "content")

        if isinstance(content, list):
            return self._extract_text_blocks(content)
        if isinstance(content, str):
            return content.strip()
        return str(content).strip() if content is not None else ""

    def _extract_stream_text(self, chunk: Any) -> str:
        """Extract provider-agnostic text delta from a LiteLLM streaming chunk."""
        choices = chunk.get("choices") if isinstance(chunk, dict) else getattr(chunk, "choices", None)
        if not choices:
            return ""

        choice = choices[0]
        delta = choice.get("delta") if isinstance(choice, dict) else getattr(choice, "delta", None)
        message = choice.get("message") if isinstance(choice, dict) else getattr(choice, "message", None)

        content: Any = None
        if isinstance(delta, dict):
            content = delta.get("content")
        elif isinstance(delta, str):
            content = delta
        elif delta is not None:
            content = getattr(delta, "content", None)

        if content is None:
            if isinstance(message, dict):
                content = message.get("content")
            elif message is not None:
                content = getattr(message, "content", None)

        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)

        return content if isinstance(content, str) else ""

    def _consume_litellm_stream(
        self,
        stream_response: Any,
        *,
        model: str,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Consume a LiteLLM stream into a single text payload."""
        chunks: List[str] = []
        usage: Dict[str, Any] = {}
        chars_received = 0
        next_emit_at = 1

        try:
            for chunk in stream_response:
                chunk_usage = chunk.get("usage") if isinstance(chunk, dict) else getattr(chunk, "usage", None)
                normalized_usage = self._normalize_usage(chunk_usage)
                if normalized_usage:
                    usage = normalized_usage

                delta_text = self._extract_stream_text(chunk)
                if not delta_text:
                    continue

                chunks.append(delta_text)
                chars_received += len(delta_text)
                if progress_callback and chars_received >= next_emit_at:
                    progress_callback(chars_received)
                    next_emit_at = chars_received + 160
        except Exception as exc:
            raise _LiteLLMStreamError(
                f"{model} stream interrupted: {exc}",
                partial_received=chars_received > 0,
            ) from exc

        response_text = "".join(chunks).strip()
        if not response_text:
            raise _LiteLLMStreamError(
                f"{model} stream returned empty response",
                partial_received=False,
            )

        if progress_callback and chars_received > 0:
            progress_callback(chars_received)

        return response_text, usage

    def _call_litellm(
        self,
        prompt: str,
        generation_config: dict,
        *,
        system_prompt: Optional[str] = None,
        stream: bool = False,
        stream_progress_callback: Optional[Callable[[int], None]] = None,
        response_validator: Optional[Callable[[str], None]] = None,
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Call LLM via litellm with fallback across configured models.

        When channels/YAML are configured, every model goes through the Router
        (which handles per-model key selection, load balancing, and retries).
        In legacy mode, the primary model may use the Router while fallback
        models fall back to direct litellm.completion().

        Args:
            prompt: User prompt text.
            generation_config: Dict with optional keys: temperature, max_output_tokens, max_tokens.
            response_validator: Optional callable that accepts the raw response text and raises
                an exception if the response is unacceptable (e.g. not valid JSON).  When it
                raises, the current model is treated as failed and the next fallback model is
                tried.  If all models fail validation, :class:`_AllModelsFailedError` is raised
                with ``last_response_text`` set to the last raw response received.

        Returns:
            Tuple of (response text, model_used, usage). On success model_used is the full model
            name and usage is a dict with prompt_tokens, completion_tokens, total_tokens.
        """
        config = self._get_runtime_config()
        max_tokens = (
            generation_config.get('max_output_tokens')
            or generation_config.get('max_tokens')
            or 8192
        )
        requested_temperature = generation_config.get('temperature', 0.7)

        models_to_try = [config.litellm_model] + (config.litellm_fallback_models or [])
        models_to_try = [m for m in models_to_try if m]

        use_channel_router = self._has_channel_config(config)

        last_error = None
        last_response_text: Optional[str] = None
        last_model: Optional[str] = None
        last_usage: Dict[str, Any] = {}
        effective_system_prompt = system_prompt or self.TEXT_SYSTEM_PROMPT
        router_model_names = set(get_configured_llm_models(config.llm_model_list))
        for model in models_to_try:
            recovery_model_list = config.llm_model_list
            legacy_router_model_list = getattr(self, "_legacy_router_model_list", None) or []
            if legacy_router_model_list and model == config.litellm_model and not use_channel_router:
                recovery_model_list = legacy_router_model_list

            try:
                model_short = model.split("/")[-1] if "/" in model else model
                extra = get_thinking_extra_body(model_short)
                call_kwargs: Dict[str, Any] = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": effective_system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": max_tokens,
                }
                if extra:
                    call_kwargs["extra_body"] = extra
                uses_router = (
                    (use_channel_router and self._router and model in router_model_names)
                    or (self._router and model == config.litellm_model and not use_channel_router)
                )
                if not uses_router:
                    try:
                        keys = get_api_keys_for_model(model, config)
                    except AttributeError:
                        keys = []
                    if keys:
                        call_kwargs["api_key"] = keys[0]
                    try:
                        call_kwargs.update(extra_litellm_params(model, config))
                    except AttributeError:
                        pass
                call_kwargs = apply_litellm_generation_params(
                    call_kwargs,
                    model,
                    requested_temperature,
                    model_list=recovery_model_list,
                )

                _stream_text: Optional[str] = None
                _stream_usage: Dict[str, Any] = {}

                if stream:
                    try:
                        stream_response = call_litellm_with_param_recovery(
                            lambda kwargs: self._dispatch_litellm_completion(
                                model,
                                kwargs,
                                config=config,
                                use_channel_router=use_channel_router,
                                router_model_names=router_model_names,
                            ),
                            model=model,
                            call_kwargs={**call_kwargs, "stream": True},
                            model_list=recovery_model_list,
                            cache_recovery=False,
                            logger=logger,
                        )
                        _stream_text, _stream_usage = self._consume_litellm_stream(
                            stream_response,
                            model=model,
                            progress_callback=stream_progress_callback,
                        )
                    except _LiteLLMStreamError as exc:
                        if exc.partial_received:
                            logger.warning(
                                "[LiteLLM] %s stream failed after partial output, retrying non-stream for same model: %s",
                                model,
                                exc,
                            )
                        else:
                            logger.warning(
                                "[LiteLLM] %s stream unavailable before first chunk, falling back to non-stream: %s",
                                model,
                                exc,
                            )
                        last_error = exc
                    except Exception as exc:
                        logger.warning(
                            "[LiteLLM] %s stream request failed before first chunk, falling back to non-stream: %s",
                            model,
                            exc,
                        )

                if _stream_text is not None:
                    last_response_text = _stream_text
                    last_model = model
                    last_usage = _stream_usage
                    if response_validator is not None:
                        response_validator(_stream_text)
                    return _stream_text, model, _stream_usage

                response = call_litellm_with_param_recovery(
                    lambda kwargs: self._dispatch_litellm_completion(
                        model,
                        kwargs,
                        config=config,
                        use_channel_router=use_channel_router,
                        router_model_names=router_model_names,
                    ),
                    model=model,
                    call_kwargs=call_kwargs,
                    model_list=recovery_model_list,
                    logger=logger,
                )

                content = self._extract_completion_text(response)
                if content:
                    usage = self._normalize_usage(self._get_response_field(response, "usage"))
                    last_response_text = content
                    last_model = model
                    last_usage = usage
                    if response_validator is not None:
                        response_validator(content)
                    return (content, model, usage)
                raise ValueError("LLM returned empty response")

            except Exception as e:
                logger.warning(f"[LiteLLM] {model} failed: {e}")
                last_error = e
                continue

        raise _AllModelsFailedError(
            f"All LLM models failed (tried {len(models_to_try)} model(s)). Last error: {last_error}",
            last_response_text=last_response_text,
            last_model=last_model,
            last_usage=last_usage,
        )

    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> Optional[str]:
        """Public entry point for free-form text generation.

        External callers (e.g. MarketAnalyzer) must use this method instead of
        calling _call_litellm() directly or accessing private attributes such as
        _litellm_available, _router, _model, _use_openai, or _use_anthropic.

        Args:
            prompt:      Text prompt to send to the LLM.
            max_tokens:  Maximum tokens in the response (default 2048).
            temperature: Sampling temperature (default 0.7).

        Returns:
            Response text, or None if the LLM call fails (error is logged).
        """
        try:
            result = self._call_litellm(
                prompt,
                generation_config={"max_tokens": max_tokens, "temperature": temperature},
            )
            if isinstance(result, tuple):
                text, model_used, usage = result
                persist_llm_usage(usage, model_used, call_type="market_review")
                return text
            return result
        except Exception as exc:
            logger.error("[generate_text] LLM call failed: %s", exc)
            return None

    def analyze(
        self, 
        context: Dict[str, Any],
        news_context: Optional[str] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        stream_progress_callback: Optional[Callable[[int], None]] = None,
        analysis_context_pack_summary: Optional[str] = None,
    ) -> AnalysisResult:
        """
        分析单只股票
        
        流程：
        1. 格式化输入数据（技术面 + 新闻）
        2. 调用 Gemini API（带重试和模型切换）
        3. 解析 JSON 响应
        4. 返回结构化结果
        
        Args:
            context: 从 storage.get_analysis_context() 获取的上下文数据
            news_context: 预先搜索的新闻内容（可选）
            
        Returns:
            AnalysisResult 对象
        """
        def _emit_progress(progress: int, message: str) -> None:
            if progress_callback is None:
                return
            try:
                progress_callback(progress, message)
            except Exception as exc:
                logger.debug("[analyzer] progress callback skipped: %s", exc)

        code = context.get('code', 'Unknown')
        config = self._get_runtime_config()
        report_language = normalize_report_language(getattr(config, "report_language", "zh"))
        system_prompt = self._get_analysis_system_prompt(report_language, stock_code=code)
        
        # 请求前增加延时（防止连续请求触发限流）
        request_delay = config.gemini_request_delay
        if request_delay > 0:
            logger.debug(f"[LLM] 请求前等待 {request_delay:.1f} 秒...")
            _emit_progress(65, f"{code}：LLM 请求前等待 {request_delay:.1f} 秒")
            time.sleep(request_delay)
        
        # 优先从上下文获取股票名称（由 main.py 传入）
        name = context.get('stock_name')
        if not name or name.startswith('股票'):
            # 备选：从 realtime 中获取
            if 'realtime' in context and context['realtime'].get('name'):
                name = context['realtime']['name']
            else:
                # 最后从映射表获取
                name = STOCK_NAME_MAP.get(code, f'股票{code}')
        
        # 如果模型不可用，返回默认结果
        if not self.is_available():
            return AnalysisResult(
                code=code,
                name=name,
                sentiment_score=50,
                trend_prediction='Sideways' if report_language == "en" else '震荡',
                operation_advice='Hold' if report_language == "en" else '持有',
                confidence_level='Low' if report_language == "en" else '低',
                analysis_summary='AI analysis is unavailable because no API key is configured.' if report_language == "en" else 'AI 分析功能未启用（未配置 API Key）',
                risk_warning='Configure an LLM API key (GEMINI_API_KEY/ANTHROPIC_API_KEY/OPENAI_API_KEY) and retry.' if report_language == "en" else '请配置 LLM API Key（GEMINI_API_KEY/ANTHROPIC_API_KEY/OPENAI_API_KEY）后重试',
                success=False,
                error_message='LLM API key is not configured' if report_language == "en" else 'LLM API Key 未配置',
                model_used=None,
                report_language=report_language,
            )
        
        try:
            # 格式化输入（包含技术面数据和新闻）
            prompt = self._format_prompt(
                context,
                name,
                news_context,
                report_language=report_language,
                analysis_context_pack_summary=analysis_context_pack_summary,
            )
            
            config = self._get_runtime_config()
            model_name = config.litellm_model or "unknown"
            logger.info(f"========== AI 分析 {name}({code}) ==========")
            logger.info(f"[LLM配置] 模型: {model_name}")
            logger.info(f"[LLM配置] Prompt 长度: {len(prompt)} 字符")
            logger.info(f"[LLM配置] 是否包含新闻: {'是' if news_context else '否'}")

            # 记录完整 prompt 到日志（INFO级别记录摘要，DEBUG记录完整）
            prompt_preview = prompt[:500] + "..." if len(prompt) > 500 else prompt
            logger.info(f"[LLM Prompt 预览]\n{prompt_preview}")
            logger.debug(f"=== 完整 Prompt ({len(prompt)}字符) ===\n{prompt}\n=== End Prompt ===")

            # 设置生成配置
            generation_config = {
                "temperature": config.llm_temperature,
                "max_output_tokens": 8192,
            }

            logger.info(f"[LLM调用] 开始调用 {model_name}...")
            _emit_progress(68, f"{name}：LLM 已接收请求，等待响应")

            # 使用 litellm 调用（支持完整性校验重试）
            current_prompt = prompt
            retry_count = 0
            max_retries = config.report_integrity_retry if config.report_integrity_enabled else 0

            while True:
                start_time = time.time()
                try:
                    response_text, model_used, llm_usage = self._call_litellm(
                        current_prompt,
                        generation_config,
                        system_prompt=system_prompt,
                        stream=True,
                        stream_progress_callback=stream_progress_callback,
                        response_validator=self._validate_json_response,
                    )
                except _AllModelsFailedError as exc:
                    if exc.last_response_text is not None:
                        logger.warning(
                            "[LLM JSON] %s(%s): all models returned invalid JSON, using text fallback",
                            name,
                            code,
                        )
                        response_text = exc.last_response_text
                        model_used = exc.last_model
                        llm_usage = exc.last_usage
                    else:
                        raise
                elapsed = time.time() - start_time

                # 记录响应信息
                logger.info(
                    f"[LLM返回] {model_name} 响应成功, 耗时 {elapsed:.2f}s, 响应长度 {len(response_text)} 字符"
                )
                response_preview = response_text[:300] + "..." if len(response_text) > 300 else response_text
                logger.info(f"[LLM返回 预览]\n{response_preview}")
                logger.debug(
                    f"=== {model_name} 完整响应 ({len(response_text)}字符) ===\n{response_text}\n=== End Response ==="
                )
                # Keep parser/retry progress monotonic so task progress/message never "goes backward".
                parse_progress = min(99, 93 + retry_count * 2)
                _emit_progress(parse_progress, f"{name}：LLM 返回完成，正在解析 JSON")

                # 解析响应
                result = self._parse_response(response_text, code, name)
                result.raw_response = response_text
                result.search_performed = bool(news_context)
                result.market_snapshot = self._build_market_snapshot(context)
                result.model_used = model_used
                result.report_language = report_language
                normalize_chip_structure_availability(result, context.get("chip"))

                # 内容完整性校验（可选）
                if not config.report_integrity_enabled:
                    break
                pass_integrity, missing_fields = self._check_content_integrity(result)
                if pass_integrity:
                    break
                if retry_count < max_retries:
                    current_prompt = self._build_integrity_retry_prompt(
                        prompt,
                        response_text,
                        missing_fields,
                        report_language=report_language,
                    )
                    retry_count += 1
                    logger.info(
                        "[LLM完整性] 必填字段缺失 %s，第 %d 次补全重试",
                        missing_fields,
                        retry_count,
                    )
                    retry_progress = min(99, 92 + retry_count * 2)
                    _emit_progress(
                        retry_progress,
                        f"{name}：报告字段不完整，正在补全重试（{retry_count}/{max_retries}）",
                    )
                else:
                    self._apply_placeholder_fill(result, missing_fields)
                    logger.warning(
                        "[LLM完整性] 必填字段缺失 %s，已占位补全，不阻塞流程",
                        missing_fields,
                    )
                    break

            persist_llm_usage(llm_usage, model_used or "", call_type="analysis", stock_code=code)

            logger.info(f"[LLM解析] {name}({code}) 分析完成: {result.trend_prediction}, 评分 {result.sentiment_score}")

            return result
            
        except Exception as e:
            logger.error(f"AI 分析 {name}({code}) 失败: {e}")
            return AnalysisResult(
                code=code,
                name=name,
                sentiment_score=50,
                trend_prediction='Sideways' if report_language == "en" else '震荡',
                operation_advice='Hold' if report_language == "en" else '持有',
                confidence_level='Low' if report_language == "en" else '低',
                analysis_summary=(f'Analysis failed: {str(e)[:100]}' if report_language == "en" else f'分析过程出错: {str(e)[:100]}'),
                risk_warning='Analysis failed. Please retry later or review manually.' if report_language == "en" else '分析失败，请稍后重试或手动分析',
                success=False,
                error_message=str(e),
                model_used=None,
                report_language=report_language,
            )
    
    def _format_prompt(
        self, 
        context: Dict[str, Any], 
        name: str,
        news_context: Optional[str] = None,
        report_language: str = "zh",
        analysis_context_pack_summary: Optional[str] = None,
    ) -> str:
        """
        格式化分析提示词（决策仪表盘 v2.0）
        
        包含：技术指标、实时行情（量比/换手率）、筹码分布、趋势分析、新闻
        
        Args:
            context: 技术面数据上下文（包含增强数据）
            name: 股票名称（默认值，可能被上下文覆盖）
            news_context: 预先搜索的新闻内容
        """
        code = context.get('code', 'Unknown')
        report_language = normalize_report_language(report_language)
        _, _, use_legacy_default_prompt = self._get_skill_prompt_sections()
        
        # 优先使用上下文中的股票名称（从 realtime_quote 获取）
        stock_name = context.get('stock_name', name)
        if not stock_name or stock_name == f'股票{code}':
            stock_name = STOCK_NAME_MAP.get(code, f'股票{code}')
            
        today = context.get('today', {})
        unknown_text = get_unknown_text(report_language)
        no_data_text = get_no_data_text(report_language)
        quote_section_title, close_price_label = _phase_aware_quote_labels(context)
        hide_regular_session_ohlc = _should_hide_regular_session_ohlc(context)
        realtime_overlay_quote = hide_regular_session_ohlc and _today_has_realtime_overlay(today)
        pct_chg_label = "Variação % em Tempo Real" if realtime_overlay_quote else "Variação %"
        volume_label = "Volume em Tempo Real" if realtime_overlay_quote else "Volume"
        amount_label = "Valor em Tempo Real" if realtime_overlay_quote else "Valor"
        quote_rows = [
            f"| {close_price_label} | {today.get('close', 'N/A')} 元 |",
        ]
        if not hide_regular_session_ohlc:
            quote_rows.extend(
                [
                    f"| Preço de Abertura | {today.get('open', 'N/A')} 元 |",
                    f"| Preço Máximo | {today.get('high', 'N/A')} 元 |",
                    f"| Preço Mínimo | {today.get('low', 'N/A')} 元 |",
                ]
            )
        quote_rows.extend(
            [
                f"| {pct_chg_label} | {today.get('pct_chg', 'N/A')}% |",
                f"| {volume_label} | {self._format_volume(today.get('volume'))} |",
                f"| {amount_label} | {self._format_amount(today.get('amount'))} |",
            ]
        )
        quote_rows_text = "\n".join(quote_rows)
        
        # ========== 构建决策仪表盘格式的输入 ==========
        prompt = f"""# Solicitação de Análise de Dashboard de Decisão

## 📊 Informações Básicas da Ação
| Item | Dados |
|------|------|
| Código da Ação | **{code}** |
| Nome da Ação | **{stock_name}** |
| Data da Análise | {context.get('date', unknown_text)} |

---
"""
        prompt += format_market_phase_prompt_section(
            context.get("market_phase_context"),
            report_language=report_language,
        )
        if isinstance(analysis_context_pack_summary, str) and analysis_context_pack_summary:
            prompt += analysis_context_pack_summary
        prompt += f"""

## 📈 Dados Técnicos

### {quote_section_title}
| Indicador | Valor |
|------|------|
{quote_rows_text}

### Sistema de Médias Móveis (Indicador Crítico de Julgamento)
| Média | Valor | Descrição |
|------|------|------|
| MA5 | {today.get('ma5', 'N/A')} | Linha de tendência de curto prazo |
| MA10 | {today.get('ma10', 'N/A')} | Linha de tendência de curto a médio prazo |
| MA20 | {today.get('ma20', 'N/A')} | Linha de tendência de médio prazo |
| Padrão de Médias | {context.get('ma_status', unknown_text)} | Alta/Baixa/Consolidando |
"""
        
        # 添加实时行情数据（量比、换手率等）
        if 'realtime' in context:
            rt = context['realtime']
            prompt += f"""
### Dados Aprimorados em Tempo Real
| Indicador | Valor | Interpretação |
|------|------|------|
| Preço Atual | {rt.get('price', 'N/A')} 元 | |
| **Taxa de Volume** | **{rt.get('volume_ratio', 'N/A')}** | {rt.get('volume_ratio_desc', '')} |
| **Taxa de Rotatividade** | **{rt.get('turnover_rate', 'N/A')}%** | |
| P/L (Dinâmico) | {rt.get('pe_ratio', 'N/A')} | |
| P/VP | {rt.get('pb_ratio', 'N/A')} | |
| Valor de Mercado Total | {self._format_amount(rt.get('total_mv'))} | |
| Valor de Mercado Circulante | {self._format_amount(rt.get('circ_mv'))} | |
| Variação 60 dias | {rt.get('change_60d', 'N/A')}% | Desempenho de médio prazo |
"""

        # 添加财报与分红（价值投资口径）
        fundamental_context = context.get("fundamental_context") if isinstance(context, dict) else None
        earnings_block = (
            fundamental_context.get("earnings", {})
            if isinstance(fundamental_context, dict)
            else {}
        )
        earnings_data = (
            earnings_block.get("data", {})
            if isinstance(earnings_block, dict)
            else {}
        )
        financial_report = (
            earnings_data.get("financial_report", {})
            if isinstance(earnings_data, dict)
            else {}
        )
        dividend_metrics = (
            earnings_data.get("dividend", {})
            if isinstance(earnings_data, dict)
            else {}
        )
        if isinstance(financial_report, dict) or isinstance(dividend_metrics, dict):
            financial_report = financial_report if isinstance(financial_report, dict) else {}
            dividend_metrics = dividend_metrics if isinstance(dividend_metrics, dict) else {}
            ttm_yield = dividend_metrics.get("ttm_dividend_yield_pct", "N/A")
            ttm_cash = dividend_metrics.get("ttm_cash_dividend_per_share", "N/A")
            ttm_count = dividend_metrics.get("ttm_event_count", "N/A")
            report_date = financial_report.get("report_date", "N/A")
            prompt += f"""### Relatórios Financeiros e Dividendos (Perspectiva de Investimento em Valor)
| Indicador | Valor | Descrição |
|------|------|------|
| Período Recente do Relatório | {report_date} | A partir dos campos financeiros estruturados |
| Receita | {financial_report.get('revenue', 'N/A')} | |
| Lucro Líquido | {financial_report.get('net_profit_parent', 'N/A')} | |
| Fluxo de Caixa Operacional | {financial_report.get('operating_cash_flow', 'N/A')} | |
| ROE | {financial_report.get('roe', 'N/A')} | |
| Div. em Dinheiro por Ação TTM | {ttm_cash} | Apenas dividendos em dinheiro, antes de impostos |
| Rendimento de Div. TTM | {ttm_yield} | Fórmula: Div. em Dinheiro por Ação TTM / Preço Atual × 100% |
| Eventos de Div. TTM | {ttm_count} | |

> Se os campos acima forem N/A ou ausentes, escreva claramente "Dados ausentes, não é possível julgar", e não invente.
"""

        capital_flow_block = (
            fundamental_context.get("capital_flow", {})
            if isinstance(fundamental_context, dict)
            else {}
        )
        capital_flow_data = (
            capital_flow_block.get("data", {})
            if isinstance(capital_flow_block, dict)
            else {}
        )
        stock_flow = (
            capital_flow_data.get("stock_flow", {})
            if isinstance(capital_flow_data, dict)
            else {}
        )
        sector_flow = (
            capital_flow_data.get("sector_rankings", {})
            if isinstance(capital_flow_data, dict)
            else {}
        )
        has_capital_flow = (
            isinstance(stock_flow, dict)
            and any(v is not None for v in stock_flow.values())
        ) or (
            isinstance(sector_flow, dict)
            and (sector_flow.get("top") or sector_flow.get("bottom"))
        )
        if has_capital_flow:
            top_sectors = sector_flow.get("top", []) if isinstance(sector_flow, dict) else []
            bottom_sectors = sector_flow.get("bottom", []) if isinstance(sector_flow, dict) else []
            top_sector_text = "、".join(
                str(item.get("name", "")).strip()
                for item in top_sectors[:3]
                if isinstance(item, dict) and str(item.get("name", "")).strip()
            ) or "N/A"
            bottom_sector_text = "、".join(
                str(item.get("name", "")).strip()
                for item in bottom_sectors[:3]
                if isinstance(item, dict) and str(item.get("name", "")).strip()
            ) or "N/A"
            prompt += f"""### Fluxo de Capital Principal (Filtro de Sugestão Operacional)
| Indicador | Valor | Implicação de Decisão |
|------|------|----------|
| Fluxo Líquido Principal | {stock_flow.get('main_net_inflow', 'N/A')} | Positivo é favorável, negativo é pressão |
| Fluxo Líquido 5d | {stock_flow.get('inflow_5d', 'N/A')} | Avaliar a sustentabilidade do fluxo |
| Fluxo Líquido 10d | {stock_flow.get('inflow_10d', 'N/A')} | Avaliar a sustentabilidade do fluxo |
| Setores Top em Entradas | {top_sector_text} | Referência de ressonância de setor |
| Setores Top em Saídas | {bottom_sector_text} | Referência de risco de setor |

> O fluxo de capital serve apenas como filtro para o preço: não sugira comprar próximo à resistência com saídas principais; próximo ao suporte sem quebra de volume, prefira conselhos de manter/observar ou observar após lavagem.
"""

        # 添加筹码分布数据
        if 'chip' in context:
            chip = context['chip']
            profit_ratio = chip.get('profit_ratio', 0)
            prompt += f"""
### Distribuição de Fichas (Indicador de Eficiência)
| Indicador | Valor | Padrão de Saúde |
|------|------|----------|
| **Índice de Lucro** | **{profit_ratio:.1%}** | Cuidado ao atingir 70-90% |
| Custo Médio | {chip.get('avg_cost', 'N/A')} 元 | Preço atual deve estar 5-15% acima |
| Concentração de Fichas (90%) | {chip.get('concentration_90', 0):.2%} | <15% indica concentração |
| Concentração de Fichas (70%) | {chip.get('concentration_70', 0):.2%} | |
| Status das Fichas | {chip.get('chip_status', unknown_text)} | |
"""
        else:
            chip_unavailable_text = get_chip_unavailable_text(report_language)
            chip_instruction = (
                "Do not fabricate profit ratio, average cost, or concentration. Mention chip data "
                "unavailability only once in the report; do not repeat per-field no-data text in `chip_structure`."
                if report_language == "en"
                else "Não invente o índice de lucro, custo médio ou concentração; mencione a indisponibilidade dos dados de fichas apenas uma vez no relatório, não repita 'dados ausentes' por campo em `chip_structure`."
            )
            prompt += f"""### Dados de Distribuição de Fichas (Indicador de Eficiência)
> {chip_unavailable_text}
> {chip_instruction}
"""
        
        # 添加趋势分析结果（仅隐式内建 bull_trend 默认回退保留旧口径）
        if 'trend_analysis' in context:
            trend = _sanitize_trend_analysis_for_prompt(
                context['trend_analysis'],
                volume_change_ratio=context.get('volume_change_ratio'),
            )
            consistency_notes = trend.get('prompt_consistency_notes', [])
            if use_legacy_default_prompt:
                bias_warning = "🚨 Acima de 5%, evite perseguir altas!" if trend.get('bias_ma5', 0) > 5 else "✅ Faixa Segura"
                prompt += f"""
### Previsão de Análise de Tendência (Com base no conceito de negociação)
| Indicador | Valor | Julgamento |
|------|------|------|
| Status da Tendência | {trend.get('trend_status', unknown_text)} | |
| Alinhamento MA | {trend.get('ma_alignment', unknown_text)} | MA5>MA10>MA20 é alta |
| Força da Tendência | {trend.get('trend_strength', 0)}/100 | |
| **Taxa de Viés (MA5)** | **{trend.get('bias_ma5', 0):+.2f}%** | {bias_warning} |
| Taxa de Viés (MA10) | {trend.get('bias_ma10', 0):+.2f}% | |
| Status de Volume | {trend.get('volume_status', unknown_text)} | {trend.get('volume_trend', '')} |
| Sinal de Compra | {trend.get('buy_signal', unknown_text)} | |
| Pontuação de Sinal | {trend.get('signal_score', 0)}/100 | |

#### Motivos de Análise do Sistema
**Motivos de Compra**:
{chr(10).join('- ' + r for r in trend.get('signal_reasons', ['Nenhum'])) if trend.get('signal_reasons') else '- Nenhum'}

**Fatores de Risco**:
{chr(10).join('- ' + r for r in trend.get('risk_factors', ['Nenhum'])) if trend.get('risk_factors') else '- Nenhum'}
"""
                if consistency_notes:
                    prompt += f"""

**Restrições de Consistência**:
{chr(10).join('- ' + note for note in consistency_notes)}
"""
            else:
                bias_warning = (
                    "🚨 Grande desvio, avalie com cuidado o risco de perseguir altas"
                    if trend.get('bias_ma5', 0) > 5
                    else "✅ Posição relativamente controlável"
                )
                prompt += f"""
### Análise Técnica e de Estrutura (Para referência na ativação de habilidades)
| Indicador | Valor | Descrição |
|------|------|------|
| Status da Tendência | {trend.get('trend_status', unknown_text)} | |
| Alinhamento MA | {trend.get('ma_alignment', unknown_text)} | Julgue a força com base em habilidades |
| Força da Tendência | {trend.get('trend_strength', 0)}/100 | |
| **Posição de Preço (MA5)** | **{trend.get('bias_ma5', 0):+.2f}%** | {bias_warning} |
| Posição de Preço (MA10) | {trend.get('bias_ma10', 0):+.2f}% | |
| Status de Volume | {trend.get('volume_status', unknown_text)} | {trend.get('volume_trend', '')} |
| Sinal de Compra | {trend.get('buy_signal', unknown_text)} | |
| Pontuação de Sinal | {trend.get('signal_score', 0)}/100 | |

#### Motivos de Análise do Sistema
**Fatores de Apoio**:
{chr(10).join('- ' + r for r in trend.get('signal_reasons', ['Nenhum'])) if trend.get('signal_reasons') else '- Nenhum'}

**Fatores de Risco**:
{chr(10).join('- ' + r for r in trend.get('risk_factors', ['Nenhum'])) if trend.get('risk_factors') else '- Nenhum'}
"""
                if consistency_notes:
                    prompt += f"""

**Restrições de Consistência**:
{chr(10).join('- ' + note for note in consistency_notes)}
"""
        
        # 添加昨日对比数据
        if 'yesterday' in context:
            volume_change = context.get('volume_change_ratio', 'N/A')
            prompt += f"""### Alterações de Preço e Volume
- Alteração de volume vs. ontem: {volume_change}x
- Variação de preço vs. ontem: {context.get('price_change_ratio', 'N/A')}%
"""
            parsed_volume_change = _safe_float(volume_change, default=math.nan)
            if math.isfinite(parsed_volume_change) and parsed_volume_change > 10:
                prompt += """
- ⚠️ Alerta de Anomalia de Volume: O volume aumentou mais de 10x em relação a ontem, possivelmente devido a dados anormais ou impacto pontual, interprete com cautela.
"""
        
        # 添加新闻搜索结果（重点区域）
        news_window_days: Optional[int] = None
        context_window = context.get("news_window_days")
        try:
            if context_window is not None:
                parsed_window = int(context_window)
                if parsed_window > 0:
                    news_window_days = parsed_window
        except (TypeError, ValueError):
            news_window_days = None

        if news_window_days is None:
            prompt_config = self._get_runtime_config()
            news_window_days = resolve_news_window_days(
                news_max_age_days=getattr(prompt_config, "news_max_age_days", 3),
                news_strategy_profile=getattr(prompt_config, "news_strategy_profile", "short"),
            )
        prompt += """
---

## 📰 Inteligência de Notícias
"""
        if news_context:
            prompt += f"""
Abaixo estão os resultados das notícias dos últimos {news_window_days} dias para **{stock_name}({code})**. Foque em:
1. 🚨 **Alertas de Risco**: Redução de participações, penalidades, pontos negativos
2. 🎯 **Catalisadores Positivos**: Ganhos, contratos, políticas
3. 📊 **Perspectiva de Lucros**: Previsões de relatórios, resultados preliminares
4. 🕒 **Regras de Tempo (Obrigatório)**:
   - Todo item em `risk_alerts` / `positive_catalysts` / `latest_news` deve incluir datas específicas (AAAA-MM-DD).
   - Ignore notícias fora da janela de {news_window_days} dias.
   - Ignore notícias com datas desconhecidas.

```
{news_context}
```
"""
        else:
            prompt += """
Nenhuma notícia recente encontrada para esta ação. Confie nos dados técnicos para análise.
"""

        # 注入缺失数据警告
        if context.get('data_missing'):
            prompt += """
⚠️ **Aviso de Dados Ausentes**
Devido a restrições de API, os dados de cotação e técnicos em tempo real estão incompletos.
**Ignore os dados N/A nas tabelas acima** e baseie-se fortemente nas **【📰 Inteligência de Notícias】** para os fundamentos e sentimentos.
Quando precisar justificar aspectos técnicos, declare "Dados ausentes, impossível julgar" e **não invente dados**.
"""

        # 明确的输出要求
        prompt += f"""
---

## ✅ Tarefa de Análise

Por favor, gere um 【Dashboard de Decisão】 para **{stock_name}({code})** estritamente no formato JSON definido.
"""
        if context.get('is_index_etf'):
            prompt += """
> ⚠️ **Restrição para Índice/ETF**: Este é um fundo de índice (ETF) ou índice de mercado.
> - A análise de risco foca apenas em: **tendência do índice, erro de rastreamento e liquidez de mercado**.
> - Não inclua litígios, reputação ou mudanças de diretoria da gestora.
> - As expectativas de lucro baseiam-se no **desempenho geral dos componentes do índice**, não no relatório financeiro da gestora.
> - Os riscos operacionais da gestora do fundo não devem aparecer em `risk_alerts`.

"""
        prompt += f"""
### ⚠️ IMPORTANTE: Produza o formato correto do nome da ação
O formato correto do nome da ação é "Nome (Código)", por exemplo "Petrobras (PETR4)".
Se o nome exibido acima for "Ação{code}" ou estiver incorreto, indique explicitamente o **nome correto** no início da sua análise.
"""
        if use_legacy_default_prompt:
            prompt += f"""

### Foco Principal (deve responder claramente):
1. ❓ O padrão MA5>MA10>MA20 é um arranjo de alta?
2. ❓ A taxa de viés atual está em uma faixa segura (<5%)? —— Se exceder 5%, você deve marcar "evite perseguir altas".
3. ❓ O volume suporta isso (correção sem volume/rompimento com volume)?
4. ❓ A estrutura das fichas é saudável?
5. ❓ Existem notícias negativas importantes? (Redução de participações, penalidades, reversão de resultados, etc.)
"""
        else:
            prompt += f"""

### Foco Principal (deve responder claramente):
1. ❓ A estrutura atual atende às condições essenciais para a ativação de habilidades?
2. ❓ A posição de entrada e o risco-recompensa são razoáveis? Se houver um grande desvio, forneça condições claras de espera.
3. ❓ Volume, volatilidade e estrutura de fichas apoiam a conclusão atual?
4. ❓ Há notícias negativas graves ou informações conflitantes com a conclusão?
5. ❓ Se a conclusão for válida, quais são as condições de gatilho, stop-loss e pontos de observação específicos?
"""
        prompt += f"""

### Requisitos do Dashboard de Decisão:
- **Nome da Ação**: Deve produzir o nome completo correto (por exemplo "Petrobras" e não "Ação PETR4")
- **Conclusão Principal**: Indique claramente se deve comprar/vender/esperar em uma frase
- **Conselhos baseados na Posição**: Ações para quem não tem posição vs. para quem tem
- **Pontos precisos de atirador**: Preço de compra, preço de stop loss, preço alvo
- **Checklist**: Marque cada item usando ✅/⚠️/❌
- **Conformidade de Tempo de Notícias**: `latest_news`, `risk_alerts`, `positive_catalysts` não podem conter informações fora dos últimos {news_window_days} dias ou com datas desconhecidas.
- **Consistência Técnica**: É estritamente proibido usar simultaneamente conclusões mutuamente exclusivas como "tendência de baixa" e "tendência de alta" como base válida; se os fundamentos ou notícias conflitarem com a parte técnica, escreva "Notícias à frente, técnica precisa de confirmação" ou "Fundamentos de alta, mas ainda sem confirmação técnica".
 
Por favor, produza o Dashboard de Decisão no formato JSON completo."""

        if report_language == "en":
            prompt += """

### Output language requirements (highest priority)
- Keep every JSON key exactly as defined above; do not translate keys.
- `decision_type` must remain `buy`, `hold`, or `sell`.
- All human-readable JSON values must be in English.
- This includes `stock_name`, `trend_prediction`, `operation_advice`, `confidence_level`, all nested dashboard text, checklist items, and every summary field.
- Use the common English company name when you are confident. If not, keep the listed company name rather than inventing one.
- When data is missing, explain it in English instead of Chinese.
"""
        elif report_language == "pt":
            prompt += f"""

### Idioma de Saída (Maior Prioridade)
- Mantenha todas as chaves do JSON exatamente como definidas acima; não traduza as chaves.
- `decision_type` deve permanecer como `buy`, `hold` ou `sell`.
- Todos os valores JSON legíveis por humanos DEVEM ser escritos em Português do Brasil (pt-BR).
- Isso inclui `stock_name`, `trend_prediction`, `operation_advice`, `confidence_level`, texto aninhado no dashboard, itens de checklist, e todos os resumos narrativos.
- Use o nome comum da empresa quando tiver certeza; caso contrário, mantenha o nome original da empresa listada, em vez de inventar um.
- Quando os dados estiverem faltando, explique em Português (ex: {no_data_text}) em vez de Chinês.
"""
        else:
            prompt += f"""

### 输出语言要求（最高优先级）
- 所有 JSON 键名必须保持不变，不要翻译键名。
- `decision_type` 必须保持为 `buy`、`hold`、`sell`。
- 所有面向用户的人类可读文本值必须使用中文。
- 当数据缺失时，请使用中文直接说明“{no_data_text}，无法判断”。
"""
        
        return prompt
    
    def _format_volume(self, volume: Optional[float]) -> str:
        """格式化成交量显示"""
        if volume is None:
            return 'N/A'
        if volume >= 1e8:
            return f"{volume / 1e8:.2f} 亿股"
        elif volume >= 1e4:
            return f"{volume / 1e4:.2f} 万股"
        else:
            return f"{volume:.0f} 股"
    
    def _format_amount(self, amount: Optional[float]) -> str:
        """格式化成交额显示"""
        if amount is None:
            return 'N/A'
        if amount >= 1e8:
            return f"{amount / 1e8:.2f} 亿元"
        elif amount >= 1e4:
            return f"{amount / 1e4:.2f} 万元"
        else:
            return f"{amount:.0f} 元"

    def _format_percent(self, value: Optional[float]) -> str:
        """格式化百分比显示"""
        if value is None:
            return 'N/A'
        try:
            return f"{value:.2f}%"
        except (TypeError, ValueError):
            return 'N/A'

    def _format_price(self, value: Optional[float]) -> str:
        """格式化价格显示"""
        if value is None:
            return 'N/A'
        try:
            return f"{value:.2f}"
        except (TypeError, ValueError):
            return 'N/A'

    def _build_market_snapshot(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """构建当日行情快照（展示用）"""
        today = context.get('today', {}) or {}
        realtime = context.get('realtime', {}) or {}
        yesterday = context.get('yesterday', {}) or {}

        prev_close = yesterday.get('close')
        close = today.get('close')
        high = today.get('high')
        low = today.get('low')

        amplitude = None
        change_amount = None
        if prev_close not in (None, 0) and high is not None and low is not None:
            try:
                amplitude = (float(high) - float(low)) / float(prev_close) * 100
            except (TypeError, ValueError, ZeroDivisionError):
                amplitude = None
        if prev_close is not None and close is not None:
            try:
                change_amount = float(close) - float(prev_close)
            except (TypeError, ValueError):
                change_amount = None

        snapshot = {
            "date": context.get('date', '未知'),
            "close": self._format_price(close),
            "open": self._format_price(today.get('open')),
            "high": self._format_price(high),
            "low": self._format_price(low),
            "prev_close": self._format_price(prev_close),
            "pct_chg": self._format_percent(today.get('pct_chg')),
            "change_amount": self._format_price(change_amount),
            "amplitude": self._format_percent(amplitude),
            "volume": self._format_volume(today.get('volume')),
            "amount": self._format_amount(today.get('amount')),
        }

        if realtime:
            snapshot.update({
                "price": self._format_price(realtime.get('price')),
                "volume_ratio": realtime.get('volume_ratio', 'N/A'),
                "turnover_rate": self._format_percent(realtime.get('turnover_rate')),
                "source": getattr(realtime.get('source'), 'value', realtime.get('source', 'N/A')),
            })

        return snapshot

    def _check_content_integrity(self, result: AnalysisResult) -> Tuple[bool, List[str]]:
        """Delegate to module-level check_content_integrity."""
        return check_content_integrity(result)

    def _build_integrity_complement_prompt(self, missing_fields: List[str], report_language: str = "zh") -> str:
        """Build complement instruction for missing mandatory fields."""
        report_language = normalize_report_language(report_language)
        if report_language == "en":
            lines = ["### Completion requirements: fill the missing mandatory fields below and output the full JSON again:"]
            for f in missing_fields:
                if f == "sentiment_score":
                    lines.append("- sentiment_score: integer score from 0 to 100")
                elif f == "operation_advice":
                    lines.append("- operation_advice: localized action advice")
                elif f == "analysis_summary":
                    lines.append("- analysis_summary: concise analysis summary")
                elif f == "dashboard.core_conclusion.one_sentence":
                    lines.append("- dashboard.core_conclusion.one_sentence: one-line decision")
                elif f == "dashboard.intelligence.risk_alerts":
                    lines.append("- dashboard.intelligence.risk_alerts: risk alert list (can be empty)")
                elif f == "dashboard.battle_plan.sniper_points.stop_loss":
                    lines.append("- dashboard.battle_plan.sniper_points.stop_loss: stop-loss level")
            return "\n".join(lines)

        lines = ["### Requisitos de Conclusão: preencha os campos obrigatórios ausentes abaixo e retorne o JSON completo novamente:"]
        for f in missing_fields:
            if f == "sentiment_score":
                lines.append("- sentiment_score: pontuação de 0-100")
            elif f == "operation_advice":
                lines.append("- operation_advice: conselho de operação localizado")
            elif f == "analysis_summary":
                lines.append("- analysis_summary: resumo conciso da análise")
            elif f == "dashboard.core_conclusion.one_sentence":
                lines.append("- dashboard.core_conclusion.one_sentence: decisão em uma frase")
            elif f == "dashboard.intelligence.risk_alerts":
                lines.append("- dashboard.intelligence.risk_alerts: lista de alertas de risco (pode ser vazia)")
            elif f == "dashboard.battle_plan.sniper_points.stop_loss":
                lines.append("- dashboard.battle_plan.sniper_points.stop_loss: nível de stop-loss")
        return "\n".join(lines)

    def _build_integrity_retry_prompt(
        self,
        base_prompt: str,
        previous_response: str,
        missing_fields: List[str],
        report_language: str = "zh",
    ) -> str:
        """Build retry prompt using the previous response as the complement baseline."""
        complement = self._build_integrity_complement_prompt(missing_fields, report_language=report_language)
        previous_output = previous_response.strip()
        if normalize_report_language(report_language) == "en":
            prefix = "### The previous output is below. Complete the missing fields based on that output and return the full JSON again. Do not omit existing fields:"
        else:
            prefix = "### A saída anterior está abaixo. Preencha os campos ausentes com base nessa saída e retorne o JSON completo novamente. Não omita os campos existentes:"
        return "\n\n".join([
            base_prompt,
            prefix,
            previous_output,
            complement,
        ])

    def _apply_placeholder_fill(self, result: AnalysisResult, missing_fields: List[str]) -> None:
        """Delegate to module-level apply_placeholder_fill."""
        apply_placeholder_fill(result, missing_fields)

    def _parse_response(
        self, 
        response_text: str, 
        code: str, 
        name: str
    ) -> AnalysisResult:
        """
        解析 Gemini 响应（决策仪表盘版）
        
        尝试从响应中提取 JSON 格式的分析结果，包含 dashboard 字段
        如果解析失败，尝试智能提取或返回默认结果
        """
        try:
            report_language = normalize_report_language(
                getattr(self._get_runtime_config(), "report_language", "zh")
            )
            # 清理响应文本：移除 markdown 代码块标记
            cleaned_text = response_text
            if '```json' in cleaned_text:
                cleaned_text = cleaned_text.replace('```json', '').replace('```', '')
            elif '```' in cleaned_text:
                cleaned_text = cleaned_text.replace('```', '')
            
            # 尝试找到 JSON 内容
            json_start = cleaned_text.find('{')
            json_end = cleaned_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = cleaned_text[json_start:json_end]
                
                # 尝试修复常见的 JSON 问题
                json_str = self._fix_json_string(json_str)
                
                data = json.loads(json_str)

                # Schema validation (lenient: on failure, continue with raw dict)
                try:
                    AnalysisReportSchema.model_validate(data)
                except Exception as e:
                    logger.warning(
                        "LLM report schema validation failed, continuing with raw dict: %s",
                        str(e)[:100],
                    )

                # 提取 dashboard 数据
                dashboard = data.get('dashboard', None)

                # 优先使用 AI 返回的股票名称（如果原名称无效或包含代码）
                ai_stock_name = data.get('stock_name')
                if ai_stock_name and (name.startswith('股票') or name == code or 'Unknown' in name):
                    name = ai_stock_name

                # 解析所有字段，使用默认值防止缺失
                # 解析 decision_type，如果没有则根据 operation_advice 推断
                decision_type = data.get('decision_type', '')
                if not decision_type:
                    op = data.get('operation_advice', 'Hold' if report_language == "en" else '持有')
                    decision_type = infer_decision_type_from_advice(op, default='hold')
                
                return AnalysisResult(
                    code=code,
                    name=name,
                    # 核心指标
                    sentiment_score=int(data.get('sentiment_score', 50)),
                    trend_prediction=data.get('trend_prediction', 'Sideways' if report_language == "en" else 'Consolidação'),
                    operation_advice=data.get('operation_advice', 'Hold' if report_language == "en" else 'Manter'),
                    decision_type=decision_type,
                    confidence_level=localize_confidence_level(
                        data.get('confidence_level', 'Medium' if report_language == "en" else 'Médio'),
                        report_language,
                    ),
                    report_language=report_language,
                    # 决策仪表盘
                    dashboard=dashboard,
                    # 走势分析
                    trend_analysis=data.get('trend_analysis', ''),
                    short_term_outlook=data.get('short_term_outlook', ''),
                    medium_term_outlook=data.get('medium_term_outlook', ''),
                    # 技术面
                    technical_analysis=data.get('technical_analysis', ''),
                    ma_analysis=data.get('ma_analysis', ''),
                    volume_analysis=data.get('volume_analysis', ''),
                    pattern_analysis=data.get('pattern_analysis', ''),
                    # 基本面
                    fundamental_analysis=data.get('fundamental_analysis', ''),
                    sector_position=data.get('sector_position', ''),
                    company_highlights=data.get('company_highlights', ''),
                    # 情绪面/消息面
                    news_summary=data.get('news_summary', ''),
                    market_sentiment=data.get('market_sentiment', ''),
                    hot_topics=data.get('hot_topics', ''),
                    # 综合
                    analysis_summary=data.get('analysis_summary', 'Analysis completed' if report_language == "en" else 'Análise concluída'),
                    key_points=data.get('key_points', ''),
                    risk_warning=data.get('risk_warning', ''),
                    buy_reason=data.get('buy_reason', ''),
                    # 元数据
                    search_performed=data.get('search_performed', False),
                    data_sources=data.get('data_sources', 'Technical data' if report_language == "en" else 'Dados técnicos'),
                    success=True,
                )
            else:
                # 没有找到 JSON，标记为失败
                logger.warning(f"Não foi possível extrair o JSON da resposta, marcado como falha")
                return self._parse_text_response(response_text, code, name)
                
        except json.JSONDecodeError as e:
            logger.warning(f"Falha ao analisar JSON: {e}, marcado como falha")
            return self._parse_text_response(response_text, code, name)
    
    def _fix_json_string(self, json_str: str) -> str:
        """修复常见的 JSON 格式问题"""
        import re
        
        # 移除注释
        json_str = re.sub(r'//.*?\n', '\n', json_str)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        
        # 修复尾随逗号
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # 确保布尔值是小写
        json_str = json_str.replace('True', 'true').replace('False', 'false')
        
        # fix by json-repair
        json_str = repair_json(json_str)
        
        return json_str

    def _validate_json_response(self, text: str) -> None:
        """Validate that *text* contains a parseable JSON object.

        Used as the ``response_validator`` argument to :meth:`_call_litellm` so
        that a JSON-less or unparseable reply from the primary model is treated
        as a model failure and triggers fallback to the next configured model.

        Raises:
            ValueError: if no JSON object is found in *text*.
            json.JSONDecodeError: if the extracted JSON cannot be parsed (after
                :meth:`_fix_json_string` attempts repair).
        """
        cleaned = text
        if "```json" in cleaned:
            cleaned = cleaned.replace("```json", "").replace("```", "")
        elif "```" in cleaned:
            cleaned = cleaned.replace("```", "")

        json_start = cleaned.find("{")
        json_end = cleaned.rfind("}") + 1

        if json_start < 0 or json_end <= json_start:
            raise ValueError("No JSON object found in LLM response")

        json_str = cleaned[json_start:json_end]
        json_str = self._fix_json_string(json_str)
        json.loads(json_str)
    
    def _parse_text_response(
        self, 
        response_text: str, 
        code: str, 
        name: str
    ) -> AnalysisResult:
        """从纯文本响应中尽可能提取分析信息"""
        report_language = normalize_report_language(
            getattr(self._get_runtime_config(), "report_language", "zh")
        )
        # 尝试识别关键词来判断情绪
        sentiment_score = 50
        trend = 'Sideways' if report_language == "en" else 'Consolidação'
        advice = 'Hold' if report_language == "en" else 'Manter'
        
        text_lower = response_text.lower()
        
        # 简单的情绪识别
        positive_keywords = ['看多', '买入', '上涨', '突破', '强势', '利好', '加仓', 'bullish', 'buy', 'alta', 'comprar', 'rompimento']
        negative_keywords = ['看空', '卖出', '下跌', '跌破', '弱势', '利空', '减仓', 'bearish', 'sell', 'baixa', 'vender']
        
        positive_count = sum(1 for kw in positive_keywords if kw in text_lower)
        negative_count = sum(1 for kw in negative_keywords if kw in text_lower)
        
        if positive_count > negative_count + 1:
            sentiment_score = 65
            trend = 'Bullish' if report_language == "en" else 'Alta'
            advice = 'Buy' if report_language == "en" else 'Comprar'
            decision_type = 'buy'
        elif negative_count > positive_count + 1:
            sentiment_score = 35
            trend = 'Bearish' if report_language == "en" else 'Baixa'
            advice = 'Sell' if report_language == "en" else 'Vender'
            decision_type = 'sell'
        else:
            decision_type = 'hold'
        
        # 截取前500字符作为摘要
        summary = response_text[:500] if response_text else ('No analysis result' if report_language == "en" else 'Sem resultado de análise')
        
        return AnalysisResult(
            code=code,
            name=name,
            sentiment_score=sentiment_score,
            trend_prediction=trend,
            operation_advice=advice,
            decision_type=decision_type,
            confidence_level='Low' if report_language == "en" else 'Baixo',
            analysis_summary=summary,
            key_points='JSON parsing failed; treat this as best-effort output.' if report_language == "en" else 'Falha na análise do JSON, apenas para referência',
            risk_warning='The result may be inaccurate. Cross-check with other information.' if report_language == "en" else 'O resultado pode ser impreciso, sugere-se verificar com outras informações',
            raw_response=response_text,
            success=False,
            error_message='LLM response is not valid JSON; analysis result will not be persisted',
            report_language=report_language,
        )
    
    def batch_analyze(
        self, 
        contexts: List[Dict[str, Any]],
        delay_between: float = 2.0
    ) -> List[AnalysisResult]:
        """
        批量分析多只股票
        
        注意：为避免 API 速率限制，每次分析之间会有延迟
        
        Args:
            contexts: 上下文数据列表
            delay_between: 每次分析之间的延迟（秒）
            
        Returns:
            AnalysisResult 列表
        """
        results = []
        
        for i, context in enumerate(contexts):
            if i > 0:
                logger.debug(f"Aguardando {delay_between} segundos antes de continuar...")
                time.sleep(delay_between)
            
            result = self.analyze(context)
            results.append(result)
        
        return results


# 便捷函数
def get_analyzer() -> GeminiAnalyzer:
    """获取 LLM 分析器实例"""
    return GeminiAnalyzer()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    # 模拟上下文数据
    test_context = {
        'code': '600519',
        'date': '2026-01-09',
        'today': {
            'open': 1800.0,
            'high': 1850.0,
            'low': 1780.0,
            'close': 1820.0,
            'volume': 10000000,
            'amount': 18200000000,
            'pct_chg': 1.5,
            'ma5': 1810.0,
            'ma10': 1800.0,
            'ma20': 1790.0,
            'volume_ratio': 1.2,
        },
        'ma_status': '多头排列 📈',
        'volume_change_ratio': 1.3,
        'price_change_ratio': 1.5,
    }
    
    analyzer = GeminiAnalyzer()
    
    if analyzer.is_available():
        print("=== AI 分析测试 ===")
        result = analyzer.analyze(test_context)
        print(f"分析结果: {result.to_dict()}")
    else:
        print("Gemini API 未配置，跳过测试")
