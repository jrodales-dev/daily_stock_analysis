# -*- coding: utf-8 -*-
"""
===================================
Sistema Inteligente de Análise de Ações - Camada de Notificação
===================================

Responsabilidades:
1. Resumir resultados da análise e gerar relatório diário
2. Suporte para saída em formato Markdown
3. Envio multicanal (reconhecimento automático):
   - WeChat Work Webhook
   - Feishu Webhook
   - Telegram Bot
   - E-mail SMTP
   - Pushover (notificações push para celular/desktop)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from enum import Enum

from src.config import Config, get_config
from src.enums import ReportType
from src.notification_routing import (
    get_notification_route_config,
    split_notification_route_channels,
)
from src.notification_noise import (
    NotificationNoiseDecision,
    evaluate_notification_noise,
    record_notification_noise,
    release_notification_noise,
)
from src.report_language import (
    get_localized_stock_name,
    get_report_labels,
    get_signal_level,
    get_chip_unavailable_reason,
    is_chip_structure_unavailable,
    localize_chip_health,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)
from bot.models import BotMessage
from src.utils.sanitize import sanitize_diagnostic_text
from src.utils.data_processing import normalize_model_used
from src.notification_sender import (
    AstrbotSender,
    CustomWebhookSender,
    DiscordSender,
    EmailSender,
    FeishuSender,
    GotifySender,
    NtfySender,
    PushoverSender,
    PushplusSender,
    Serverchan3Sender,
    SlackSender,
    TelegramSender,
    WechatSender,
    WECHAT_IMAGE_MAX_BYTES,
    resolve_gotify_message_endpoint,
    resolve_ntfy_endpoint,
)

logger = logging.getLogger(__name__)


def _safe_float(value: Any) -> Optional[float]:
    """Best-effort float conversion; handles `"3.2%"` and `"1,234"` shapes."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    text = str(value).strip().replace(",", "")
    if text.endswith("%"):
        text = text[:-1].strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None

if TYPE_CHECKING:
    from src.analyzer import AnalysisResult


class NotificationChannel(Enum):
    """Tipos de canal de notificação"""
    WECHAT = "wechat"      # WeChat Work
    FEISHU = "feishu"      # Feishu
    TELEGRAM = "telegram"  # Telegram
    EMAIL = "email"        # E-mail
    PUSHOVER = "pushover"  # Pushover (notificação celular/desktop)
    NTFY = "ntfy"          # ntfy
    GOTIFY = "gotify"      # Gotify
    PUSHPLUS = "pushplus"  # PushPlus
    SERVERCHAN3 = "serverchan3"  # ServerChan3
    CUSTOM = "custom"      # Webhook personalizado
    DISCORD = "discord"    # Bot do Discord
    SLACK = "slack"        # Slack
    ASTRBOT = "astrbot"
    UNKNOWN = "unknown"    # Desconhecido


@dataclass
class ChannelAttemptResult:
    """One static notification channel send attempt."""

    channel: str
    success: bool
    error_code: Optional[str] = None
    retryable: bool = False
    latency_ms: Optional[int] = None
    diagnostics: Optional[str] = None


@dataclass
class NotificationDispatchResult:
    """Structured result for notification dispatch diagnostics."""

    dispatched: bool
    success: bool
    status: str
    channel_results: List[ChannelAttemptResult] = field(default_factory=list)
    message: Optional[str] = None


class ChannelDetector:
    """
    Detector de canal - Versão simplificada
    
    Determina o tipo de canal diretamente com base na configuração (não é mais necessário analisar a URL)
    """
    
    @staticmethod
    def get_channel_name(channel: NotificationChannel) -> str:
        """Obter o nome do canal"""
        names = {
            NotificationChannel.WECHAT: "WeChat Work",
            NotificationChannel.FEISHU: "Feishu",
            NotificationChannel.TELEGRAM: "Telegram",
            NotificationChannel.EMAIL: "E-mail",
            NotificationChannel.PUSHOVER: "Pushover",
            NotificationChannel.NTFY: "ntfy",
            NotificationChannel.GOTIFY: "Gotify",
            NotificationChannel.PUSHPLUS: "PushPlus",
            NotificationChannel.SERVERCHAN3: "ServerChan3",
            NotificationChannel.CUSTOM: "Webhook personalizado",
            NotificationChannel.DISCORD: "Bot do Discord",
            NotificationChannel.SLACK: "Slack",
            NotificationChannel.ASTRBOT: "Bot ASTRBOT",
            NotificationChannel.UNKNOWN: "Canal desconhecido",
        }
        return names.get(channel, "Canal desconhecido")


