import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { portfolioApi } from '../../api/portfolio';
import type {
  AlertRuleCreateRequest,
  AlertSeverity,
  AlertTargetScope,
  AlertType,
  MarketLightStatus,
  MarketRegion,
  PortfolioStopLossMode,
} from '../../types/alerts';
import type { PortfolioAccountItem } from '../../types/portfolio';
import { validateStockCode } from '../../utils/validation';
import { Button, Card, Checkbox, Input, Select } from '../common';

const SYMBOL_ALERT_TYPE_OPTIONS = [
  { value: 'price_cross', label: 'Cruzamento de Preço' },
  { value: 'price_change_percent', label: 'Variação de Preço (%)' },
  { value: 'volume_spike', label: 'Aumento de Volume' },
  { value: 'ma_price_cross', label: 'Preço Cruza MA' },
  { value: 'rsi_threshold', label: 'Limite RSI' },
  { value: 'macd_cross', label: 'Cruzamento MACD' },
  { value: 'kdj_cross', label: 'Cruzamento KDJ' },
  { value: 'cci_threshold', label: 'Limite CCI' },
];

const PORTFOLIO_ALERT_TYPE_OPTIONS = [
  { value: 'portfolio_stop_loss', label: 'Stop-Loss de Portfólio' },
  { value: 'portfolio_concentration', label: 'Concentração de Portfólio' },
  { value: 'portfolio_drawdown', label: 'Drawdown do Portfólio' },
  { value: 'portfolio_price_stale', label: 'Preços Obsoletos' },
];

const MARKET_ALERT_TYPE_OPTIONS = [
  { value: 'market_light_status', label: 'Farol de Mercado' },
  { value: 'market_light_score_drop', label: 'Queda na Pontuação do Farol' },
];

const TARGET_SCOPE_OPTIONS = [
  { value: 'single_symbol', label: 'Ação Única' },
  { value: 'watchlist', label: 'Lista de Ações (Watchlist)' },
  { value: 'portfolio_holdings', label: 'Posições Atuais' },
  { value: 'portfolio_account', label: 'Conta Específica' },
  { value: 'market', label: 'Mercado' },
];

const SEVERITY_OPTIONS = [
  { value: 'info', label: 'Info' },
  { value: 'warning', label: 'Aviso' },
  { value: 'critical', label: 'Crítico' },
];

const PRICE_DIRECTION_OPTIONS = [
  { value: 'above', label: 'Rompe Acima' },
  { value: 'below', label: 'Rompe Abaixo' },
];

const CHANGE_DIRECTION_OPTIONS = [
  { value: 'up', label: 'Sobe até' },
  { value: 'down', label: 'Cai até' },
];

const THRESHOLD_DIRECTION_OPTIONS = [
  { value: 'above', label: 'Cruza Acima' },
  { value: 'below', label: 'Cruza Abaixo' },
];

const CROSS_DIRECTION_OPTIONS = [
  { value: 'bullish_cross', label: 'Cruzamento Alta (Golden)' },
  { value: 'bearish_cross', label: 'Cruzamento Baixa (Death)' },
];

const STOP_LOSS_MODE_OPTIONS = [
  { value: 'near', label: 'Perto do Stop-Loss' },
  { value: 'breach', label: 'Stop-Loss Acionado' },
];

const MARKET_REGION_OPTIONS = [
  { value: 'cn', label: 'A-Share (cn)' },
  { value: 'hk', label: 'Ações HK (hk)' },
  { value: 'us', label: 'Ações US (us)' },
];

const MARKET_LIGHT_STATUS_OPTIONS: Array<{ value: MarketLightStatus; label: string }> = [
  { value: 'red', label: 'Vermelho' },
  { value: 'yellow', label: 'Amarelo' },
];

const MAX_REQUESTED_DAYS = 365;

interface AlertRuleFormProps {
  onSubmit: (payload: AlertRuleCreateRequest) => Promise<boolean | void> | boolean | void;
  isSubmitting?: boolean;
}

function isPortfolioScope(scope: AlertTargetScope): boolean {
  return scope === 'portfolio_holdings' || scope === 'portfolio_account';
}

