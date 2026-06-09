# -*- coding: utf-8 -*-
"""
===================================
A-Share Smart Stock Analysis System - Main Scheduler
===================================

Responsibilities:
1. Coordinate modules to complete the stock analysis workflow
2. Implement low-concurrency thread pool scheduling
3. Global exception handling to ensure single stock failure doesn't affect the whole
4. Provide a command-line entry point

Usage:
    python main.py              # Normal execution
    python main.py --debug      # Debug mode
    python main.py --dry-run    # Fetch data only, no analysis

Trading philosophy (integrated into analysis):
- Strict entry: Do not chase highs, do not buy if bias > 5%
- Trend trading: Only trade long setups MA5 > MA10 > MA20
- Efficiency first: Focus on stocks with good chip concentration
- Buying preference: Shrinking volume pulling back to MA5/MA10 support
"""
from __future__ import annotations

import multiprocessing
import sys
import os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from dotenv import dotenv_values
from src.config import setup_env

_INITIAL_PROCESS_ENV = dict(os.environ)
setup_env()

# Configuração de proxy - controlada pela variável de ambiente USE_PROXY, desativada por padrão
# O ambiente do GitHub Actions pula automaticamente a configuração de proxy
if os.getenv("GITHUB_ACTIONS") != "true" and os.getenv("USE_PROXY", "false").lower() == "true":
    # Ambiente de desenvolvimento local, habilita proxy (pode ser configurado no .env com PROXY_HOST e PROXY_PORT)
    proxy_host = os.getenv("PROXY_HOST", "127.0.0.1")
    proxy_port = os.getenv("PROXY_PORT", "10809")
    proxy_url = f"http://{proxy_host}:{proxy_port}"
    os.environ["http_proxy"] = proxy_url
    os.environ["https_proxy"] = proxy_url

import argparse
import logging
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta

from data_provider.base import canonical_stock_code
from src.webui_frontend import prepare_webui_frontend_assets
from src.config import get_config, Config
from src.logging_config import setup_logging


logger = logging.getLogger(__name__)
_RUNTIME_ENV_FILE_KEYS = set()


def _get_active_env_path() -> Path:
    env_file = os.getenv("ENV_FILE")
    if env_file:
        return Path(env_file)
    return Path(__file__).resolve().parent / ".env"


def _read_active_env_values() -> Optional[Dict[str, str]]:
    env_path = _get_active_env_path()
    if not env_path.exists():
        return {}

    try:
        values = dotenv_values(env_path)
    except Exception as exc:  # pragma: no cover - defensive branch
        logger.warning("Falha ao ler o arquivo de configuração %s, continuando com as variáveis de ambiente atuais: %s", env_path, exc)
        return None

    return {
        key: "" if value is None else value
        for key, value in values.items()
        if key is not None
    }


_ACTIVE_ENV_FILE_VALUES = _read_active_env_values() or {}
_RUNTIME_ENV_FILE_KEYS = {
    key for key in _ACTIVE_ENV_FILE_VALUES
    if key not in _INITIAL_PROCESS_ENV
}

# setup_env() already ran at import time above.
_env_bootstrapped = True


def _bootstrap_environment() -> None:
    """Load .env and apply optional local proxy settings.

    Guarded to be idempotent so it can safely be called from lazy-import
    paths used by API / bot consumers.
    """
    global _env_bootstrapped
    if _env_bootstrapped:
        return

    from src.config import setup_env

    setup_env()

    if os.getenv("GITHUB_ACTIONS") != "true" and os.getenv("USE_PROXY", "false").lower() == "true":
        proxy_host = os.getenv("PROXY_HOST", "127.0.0.1")
        proxy_port = os.getenv("PROXY_PORT", "10809")
        proxy_url = f"http://{proxy_host}:{proxy_port}"
        os.environ["http_proxy"] = proxy_url
        os.environ["https_proxy"] = proxy_url

    _env_bootstrapped = True