class NotificationService(
    AstrbotSender,
    CustomWebhookSender,
    DiscordSender,
    EmailSender,
    FeishuSender,
    GotifySender,
    NtfySender,
    PushoverSender,
    PushplusSender,
    Serverchan3Sender,
    SlackSender,
    TelegramSender,
    WechatSender
):
    """
    Serviço de notificação
    
    Responsabilidades:
    1. Gerar relatório diário em formato Markdown
    2. Enviar mensagens para todos os canais configurados (simultaneamente)
    3. Suportar o salvamento de relatórios diários localmente
    
    Canais suportados:
    - WeChat Work Webhook
    - Feishu Webhook
    - Telegram Bot
    - E-mail SMTP
    - Pushover (notificações push para celular/desktop)
    
    Nota: Todos os canais configurados receberão as notificações
    """
    
    def __init__(self, source_message: Optional[BotMessage] = None):
        """
        Inicializar serviço de notificação
        
        Detecta todos os canais configurados; as notificações serão enviadas para todos eles
        """
        config = get_config()
        self._config = config
        self._source_message = source_message
        self._context_channels: List[str] = []

        # Markdown 转图片（Issue #289）
        self._markdown_to_image_channels = set(
            getattr(config, 'markdown_to_image_channels', []) or []
        )
        self._markdown_to_image_max_chars = getattr(
            config, 'markdown_to_image_max_chars', 15000
        )

        # 仅分析结果摘要（Issue #262）：true 时只推送汇总，不含个股详情
        self._report_summary_only = getattr(config, 'report_summary_only', False)
        self._report_show_llm_model = getattr(config, 'report_show_llm_model', True)
        self._history_compare_cache: Dict[Tuple[int, Tuple[Tuple[str, str], ...]], Dict[str, List[Dict[str, Any]]]] = {}

        # 初始化各渠道
        AstrbotSender.__init__(self, config)
        CustomWebhookSender.__init__(self, config)
        DiscordSender.__init__(self, config)
        EmailSender.__init__(self, config)
        FeishuSender.__init__(self, config)
        GotifySender.__init__(self, config)
        NtfySender.__init__(self, config)
        PushoverSender.__init__(self, config)
        PushplusSender.__init__(self, config)
        Serverchan3Sender.__init__(self, config)
        SlackSender.__init__(self, config)
        TelegramSender.__init__(self, config)
        WechatSender.__init__(self, config)

        # 检测所有已配置的渠道
        self._available_channels = self._detect_all_channels()
        if self._extract_dingtalk_session_webhook() is not None:
            self._context_channels.append("钉钉会话")
        if self._extract_feishu_reply_info() is not None:
            self._context_channels.append("飞书会话")

        if not self._available_channels and not self._context_channels:
            logger.warning("Nenhum canal de notificação configurado, notificações push não serão enviadas")
        else:
            channel_names = [ChannelDetector.get_channel_name(ch) for ch in self._available_channels]
            channel_names.extend(self._context_channels)
            logger.info(f"Configurado {len(channel_names)} canais de notificação: {', '.join(channel_names)}")

    def _normalize_report_type(self, report_type: Any) -> ReportType:
        """Normalize string/enum input into ReportType."""
        if isinstance(report_type, ReportType):
            return report_type
        return ReportType.from_str(report_type)

    def _get_report_language(self, payload: Optional[Any] = None) -> str:
        """Resolve report language from result payload or global config."""
        if isinstance(payload, list):
            for item in payload:
                language = getattr(item, "report_language", None)
                if language:
                    return normalize_report_language(language)
        elif payload is not None:
            language = getattr(payload, "report_language", None)
            if language:
                return normalize_report_language(language)

        return normalize_report_language(getattr(get_config(), "report_language", "zh"))

    def _get_labels(self, payload: Optional[Any] = None) -> Dict[str, str]:
        return get_report_labels(self._get_report_language(payload))

    def _get_display_name(self, result: AnalysisResult, language: Optional[str] = None) -> str:
        report_language = normalize_report_language(language or self._get_report_language(result))
        return self._escape_md(
            get_localized_stock_name(result.name, result.code, report_language)
        )

    def _get_history_compare_context(self, results: List[AnalysisResult]) -> Dict[str, Any]:
        """Fetch and cache history comparison data for markdown rendering."""
        config = get_config()
        history_compare_n = getattr(config, 'report_history_compare_n', 0)
        if history_compare_n <= 0 or not results:
            return {"history_by_code": {}}

        cache_key = (
            history_compare_n,
            tuple(sorted((r.code, getattr(r, 'query_id', '') or '') for r in results)),
        )
        if cache_key in self._history_compare_cache:
            return {"history_by_code": self._history_compare_cache[cache_key]}

        try:
            from src.services.history_comparison_service import get_signal_changes_batch

            exclude_ids = {
                r.code: r.query_id
                for r in results
                if getattr(r, 'query_id', None)
            }
            codes = list(dict.fromkeys(r.code for r in results))
            history_by_code = get_signal_changes_batch(
                codes,
                limit=history_compare_n,
                exclude_query_ids=exclude_ids,
            )
        except Exception as e:
            logger.debug("History comparison skipped: %s", e)
            history_by_code = {}

        self._history_compare_cache[cache_key] = history_by_code
        return {"history_by_code": history_by_code}

    def generate_aggregate_report(
        self,
        results: List[AnalysisResult],
        report_type: Any,
        report_date: Optional[str] = None,
    ) -> str:
        """Generate the aggregate report content used by merge/save/push paths."""
        normalized_type = self._normalize_report_type(report_type)
        if normalized_type == ReportType.BRIEF:
            return self.generate_brief_report(results, report_date=report_date)
        return self.generate_dashboard_report(results, report_date=report_date)

    def _collect_models_used(self, results: List[AnalysisResult]) -> List[str]:
        if not self._should_show_llm_model():
            return []
        models: List[str] = []
        for result in results:
            model = normalize_model_used(getattr(result, "model_used", None))
            if model:
                models.append(model)
        return list(dict.fromkeys(models))

    def _should_show_llm_model(self) -> bool:
        return bool(getattr(self._config, "report_show_llm_model", self._report_show_llm_model))
    
    @staticmethod
    def detect_configured_channels(config: Config) -> List[NotificationChannel]:
        """
        Detect statically configured notification channels from Config.

        This intentionally mirrors sender availability without instantiating
        sender objects, so diagnostics and runtime use the same channel truth.
        Runtime-only context channels are handled by instance methods.
        """
        channels = []

        if getattr(config, "wechat_webhook_url", None):
            channels.append(NotificationChannel.WECHAT)

        if getattr(config, "feishu_webhook_url", None):
            channels.append(NotificationChannel.FEISHU)

        if (
            getattr(config, "telegram_bot_token", None)
            and getattr(config, "telegram_chat_id", None)
        ):
            channels.append(NotificationChannel.TELEGRAM)

        if getattr(config, "email_sender", None) and getattr(config, "email_password", None):
            channels.append(NotificationChannel.EMAIL)

        if (
            getattr(config, "pushover_user_key", None)
            and getattr(config, "pushover_api_token", None)
        ):
            channels.append(NotificationChannel.PUSHOVER)

        ntfy_server_url, ntfy_topic = resolve_ntfy_endpoint(getattr(config, "ntfy_url", None))
        if ntfy_server_url and ntfy_topic:
            channels.append(NotificationChannel.NTFY)

        gotify_endpoint = resolve_gotify_message_endpoint(getattr(config, "gotify_url", None))
        if gotify_endpoint and (getattr(config, "gotify_token", None) or "").strip():
            channels.append(NotificationChannel.GOTIFY)

        if getattr(config, "pushplus_token", None):
            channels.append(NotificationChannel.PUSHPLUS)

        if getattr(config, "serverchan3_sendkey", None):
            channels.append(NotificationChannel.SERVERCHAN3)

        if getattr(config, "custom_webhook_urls", None):
            channels.append(NotificationChannel.CUSTOM)

        if (
            getattr(config, "discord_webhook_url", None)
            or (
                getattr(config, "discord_bot_token", None)
                and getattr(config, "discord_main_channel_id", None)
            )
        ):
            channels.append(NotificationChannel.DISCORD)

        if (
            getattr(config, "slack_webhook_url", None)
            or (
                getattr(config, "slack_bot_token", None)
                and getattr(config, "slack_channel_id", None)
            )
        ):
            channels.append(NotificationChannel.SLACK)

        if getattr(config, "astrbot_url", None):
            channels.append(NotificationChannel.ASTRBOT)

        return channels

    def _detect_all_channels(self) -> List[NotificationChannel]:
        """
        Detectar todos os canais configurados

        Returns:
            Lista de canais configurados
        """
        return self.detect_configured_channels(self._config)

    def is_available(self) -> bool:
        """Verificar se o serviço de notificação está disponível (pelo menos um canal ou contexto)"""
        return len(self._available_channels) > 0 or self._has_context_channel()
    
    def get_available_channels(self) -> List[NotificationChannel]:
        """Obter todos os canais configurados"""
        return self._available_channels

    def get_channels_for_route(
        self,
        route_type: Optional[str],
        channels: Optional[List[NotificationChannel]] = None,
    ) -> List[NotificationChannel]:
        """Return channels allowed for a route type.

        ``route_type=None`` keeps the legacy behavior and returns all supplied
        static channels. Empty route config also keeps all supplied channels.
        Non-empty route config that matches no enabled channel returns an empty
        list.
        """
        target_channels = list(channels if channels is not None else self._available_channels)
        if route_type is None:
            return target_channels

        route_config = get_notification_route_config(route_type)
        if route_config is None:
            logger.warning("Tipo de rota de notificação desconhecido %s, usando todos os canais", route_type)
            return target_channels

        configured_route_channels = getattr(self._config, route_config["config_attr"], []) or []
        if not configured_route_channels:
            return target_channels

        valid_channels, invalid_channels = split_notification_route_channels(configured_route_channels)
        if invalid_channels:
            logger.warning(
                "%s contém canais desconhecidos, serão ignorados: %s",
                route_config["env_key"],
                ", ".join(invalid_channels),
            )

        allowed = set(valid_channels)
        return [channel for channel in target_channels if channel.value in allowed]
    
    def get_channel_names(self) -> str:
        """Obter nomes de todos os canais configurados"""
        names = [ChannelDetector.get_channel_name(ch) for ch in self._available_channels]
        if self._has_context_channel():
            names.append("Sessão DingTalk")
        return ', '.join(names)

    def evaluate_noise_control(
        self,
        content: str,
        *,
        route_type: Optional[str] = None,
        severity: Optional[str] = None,
        dedup_key: Optional[str] = None,
        cooldown_key: Optional[str] = None,
    ) -> NotificationNoiseDecision:
        """Evaluate static-channel notification noise controls."""
        return evaluate_notification_noise(
            self._config,
            content=content,
            route_type=route_type,
            severity=severity,
            dedup_key=dedup_key,
            cooldown_key=cooldown_key,
        )

    @staticmethod
    def record_noise_control(decision: NotificationNoiseDecision) -> None:
        """Record static-channel notification noise state after a successful send."""
        record_notification_noise(decision)

    @staticmethod
    def release_noise_control(decision: NotificationNoiseDecision) -> None:
        """Release static-channel in-flight noise reservation after send failure."""
        release_notification_noise(decision)

    # ===== Context channel =====
    def _has_context_channel(self) -> bool:
        """Verificar se há um canal temporário baseado no contexto da mensagem (ex: sessão DingTalk, Feishu)"""
        return (
            self._extract_dingtalk_session_webhook() is not None
            or self._extract_feishu_reply_info() is not None
            or self._extract_telegram_context_chat_id() is not None
        )

    def _source_platform(self) -> str:
        """Return normalized platform from the source bot message."""
        platform = getattr(self._source_message, "platform", "")
        if hasattr(platform, "value"):
            platform = platform.value
        return str(platform or "").lower()

    def _extract_telegram_context_chat_id(self) -> Optional[str]:
        """Extrair chat_id do contexto do Telegram da mensagem de origem (para resposta assíncrona)."""
        if not isinstance(self._source_message, BotMessage):
            return None
        if self._source_platform() != "telegram":
            return None
        raw_data = getattr(self._source_message, "raw_data", {}) or {}
        for candidate in (
            getattr(self._source_message, "chat_id", ""),
            raw_data.get("chat_id"),
            raw_data.get("message", {}).get("chat", {}).get("id") if isinstance(raw_data.get("message"), dict) else None,
        ):
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
            if candidate is not None and not isinstance(candidate, str):
                candidate_text = str(candidate).strip()
                if candidate_text:
                    return candidate_text
        return None

    def should_broadcast_static_channels(self) -> bool:
        """Whether static notification channels should receive this dispatch."""
        return not self._has_context_channel()

    def _extract_dingtalk_session_webhook(self) -> Optional[str]:
        """Extrair Webhook de sessão DingTalk da mensagem de origem (para resposta em modo Stream)"""
        if not isinstance(self._source_message, BotMessage):
            return None
        raw_data = getattr(self._source_message, "raw_data", {}) or {}
        if not isinstance(raw_data, dict):
            return None
        session_webhook = (
            raw_data.get("_session_webhook")
            or raw_data.get("sessionWebhook")
            or raw_data.get("session_webhook")
            or raw_data.get("session_webhook_url")
        )
        if not session_webhook and isinstance(raw_data.get("headers"), dict):
            session_webhook = raw_data["headers"].get("sessionWebhook")
        return session_webhook

    def _extract_feishu_reply_info(self) -> Optional[Dict[str, str]]:
        """
        Extrair informações de resposta do Feishu da mensagem de origem (para resposta em modo Stream)
        
        Returns:
            Dicionário contendo chat_id, ou None
        """
        if not isinstance(self._source_message, BotMessage):
            return None
        if getattr(self._source_message, "platform", "") != "feishu":
            return None
        chat_id = getattr(self._source_message, "chat_id", "")
        if not chat_id:
            return None
        return {"chat_id": chat_id}

    def send_to_context(self, content: str) -> bool:
        """
        Enviar mensagem para canal baseado em contexto (ex: sessão DingTalk Stream)
        
        Args:
            content: Conteúdo formatado em Markdown
        """
        return self._send_via_source_context(content)
    
    def _send_via_source_context(self, content: str) -> bool:
        """
        Enviar relatório via contexto da mensagem (DingTalk/Feishu)
        
        Usado principalmente para tarefas iniciadas a partir do bot em modo Stream.
        """
        success = False
        
        # Tentar DingTalk
        session_webhook = self._extract_dingtalk_session_webhook()
        if session_webhook:
            try:
                if self._send_dingtalk_chunked(session_webhook, content, max_bytes=20000):
                    logger.info("Relatório enviado via sessão DingTalk (Stream)")
                    success = True
                else:
                    logger.error("Falha ao enviar via sessão DingTalk (Stream)")
            except Exception as e:
                logger.error(f"Erro ao enviar via sessão DingTalk (Stream): {e}")

        # Tentar Feishu
        feishu_info = self._extract_feishu_reply_info()
        if feishu_info:
            try:
                if self._send_feishu_stream_reply(feishu_info["chat_id"], content):
                    logger.info("Relatório enviado via sessão Feishu (Stream)")
                    success = True
                else:
                    logger.error("Falha ao enviar via sessão Feishu (Stream)")
            except Exception as e:
                logger.error(f"Erro ao enviar via sessão Feishu (Stream): {e}")

        # Tentar Telegram
        telegram_chat_id = self._extract_telegram_context_chat_id()
        if telegram_chat_id:
            try:
                if self.send_to_telegram(content, chat_id=telegram_chat_id):
                    logger.info("Relatório enviado via sessão Telegram")
                    success = True
                else:
                    logger.error("Falha ao enviar via sessão Telegram")
            except Exception as e:
                logger.error(f"Erro ao enviar via sessão Telegram: {e}")

        return success

    def _send_feishu_stream_reply(self, chat_id: str, content: str) -> bool:
        """
        Enviar mensagem para sessão específica via modo Stream do Feishu
        
        Args:
            chat_id: ID da sessão Feishu
            content: Conteúdo da mensagem
            
        Returns:
            Verdadeiro se enviado com sucesso
        """
        try:
            from bot.platforms.feishu_stream import FeishuReplyClient, FEISHU_SDK_AVAILABLE
            if not FEISHU_SDK_AVAILABLE:
                logger.warning("SDK do Feishu não disponível, não é possível enviar resposta Stream")
                return False
            
            from src.config import get_config
            config = get_config()
            
            app_id = getattr(config, 'feishu_app_id', None)
            app_secret = getattr(config, 'feishu_app_secret', None)
            
            if not app_id or not app_secret:
                logger.warning("APP_ID ou APP_SECRET do Feishu não configurados")
                return False
            
            # Criar cliente de resposta
            reply_client = FeishuReplyClient(app_id, app_secret)
            
            # Mensagens de texto do Feishu têm limite de comprimento, precisam ser enviadas em lotes
            max_bytes = getattr(config, 'feishu_max_bytes', 20000)
            content_bytes = len(content.encode('utf-8'))
            
            if content_bytes > max_bytes:
                return self._send_feishu_stream_chunked(reply_client, chat_id, content, max_bytes)
            
            return reply_client.send_to_chat(chat_id, content)
            
        except ImportError as e:
            logger.error(f"Falha ao importar módulo Stream do Feishu: {e}")
            return False
        except Exception as e:
            logger.error(f"Exceção na resposta Stream do Feishu: {e}")
            return False

    def _send_feishu_stream_chunked(
        self, 
        reply_client, 
        chat_id: str, 
        content: str, 
        max_bytes: int
    ) -> bool:
        """
        Enviar mensagens longas em lotes para Feishu (modo Stream)
        
        Args:
            reply_client: Instância do FeishuReplyClient
            chat_id: ID da sessão Feishu
            content: Conteúdo completo da mensagem
            max_bytes: Máximo de bytes por mensagem
            
        Returns:
            Verdadeiro se tudo foi enviado com sucesso
        """
        import time
        
        def get_bytes(s: str) -> int:
            return len(s.encode('utf-8'))
        
        # Dividir por parágrafos ou linhas separadoras
        if "\n---\n" in content:
            sections = content.split("\n---\n")
            separator = "\n---\n"
        elif "\n### " in content:
            parts = content.split("\n### ")
            sections = [parts[0]] + [f"### {p}" for p in parts[1:]]
            separator = "\n"
        else:
            # Dividir por linhas
            sections = content.split("\n")
            separator = "\n"
        
        chunks = []
        current_chunk = []
        current_bytes = 0
        separator_bytes = get_bytes(separator)
        
        for section in sections:
            section_bytes = get_bytes(section) + separator_bytes
            
            if current_bytes + section_bytes > max_bytes:
                if current_chunk:
                    chunks.append(separator.join(current_chunk))
                current_chunk = [section]
                current_bytes = section_bytes
            else:
                current_chunk.append(section)
                current_bytes += section_bytes
        
        if current_chunk:
            chunks.append(separator.join(current_chunk))
        
        # Enviar cada bloco
        success = True
        for i, chunk in enumerate(chunks):
            if i > 0:
                time.sleep(0.5)  # Evitar requisições muito rápidas
            
            if not reply_client.send_to_chat(chat_id, chunk):
                success = False
                logger.error(f"Falha ao enviar bloco {i+1}/{len(chunks)} Stream do Feishu")
        
        return success
        
    def generate_daily_report(
        self,
        results: List[AnalysisResult],
        report_date: Optional[str] = None
    ) -> str:
        """
        Gerar relatório diário em formato Markdown (Versão detalhada)

        Args:
            results: Lista de resultados da análise
            report_date: Data do relatório (padrão é hoje)

        Returns:
            Conteúdo do relatório em Markdown
        """
        if report_date is None:
            report_date = datetime.now().strftime('%Y-%m-%d')
        report_language = self._get_report_language(results)
        labels = get_report_labels(report_language)

        # Título
        report_lines = [
            f"# 📅 {report_date} {labels['report_title']}",
            "",
            f"> {labels['analyzed_prefix']} **{len(results)}** {labels['stock_unit']} | "
            f"{labels['generated_at_label']}：{datetime.now().strftime('%H:%M:%S')}",
            "",
            "---",
            "",
        ]
        
        # Ordenar por pontuação (maior primeiro)
        sorted_results = sorted(
            results, 
            key=lambda x: x.sentiment_score, 
            reverse=True
        )
        
        # Estatísticas - usar campo decision_type para estatísticas precisas
        buy_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'buy')
        sell_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'sell')
        hold_count = sum(1 for r in results if getattr(r, 'decision_type', '') in ('hold', ''))
        avg_score = sum(r.sentiment_score for r in results) / len(results) if results else 0
        
        report_lines.extend([
            f"## 📊 {labels['summary_heading']}",
            "",
            "| Métrica | Valor |",
            "|------|------|",
            f"| 🟢 {labels['buy_label']} | **{buy_count}** {labels['stock_unit_compact']} |",
            f"| 🟡 {labels['watch_label']} | **{hold_count}** {labels['stock_unit_compact']} |",
            f"| 🔴 {labels['sell_label']} | **{sell_count}** {labels['stock_unit_compact']} |",
            f"| 📈 {labels['avg_score_label']} | **{avg_score:.1f}** |",
            "",
            "---",
            "",
        ])
        
        # Issue #262: se summary_only for verdadeiro, produzir apenas resumo e pular detalhes de ações
        if self._report_summary_only:
            report_lines.extend([f"## 📊 {labels['summary_heading']}", ""])
            for r in sorted_results:
                _, emoji, _ = self._get_signal_level(r)
                report_lines.append(
                    f"{emoji} **{self._get_display_name(r, report_language)}({r.code})**: "
                    f"{localize_operation_advice(r.operation_advice, report_language)} | "
                    f"{labels['score_label']} {r.sentiment_score} | "
                    f"{localize_trend_prediction(r.trend_prediction, report_language)}"
                )
        else:
            report_lines.extend([f"## 📈 {labels['report_title']}", ""])
            # Análise detalhada por ação
            for result in sorted_results:
                _, emoji, _ = self._get_signal_level(result)
                confidence_stars = result.get_confidence_stars() if hasattr(result, 'get_confidence_stars') else '⭐⭐'
                
                report_lines.extend([
                    f"### {emoji} {self._get_display_name(result, report_language)} ({result.code})",
                    "",
                    f"**{labels['action_advice_label']}：{localize_operation_advice(result.operation_advice, report_language)}** | "
                    f"**{labels['score_label']}：{result.sentiment_score}** | "
                    f"**{labels['trend_label']}：{localize_trend_prediction(result.trend_prediction, report_language)}** | "
                    f"**Confidence：{confidence_stars}**",
                    "",
                ])

                self._append_market_snapshot(report_lines, result)
                
                # Pontos chave
                if hasattr(result, 'key_points') and result.key_points:
                    report_lines.extend([
                        f"**🎯 Pontos Chave**：{result.key_points}",
                        "",
                    ])
                
                # Motivos de compra/venda
                if hasattr(result, 'buy_reason') and result.buy_reason:
                    report_lines.extend([
                        f"**💡 Motivo Operação**：{result.buy_reason}",
                        "",
                    ])
                
                # Análise de tendência
                if hasattr(result, 'trend_analysis') and result.trend_analysis:
                    report_lines.extend([
                        "#### 📉 Análise de Tendência",
                        f"{result.trend_analysis}",
                        "",
                    ])
                
                # Perspectiva de Curto/Médio Prazo
                outlook_lines = []
                if hasattr(result, 'short_term_outlook') and result.short_term_outlook:
                    outlook_lines.append(f"- **Curto Prazo (1-3 dias)**：{result.short_term_outlook}")
                if hasattr(result, 'medium_term_outlook') and result.medium_term_outlook:
                    outlook_lines.append(f"- **Médio Prazo (1-2 semanas)**：{result.medium_term_outlook}")
                if outlook_lines:
                    report_lines.extend([
                        "#### 🔮 Perspectiva de Mercado",
                        *outlook_lines,
                        "",
                    ])
                
                # Análise técnica
                tech_lines = []
                if result.technical_analysis:
                    tech_lines.append(f"**Geral**：{result.technical_analysis}")
                if hasattr(result, 'ma_analysis') and result.ma_analysis:
                    tech_lines.append(f"**Médias Móveis**：{result.ma_analysis}")
                if hasattr(result, 'volume_analysis') and result.volume_analysis:
                    tech_lines.append(f"**Volume**：{result.volume_analysis}")
                if hasattr(result, 'pattern_analysis') and result.pattern_analysis:
                    tech_lines.append(f"**Padrão**：{result.pattern_analysis}")
                if tech_lines:
                    report_lines.extend([
                        "#### 📊 Análise Técnica",
                        *tech_lines,
                        "",
                    ])
                
                # Análise Fundamentalista
                fund_lines = []
                if hasattr(result, 'fundamental_analysis') and result.fundamental_analysis:
                    fund_lines.append(result.fundamental_analysis)
                if hasattr(result, 'sector_position') and result.sector_position:
                    fund_lines.append(f"**Posição no Setor**：{result.sector_position}")
                if hasattr(result, 'company_highlights') and result.company_highlights:
                    fund_lines.append(f"**Destaques da Empresa**：{result.company_highlights}")
                if fund_lines:
                    report_lines.extend([
                        "#### 🏢 Análise Fundamentalista",
                        *fund_lines,
                        "",
                    ])
                
                # Notícias / Sentimento
                news_lines = []
                if result.news_summary:
                    news_lines.append(f"**Resumo de Notícias**：{result.news_summary}")
                if hasattr(result, 'market_sentiment') and result.market_sentiment:
                    news_lines.append(f"**Sentimento do Mercado**：{result.market_sentiment}")
                if hasattr(result, 'hot_topics') and result.hot_topics:
                    news_lines.append(f"**Tópicos Quentes**：{result.hot_topics}")
                if news_lines:
                    report_lines.extend([
                        "#### 📰 Notícias / Sentimento",
                        *news_lines,
                        "",
                    ])
                
                # Análise Abrangente
                if result.analysis_summary:
                    report_lines.extend([
                        "#### 📝 Análise Abrangente",
                        result.analysis_summary,
                        "",
                    ])
                
                # Aviso de Risco
                if hasattr(result, 'risk_warning') and result.risk_warning:
                    report_lines.extend([
                        f"⚠️ **Aviso de Risco**：{result.risk_warning}",
                        "",
                    ])
                
                # Explicação da fonte de dados
                if hasattr(result, 'search_performed') and result.search_performed:
                    report_lines.append("*🔍 Busca online realizada*")
                if hasattr(result, 'data_sources') and result.data_sources:
                    report_lines.append(f"*📋 Fonte de dados：{result.data_sources}*")
                
                # Informação de erro (se houver)
                if not result.success and result.error_message:
                    report_lines.extend([
                        "",
                        f"❌ **Exceção de análise**：{result.error_message[:100]}",
                    ])
                
                report_lines.extend([
                    "",
                    "---",
                    "",
                ])
        
        # Informação de rodapé (remoção do aviso de responsabilidade)
        report_lines.extend([
            "",
            f"*{labels['generated_at_label']}：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ])
        
        return "\n".join(report_lines)
    
    @staticmethod
    def _escape_md(name: str) -> str:
        """Escape markdown special characters in stock names (e.g. *ST → \\*ST)."""
        return name.replace('*', r'\*') if name else name

    @staticmethod
    def _clean_sniper_value(value: Any) -> str:
        """Normalize sniper point values and remove redundant label prefixes."""
        if value is None:
            return 'N/A'
        if isinstance(value, (int, float)):
            return str(value)
        if not isinstance(value, str):
            return str(value)
        if not value or value == 'N/A':
            return value
        prefixes = ['理想买入点：', '次优买入点：', '止损位：', '目标位：',
                     '理想买入点:', '次优买入点:', '止损位:', '目标位:',
                     'Ideal Entry:', 'Secondary Entry:', 'Stop Loss:', 'Target:']
        for prefix in prefixes:
            if value.startswith(prefix):
                return value[len(prefix):]
        return value

    def _get_signal_level(self, result: AnalysisResult) -> tuple:
        """Get localized signal level and color based on operation advice."""
        return get_signal_level(
            result.operation_advice,
            result.sentiment_score,
            self._get_report_language(result),
        )
    
    def generate_dashboard_report(
        self,
        results: List[AnalysisResult],
        report_date: Optional[str] = None
    ) -> str:
        """
        Gerar relatório diário no formato Dashboard de Decisão (Versão detalhada)

        Formato: Visão geral do mercado + Informações importantes + Conclusão principal + Dados essenciais + Plano de ação

        Args:
            results: Lista de resultados da análise
            report_date: Data do relatório (padrão é hoje)

        Returns:
            Relatório diário em Markdown
        """
        config = get_config()
        report_language = self._get_report_language(results)
        labels = get_report_labels(report_language)
        reason_label = "Rationale" if report_language == "en" else "Motivo Operação"
        risk_warning_label = "Risk Warning" if report_language == "en" else "Aviso de Risco"
        technical_heading = "Technicals" if report_language == "en" else "Análise Técnica"
        ma_label = "Moving Averages" if report_language == "en" else "Médias Móveis"
        volume_analysis_label = "Volume" if report_language == "en" else "Volume"
        news_heading = "News Flow" if report_language == "en" else "Notícias"
        if getattr(config, 'report_renderer_enabled', False) and results:
            from src.services.report_renderer import render
            out = render(
                platform='markdown',
                results=results,
                report_date=report_date,
                summary_only=self._report_summary_only,
                extra_context={
                    **self._get_history_compare_context(results),
                    "report_language": report_language,
                },
            )
            if out:
                return out

        if report_date is None:
            report_date = datetime.now().strftime('%Y-%m-%d')

        # Ordenar por pontuação (maior primeiro)
        sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)

        # Estatísticas - usar campo decision_type para estatísticas precisas
        buy_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'buy')
        sell_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'sell')
        hold_count = sum(1 for r in results if getattr(r, 'decision_type', '') in ('hold', ''))

        report_lines = [
            f"# 🎯 {report_date} {labels['dashboard_title']}",
            "",
            f"> {labels['analyzed_prefix']} **{len(results)}** {labels['stock_unit']} | "
            f"🟢{labels['buy_label']}:{buy_count} 🟡{labels['watch_label']}:{hold_count} 🔴{labels['sell_label']}:{sell_count}",
            "",
        ]

        # === Adicionado: Resumo dos resultados da análise (Issue #112) ===
        if results:
            report_lines.extend([
                f"## 📊 {labels['summary_heading']}",
                "",
            ])
            for r in sorted_results:
                _, signal_emoji, _ = self._get_signal_level(r)
                display_name = self._get_display_name(r, report_language)
                report_lines.append(
                    f"{signal_emoji} **{display_name}({r.code})**: "
                    f"{localize_operation_advice(r.operation_advice, report_language)} | "
                    f"{labels['score_label']} {r.sentiment_score} | "
                    f"{localize_trend_prediction(r.trend_prediction, report_language)}"
                )
            report_lines.extend([
                "",
                "---",
                "",
            ])

        # Painel de decisão para cada ação (Issue #262: pular detalhes se summary_only for verdadeiro)
        if not self._report_summary_only:
            for result in sorted_results:
                signal_text, signal_emoji, signal_tag = self._get_signal_level(result)
                dashboard = result.dashboard if hasattr(result, 'dashboard') and result.dashboard else {}
                
                # Nome da ação (priorizar nome do dashboard ou result, escapar caracteres especiais como *ST)
                stock_name = self._get_display_name(result, report_language)
                
                report_lines.extend([
                    f"## {signal_emoji} {stock_name} ({result.code})",
                    "",
                ])
                
                # ========== Visão Geral do Sentimento e Fundamentos (No início) ==========
                intel = dashboard.get('intelligence', {}) if dashboard else {}
                if intel:
                    report_lines.extend([
                        f"### 📰 {labels['info_heading']}",
                        "",
                    ])
                    # Resumo do Sentimento Público
                    if intel.get('sentiment_summary'):
                        report_lines.append(f"**💭 {labels['sentiment_summary_label']}**: {intel['sentiment_summary']}")
                    # Perspectiva de Lucros
                    if intel.get('earnings_outlook'):
                        report_lines.append(f"**📊 {labels['earnings_outlook_label']}**: {intel['earnings_outlook']}")
                    # Alertas de Risco (destacados)
                    risk_alerts = intel.get('risk_alerts', [])
                    if risk_alerts:
                        report_lines.append("")
                        report_lines.append(f"**🚨 {labels['risk_alerts_label']}**:")
                        for alert in risk_alerts:
                            report_lines.append(f"- {alert}")
                    # Catalisadores Positivos
                    catalysts = intel.get('positive_catalysts', [])
                    if catalysts:
                        report_lines.append("")
                        report_lines.append(f"**✨ {labels['positive_catalysts_label']}**:")
                        for cat in catalysts:
                            report_lines.append(f"- {cat}")
                    # Últimas Notícias
                    if intel.get('latest_news'):
                        report_lines.append("")
                        report_lines.append(f"**📢 {labels['latest_news_label']}**: {intel['latest_news']}")
                    report_lines.append("")
                
                # ========== Conclusão Principal ==========
                core = dashboard.get('core_conclusion', {}) if dashboard else {}
                one_sentence = core.get('one_sentence', result.analysis_summary)
                time_sense = core.get('time_sensitivity', labels['default_time_sensitivity'])
                pos_advice = core.get('position_advice', {})
                
                report_lines.extend([
                    f"### 📌 {labels['core_conclusion_heading']}",
                    "",
                    f"**{signal_emoji} {signal_text}** | {localize_trend_prediction(result.trend_prediction, report_language)}",
                    "",
                    f"> **{labels['one_sentence_label']}**: {one_sentence}",
                    "",
                    f"⏰ **{labels['time_sensitivity_label']}**: {time_sense}",
                    "",
                ])
                # Sugestões de alocação de portfólio
                if pos_advice:
                    report_lines.extend([
                        f"| {labels['position_status_label']} | {labels['action_advice_label']} |",
                        "|---------|---------|",
                        f"| 🆕 **{labels['no_position_label']}** | {pos_advice.get('no_position', localize_operation_advice(result.operation_advice, report_language))} |",
                        f"| 💼 **{labels['has_position_label']}** | {pos_advice.get('has_position', labels['continue_holding'])} |",
                        "",
                    ])

                self._append_market_snapshot(report_lines, result)
                
                # ========== Dados Essenciais ==========
                data_persp = dashboard.get('data_perspective', {}) if dashboard else {}
                if data_persp:
                    trend_data = data_persp.get('trend_status', {})
                    price_data = data_persp.get('price_position', {})
                    vol_data = data_persp.get('volume_analysis', {})
                    chip_data = data_persp.get('chip_structure', {})
                    
                    report_lines.extend([
                        f"### 📊 {labels['data_perspective_heading']}",
                        "",
                    ])
                    # Status de Tendência
                    if trend_data:
                        is_bullish = (
                            f"✅ {labels['yes_label']}"
                            if trend_data.get('is_bullish', False)
                            else f"❌ {labels['no_label']}"
                        )
                        report_lines.extend([
                            f"**{labels['ma_alignment_label']}**: {trend_data.get('ma_alignment', 'N/A')} | "
                            f"{labels['bullish_alignment_label']}: {is_bullish} | "
                            f"{labels['trend_strength_label']}: {trend_data.get('trend_score', 'N/A')}/100",
                            "",
                        ])
                    # Posição de Preço
                    if price_data:
                        bias_status = price_data.get('bias_status', 'N/A')
                        report_lines.extend([
                            f"| {labels['price_metrics_label']} | {labels['current_price_label']} |",
                            "|---------|------|",
                            f"| {labels['current_price_label']} | {price_data.get('current_price', 'N/A')} |",
                            f"| {labels['ma5_label']} | {price_data.get('ma5', 'N/A')} |",
                            f"| {labels['ma10_label']} | {price_data.get('ma10', 'N/A')} |",
                            f"| {labels['ma20_label']} | {price_data.get('ma20', 'N/A')} |",
                            f"| {labels['bias_ma5_label']} | {price_data.get('bias_ma5', 'N/A')}% {bias_status} |",
                            f"| {labels['support_level_label']} | {price_data.get('support_level', 'N/A')} |",
                            f"| {labels['resistance_level_label']} | {price_data.get('resistance_level', 'N/A')} |",
                            "",
                        ])
                    # Análise de Volume
                    if vol_data:
                        report_lines.extend([
                            f"**{labels['volume_label']}**: {labels['volume_ratio_label']} {vol_data.get('volume_ratio', 'N/A')} ({vol_data.get('volume_status', '')}) | "
                            f"{labels['turnover_rate_label']} {vol_data.get('turnover_rate', 'N/A')}%",
                            f"💡 *{vol_data.get('volume_meaning', '')}*",
                            "",
                        ])
                    # Estrutura de Fichas
                    if chip_data:
                        if is_chip_structure_unavailable(chip_data):
                            report_lines.extend([
                                f"**{labels['chip_label']}**: {get_chip_unavailable_reason(chip_data, report_language)}",
                                "",
                            ])
                        else:
                            chip_health = localize_chip_health(chip_data.get('chip_health', 'N/A'), report_language)
                            report_lines.extend([
                                f"**{labels['chip_label']}**: {chip_data.get('profit_ratio', 'N/A')} | {chip_data.get('avg_cost', 'N/A')} | "
                                f"{chip_data.get('concentration', 'N/A')} {chip_health}",
                                "",
                            ])
                    else:
                        chip_unavailable_reason = get_chip_unavailable_reason(data_persp, report_language)
                        if chip_unavailable_reason:
                            report_lines.extend([
                                f"**{labels['chip_label']}**: {chip_unavailable_reason}",
                                "",
                            ])
                
                # ========== Plano de Ação ==========
                battle = dashboard.get('battle_plan', {}) if dashboard else {}
                if battle:
                    report_lines.extend([
                        f"### 🎯 {labels['battle_plan_heading']}",
                        "",
                    ])
                    # Pontos de Sniper
                    sniper = battle.get('sniper_points', {})
                    if sniper:
                        report_lines.extend([
                            f"**📍 {labels['action_points_heading']}**",
                            "",
                            f"| {labels['action_points_heading']} | {labels['current_price_label']} |",
                            "|---------|------|",
                            f"| 🎯 {labels['ideal_buy_label']} | {self._clean_sniper_value(sniper.get('ideal_buy', 'N/A'))} |",
                            f"| 🔵 {labels['secondary_buy_label']} | {self._clean_sniper_value(sniper.get('secondary_buy', 'N/A'))} |",
                            f"| 🛑 {labels['stop_loss_label']} | {self._clean_sniper_value(sniper.get('stop_loss', 'N/A'))} |",
                            f"| 🎊 {labels['take_profit_label']} | {self._clean_sniper_value(sniper.get('take_profit', 'N/A'))} |",
                            "",
                        ])
                    # Estratégia de Posição
                    position = battle.get('position_strategy', {})
                    if position:
                        report_lines.extend([
                            f"**💰 {labels['suggested_position_label']}**: {position.get('suggested_position', 'N/A')}",
                            f"- {labels['entry_plan_label']}: {position.get('entry_plan', 'N/A')}",
                            f"- {labels['risk_control_label']}: {position.get('risk_control', 'N/A')}",
                            "",
                        ])
                    # Checklist de Ações
                    checklist = battle.get('action_checklist', []) if battle else []
                    if checklist:
                        report_lines.extend([
                            f"**✅ {labels['checklist_heading']}**",
                            "",
                        ])
                        for item in checklist:
                            report_lines.append(f"- {item}")
                        report_lines.append("")

                # Resumo Financeiro / Retorno ao Acionista / Setores Relacionados (oculta automaticamente a seção se os dados estiverem faltando)
                self._append_fundamental_blocks(report_lines, result)

                # Se não houver dashboard, mostrar formato tradicional
                if not dashboard:
                    # Motivo de operação
                    if result.buy_reason:
                        report_lines.extend([
                            f"**💡 {reason_label}**: {result.buy_reason}",
                            "",
                        ])
                    # Aviso de risco
                    if result.risk_warning:
                        report_lines.extend([
                            f"**⚠️ {risk_warning_label}**: {result.risk_warning}",
                            "",
                        ])
                    # Análise técnica
                    if result.ma_analysis or result.volume_analysis:
                        report_lines.extend([
                            f"### 📊 {technical_heading}",
                            "",
                        ])
                        if result.ma_analysis:
                            report_lines.append(f"**{ma_label}**: {result.ma_analysis}")
                        if result.volume_analysis:
                            report_lines.append(f"**{volume_analysis_label}**: {result.volume_analysis}")
                        report_lines.append("")
                    # Notícias
                    if result.news_summary:
                        report_lines.extend([
                            f"### 📰 {news_heading}",
                            f"{result.news_summary}",
                            "",
                        ])
                
                report_lines.extend([
                    "---",
                    "",
                ])
        
        # Rodapé (remoção do aviso de responsabilidade)
        report_lines.extend([
            "",
            f"*{labels['generated_at_label']}：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ])
        models = self._collect_models_used(results)
        if models:
            report_lines.append(f"*{labels['analysis_model_label']}：{', '.join(models)}*")
        
        return "\n".join(report_lines)
    
    def generate_wechat_dashboard(self, results: List[AnalysisResult]) -> str:
        """
        Gerar relatório condensado de Dashboard de Decisão para WeChat Work (Limite de 4000 caracteres)
        
        Mantém apenas as conclusões principais e os pontos de sniper
        
        Args:
            results: Lista de resultados da análise
            
        Returns:
            Dashboard condensado de Decisão
        """
        config = get_config()
        report_language = self._get_report_language(results)
        labels = get_report_labels(report_language)
        if getattr(config, 'report_renderer_enabled', False) and results:
            from src.services.report_renderer import render
            out = render(
                platform='wechat',
                results=results,
                report_date=datetime.now().strftime('%Y-%m-%d'),
                summary_only=self._report_summary_only,
                extra_context={"report_language": report_language},
            )
            if out:
                return out

        report_date = datetime.now().strftime('%Y-%m-%d')
        
        # Ordenar por pontuação
        sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)
        
        # Estatísticas - usar campo decision_type para estatísticas precisas
        buy_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'buy')
        sell_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'sell')
        hold_count = sum(1 for r in results if getattr(r, 'decision_type', '') in ('hold', ''))
        
        lines = [
            f"## 🎯 {report_date} {labels['dashboard_title']}",
            "",
            f"> {len(results)} {labels['stock_unit']} | "
            f"🟢{labels['buy_label']}:{buy_count} 🟡{labels['watch_label']}:{hold_count} 🔴{labels['sell_label']}:{sell_count}",
            "",
        ]
        
        # Issue #262: se summary_only for verdadeiro, produzir apenas lista de resumos
        if self._report_summary_only:
            lines.append(f"**📊 {labels['summary_heading']}**")
            lines.append("")
            for r in sorted_results:
                _, signal_emoji, _ = self._get_signal_level(r)
                stock_name = self._get_display_name(r, report_language)
                lines.append(
                    f"{signal_emoji} **{stock_name}({r.code})**: "
                    f"{localize_operation_advice(r.operation_advice, report_language)} | "
                    f"{labels['score_label']} {r.sentiment_score} | "
                    f"{localize_trend_prediction(r.trend_prediction, report_language)}"
                )
        else:
            for result in sorted_results:
                signal_text, signal_emoji, _ = self._get_signal_level(result)
                dashboard = result.dashboard if hasattr(result, 'dashboard') and result.dashboard else {}
                core = dashboard.get('core_conclusion', {}) if dashboard else {}
                battle = dashboard.get('battle_plan', {}) if dashboard else {}
                intel = dashboard.get('intelligence', {}) if dashboard else {}
                
                # Nome da ação
                stock_name = self._get_display_name(result, report_language)
                
                # Linha de título: Sinal + Nome da ação
                lines.append(f"### {signal_emoji} **{signal_text}** | {stock_name}({result.code})")
                lines.append("")
                
                # Decisão principal (uma frase)
                one_sentence = core.get('one_sentence', result.analysis_summary) if core else result.analysis_summary
                if one_sentence:
                    lines.append(f"📌 **{one_sentence[:80]}**")
                    lines.append("")
                
                # Seção de Informações Importantes (Sentimento + Fundamentos)
                info_lines = []
                
                # Perspectiva de lucros
                if intel.get('earnings_outlook'):
                    outlook = str(intel['earnings_outlook'])[:60]
                    info_lines.append(f"📊 {labels['earnings_outlook_label']}: {outlook}")
                if intel.get('sentiment_summary'):
                    sentiment = str(intel['sentiment_summary'])[:50]
                    info_lines.append(f"💭 {labels['sentiment_summary_label']}: {sentiment}")
                if info_lines:
                    lines.extend(info_lines)
                    lines.append("")
                
                # Alertas de Risco (o mais importante, destaque-o)
                risks = intel.get('risk_alerts', []) if intel else []
                if risks:
                    lines.append(f"🚨 **{labels['risk_alerts_label']}**:")
                    for risk in risks[:2]:  # Mostrar até 2
                        risk_str = str(risk)
                        risk_text = risk_str[:50] + "..." if len(risk_str) > 50 else risk_str
                        lines.append(f"   • {risk_text}")
                    lines.append("")
                
                # Catalisadores Positivos
                catalysts = intel.get('positive_catalysts', []) if intel else []
                if catalysts:
                    lines.append(f"✨ **{labels['positive_catalysts_label']}**:")
                    for cat in catalysts[:2]:  # Mostrar até 2
                        cat_str = str(cat)
                        cat_text = cat_str[:50] + "..." if len(cat_str) > 50 else cat_str
                        lines.append(f"   • {cat_text}")
                    lines.append("")
                
                # Pontos de Sniper
                sniper = battle.get('sniper_points', {}) if battle else {}
                if sniper:
                    ideal_buy = str(sniper.get('ideal_buy', ''))
                    stop_loss = str(sniper.get('stop_loss', ''))
                    take_profit = str(sniper.get('take_profit', ''))
                    points = []
                    if ideal_buy:
                        points.append(f"🎯{labels['ideal_buy_label']}:{ideal_buy[:15]}")
                    if stop_loss:
                        points.append(f"🛑{labels['stop_loss_label']}:{stop_loss[:15]}")
                    if take_profit:
                        points.append(f"🎊{labels['take_profit_label']}:{take_profit[:15]}")
                    if points:
                        lines.append(" | ".join(points))
                        lines.append("")
                
                # Sugestão de posição
                pos_advice = core.get('position_advice', {}) if core else {}
                if pos_advice:
                    no_pos = str(pos_advice.get('no_position', ''))
                    has_pos = str(pos_advice.get('has_position', ''))
                    if no_pos:
                        lines.append(f"🆕 {labels['no_position_label']}: {no_pos[:50]}")
                    if has_pos:
                        lines.append(f"💼 {labels['has_position_label']}: {has_pos[:50]}")
                    lines.append("")
                
                # Checklist de Ações Simplificado
                checklist = battle.get('action_checklist', []) if battle else []
                if checklist:
                    # Mostrar apenas itens não passados
                    failed_checks = [str(c) for c in checklist if str(c).startswith('❌') or str(c).startswith('⚠️')]
                    if failed_checks:
                        lines.append(f"**{labels['failed_checks_heading']}**:")
                        for check in failed_checks[:3]:
                            lines.append(f"   {check[:40]}")
                        lines.append("")
                
                lines.append("---")
                lines.append("")
        
        # Rodapé
        lines.append(f"*{labels['report_time_label']}: {datetime.now().strftime('%H:%M')}*")
        models = self._collect_models_used(results)
        if models:
            lines.append(f"*{labels['analysis_model_label']}: {', '.join(models)}*")

        content = "\n".join(lines)

        return content

    def generate_wechat_summary(self, results: List[AnalysisResult]) -> str:
        """
        Gerar Relatório Diário de WeChat Condensado (Limite de 4000 caracteres)

        Args:
            results: Lista de resultados da análise

        Returns:
            Conteúdo condensado de Markdown
        """
        report_date = datetime.now().strftime('%Y-%m-%d')
        report_language = self._get_report_language(results)
        labels = get_report_labels(report_language)

        # Ordenar por pontuação
        sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)

        # Estatísticas - usar campo decision_type para estatísticas precisas
        buy_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'buy')
        sell_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'sell')
        hold_count = sum(1 for r in results if getattr(r, 'decision_type', '') in ('hold', ''))
        avg_score = sum(r.sentiment_score for r in results) / len(results) if results else 0

        lines = [
            f"## 📅 {report_date} {labels['report_title']}",
            "",
            f"> {labels['analyzed_prefix']} **{len(results)}** {labels['stock_unit_compact']} | "
            f"🟢{labels['buy_label']}:{buy_count} 🟡{labels['watch_label']}:{hold_count} 🔴{labels['sell_label']}:{sell_count} | "
            f"{labels['avg_score_label']}:{avg_score:.0f}",
            "",
        ]
        
        # Informação condensada para cada ação (controle de comprimento)
        for result in sorted_results:
            _, emoji, _ = self._get_signal_level(result)
            
            # Linha de Informação Principal
            lines.append(f"### {emoji} {self._get_display_name(result, report_language)}({result.code})")
            lines.append(
                f"**{localize_operation_advice(result.operation_advice, report_language)}** | "
                f"{labels['score_label']}:{result.sentiment_score} | "
                f"{localize_trend_prediction(result.trend_prediction, report_language)}"
            )
            
            # Motivo de operação (truncado)
            if hasattr(result, 'buy_reason') and result.buy_reason:
                reason = result.buy_reason[:80] + "..." if len(result.buy_reason) > 80 else result.buy_reason
                lines.append(f"💡 {reason}")
            
            # Ponto chave principal
            if hasattr(result, 'key_points') and result.key_points:
                points = result.key_points[:60] + "..." if len(result.key_points) > 60 else result.key_points
                lines.append(f"🎯 {points}")
            
            # Aviso de risco (truncado)
            if hasattr(result, 'risk_warning') and result.risk_warning:
                risk = result.risk_warning[:50] + "..." if len(result.risk_warning) > 50 else result.risk_warning
                lines.append(f"⚠️ {risk}")
            
            lines.append("")
        
        # Rodapé (Linha do modelo antes de ---, Issue #528)
        models = self._collect_models_used(results)
        if models:
            lines.append(f"*{labels['analysis_model_label']}: {', '.join(models)}*")
        lines.extend([
            "---",
            f"*{labels['not_investment_advice']}*",
            f"*{labels['details_report_hint']} reports/report_{report_date.replace('-', '')}.md*"
        ])

        content = "\n".join(lines)

        return content

    def generate_brief_report(
        self,
        results: List[AnalysisResult],
        report_date: Optional[str] = None,
    ) -> str:
        """
        Generate brief report (3-5 sentences per stock) for mobile/push.

        Args:
            results: Analysis results list (use [result] for single stock).
            report_date: Report date (default: today).

        Returns:
            Brief markdown content.
        """
        if report_date is None:
            report_date = datetime.now().strftime('%Y-%m-%d')
        report_language = self._get_report_language(results)
        labels = get_report_labels(report_language)
        config = get_config()
        if getattr(config, 'report_renderer_enabled', False) and results:
            from src.services.report_renderer import render
            out = render(
                platform='brief',
                results=results,
                report_date=report_date,
                summary_only=False,
                extra_context={"report_language": report_language},
            )
            if out:
                return out
        # Fallback: brief summary from dashboard report
        if not results:
            return f"# {report_date} {labels['brief_title']}\n\n{labels['no_results']}"
        sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)
        buy_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'buy')
        sell_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'sell')
        hold_count = sum(1 for r in results if getattr(r, 'decision_type', '') in ('hold', ''))
        lines = [
            f"# {report_date} {labels['brief_title']}",
            "",
            f"> {len(results)} {labels['stock_unit_compact']} | 🟢{buy_count} 🟡{hold_count} 🔴{sell_count}",
            "",
        ]
        for r in sorted_results:
            _, emoji, _ = self._get_signal_level(r)
            name = self._get_display_name(r, report_language)
            dash = r.dashboard or {}
            core = dash.get('core_conclusion', {}) or {}
            one = (core.get('one_sentence') or r.analysis_summary or '')[:60]
            lines.append(
                f"**{name}({r.code})** {emoji} "
                f"{localize_operation_advice(r.operation_advice, report_language)} | "
                f"{labels['score_label']} {r.sentiment_score} | {one}"
            )
        lines.append("")
        lines.append(f"*{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        models = self._collect_models_used(results)
        if models:
            lines.append(f"*{labels['analysis_model_label']}: {', '.join(models)}*")
        return "\n".join(lines)

    def generate_single_stock_report(self, result: AnalysisResult) -> str:
        """
        Gerar Relatório de Análise para uma Única Ação (para modo de envio de única ação #55)
        
        Formato conciso e completo, adequado para enviar o relatório assim que a análise terminar.
        
        Args:
            result: Resultado da análise para a ação
            
        Returns:
            Relatório da ação em Markdown
        """
        report_date = datetime.now().strftime('%Y-%m-%d %H:%M')
        report_language = self._get_report_language(result)
        labels = get_report_labels(report_language)
        signal_text, signal_emoji, _ = self._get_signal_level(result)
        dashboard = result.dashboard if hasattr(result, 'dashboard') and result.dashboard else {}
        core = dashboard.get('core_conclusion', {}) if dashboard else {}
        battle = dashboard.get('battle_plan', {}) if dashboard else {}
        intel = dashboard.get('intelligence', {}) if dashboard else {}
        
        # Nome da Ação (escapar de caracteres como *ST)
        stock_name = self._get_display_name(result, report_language)
        
        lines = [
            f"## {signal_emoji} {stock_name} ({result.code})",
            "",
            f"> {report_date} | {labels['score_label']}: **{result.sentiment_score}** | {localize_trend_prediction(result.trend_prediction, report_language)}",
            "",
        ]

        self._append_market_snapshot(lines, result)
        
        # Decisão Central (uma frase)
        one_sentence = core.get('one_sentence', result.analysis_summary) if core else result.analysis_summary
        if one_sentence:
            lines.extend([
                f"### 📌 {labels['core_conclusion_heading']}",
                "",
                f"**{signal_text}**: {one_sentence}",
                "",
            ])
        
        # Informações Importantes (Sentimento + Fundamentos)
        info_added = False
        if intel:
            if intel.get('earnings_outlook'):
                if not info_added:
                    lines.append(f"### 📰 {labels['info_heading']}")
                    lines.append("")
                    info_added = True
                lines.append(f"📊 **{labels['earnings_outlook_label']}**: {str(intel['earnings_outlook'])[:100]}")
            
            if intel.get('sentiment_summary'):
                if not info_added:
                    lines.append(f"### 📰 {labels['info_heading']}")
                    lines.append("")
                    info_added = True
                lines.append(f"💭 **{labels['sentiment_summary_label']}**: {str(intel['sentiment_summary'])[:80]}")
            
            # Alertas de Risco
            risks = intel.get('risk_alerts', [])
            if risks:
                if not info_added:
                    lines.append(f"### 📰 {labels['info_heading']}")
                    lines.append("")
                    info_added = True
                lines.append("")
                lines.append(f"🚨 **{labels['risk_alerts_label']}**:")
                for risk in risks[:3]:
                    lines.append(f"- {str(risk)[:60]}")
            
            # Catalisadores Positivos
            catalysts = intel.get('positive_catalysts', [])
            if catalysts:
                lines.append("")
                lines.append(f"✨ **{labels['positive_catalysts_label']}**:")
                for cat in catalysts[:3]:
                    lines.append(f"- {str(cat)[:60]}")
        
        if info_added:
            lines.append("")
        
        # Pontos de Sniper
        sniper = battle.get('sniper_points', {}) if battle else {}
        if sniper:
            lines.extend([
                f"### 🎯 {labels['action_points_heading']}",
                "",
                f"| {labels['ideal_buy_label']} | {labels['stop_loss_label']} | {labels['take_profit_label']} |",
                "|------|------|------|",
            ])
            ideal_buy = sniper.get('ideal_buy', '-')
            stop_loss = sniper.get('stop_loss', '-')
            take_profit = sniper.get('take_profit', '-')
            lines.append(f"| {ideal_buy} | {stop_loss} | {take_profit} |")
            lines.append("")
        
        # Sugestão de posição
        pos_advice = core.get('position_advice', {}) if core else {}
        if pos_advice:
            lines.extend([
                f"### 💼 {labels['position_advice_heading']}",
                "",
                f"- 🆕 **{labels['no_position_label']}**: {pos_advice.get('no_position', localize_operation_advice(result.operation_advice, report_language))}",
                f"- 💼 **{labels['has_position_label']}**: {pos_advice.get('has_position', labels['continue_holding'])}",
                "",
            ])

        # Resumo Financeiro / Retorno ao Acionista / Setores Relacionados (oculta automaticamente a seção se os dados estiverem faltando)
        self._append_fundamental_blocks(lines, result)

        lines.append("---")
        if self._should_show_llm_model():
            model_used = normalize_model_used(getattr(result, "model_used", None))
            if model_used:
                lines.append(f"*{labels['analysis_model_label']}: {model_used}*")
        lines.append(f"*{labels['not_investment_advice']}*")

        return "\n".join(lines)

    # Display name mapping for realtime data sources
    _SOURCE_DISPLAY_NAMES = {
        "tencent": {"zh": "Tencent Finance", "en": "Tencent Finance", "pt": "Tencent Finance"},
        "akshare_em": {"zh": "Eastmoney", "en": "Eastmoney", "pt": "Eastmoney"},
        "akshare_sina": {"zh": "Sina Finance", "en": "Sina Finance", "pt": "Sina Finance"},
        "akshare_qq": {"zh": "Tencent Finance", "en": "Tencent Finance", "pt": "Tencent Finance"},
        "efinance": {"zh": "Eastmoney (efinance)", "en": "Eastmoney (efinance)", "pt": "Eastmoney (efinance)"},
        "tushare": {"zh": "Tushare Pro", "en": "Tushare Pro", "pt": "Tushare Pro"},
        "sina": {"zh": "Sina Finance", "en": "Sina Finance", "pt": "Sina Finance"},
        "stooq": {"zh": "Stooq", "en": "Stooq", "pt": "Stooq"},
        "longbridge": {"zh": "Longbridge", "en": "Longbridge", "pt": "Longbridge"},
        "fallback": {"zh": "Fallback", "en": "Fallback", "pt": "Fallback"},
    }

    def _get_source_display_name(self, source: Any, language: Optional[str]) -> str:
        raw_source = str(source or "N/A")
        mapping = self._SOURCE_DISPLAY_NAMES.get(raw_source)
        if not mapping:
            return raw_source
        return mapping.get(normalize_report_language(language), mapping["en"])

    def _append_market_snapshot(self, lines: List[str], result: AnalysisResult) -> None:
        snapshot = getattr(result, 'market_snapshot', None)
        if not snapshot:
            return

        report_language = self._get_report_language(result)
        labels = get_report_labels(report_language)

        lines.extend([
            f"### 📈 {labels['market_snapshot_heading']}",
            "",
            f"| {labels['close_label']} | {labels['prev_close_label']} | {labels['open_label']} | {labels['high_label']} | {labels['low_label']} | {labels['change_pct_label']} | {labels['change_amount_label']} | {labels['amplitude_label']} | {labels['volume_label']} | {labels['amount_label']} |",
            "|------|------|------|------|------|-------|-------|------|--------|--------|",
            f"| {snapshot.get('close', 'N/A')} | {snapshot.get('prev_close', 'N/A')} | "
            f"{snapshot.get('open', 'N/A')} | {snapshot.get('high', 'N/A')} | "
            f"{snapshot.get('low', 'N/A')} | {snapshot.get('pct_chg', 'N/A')} | "
            f"{snapshot.get('change_amount', 'N/A')} | {snapshot.get('amplitude', 'N/A')} | "
            f"{snapshot.get('volume', 'N/A')} | {snapshot.get('amount', 'N/A')} |",
        ])

        if "price" in snapshot:
            display_source = self._get_source_display_name(snapshot.get('source', 'N/A'), report_language)
            lines.extend([
                "",
                f"| {labels['current_price_label']} | {labels['volume_ratio_label']} | {labels['turnover_rate_label']} | {labels['source_label']} |",
                "|-------|------|--------|----------|",
                f"| {snapshot.get('price', 'N/A')} | {snapshot.get('volume_ratio', 'N/A')} | "
                f"{snapshot.get('turnover_rate', 'N/A')} | {display_source} |",
            ])

        lines.append("")

    _CURRENCY_SUFFIX = {
        "USD": " Dólares",
        "HKD": " HKD",
        "CNY": " RMB",
        "RMB": " RMB",
        "CNH": " RMB",
    }

    @classmethod
    def _format_amount_cn(cls, value: Any, currency: Optional[str] = None) -> str:
        """Format absolute amounts in Milhões / Bilhões + currency suffix; returns N/A on non-numeric.

        ``currency`` accepts ``USD``/``HKD``/``CNY``; unknown values fall back to RMB.
        """
        try:
            amount = float(value)
        except (TypeError, ValueError):
            return "N/A"
        if amount != amount:  # NaN
            return "N/A"
        sign = "-" if amount < 0 else ""
        abs_amount = abs(amount)
        suffix = cls._CURRENCY_SUFFIX.get((currency or "").upper(), " RMB")
        if abs_amount >= 1e8:
            return f"{sign}{abs_amount / 1e8:.2f} Bilhões{suffix}"
        if abs_amount >= 1e4:
            return f"{sign}{abs_amount / 1e4:.2f} Milhões{suffix}"
        return f"{sign}{abs_amount:.0f}{suffix}"

    @staticmethod
    def _format_percent(value: Any) -> str:
        try:
            return f"{float(value):.2f}%"
        except (TypeError, ValueError):
            return "N/A"

    @classmethod
    def _format_per_share(cls, value: Any, currency: Optional[str] = None) -> str:
        try:
            amount = float(value)
        except (TypeError, ValueError):
            return "N/A"
        if amount != amount:  # NaN
            return "N/A"
        suffix = cls._CURRENCY_SUFFIX.get((currency or "").upper(), " RMB")
        return f"{amount:.4f}{suffix}"

    @staticmethod
    def _format_text(value: Any) -> str:
        if value is None:
            return "N/A"
        text = str(value).strip()
        return text if text else "N/A"

    def _get_fundamental_blocks(self, result: AnalysisResult) -> Dict[str, Any]:
        """Extract financial_report / dividend / belong_boards / sector_rankings.

        Falls back to empty containers when fundamental_context is missing or partial,
        so callers can rely on dict shape without re-checking types.
        """
        ctx = getattr(result, "fundamental_context", None)
        if not isinstance(ctx, dict):
            return {
                "financial_report": {},
                "growth": {},
                "dividend": {},
                "belong_boards": [],
                "sector_top": [],
                "sector_bottom": [],
            }

        earnings_block = ctx.get("earnings") if isinstance(ctx.get("earnings"), dict) else {}
        earnings_data = earnings_block.get("data") if isinstance(earnings_block.get("data"), dict) else {}
        financial_report = earnings_data.get("financial_report") if isinstance(earnings_data.get("financial_report"), dict) else {}
        dividend = earnings_data.get("dividend") if isinstance(earnings_data.get("dividend"), dict) else {}

        growth_block = ctx.get("growth") if isinstance(ctx.get("growth"), dict) else {}
        growth_data = growth_block.get("data") if isinstance(growth_block.get("data"), dict) else {}

        boards_block = ctx.get("boards") if isinstance(ctx.get("boards"), dict) else {}
        boards_data = boards_block.get("data") if isinstance(boards_block.get("data"), dict) else {}
        sector_top = boards_data.get("top") if isinstance(boards_data.get("top"), list) else []
        sector_bottom = boards_data.get("bottom") if isinstance(boards_data.get("bottom"), list) else []

        belong_boards = ctx.get("belong_boards") if isinstance(ctx.get("belong_boards"), list) else []

        return {
            "financial_report": financial_report,
            "growth": growth_data,
            "dividend": dividend,
            "belong_boards": belong_boards,
            "sector_top": sector_top,
            "sector_bottom": sector_bottom,
        }

    def _append_fundamental_blocks(self, lines: List[str], result: AnalysisResult) -> None:
        """Append Resumo Financeiro / Retorno ao Acionista / Setores Relacionados markdown blocks.

        Each block is only rendered when at least one cell has data; this keeps
        the email compact when the fundamental pipeline returned partial/failed
        results (e.g. HK/US markets, ETF, or AkShare outages).
        """
        blocks = self._get_fundamental_blocks(result)
        report_language = self._get_report_language(result)
        labels = get_report_labels(report_language)

        self._append_financial_summary(lines, blocks, labels)
        self._append_shareholder_return(lines, blocks, labels)
        self._append_related_boards(lines, blocks, labels)

    def _append_financial_summary(
        self,
        lines: List[str],
        blocks: Dict[str, Any],
        labels: Dict[str, str],
    ) -> None:
        report = blocks.get("financial_report") or {}
        growth = blocks.get("growth") or {}
        currency = report.get("currency") if isinstance(report.get("currency"), str) else None
        cells = {
            "report_date": self._format_text(report.get("report_date")),
            "revenue": self._format_amount_cn(report.get("revenue"), currency),
            "net_profit": self._format_amount_cn(report.get("net_profit_parent"), currency),
            "operating_cash_flow": self._format_amount_cn(report.get("operating_cash_flow"), currency),
            "roe": self._format_percent(report.get("roe") if report.get("roe") is not None else growth.get("roe")),
            "revenue_yoy": self._format_percent(growth.get("revenue_yoy")),
            "net_profit_yoy": self._format_percent(growth.get("net_profit_yoy")),
            "gross_margin": self._format_percent(growth.get("gross_margin")),
        }
        if all(v == "N/A" for v in cells.values()):
            return

        lines.extend([
            f"### 💼 {labels['financial_summary_heading']}",
            "",
            (
                f"| {labels['report_date_label']} | {labels['revenue_label']} | "
                f"{labels['net_profit_label']} | {labels['operating_cash_flow_label']} | "
                f"{labels['roe_label']} | {labels['revenue_yoy_label']} | "
                f"{labels['net_profit_yoy_label']} | {labels['gross_margin_label']} |"
            ),
            # Alinhamento no centro para período, alinhamento à direita para valores/proporções
            "|:------:|-------:|-------:|-------:|------:|------:|------:|------:|",
            (
                f"| {cells['report_date']} | {cells['revenue']} | {cells['net_profit']} | "
                f"{cells['operating_cash_flow']} | {cells['roe']} | {cells['revenue_yoy']} | "
                f"{cells['net_profit_yoy']} | {cells['gross_margin']} |"
            ),
            "",
        ])

    def _append_shareholder_return(
        self,
        lines: List[str],
        blocks: Dict[str, Any],
        labels: Dict[str, str],
    ) -> None:
        dividend = blocks.get("dividend") or {}
        report = blocks.get("financial_report") or {}
        # Dividends are paid in the trading currency (yfinance `info.currency`)
        # which can differ from the financial-statement currency (e.g. HK ADRs
        # often report `financialCurrency=CNY` but pay dividends in HKD).
        dividend_currency = dividend.get("currency") if isinstance(dividend.get("currency"), str) else None
        if not dividend_currency:
            dividend_currency = report.get("currency") if isinstance(report.get("currency"), str) else None
        events = dividend.get("events") if isinstance(dividend.get("events"), list) else []
        latest_event = events[0] if events else {}
        if not isinstance(latest_event, dict):
            latest_event = {}

        ttm_event_count = dividend.get("ttm_event_count")
        cells = {
            "ttm_cash": self._format_per_share(dividend.get("ttm_cash_dividend_per_share"), dividend_currency),
            "ttm_count": str(ttm_event_count) if isinstance(ttm_event_count, int) else "N/A",
            "ttm_yield": self._format_percent(dividend.get("ttm_dividend_yield_pct")),
            "latest_ex": self._format_text(latest_event.get("ex_dividend_date") or latest_event.get("event_date")),
        }
        if all(v == "N/A" for v in cells.values()):
            return

        lines.extend([
            f"### 💵 {labels['shareholder_return_heading']}",
            "",
            (
                f"| {labels['ttm_cash_dividend_label']} | {labels['ttm_event_count_label']} | "
                f"{labels['ttm_dividend_yield_label']} | {labels['latest_ex_dividend_label']} |"
            ),
            "|---------------------:|----------:|--------:|:--------:|",
            (
                f"| {cells['ttm_cash']} | {cells['ttm_count']} | "
                f"{cells['ttm_yield']} | {cells['latest_ex']} |"
            ),
            "",
        ])

    def _append_related_boards(
        self,
        lines: List[str],
        blocks: Dict[str, Any],
        labels: Dict[str, str],
    ) -> None:
        belong_boards = blocks.get("belong_boards") or []
        if not belong_boards:
            return

        sector_signals: Dict[str, Tuple[str, Optional[float]]] = {}
        for item in blocks.get("sector_top") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            sector_signals[name] = (labels["leading_board_label"], _safe_float(item.get("change_pct")))
        for item in blocks.get("sector_bottom") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name or name in sector_signals:
                continue
            sector_signals[name] = (labels["lagging_board_label"], _safe_float(item.get("change_pct")))

        # Pre-resolve rows so we know whether sector-signal columns carry any
        # data — drop them entirely when every cell would be "--" (typical for
        # HK/US where there's no 板块涨跌榜 feed) so the table stays compact.
        prepared: List[Tuple[str, str, Optional[str], Optional[float]]] = []
        for raw in belong_boards[:5]:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "").strip()
            if not name:
                continue
            board_type = self._format_text(raw.get("type"))
            status_text, change_pct = sector_signals.get(name, (None, None))
            prepared.append((name, board_type, status_text, change_pct))

        if not prepared:
            return

        has_sector_signal = any(status is not None for _, _, status, _ in prepared)

        lines.append(f"### 🧩 {labels['related_boards_heading']}")
        lines.append("")
        if has_sector_signal:
            lines.append(
                f"| {labels['board_name_label']} | {labels['board_type_label']} | "
                f"{labels['board_status_label']} | {labels['board_change_pct_label']} |"
            )
            lines.append("|:-----|:----:|:------:|------:|")
            for name, board_type, status_text, change_pct in prepared:
                status = status_text if status_text is not None else "--"
                change = "--" if change_pct is None else f"{change_pct:+.2f}%"
                lines.append(f"| {name} | {board_type} | {status} | {change} |")
        else:
            if all(board_type == "N/A" for _, board_type, _, _ in prepared):
                lines.append(" / ".join(name for name, _, _, _ in prepared))
                lines.append("")
                return
            lines.append(f"| {labels['board_name_label']} | {labels['board_type_label']} |")
            lines.append("|:-----|:----:|")
            for name, board_type, _, _ in prepared:
                lines.append(f"| {name} | {board_type} |")
        lines.append("")

    def _should_use_image_for_channel(
        self, channel: NotificationChannel, image_bytes: Optional[bytes]
    ) -> bool:
        """
        Decide whether to send as image for the given channel (Issue #289).

        Fallback rules (send as Markdown text instead of image):
        - image_bytes is None: conversion failed / imgkit not installed / content over max_chars
        - WeChat: image exceeds ~2MB limit
        """
        if channel.value not in self._markdown_to_image_channels or image_bytes is None:
            return False
        if channel == NotificationChannel.WECHAT and len(image_bytes) > WECHAT_IMAGE_MAX_BYTES:
            logger.warning(
                "Imagem WeChat excede o limite (%d bytes), retornando para enviar via texto Markdown",
                len(image_bytes),
            )
            return False
        return True

    @staticmethod
    def _sanitize_notification_diagnostics(text: Any) -> str:
        return sanitize_diagnostic_text(text)

    def _send_to_static_channel(
        self,
        channel: NotificationChannel,
        content: str,
        *,
        image_bytes: Optional[bytes],
        email_stock_codes: Optional[List[str]],
        email_send_to_all: bool,
    ) -> bool:
        use_image = self._should_use_image_for_channel(channel, image_bytes)
        if channel == NotificationChannel.WECHAT:
            if use_image:
                return self._send_wechat_image(image_bytes)
            return self.send_to_wechat(content)
        if channel == NotificationChannel.FEISHU:
            return self.send_to_feishu(content)
        if channel == NotificationChannel.TELEGRAM:
            if use_image:
                return self._send_telegram_photo(image_bytes)
            return self.send_to_telegram(content)
        if channel == NotificationChannel.EMAIL:
            receivers = None
            if email_send_to_all and self._stock_email_groups:
                receivers = self.get_all_email_receivers()
            elif email_stock_codes and self._stock_email_groups:
                receivers = self.get_receivers_for_stocks(email_stock_codes)
            if use_image:
                return self._send_email_with_inline_image(image_bytes, receivers=receivers)
            return self.send_to_email(content, receivers=receivers)
        if channel == NotificationChannel.PUSHOVER:
            return self.send_to_pushover(content)
        if channel == NotificationChannel.NTFY:
            return self.send_to_ntfy(content)
        if channel == NotificationChannel.GOTIFY:
            return self.send_to_gotify(content)
        if channel == NotificationChannel.PUSHPLUS:
            return self.send_to_pushplus(content)
        if channel == NotificationChannel.SERVERCHAN3:
            return self.send_to_serverchan3(content)
        if channel == NotificationChannel.CUSTOM:
            if use_image:
                return self._send_custom_webhook_image(image_bytes, fallback_content=content)
            return self.send_to_custom(content)
        if channel == NotificationChannel.DISCORD:
            return self.send_to_discord(content)
        if channel == NotificationChannel.SLACK:
            if use_image:
                return self._send_slack_image(image_bytes, fallback_content=content)
            return self.send_to_slack(content)
        if channel == NotificationChannel.ASTRBOT:
            return self.send_to_astrbot(content)
        logger.warning(f"Canal de notificação não suportado: {channel}")
        return False

    def send_with_results(
        self,
        content: str,
        email_stock_codes: Optional[List[str]] = None,
        email_send_to_all: bool = False,
        route_type: Optional[str] = None,
        severity: Optional[str] = None,
        dedup_key: Optional[str] = None,
        cooldown_key: Optional[str] = None,
    ) -> NotificationDispatchResult:
        """
        Send a notification and return per-channel diagnostics.

        ``send()`` keeps the historical bool API and delegates here.

        Fallback rules (Markdown-to-image, Issue #289):
        - When image_bytes is None (conversion failed / imgkit not installed /
          content over max_chars): all channels configured for image will send
          as Markdown text instead.
        - When WeChat image exceeds ~2MB: that channel falls back to Markdown text.

        Args:
            content: Conteúdo da mensagem (formato Markdown)
            email_stock_codes: Lista de códigos de ações (opcional, usado para enviar para emails do grupo correspondente)
            email_send_to_all: Se deve enviar emails para todos configurados (útil para revisões do mercado, não relacionados a ações únicas)
            route_type: Tipo de rotas de notificação; None mantém comportamento antigo, report/alert/system_error processa canais estáticos com filtro
            severity: Nível de severidade da notificação; inferido se não for definido
            dedup_key: Chave opcional de desduplicação estável; hash do conteúdo se não for definida
            cooldown_key: Chave opcional de resfriamento; usa padrão de rota/severidade se não definida

        Returns:
            Structured dispatch diagnostics.
        """
        context_success = self.send_to_context(content)
        if not self.should_broadcast_static_channels():
            if context_success:
                logger.info("Envio via contexto concluído com sucesso, ignorando os canais de notificação estáticos")
                return NotificationDispatchResult(
                    dispatched=True,
                    success=True,
                    status="sent",
                    channel_results=[ChannelAttemptResult(channel="__context__", success=True)],
                )
            logger.warning("Falha de envio via contexto interativo, os canais de notificação estáticos foram ignorados")
            return NotificationDispatchResult(
                dispatched=True,
                success=False,
                status="all_failed",
                channel_results=[
                    ChannelAttemptResult(
                        channel="__context__",
                        success=False,
                        error_code="send_failed",
                        retryable=True,
                    )
                ],
                message="interactive context delivery failed; static channels skipped",
            )

        if not self._available_channels:
            if context_success:
                logger.info("Envio via contexto concluído com sucesso (não há outros canais de notificação configurados)")
                return NotificationDispatchResult(
                    dispatched=True,
                    success=True,
                    status="sent",
                    channel_results=[ChannelAttemptResult(channel="__context__", success=True)],
                )
            logger.warning("Serviço de notificação indisponível, ignorando envio de notificação")
            return NotificationDispatchResult(
                dispatched=False,
                success=False,
                status="no_channel",
                message="notification service unavailable",
            )

        target_channels = self.get_channels_for_route(route_type)
        if not target_channels:
            if context_success:
                logger.info("已通过消息上下文渠道完成推送（路由后无其他通知渠道）")
                return NotificationDispatchResult(
                    dispatched=True,
                    success=True,
                    status="sent",
                    channel_results=[ChannelAttemptResult(channel="__context__", success=True)],
                )
            logger.warning("A rota de notificação %s não atingiu nenhum canal configurado, ignorando os canais estáticos", route_type)
            return NotificationDispatchResult(
                dispatched=False,
                success=False,
                status="no_channel",
                message=f"notification route {route_type} has no configured channel",
            )

        noise_decision = self.evaluate_noise_control(
            content,
            route_type=route_type,
            severity=severity,
            dedup_key=dedup_key,
            cooldown_key=cooldown_key,
        )
        if not noise_decision.should_send:
            logger.info(noise_decision.message)
            status = "sent" if context_success else "noise_suppressed"
            results = [ChannelAttemptResult(channel="__context__", success=True)] if context_success else []
            return NotificationDispatchResult(
                dispatched=bool(context_success),
                success=bool(context_success),
                status=status,
                channel_results=results,
                message=noise_decision.message,
            )

        # Markdown to image (Issue #289): convert once if any channel needs it.
        # Per-channel decision via _should_use_image_for_channel (see send() docstring for fallback rules).
        image_bytes = None
        channels_needing_image = {
            ch for ch in target_channels
            if ch.value in self._markdown_to_image_channels
            and ch not in {NotificationChannel.NTFY, NotificationChannel.GOTIFY}
        }
        if channels_needing_image:
            from src.md2img import markdown_to_image
            image_bytes = markdown_to_image(
                content, max_chars=self._markdown_to_image_max_chars
            )
            if image_bytes:
                logger.info("Markdown convertido em imagem, a imagem será enviada para %s",
                            [ch.value for ch in channels_needing_image])
            elif channels_needing_image:
                try:
                    from src.config import get_config
                    engine = getattr(get_config(), "md2img_engine", "wkhtmltoimage")
                except Exception:
                    engine = "wkhtmltoimage"
                hint = (
                    "npm i -g markdown-to-file" if engine == "markdown-to-file"
                    else "wkhtmltopdf (apt install wkhtmltopdf / brew install wkhtmltopdf)"
                )
                logger.warning(
                    "Falha ao converter Markdown para imagem, será retornado para enviar via texto. Verifique a configuração MARKDOWN_TO_IMAGE_CHANNELS e instale %s",
                    hint,
                )

        channel_names = ', '.join(ChannelDetector.get_channel_name(ch) for ch in target_channels)
        logger.info(f"Enviando notificação para {len(target_channels)} canais: {channel_names}")

        success_count = 0
        fail_count = 0
        channel_results: List[ChannelAttemptResult] = []

        for channel in target_channels:
            channel_name = ChannelDetector.get_channel_name(channel)
            started_at = time.monotonic()
            try:
                result = self._send_to_static_channel(
                    channel,
                    content,
                    image_bytes=image_bytes,
                    email_stock_codes=email_stock_codes,
                    email_send_to_all=email_send_to_all,
                )
                latency_ms = int((time.monotonic() - started_at) * 1000)

                if result:
                    success_count += 1
                else:
                    fail_count += 1
                channel_results.append(
                    ChannelAttemptResult(
                        channel=channel.value,
                        success=bool(result),
                        error_code=None if result else "send_failed",
                        retryable=not bool(result),
                        latency_ms=latency_ms,
                    )
                )

            except Exception as e:
                logger.error(f"Falha ao enviar para {channel_name}: {e}")
                fail_count += 1
                channel_results.append(
                    ChannelAttemptResult(
                        channel=channel.value,
                        success=False,
                        error_code="exception",
                        retryable=True,
                        latency_ms=int((time.monotonic() - started_at) * 1000),
                        diagnostics=self._sanitize_notification_diagnostics(str(e)),
                    )
                )

        logger.info(f"Envio de notificações concluído: {success_count} sucessos, {fail_count} falhas")
        if success_count > 0:
            self.record_noise_control(noise_decision)
        else:
            self.release_noise_control(noise_decision)
        success = success_count > 0 or context_success
        if success_count > 0 and fail_count > 0:
            status = "partial_failed"
        elif success_count > 0 or context_success:
            status = "sent"
        else:
            status = "all_failed"
        if context_success:
            channel_results.insert(0, ChannelAttemptResult(channel="__context__", success=True))
        return NotificationDispatchResult(
            dispatched=True,
            success=success,
            status=status,
            channel_results=channel_results,
        )

    def send(
        self,
        content: str,
        email_stock_codes: Optional[List[str]] = None,
        email_send_to_all: bool = False,
        route_type: Optional[str] = None,
        severity: Optional[str] = None,
        dedup_key: Optional[str] = None,
        cooldown_key: Optional[str] = None,
    ) -> bool:
        """
        Interface de envio unificada - enviar para todos os canais configurados.

        Returns:
            Se o envio foi bem-sucedido em pelo menos um canal
        """
        result = self.send_with_results(
            content,
            email_stock_codes=email_stock_codes,
            email_send_to_all=email_send_to_all,
            route_type=route_type,
            severity=severity,
            dedup_key=dedup_key,
            cooldown_key=cooldown_key,
        )
        return bool(result.success)
   
    def save_report_to_file(
        self, 
        content: str, 
        filename: Optional[str] = None
    ) -> str:
        """
        Salvar relatório diário no arquivo local
        
        Args:
            content: Conteúdo do relatório
            filename: Nome do arquivo (opcional, gerado por data por padrão)
            
        Returns:
            Caminho do arquivo salvo
        """
        from pathlib import Path
        
        if filename is None:
            date_str = datetime.now().strftime('%Y%m%d')
            filename = f"report_{date_str}.md"
        
        # Garantir que o diretório reports exista (usando a pasta reports na raiz do projeto)
        reports_dir = Path(__file__).parent.parent / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = reports_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Relatório diário salvo em: {filepath}")
        return str(filepath)