function defaultAlertTypeForScope(scope: AlertTargetScope): AlertType {
  if (scope === 'market') return 'market_light_status';
  return scope === 'portfolio_account' ? 'portfolio_stop_loss' : 'price_cross';
}

function optionsForScope(scope: AlertTargetScope) {
  if (scope === 'market') return MARKET_ALERT_TYPE_OPTIONS;
  return scope === 'portfolio_account' ? PORTFOLIO_ALERT_TYPE_OPTIONS : SYMBOL_ALERT_TYPE_OPTIONS;
}

export const AlertRuleForm: React.FC<AlertRuleFormProps> = ({ onSubmit, isSubmitting = false }) => {
  const [name, setName] = useState('');
  const [targetScope, setTargetScope] = useState<AlertTargetScope>('single_symbol');
  const [target, setTarget] = useState('');
  const [portfolioTarget, setPortfolioTarget] = useState('all');
  const [marketRegion, setMarketRegion] = useState<MarketRegion>('cn');
  const [accounts, setAccounts] = useState<PortfolioAccountItem[]>([]);
  const [accountsError, setAccountsError] = useState<string | null>(null);
  const [alertType, setAlertType] = useState<AlertType>('price_cross');
  const [severity, setSeverity] = useState<AlertSeverity>('warning');
  const [enabled, setEnabled] = useState(true);
  const [priceDirection, setPriceDirection] = useState<'above' | 'below'>('above');
  const [changeDirection, setChangeDirection] = useState<'up' | 'down'>('up');
  const [thresholdDirection, setThresholdDirection] = useState<'above' | 'below'>('above');
  const [crossDirection, setCrossDirection] = useState<'bullish_cross' | 'bearish_cross'>('bullish_cross');
  const [stopLossMode, setStopLossMode] = useState<PortfolioStopLossMode>('near');
  const [price, setPrice] = useState('');
  const [changePct, setChangePct] = useState('');
  const [multiplier, setMultiplier] = useState('');
  const [window, setWindow] = useState('20');
  const [period, setPeriod] = useState('12');
  const [threshold, setThreshold] = useState('');
  const [fastPeriod, setFastPeriod] = useState('12');
  const [slowPeriod, setSlowPeriod] = useState('26');
  const [signalPeriod, setSignalPeriod] = useState('9');
  const [kPeriod, setKPeriod] = useState('3');
  const [dPeriod, setDPeriod] = useState('3');
  const [marketLightStatuses, setMarketLightStatuses] = useState<MarketLightStatus[]>(['red', 'yellow']);
  const [minDrop, setMinDrop] = useState('10');
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!isPortfolioScope(targetScope)) return undefined;
    let cancelled = false;
    void portfolioApi.getAccounts(false)
      .then((response) => {
        if (cancelled) return;
        setAccounts(response.accounts ?? []);
        setAccountsError(null);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setAccounts([]);
        setAccountsError(error instanceof Error ? error.message : 'Falha ao carregar a Conta');
      });
    return () => {
      cancelled = true;
    };
  }, [targetScope]);

  const alertTypeOptions = useMemo(() => optionsForScope(targetScope), [targetScope]);
  const portfolioTargetOptions = useMemo(() => [
    { value: 'all', label: 'Todas as Contas' },
    ...accounts.map((account) => ({
      value: String(account.id),
      label: `${account.name} #${account.id}`,
    })),
  ], [accounts]);

  const resetParameters = (nextType: AlertType) => {
    if (nextType === 'price_cross') {
      setPriceDirection('above');
      setPrice('');
    } else if (nextType === 'price_change_percent') {
      setChangeDirection('up');
      setChangePct('');
    } else if (nextType === 'volume_spike') {
      setMultiplier('');
    } else if (nextType === 'ma_price_cross') {
      setThresholdDirection('above');
      setWindow('20');
    } else if (nextType === 'rsi_threshold') {
      setThresholdDirection('above');
      setPeriod('12');
      setThreshold('');
    } else if (nextType === 'macd_cross') {
      setCrossDirection('bullish_cross');
      setFastPeriod('12');
      setSlowPeriod('26');
      setSignalPeriod('9');
    } else if (nextType === 'kdj_cross') {
      setCrossDirection('bullish_cross');
      setPeriod('9');
      setKPeriod('3');
      setDPeriod('3');
    } else if (nextType === 'cci_threshold') {
      setThresholdDirection('above');
      setPeriod('14');
      setThreshold('');
    } else if (nextType === 'portfolio_stop_loss') {
      setStopLossMode('near');
    } else if (nextType === 'market_light_status') {
      setMarketLightStatuses(['red', 'yellow']);
    } else if (nextType === 'market_light_score_drop') {
      setMinDrop('10');
    }
  };

  const toggleMarketLightStatus = (status: MarketLightStatus) => {
    setMarketLightStatuses((current) => (
      current.includes(status)
        ? current.filter((item) => item !== status)
        : [...current, status]
    ));
  };

  const parsePositiveNumber = (value: string, label: string): number | null => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setFormError(`${label}deve ser > 0`);
      return null;
    }
    return parsed;
  };

  const parseIntegerInRange = (value: string, label: string, min = 2, max = 250): number | null => {
    const parsed = Number(value);
    if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
      setFormError(`${label}deve ser ${min} a ${max} inteiro`);
      return null;
    }
    return parsed;
  };

  const parseFiniteNumber = (value: string, label: string): number | null => {
    if (value.trim() === '') {
      setFormError(`${label}não pode estar vazio`);
      return null;
    }
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      setFormError(`${label} deve ser um número válido`);
      return null;
    }
    return parsed;
  };

  const parseRsiThreshold = (value: string): number | null => {
    const parsed = parseFiniteNumber(value, 'Limite RSI');
    if (parsed == null) return null;
    if (parsed < 0 || parsed > 100) {
      setFormError('Limite de RSI deve estar entre 0 a 100');
      return null;
    }
    return parsed;
  };

  const ensureRequiredBarsWithinLimit = (label: string, requiredBars: number): boolean => {
    if (requiredBars > MAX_REQUESTED_DAYS) {
      setFormError(`O ciclo ${label} exige ${requiredBars} linhas diárias, com um máximo de ${MAX_REQUESTED_DAYS}`);
      return false;
    }
    return true;
  };

  const buildParameters = (): AlertRuleCreateRequest['parameters'] | null => {
    if (alertType === 'price_cross') {
      const parsedPrice = parsePositiveNumber(price, 'Preço Limite');
      if (parsedPrice == null) return null;
      return { direction: priceDirection, price: parsedPrice };
    }
    if (alertType === 'price_change_percent') {
      const parsedChangePct = parsePositiveNumber(changePct, 'Limiar de Variação de Preço (%)');
      if (parsedChangePct == null) return null;
      return { direction: changeDirection, changePct: parsedChangePct };
    }
    if (alertType === 'volume_spike') {
      const parsedMultiplier = parsePositiveNumber(multiplier, 'Múltiplo de Volume');
      if (parsedMultiplier == null) return null;
      return { multiplier: parsedMultiplier };
    }
    if (alertType === 'ma_price_cross') {
      const parsedWindow = parseIntegerInRange(window, 'Período MA');
      if (parsedWindow == null) return null;
      return { direction: thresholdDirection, window: parsedWindow };
    }
    if (alertType === 'rsi_threshold') {
      const parsedPeriod = parseIntegerInRange(period, 'Período RSI');
      const parsedThreshold = parseRsiThreshold(threshold);
      if (parsedPeriod == null || parsedThreshold == null) return null;
      return { direction: thresholdDirection, period: parsedPeriod, threshold: parsedThreshold };
    }
    if (alertType === 'macd_cross') {
      const parsedFast = parseIntegerInRange(fastPeriod, 'Período Linha Rápida');
      const parsedSlow = parseIntegerInRange(slowPeriod, 'Período Linha Lenta');
      const parsedSignal = parseIntegerInRange(signalPeriod, 'Período de Sinal');
      if (parsedFast == null || parsedSlow == null || parsedSignal == null) return null;
      if (parsedFast >= parsedSlow) {
        setFormError('Período Linha Rápida deve ser menor que o Período Linha Lenta');
        return null;
      }
      if (!ensureRequiredBarsWithinLimit('MACD', parsedSlow + parsedSignal + 1)) return null;
      return {
        direction: crossDirection,
        fastPeriod: parsedFast,
        slowPeriod: parsedSlow,
        signalPeriod: parsedSignal,
      };
    }
    if (alertType === 'kdj_cross') {
      const parsedPeriod = parseIntegerInRange(period, 'Período KDJ');
      const parsedK = parseIntegerInRange(kPeriod, 'Período Suavização K');
      const parsedD = parseIntegerInRange(dPeriod, 'Período Suavização D');
      if (parsedPeriod == null || parsedK == null || parsedD == null) return null;
      if (!ensureRequiredBarsWithinLimit('KDJ', parsedPeriod + parsedK + parsedD + 1)) return null;
      return { direction: crossDirection, period: parsedPeriod, kPeriod: parsedK, dPeriod: parsedD };
    }
    if (alertType === 'cci_threshold') {
      const parsedPeriod = parseIntegerInRange(period, 'Período CCI');
      const parsedThreshold = parseFiniteNumber(threshold, 'Limite CCI');
      if (parsedPeriod == null || parsedThreshold == null) return null;
      return { direction: thresholdDirection, period: parsedPeriod, threshold: parsedThreshold };
    }
    if (alertType === 'portfolio_stop_loss') {
      return { mode: stopLossMode };
    }
    if (alertType === 'market_light_status') {
      if (marketLightStatuses.length === 0) {
        setFormError('Selecione pelo menos uma cor do farol');
        return null;
      }
      return { statuses: marketLightStatuses };
    }
    if (alertType === 'market_light_score_drop') {
      const parsedMinDrop = parsePositiveNumber(minDrop, 'Queda na Pontuação');
      if (parsedMinDrop == null) return null;
      return { minDrop: parsedMinDrop };
    }
    return {};
  };

  const handleScopeChange = (value: string) => {
    const nextScope = value as AlertTargetScope;
    const nextType = defaultAlertTypeForScope(nextScope);
    setTargetScope(nextScope);
    setAlertType(nextType);
    setPortfolioTarget('all');
    setMarketRegion('cn');
    resetParameters(nextType);
    setFormError(null);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    let resolvedTarget = target.trim();
    if (targetScope === 'single_symbol') {
      const targetValidation = validateStockCode(target);
      if (!targetValidation.valid) {
        setFormError(targetValidation.message ?? 'Formato do código da ação inválido');
        return;
      }
      resolvedTarget = targetValidation.normalized;
    } else if (targetScope === 'watchlist') {
      resolvedTarget = 'default';
    } else if (targetScope === 'market') {
      resolvedTarget = marketRegion;
    } else {
      resolvedTarget = portfolioTarget;
    }

    const parameters = buildParameters();
    if (parameters == null) return;

    setFormError(null);
    const submitted = await onSubmit({
      name: name.trim() || undefined,
      targetScope,
      target: resolvedTarget,
      alertType,
      parameters,
      severity,
      enabled,
    });
    if (submitted === false) return;
    setName('');
    setTarget('');
    setPortfolioTarget('all');
    setMarketRegion('cn');
    setPrice('');
    setChangePct('');
    setMultiplier('');
    setWindow('20');
    setPeriod('12');
    setThreshold('');
    setFastPeriod('12');
    setSlowPeriod('26');
    setSignalPeriod('9');
    setKPeriod('3');
    setDPeriod('3');
    setMarketLightStatuses(['red', 'yellow']);
    setMinDrop('10');
    resetParameters(alertType);
    setEnabled(true);
  };

  const renderTargetControl = () => {
    if (targetScope === 'single_symbol') {
      return (
        <Input
          label="Código da Ação"
          value={target}
          onChange={(event) => setTarget(event.target.value)}
          placeholder="600519 / AAPL / hk00700"
          disabled={isSubmitting}
        />
      );
    }
    if (targetScope === 'watchlist') {
      return (
        <Input
          label="Alvo"
          value="default"
          onChange={() => undefined}
          disabled
        />
      );
    }
    if (targetScope === 'market') {
      return (
        <Select
          label="Mercado"
          value={marketRegion}
          options={MARKET_REGION_OPTIONS}
          disabled={isSubmitting}
          onChange={(value) => setMarketRegion(value as MarketRegion)}
        />
      );
    }
    return (
      <div className="space-y-2">
        <Select
          label="Conta"
          value={portfolioTarget}
          options={portfolioTargetOptions}
          disabled={isSubmitting}
          onChange={setPortfolioTarget}
        />
        {accountsError ? <p role="alert" className="text-xs text-warning">{accountsError}</p> : null}
      </div>
    );
  };

  return (
    <Card title="Criar Regra de Alerta" subtitle="Centro de Alertas Web" variant="bordered" padding="md">
      <form className="space-y-4" noValidate onSubmit={(event) => void handleSubmit(event)}>
        <div className="grid gap-4 md:grid-cols-2">
          <Input
            label="Nome da Regra"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Opcional, Exemplo: Cruzamento de Preço"
            disabled={isSubmitting}
          />
          <Select
            label="Escopo do Alvo"
            value={targetScope}
            options={TARGET_SCOPE_OPTIONS}
            disabled={isSubmitting}
            onChange={handleScopeChange}
          />
          {renderTargetControl()}
          <Select
            label="Tipo da Regra"
            value={alertType}
            options={alertTypeOptions}
            disabled={isSubmitting}
            onChange={(value) => {
              const nextType = value as AlertType;
              setAlertType(nextType);
              resetParameters(nextType);
            }}
          />
          <Select
            label="Nível Crítico"
            value={severity}
            options={SEVERITY_OPTIONS}
            disabled={isSubmitting}
            onChange={(value) => setSeverity(value as AlertSeverity)}
          />
        </div>

        {alertType === 'price_cross' ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Select
              label="Direção"
              value={priceDirection}
              options={PRICE_DIRECTION_OPTIONS}
              disabled={isSubmitting}
              onChange={(value) => setPriceDirection(value as 'above' | 'below')}
            />
            <Input
              label="Preço Limite"
              type="number"
              min="0"
              step="0.0001"
              value={price}
              onChange={(event) => setPrice(event.target.value)}
              disabled={isSubmitting}
            />
          </div>
        ) : null}

        {alertType === 'price_change_percent' ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Select
              label="Direção"
              value={changeDirection}
              options={CHANGE_DIRECTION_OPTIONS}
              disabled={isSubmitting}
              onChange={(value) => setChangeDirection(value as 'up' | 'down')}
            />
            <Input
              label="Limiar de Variação de Preço (%)"
              type="number"
              min="0"
              step="0.01"
              value={changePct}
              onChange={(event) => setChangePct(event.target.value)}
              disabled={isSubmitting}
            />
          </div>
        ) : null}

        {alertType === 'volume_spike' ? (
          <Input
            label="Múltiplo de Aumento de Volume"
            type="number"
            min="0"
            step="0.01"
            value={multiplier}
            onChange={(event) => setMultiplier(event.target.value)}
            disabled={isSubmitting}
          />
        ) : null}

        {alertType === 'ma_price_cross' ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Select
              label="Direção de Cruzamento"
              value={thresholdDirection}
              options={THRESHOLD_DIRECTION_OPTIONS}
              disabled={isSubmitting}
              onChange={(value) => setThresholdDirection(value as 'above' | 'below')}
            />
            <Input
              label="Período MA"
              type="number"
              min="2"
              max="250"
              step="1"
              value={window}
              onChange={(event) => setWindow(event.target.value)}
              disabled={isSubmitting}
            />
          </div>
        ) : null}

        {alertType === 'rsi_threshold' ? (
          <div className="grid gap-4 md:grid-cols-3">
            <Select
              label="Direção de Limiar"
              value={thresholdDirection}
              options={THRESHOLD_DIRECTION_OPTIONS}
              disabled={isSubmitting}
              onChange={(value) => setThresholdDirection(value as 'above' | 'below')}
            />
            <Input
              label="Período RSI"
              type="number"
              min="2"
              max="250"
              step="1"
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
              disabled={isSubmitting}
            />
            <Input
              label="Limite RSI"
              type="number"
              min="0"
              max="100"
              step="0.01"
              value={threshold}
              onChange={(event) => setThreshold(event.target.value)}
              disabled={isSubmitting}
            />
          </div>
        ) : null}

        {alertType === 'macd_cross' ? (
          <div className="grid gap-4 md:grid-cols-4">
            <Select
              label="Direção de Interseção"
              value={crossDirection}
              options={CROSS_DIRECTION_OPTIONS}
              disabled={isSubmitting}
              onChange={(value) => setCrossDirection(value as 'bullish_cross' | 'bearish_cross')}
            />
            <Input
              label="Período Linha Rápida"
              type="number"
              min="2"
              max="250"
              step="1"
              value={fastPeriod}
              onChange={(event) => setFastPeriod(event.target.value)}
              disabled={isSubmitting}
            />
            <Input
              label="Período Linha Lenta"
              type="number"
              min="2"
              max="250"
              step="1"
              value={slowPeriod}
              onChange={(event) => setSlowPeriod(event.target.value)}
              disabled={isSubmitting}
            />
            <Input
              label="Período de Sinal"
              type="number"
              min="2"
              max="250"
              step="1"
              value={signalPeriod}
              onChange={(event) => setSignalPeriod(event.target.value)}
              disabled={isSubmitting}
            />
          </div>
        ) : null}

        {alertType === 'kdj_cross' ? (
          <div className="grid gap-4 md:grid-cols-4">
            <Select
              label="Direção de Interseção"
              value={crossDirection}
              options={CROSS_DIRECTION_OPTIONS}
              disabled={isSubmitting}
              onChange={(value) => setCrossDirection(value as 'bullish_cross' | 'bearish_cross')}
            />
            <Input
              label="Período KDJ"
              type="number"
              min="2"
              max="250"
              step="1"
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
              disabled={isSubmitting}
            />
            <Input
              label="Período Suavização K"
              type="number"
              min="2"
              max="250"
              step="1"
              value={kPeriod}
              onChange={(event) => setKPeriod(event.target.value)}
              disabled={isSubmitting}
            />
            <Input
              label="Período Suavização D"
              type="number"
              min="2"
              max="250"
              step="1"
              value={dPeriod}
              onChange={(event) => setDPeriod(event.target.value)}
              disabled={isSubmitting}
            />
          </div>
        ) : null}

        {alertType === 'cci_threshold' ? (
          <div className="grid gap-4 md:grid-cols-3">
            <Select
              label="Direção de Limiar"
              value={thresholdDirection}
              options={THRESHOLD_DIRECTION_OPTIONS}
              disabled={isSubmitting}
              onChange={(value) => setThresholdDirection(value as 'above' | 'below')}
            />
            <Input
              label="Período CCI"
              type="number"
              min="2"
              max="250"
              step="1"
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
              disabled={isSubmitting}
            />
            <Input
              label="Limite CCI"
              type="number"
              step="0.01"
              value={threshold}
              onChange={(event) => setThreshold(event.target.value)}
              disabled={isSubmitting}
            />
          </div>
        ) : null}

        {alertType === 'portfolio_stop_loss' ? (
          <Select
            label="Modo de Stop-Loss"
            value={stopLossMode}
            options={STOP_LOSS_MODE_OPTIONS}
            disabled={isSubmitting}
            onChange={(value) => setStopLossMode(value as PortfolioStopLossMode)}
          />
        ) : null}

        {alertType === 'market_light_status' ? (
          <div className="space-y-2">
            <div className="text-sm font-medium text-foreground">Status de Disparo</div>
            <div className="grid gap-3 sm:grid-cols-2">
              {MARKET_LIGHT_STATUS_OPTIONS.map((option) => (
                <Checkbox
                  key={option.value}
                  label={option.label}
                  checked={marketLightStatuses.includes(option.value)}
                  disabled={isSubmitting}
                  onChange={() => toggleMarketLightStatus(option.value)}
                />
              ))}
            </div>
          </div>
        ) : null}

        {alertType === 'market_light_score_drop' ? (
          <Input
            label="Queda na Pontuação"
            type="number"
            min="0"
            max="100"
            step="1"
            value={minDrop}
            onChange={(event) => setMinDrop(event.target.value)}
            disabled={isSubmitting}
          />
        ) : null}

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Checkbox
            label="Ativar após Criação"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
            disabled={isSubmitting}
          />
          <Button type="submit" isLoading={isSubmitting} loadingText="Criando...">
            Criar Regra
          </Button>
        </div>
        {formError ? <p role="alert" className="text-sm text-danger">{formError}</p> : null}
      </form>
    </Card>
  );
};