def _setup_bootstrap_logging(debug: bool = False) -> None:
    """Initialize stderr-only logging before config is loaded.

    File handlers are deferred until ``config.log_dir`` is known (via the
    subsequent ``setup_logging()`` call) so that healthy runs never create
    log files in a hard-coded directory.
    """
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    if not any(
        isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stderr
        for h in root.handlers
    ):
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(handler)


def _setup_runtime_logging(log_dir: str, debug: bool = False) -> bool:
    """Switch to configured logging, falling back to console on file I/O errors."""
    try:
        setup_logging(log_prefix="stock_analysis", debug=debug, log_dir=log_dir)
        return True
    except OSError as exc:
        logger.warning(
            "Falha na inicialização do log em arquivo, rebaixado para saída de log no console; o diretório de log %r não pode ser gravado ou criado no momento: %s. O ponto de entrada do contêiner Docker oficial corrigirá automaticamente as permissões do diretório de montagem padrão; se ainda falhar, verifique se há restrições de gravação no ambiente, como o uso de --user, montagem somente leitura, Docker rootless ou NFS.",
            log_dir,
            exc,
        )
        return False


def _get_stock_analysis_pipeline():
    """Lazily import StockAnalysisPipeline for external consumers.

    Also ensures env/proxy bootstrap has run so that API / bot consumers
    that never call ``main()`` still get ``USE_PROXY`` applied.
    """
    _bootstrap_environment()
    from src.core.pipeline import StockAnalysisPipeline as _Pipeline

    return _Pipeline


class _LazyPipelineDescriptor:
    """Descriptor that resolves StockAnalysisPipeline on first attribute access."""

    _resolved = None

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, obj, objtype=None):
        if self._resolved is None:
            self._resolved = _get_stock_analysis_pipeline()
        return self._resolved


class _ModuleExports:
    StockAnalysisPipeline = _LazyPipelineDescriptor()


_exports = _ModuleExports()