class NotificationBuilder:
    """
    Construtor de mensagem de notificação
    
    Fornece métodos convenientes para construção de mensagens
    """
    
    @staticmethod
    def build_simple_alert(
        title: str,
        content: str,
        alert_type: str = "info"
    ) -> str:
        """
        Construir uma mensagem de alerta simples
        
        Args:
            title: Título
            content: Conteúdo
            alert_type: Tipo (info, warning, error, success)
        """
        emoji_map = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅",
        }
        emoji = emoji_map.get(alert_type, "📢")
        
        return f"{emoji} **{title}**\n\n{content}"
    
    @staticmethod
    def build_stock_summary(results: List[AnalysisResult]) -> str:
        """
        Construir resumo de ações (versão curta)
        
        Adequado para notificações rápidas
        """
        report_language = normalize_report_language(
            next((getattr(result, "report_language", None) for result in results if getattr(result, "report_language", None)), None)
        )
        labels = get_report_labels(report_language)
        lines = [f"📊 **{labels['summary_heading']}**", ""]
        
        for r in sorted(results, key=lambda x: x.sentiment_score, reverse=True):
            _, emoji, _ = get_signal_level(r.operation_advice, r.sentiment_score, report_language)
            name = get_localized_stock_name(r.name, r.code, report_language)
            lines.append(
                f"{emoji} {name}({r.code}): {localize_operation_advice(r.operation_advice, report_language)} | "
                f"{labels['score_label']} {r.sentiment_score}"
            )
        
        return "\n".join(lines)


# Funções convenientes
def get_notification_service() -> NotificationService:
    """Obter instância do serviço de notificação"""
    return NotificationService()


def send_daily_report(results: List[AnalysisResult]) -> bool:
    """
    Atalho para enviar relatório diário
    
    Identifica automaticamente os canais e envia
    """
    service = get_notification_service()
    
    # Gerar relatório
    report = service.generate_daily_report(results)
    
    # Salvar localmente
    service.save_report_to_file(report)
    
    # Enviar para os canais configurados (identificação automática)
    return service.send(report)


if __name__ == "__main__":
    # Código de teste
    logging.basicConfig(level=logging.DEBUG)
    from src.analyzer import AnalysisResult
    
    # Simular resultados da análise
    test_results = [
        AnalysisResult(
            code='600519',
            name='Kweichow Moutai',
            sentiment_score=75,
            trend_prediction='Alta',
            analysis_summary='Técnica forte, notícias favoráveis',
            operation_advice='Comprar',
            technical_analysis='Ruptura de volume MA20, MACD Golden Cross',
            news_summary='Empresa anunciou dividendos, lucros acima das expectativas',
        ),
        AnalysisResult(
            code='000001',
            name='Ping An Bank',
            sentiment_score=45,
            trend_prediction='Lateral',
            analysis_summary='Consolidação lateral, aguardando direção',
            operation_advice='Manter',
            technical_analysis='Médias móveis emaranhadas, volume decrescente',
            news_summary='Sem novidades importantes recentes',
        ),
        AnalysisResult(
            code='300750',
            name='CATL',
            sentiment_score=35,
            trend_prediction='Baixa',
            analysis_summary='Técnica enfraquecendo, note o risco',
            operation_advice='Vender',
            technical_analysis='Quebrou o suporte MA10, volume insuficiente',
            news_summary='Aumento da concorrência no setor, pressão sobre a margem de lucro bruto',
        ),
    ]
    
    service = NotificationService()
    
    # Mostrar os canais detectados
    print("=== Detecção de Canal de Notificação ===")
    print(f"Canal atual: {service.get_channel_names()}")
    print(f"Lista de canais: {service.get_available_channels()}")
    print(f"Serviço disponível: {service.is_available()}")
    
    # Teste de geração de relatório diário
    print("\n=== Teste de Geração de Relatório Diário ===")
    report = service.generate_daily_report(test_results)
    print(report)
    
    # Salvar em arquivo
    print("\n=== Salvar Relatório Diário ===")
    filepath = service.save_report_to_file(report)
    print(f"Salvo com sucesso: {filepath}")
    
    # Teste de envio
    if service.is_available():
        print(f"\n=== Teste de Envio ({service.get_channel_names()}) ===")
        success = service.send(report)
        print(f"Resultado do envio: {'Sucesso' if success else 'Falha'}")
    else:
        print("\nCanais de notificação não configurados, pulando o teste de envio")