def __getattr__(name: str):
    if name == "StockAnalysisPipeline":
        return _exports.StockAnalysisPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _reload_env_file_values_preserving_overrides() -> None:
    """Refresh `.env`-managed env vars without clobbering process env overrides."""
    global _RUNTIME_ENV_FILE_KEYS

    latest_values = _read_active_env_values()
    if latest_values is None:
        return

    managed_keys = {
        key for key in latest_values
        if key not in _INITIAL_PROCESS_ENV
    }

    for key in _RUNTIME_ENV_FILE_KEYS - managed_keys:
        os.environ.pop(key, None)

    for key in managed_keys:
        os.environ[key] = latest_values[key]

    _RUNTIME_ENV_FILE_KEYS = managed_keys


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Smart Stock Analysis System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python main.py                    # Normal execution
  python main.py --debug            # Debug mode
  python main.py --dry-run          # Fetch data only, no AI analysis
  python main.py --stocks 600519,000001  # Specify stocks to analyze
  python main.py --no-notify        # Do not send push notifications
  python main.py --check-notify     # Check notification config only
  python main.py --single-notify    # Single-stock push mode (push immediately after each analysis)
  python main.py --schedule         # Scheduled task mode
  python main.py --market-review    # Run market review only
        '''
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode with detailed logs'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Fetch data only, no AI analysis'
    )

    parser.add_argument(
        '--stocks',
        type=str,
        help='Specify stocks to analyze, comma-separated (overrides config file)'
    )

    parser.add_argument(
        '--no-notify',
        action='store_true',
        help='Do not send push notifications'
    )

    parser.add_argument(
        '--check-notify',
        action='store_true',
        help='Read-only check notification channel config, do not send notifications'
    )

    parser.add_argument(
        '--single-notify',
        action='store_true',
        help='Enable single-stock push mode: push immediately after each analysis instead of aggregating'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='Number of concurrent threads (defaults to config value)'
    )

    parser.add_argument(
        '--schedule',
        action='store_true',
        help='Enable scheduled task mode, execute daily at set time'
    )

    parser.add_argument(
        '--no-run-immediately',
        action='store_true',
        help='Do not execute immediately upon starting scheduled task'
    )

    parser.add_argument(
        '--market-review',
        action='store_true',
        help='Run market review analysis only'
    )

    parser.add_argument(
        '--no-market-review',
        action='store_true',
        help='Skip market review analysis'
    )

    parser.add_argument(
        '--force-run',
        action='store_true',
        help='Skip trading day check, force full analysis execution'
    )

    parser.add_argument(
        '--webui',
        action='store_true',
        help='Start Web management interface'
    )

    parser.add_argument(
        '--webui-only',
        action='store_true',
        help='Start Web service only, do not run automatic analysis'
    )

    parser.add_argument(
        '--serve',
        action='store_true',
        help='Start FastAPI backend service (and execute analysis tasks)'
    )

    parser.add_argument(
        '--serve-only',
        action='store_true',
        help='Start FastAPI backend service only, do not run automatic analysis'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='FastAPI service port (default 8000)'
    )

    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='FastAPI service listening address (default 0.0.0.0)'
    )

    parser.add_argument(
        '--no-context-snapshot',
        action='store_true',
        help='Do not save analysis context snapshot'
    )

    # === Backtest ===
    parser.add_argument(
        '--backtest',
        action='store_true',
        help='Run backtest (evaluate historical analysis results)'
    )

    parser.add_argument(
        '--backtest-code',
        type=str,
        default=None,
        help='Backtest only specified stock code'
    )

    parser.add_argument(
        '--backtest-days',
        type=int,
        default=None,
        help='Backtest evaluation window (trading days, defaults to config)'
    )

    parser.add_argument(
        '--backtest-force',
        action='store_true',
        help='Force backtest (recalculate even if results exist)'
    )

    return parser.parse_args()


def _compute_trading_day_filter(
    config: Config,
    args: argparse.Namespace,
    stock_codes: List[str],
) -> Tuple[List[str], Optional[str], bool]:
    """
    Compute filtered stock list and effective market review region (Issue #373).

    Returns:
        (filtered_codes, effective_region, should_skip_all)
        - effective_region None = use config default (check disabled)
        - effective_region '' = all relevant markets closed, skip market review
        - should_skip_all: skip entire run when no stocks and no market review to run
    """
    force_run = getattr(args, 'force_run', False)
    if force_run or not getattr(config, 'trading_day_check_enabled', True):
        return (stock_codes, None, False)

    from src.core.trading_calendar import (
        get_market_for_stock,
        get_open_markets_today,
        compute_effective_region,
    )

    open_markets = get_open_markets_today()
    filtered_codes = []
    for code in stock_codes:
        mkt = get_market_for_stock(code)
        if mkt in open_markets or mkt is None:
            filtered_codes.append(code)

    if config.market_review_enabled and not getattr(args, 'no_market_review', False):
        effective_region = compute_effective_region(
            getattr(config, 'market_review_region', 'cn') or 'cn', open_markets
        )
    else:
        effective_region = None

    should_skip_all = (not filtered_codes) and (effective_region or '') == ''
    return (filtered_codes, effective_region, should_skip_all)


def _run_market_review_with_shared_lock(
    config: Config,
    run_market_review_func: Callable[..., Optional[str]],
    **kwargs: Any,
) -> Optional[str]:
    from src.core.market_review_lock import (
        release_market_review_lock,
        try_acquire_market_review_lock,
    )

    lock_token = try_acquire_market_review_lock(config)
    if lock_token is None:
        logger.warning("A análise de fechamento de mercado já está em execução, pulando esta execução")
        return None

    try:
        return run_market_review_func(**kwargs)
    finally:
        release_market_review_lock(lock_token)


def _refresh_stock_index_cache_for_analysis(config: Config) -> None:
    """Best-effort stock-index refresh for CLI/scheduled analysis paths."""
    try:
        from src.services.stock_index_remote_service import (
            refresh_remote_stock_index_cache,
            settings_from_config,
        )

        result = refresh_remote_stock_index_cache(settings_from_config(config))
        if result.refreshed:
            logger.info("[stock-index] Cache de índice de ações atualizado antes da análise: %s", result.cache_path)
        elif result.error:
            logger.debug("[stock-index] A atualização antes da análise não foi concluída, continuando com o índice local: %s", result.error)
    except Exception as exc:  # noqa: BLE001 - stock index freshness must not block analysis.
        logger.warning("[stock-index] Falha ao atualizar o índice de ações antes da análise, continuando com a execução da análise: %s", exc)


def run_full_analysis(
    config: Config,
    args: argparse.Namespace,
    stock_codes: Optional[List[str]] = None
):
    """
    Executa o fluxo completo de análise (ações individuais + fechamento de mercado)

    Esta é a função principal chamada pela tarefa agendada
    """
    # Import pipeline modules outside the broad try/except so that import-time
    # failures propagate to the caller instead of being silently swallowed.
    from src.core.market_review import run_market_review
    from src.core.pipeline import StockAnalysisPipeline

    try:
        _refresh_stock_index_cache_for_analysis(config)

        # Issue #529: Hot-reload STOCK_LIST from .env on each scheduled run
        if stock_codes is None:
            config.refresh_stock_list()

        # Issue #373: Trading day filter (per-stock, per-market)
        effective_codes = stock_codes if stock_codes is not None else config.stock_list
        filtered_codes, effective_region, should_skip = _compute_trading_day_filter(
            config, args, effective_codes
        )
        if should_skip:
            logger.info(
                "Hoje não é um dia de negociação em nenhum dos mercados relevantes, pulando a execução. Use --force-run para forçar a execução."
            )
            return
        if set(filtered_codes) != set(effective_codes):
            skipped = set(effective_codes) - set(filtered_codes)
            logger.info("Ações com mercado fechado hoje foram puladas: %s", skipped)
        stock_codes = filtered_codes

        # O argumento de linha de comando --single-notify substitui a configuração (#55)
        if getattr(args, 'single_notify', False):
            config.single_stock_notify = True

        # Ensure pipeline.py respects the CLI force_run flag for the economical fast path
        config.force_run = getattr(args, 'force_run', False)

        # Issue #190: Envio consolidado de análise de ações individuais e fechamento de mercado
        merge_notification = (
            getattr(config, 'merge_email_notification', False)
            and config.market_review_enabled
            and not getattr(args, 'no_market_review', False)
            and not config.single_stock_notify
        )

        # Criar agendador
        save_context_snapshot = None
        if getattr(args, 'no_context_snapshot', False):
            save_context_snapshot = False
        query_id = uuid.uuid4().hex
        pipeline = StockAnalysisPipeline(
            config=config,
            max_workers=args.workers,
            query_id=query_id,
            query_source="cli",
            save_context_snapshot=save_context_snapshot
        )

        # 1. Executar análise de ações individuais
        results = pipeline.run(
            stock_codes=stock_codes,
            dry_run=args.dry_run,
            send_notification=not args.no_notify,
            merge_notification=merge_notification
        )

        # Issue #128: Intervalo de análise - adiciona um atraso entre a análise de ações individuais e a análise de mercado
        analysis_delay = getattr(config, 'analysis_delay', 0)
        if (
            analysis_delay > 0
            and config.market_review_enabled
            and not args.no_market_review
            and effective_region != ''
        ):
            logger.info(f"Aguardando {analysis_delay} segundos antes de executar o fechamento de mercado (para evitar limite de taxa da API)...")
            time.sleep(analysis_delay)

        # 2. Executar fechamento de mercado (se ativado e não for o modo apenas ações individuais)
        market_report = ""
        if (
            config.market_review_enabled
            and not args.no_market_review
            and effective_region != ''
        ):
            review_result = _run_market_review_with_shared_lock(
                config,
                run_market_review,
                notifier=pipeline.notifier,
                analyzer=pipeline.analyzer,
                search_service=pipeline.search_service,
                send_notification=not args.no_notify,
                merge_notification=merge_notification,
                override_region=effective_region,
            )
            # Se houver resultados, atribui ao market_report para posterior geração de documentos do Feishu
            if review_result:
                market_report = review_result

        # Issue #190: Envio consolidado (ações individuais + fechamento de mercado)
        if merge_notification and (results or market_report) and not args.no_notify:
            parts = []
            if market_report:
                parts.append(f"# 📈 Fechamento de Mercado\n\n{market_report}")
            if results:
                dashboard_content = pipeline.notifier.generate_aggregate_report(
                    results,
                    getattr(config, 'report_type', 'simple'),
                )
                parts.append(f"# 🚀 Painel de Decisão de Ações Individuais\n\n{dashboard_content}")
            if parts:
                combined_content = "\n\n---\n\n".join(parts)
                if pipeline.notifier.is_available():
                    if pipeline.notifier.send(combined_content, email_send_to_all=True, route_type="report"):
                        logger.info("Envio consolidado realizado (ações individuais + fechamento de mercado)")
                    else:
                        logger.warning("Falha no envio consolidado")

        # Exibir resumo
        if results:
            logger.info("\n===== Analysis Summary =====")
            for r in sorted(results, key=lambda x: x.sentiment_score, reverse=True):
                emoji = r.get_emoji()
                logger.info(
                    f"{emoji} {r.name}({r.code}): {r.operation_advice} | "
                    f"Score {r.sentiment_score} | {r.trend_prediction}"
                )

        logger.info("\nTask execution completed")

        # === New: Generate Feishu Cloud Document ===
        try:
            from src.feishu_doc import FeishuDocManager

            feishu_doc = FeishuDocManager()
            if feishu_doc.is_configured() and (results or market_report):
                logger.info("Creating Feishu Cloud Document...")

                # 1. Prepare title
                tz_cn = timezone(timedelta(hours=8))
                now = datetime.now(tz_cn)
                doc_title = f"{now.strftime('%Y-%m-%d %H:%M')} Market Review"

                # 2. Prepare content
                full_content = ""

                # Add market review content (if any)
                if market_report:
                    full_content += f"# 📈 Market Review\n\n{market_report}\n\n---\n\n"

                # Add stock decision dashboard
                if results:
                    dashboard_content = pipeline.notifier.generate_aggregate_report(
                        results,
                        getattr(config, 'report_type', 'simple'),
                    )
                    full_content += f"# 🚀 Decision Dashboard\n\n{dashboard_content}"

                # 3. Create document
                doc_url = feishu_doc.create_daily_doc(doc_title, full_content)
                if doc_url:
                    logger.info(f"Feishu Cloud Document created successfully: {doc_url}")
                    # Optional: push document link to group
                    if not args.no_notify:
                        pipeline.notifier.send(
                            f"[{now.strftime('%Y-%m-%d %H:%M')}] Review document created successfully: {doc_url}",
                            route_type="report",
                        )

        except Exception as e:
            logger.error(f"Failed to generate Feishu document: {e}")

        # === Auto backtest ===
        try:
            if getattr(config, 'backtest_enabled', False):
                from src.services.backtest_service import BacktestService

                logger.info("Starting automatic backtest...")
                service = BacktestService()
                stats = service.run_backtest(
                    force=False,
                    eval_window_days=getattr(config, 'backtest_eval_window_days', 10),
                    min_age_days=getattr(config, 'backtest_min_age_days', 14),
                    limit=200,
                )
                logger.info(
                    f"Auto backtest completed: processed={stats.get('processed')} saved={stats.get('saved')} "
                    f"completed={stats.get('completed')} insufficient={stats.get('insufficient')} errors={stats.get('errors')}"
                )
        except Exception as e:
            logger.warning(f"Auto backtest failed (ignored): {e}")

    except Exception as e:
        logger.exception(f"Analysis pipeline execution failed: {e}")


def start_api_server(host: str, port: int, config: Config) -> None:
    """
    Inicia o serviço FastAPI em uma thread de segundo plano

    Args:
        host: Endereço de escuta
        port: Porta de escuta
        config: Objeto de configuração
    """
    import threading
    import uvicorn

    def run_server():
        level_name = (config.log_level or "INFO").lower()
        uvicorn.run(
            "api.app:app",
            host=host,
            port=port,
            log_level=level_name,
            log_config=None,
        )

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    logger.info(f"Serviço FastAPI iniciado: http://{host}:{port}")


def _is_truthy_env(var_name: str, default: str = "true") -> bool:
    """Parse common truthy / falsy environment values."""
    value = os.getenv(var_name, default).strip().lower()
    return value not in {"0", "false", "no", "off"}


def start_bot_stream_clients(config: Config) -> None:
    """Start bot stream clients when enabled in config."""
    # Iniciar cliente DingTalk Stream
    if config.dingtalk_stream_enabled:
        try:
            from bot.platforms import start_dingtalk_stream_background, DINGTALK_STREAM_AVAILABLE
            if DINGTALK_STREAM_AVAILABLE:
                if start_dingtalk_stream_background():
                    logger.info("[Main] Dingtalk Stream client started in background.")
                else:
                    logger.warning("[Main] Dingtalk Stream client failed to start.")
            else:
                logger.warning("[Main] Dingtalk Stream enabled but SDK is missing.")
                logger.warning("[Main] Run: pip install dingtalk-stream")
        except Exception as exc:
            logger.error(f"[Main] Failed to start Dingtalk Stream client: {exc}")

    # Iniciar cliente Feishu Stream
    if getattr(config, 'feishu_stream_enabled', False):
        try:
            from bot.platforms import start_feishu_stream_background, FEISHU_SDK_AVAILABLE
            if FEISHU_SDK_AVAILABLE:
                if start_feishu_stream_background():
                    logger.info("[Main] Feishu Stream client started in background.")
                else:
                    logger.warning("[Main] Feishu Stream client failed to start.")
            else:
                logger.warning("[Main] Feishu Stream enabled but SDK is missing.")
                logger.warning("[Main] Run: pip install lark-oapi")
        except Exception as exc:
            logger.error(f"[Main] Failed to start Feishu Stream client: {exc}")


def _resolve_scheduled_stock_codes(stock_codes: Optional[List[str]]) -> Optional[List[str]]:
    """Scheduled runs should always read the latest persisted watchlist."""
    if stock_codes is not None:
        logger.warning(
            "Parâmetro --stocks detectado no modo agendado; a execução planejada ignorará o snapshot de ações na inicialização e relerá a STOCK_LIST mais recente antes de cada execução."
        )
    return None


def _reload_runtime_config() -> Config:
    """Reload config from the latest persisted `.env` values for scheduled runs."""
    _reload_env_file_values_preserving_overrides()
    Config.reset_instance()
    return get_config()


def _build_schedule_time_provider(default_schedule_time: str):
    """Read the latest schedule time directly from the active config file.

    Fallback order:
    1. Process-level env override (set before launch) → honour it.
    2. Persisted config file value (written by WebUI) → use it.
    3. Documented system default ``"18:00"`` → always fall back here so
       that clearing SCHEDULE_TIME in WebUI correctly resets the schedule.
    """
    from src.core.config_manager import ConfigManager

    _SYSTEM_DEFAULT_SCHEDULE_TIME = "18:00"
    manager = ConfigManager()

    def _provider() -> str:
        if "SCHEDULE_TIME" in _INITIAL_PROCESS_ENV:
            return os.getenv("SCHEDULE_TIME", default_schedule_time)

        config_map = manager.read_config_map()
        schedule_time = (config_map.get("SCHEDULE_TIME", "") or "").strip()
        if schedule_time:
            return schedule_time
        return _SYSTEM_DEFAULT_SCHEDULE_TIME

    return _provider


def main() -> int:
    """
    Função de entrada principal

    Retorna:
        Código de saída (0 significa sucesso)
    """
    # Analisar argumentos de linha de comando
    args = parse_arguments()

    # Inicializar o log de bootstrap antes do carregamento da configuração para garantir que falhas iniciais sejam registradas
    try:
        _setup_bootstrap_logging(debug=args.debug)
    except Exception as exc:
        logging.basicConfig(
            level=logging.DEBUG if getattr(args, "debug", False) else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stderr,
        )
        logger.warning("Falha na inicialização do log de Bootstrap, revertido para stderr: %s", exc)

    # Carregar configuração (executado após o bootstrap logging para garantir que as exceções sejam registradas)
    try:
        config = get_config()
    except Exception as exc:
        logger.exception("Falha ao carregar a configuração: %s", exc)
        return 1

    # Configurar logs (saída para o console e arquivo)
    try:
        _setup_runtime_logging(config.log_dir, debug=args.debug)
    except Exception as exc:
        logger.exception("Falha ao alternar para o diretório de logs configurado: %s", exc)
        return 1

    logger.info("=" * 60)
    logger.info("Sistema Inteligente de Análise de Ações Classe A Iniciado")
    logger.info(f"Tempo de execução: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # Validar configuração
    warnings = config.validate()
    for warning in warnings:
        logger.warning(warning)

    if getattr(args, "check_notify", False):
        from src.services.notification_diagnostics import (
            format_notification_diagnostics,
            run_notification_diagnostics,
        )

        result = run_notification_diagnostics(config)
        print(format_notification_diagnostics(result))
        return 0 if result.ok else 1

    # Analisar lista de ações (padronizar para maiúsculas Issue #355)
    stock_codes = None
    if args.stocks:
        stock_codes = [canonical_stock_code(c) for c in args.stocks.split(',') if (c or "").strip()]
        logger.info(f"Usando a lista de ações especificada pela linha de comando: {stock_codes}")

    # === Processar parâmetros --webui / --webui-only, mapeando para --serve / --serve-only ===
    if args.webui:
        args.serve = True
    if args.webui_only:
        args.serve_only = True

    # Compatibilidade com a variável de ambiente antiga WEBUI_ENABLED
    if config.webui_enabled and not (args.serve or args.serve_only):
        args.serve = True

    # === Iniciar serviço Web (se ativado) ===
    start_serve = (args.serve or args.serve_only) and os.getenv("GITHUB_ACTIONS") != "true"

    # Compatibilidade com WEBUI_HOST/WEBUI_PORT antigos: se o usuário não especificou via --host/--port, usa as variáveis antigas
    if start_serve:
        webui_host = os.getenv('WEBUI_HOST')
        if args.host == '0.0.0.0' and webui_host:
            args.host = webui_host
            
        webui_port = os.getenv('WEBUI_PORT')
        if args.port == 8000 and webui_port:
            args.port = int(webui_port)

    bot_clients_started = False
    if start_serve:
        if not prepare_webui_frontend_assets():
            logger.warning("Recursos estáticos do frontend não estão prontos, continuando a iniciar o serviço FastAPI (a página Web pode não estar disponível)")
        try:
            start_api_server(host=args.host, port=args.port, config=config)
            bot_clients_started = True
        except Exception as e:
            logger.error(f"Falha ao iniciar o serviço FastAPI: {e}")

    if bot_clients_started:
        start_bot_stream_clients(config)

    # === Modo apenas serviço Web: não executa análise automática ===
    if args.serve_only:
        logger.info("Modo: Apenas serviço Web")
        logger.info(f"Serviço Web em execução: http://{args.host}:{args.port}")
        logger.info("Dispare a análise através do endpoint /api/v1/analysis/analyze")
        logger.info(f"Documentação da API: http://{args.host}:{args.port}/docs")
        logger.info("Pressione Ctrl+C para sair...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\nInterrompido pelo usuário, encerrando o programa")
        return 0

    try:
        # Modo 0: Backtest
        if getattr(args, 'backtest', False):
            logger.info("Modo: Backtest")
            from src.services.backtest_service import BacktestService

            service = BacktestService()
            stats = service.run_backtest(
                code=getattr(args, 'backtest_code', None),
                force=getattr(args, 'backtest_force', False),
                eval_window_days=getattr(args, 'backtest_days', None),
            )
            logger.info(
                f"Backtest concluído: processed={stats.get('processed')} saved={stats.get('saved')} "
                f"completed={stats.get('completed')} insufficient={stats.get('insufficient')} errors={stats.get('errors')}"
            )
            return 0

        # Modo 1: Apenas fechamento de mercado
        if args.market_review:
            from src.core.market_review import run_market_review
            from src.core.market_review_runtime import build_market_review_runtime

            # Issue #373: Trading day check for market-review-only mode.
            # Do NOT use _compute_trading_day_filter here: that helper checks
            # config.market_review_enabled, which would wrongly block an
            # explicit --market-review invocation when the flag is disabled.
            effective_region = None
            if not getattr(args, 'force_run', False) and getattr(config, 'trading_day_check_enabled', True):
                from src.core.trading_calendar import get_open_markets_today, compute_effective_region as _compute_region
                open_markets = get_open_markets_today()
                effective_region = _compute_region(
                    getattr(config, 'market_review_region', 'cn') or 'cn', open_markets
                )
                if effective_region == '':
                    logger.info("Hoje não é um dia de negociação nos mercados relevantes para o fechamento de mercado, pulando a execução. Use --force-run para forçar a execução.")
                    return 0

            logger.info("Modo: Apenas fechamento de mercado")
            notifier, analyzer, search_service = build_market_review_runtime(config)

            _run_market_review_with_shared_lock(
                config,
                run_market_review,
                notifier=notifier,
                analyzer=analyzer,
                search_service=search_service,
                send_notification=not args.no_notify,
                override_region=effective_region,
            )
            return 0

        # Modo 2: Modo de tarefa agendada
        if args.schedule or config.schedule_enabled:
            logger.info("Modo: Tarefa agendada")
            logger.info(f"Horário de execução diária: {config.schedule_time}")

            # Determine whether to run immediately:
            # Command line arg --no-run-immediately overrides config if present.
            # Otherwise use config (defaults to True).
            should_run_immediately = config.schedule_run_immediately
            if getattr(args, 'no_run_immediately', False):
                should_run_immediately = False

            logger.info(f"Executar imediatamente na inicialização: {should_run_immediately}")

            from src.scheduler import run_with_schedule
            scheduled_stock_codes = _resolve_scheduled_stock_codes(stock_codes)
            schedule_time_provider = _build_schedule_time_provider(config.schedule_time)

            def scheduled_task():
                runtime_config = _reload_runtime_config()
                run_full_analysis(runtime_config, args, scheduled_stock_codes)

            background_tasks = []
            if getattr(config, 'agent_event_monitor_enabled', False):
                from src.services.alert_worker import AlertWorker

                interval_minutes = max(1, getattr(config, 'agent_event_monitor_interval_minutes', 5))
                alert_worker = AlertWorker(config_provider=_reload_runtime_config)

                def event_monitor_task():
                    stats = alert_worker.run_once()
                    triggered_count = stats.get("triggered", 0)
                    if triggered_count:
                        logger.info("[EventMonitor] Esta rodada disparou %d alertas", triggered_count)

                background_tasks.append({
                    "task": event_monitor_task,
                    "interval_seconds": interval_minutes * 60,
                    "run_immediately": True,
                    "name": "agent_event_monitor",
                })

            run_with_schedule(
                task=scheduled_task,
                schedule_time=config.schedule_time,
                run_immediately=should_run_immediately,
                background_tasks=background_tasks,
                schedule_time_provider=schedule_time_provider,
            )
            return 0

        # Modo 3: Execução única normal
        if config.run_immediately:
            if start_serve and not getattr(args, 'force_run', False):
                logger.info("Executando análise inicial (será ignorada se já houver análise hoje; use --force-run para reanalisar)...")
            run_full_analysis(config, args, stock_codes)
        else:
            logger.info("Configurado para não executar a análise imediatamente (RUN_IMMEDIATELY=false)")

        logger.info("\nExecução do programa concluída")

        # Se o serviço estiver ativado e não for o modo de tarefa agendada, mantém o programa em execução
        keep_running = start_serve and not (args.schedule or config.schedule_enabled)
        if keep_running:
            logger.info("Serviço API em execução (Pressione Ctrl+C para sair)...")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

        return 0

    except KeyboardInterrupt:
        logger.info("\nInterrompido pelo usuário, encerrando o programa")
        return 130

    except Exception as e:
        logger.exception(f"Falha na execução do programa: {e}")
        return 1


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())