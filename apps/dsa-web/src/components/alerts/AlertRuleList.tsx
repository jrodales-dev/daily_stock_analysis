import type React from 'react';
import { useState } from 'react';
import { Bell, Trash2 } from 'lucide-react';
import { Badge, Button, Card, ConfirmDialog, EmptyState, Pagination, Select } from '../common';
import type { AlertRuleItem, AlertType } from '../../types/alerts';
import { formatDateTime } from '../../utils/format';

export type AlertRuleEnabledFilter = 'all' | 'enabled' | 'disabled';
export type AlertTypeFilter = 'all' | AlertType;
export type AlertRuleBusyAction = 'test' | 'toggle' | 'delete';

export interface AlertRuleBusyState {
  id: number;
  action: AlertRuleBusyAction;
}

const ENABLED_FILTER_OPTIONS = [
  { value: 'all', label: 'Todos os Status' },
  { value: 'enabled', label: 'Ativado' },
  { value: 'disabled', label: 'Desativado' },
];

const ALERT_TYPE_FILTER_OPTIONS = [
  { value: 'all', label: 'Todos os Tipos' },
  { value: 'price_cross', label: 'Cruzamento de Preço' },
  { value: 'price_change_percent', label: 'Variação de Preço (%)' },
  { value: 'volume_spike', label: 'Aumento de Volume' },
  { value: 'ma_price_cross', label: 'Preço Cruza MA' },
  { value: 'rsi_threshold', label: 'Limite RSI' },
  { value: 'macd_cross', label: 'Cruzamento MACD' },
  { value: 'kdj_cross', label: 'Cruzamento KDJ' },
  { value: 'cci_threshold', label: 'Limite CCI' },
  { value: 'portfolio_stop_loss', label: 'Stop-Loss de Portfólio' },
  { value: 'portfolio_concentration', label: 'Concentração de Portfólio' },
  { value: 'portfolio_drawdown', label: 'Drawdown do Portfólio' },
  { value: 'portfolio_price_stale', label: 'Preços Obsoletos' },
  { value: 'market_light_status', label: 'Farol de Mercado' },
  { value: 'market_light_score_drop', label: 'Queda na Pontuação do Farol' },
];

const typeLabel: Record<AlertType, string> = {
  price_cross: 'Cruzamento de Preço',
  price_change_percent: 'Variação de Preço (%)',
  volume_spike: 'Aumento de Volume',
  ma_price_cross: 'Preço Cruza MA',
  rsi_threshold: 'Limite RSI',
  macd_cross: 'Cruzamento MACD',
  kdj_cross: 'Cruzamento KDJ',
  cci_threshold: 'Limite CCI',
  portfolio_stop_loss: 'Stop-Loss de Portfólio',
  portfolio_concentration: 'Concentração de Portfólio',
  portfolio_drawdown: 'Drawdown do Portfólio',
  portfolio_price_stale: 'Preços Obsoletos',
  market_light_status: 'Farol de Mercado',
  market_light_score_drop: 'Queda na Pontuação do Farol',
};

const severityLabel: Record<string, string> = {
  info: 'Info',
  warning: 'Aviso',
  critical: 'Crítico',
};

const scopeLabel: Record<string, string> = {
  single_symbol: 'Ação Única',
  watchlist: 'Lista de Ações (Watchlist)',
  portfolio_holdings: 'Posições Atuais',
  portfolio_account: 'Conta Específica',
  market: 'Mercado',
};

const marketRegionLabel: Record<string, string> = {
  cn: 'A-Share',
  hk: 'Ações HK',
  us: 'Ações US',
};

const marketLightStatusLabel: Record<string, string> = {
  yellow: 'Amarelo',
  red: 'Vermelho',
};

function formatParameters(rule: AlertRuleItem): string {
  if (rule.alertType === 'market_light_status') {
    const statuses = rule.parameters.statuses ?? [];
    return statuses.length > 0
      ? statuses.map((status) => marketLightStatusLabel[status] ?? status).join(' / ')
      : '--';
  }
  if (rule.alertType === 'market_light_score_drop') {
    return `Score diminuiu >= ${rule.parameters.minDrop ?? '--'}`;
  }
  if (rule.alertType === 'price_cross') {
    return `${rule.parameters.direction === 'below' ? 'Rompe Abaixo' : 'Rompe Acima'} ${rule.parameters.price ?? '--'}`;
  }
  if (rule.alertType === 'price_change_percent') {
    return `${rule.parameters.direction === 'down' ? 'Queda' : 'Alta'} ${rule.parameters.changePct ?? '--'}%`;
  }
  if (rule.alertType === 'volume_spike') {
    return `${rule.parameters.multiplier ?? '--'}x`;
  }
  if (rule.alertType === 'ma_price_cross') {
    return `${rule.parameters.direction === 'below' ? 'Cruza Abaixo' : 'Cruza Acima'} MA${rule.parameters.window ?? '--'}`;
  }
  if (rule.alertType === 'rsi_threshold') {
    return `RSI${rule.parameters.period ?? '--'} ${rule.parameters.direction === 'below' ? 'Cruza Abaixo' : 'Cruza Acima'} ${rule.parameters.threshold ?? '--'}`;
  }
  if (rule.alertType === 'macd_cross' || rule.alertType === 'kdj_cross') {
    const direction = rule.parameters.direction === 'bearish_cross' ? 'Cruzamento Baixa (Death)' : 'Cruzamento Alta (Golden)';
    if (rule.alertType === 'macd_cross') {
      return `MACD(${rule.parameters.fastPeriod ?? '--'},${rule.parameters.slowPeriod ?? '--'},${rule.parameters.signalPeriod ?? '--'}) ${direction}`;
    }
    return `KDJ(${rule.parameters.period ?? '--'},${rule.parameters.kPeriod ?? '--'},${rule.parameters.dPeriod ?? '--'}) ${direction}`;
  }
  if (rule.alertType === 'portfolio_stop_loss') {
    return rule.parameters.mode === 'breach' ? 'Stop-Loss Acionado' : 'Perto do Stop-Loss';
  }
  if (rule.alertType === 'portfolio_concentration') return 'top_weight_pct';
  if (rule.alertType === 'portfolio_drawdown') return 'max_drawdown_pct';
  if (rule.alertType === 'portfolio_price_stale') return 'price_stale / price_available';
  return `CCI${rule.parameters.period ?? '--'} ${rule.parameters.direction === 'below' ? 'Cruza Abaixo' : 'Cruza Acima'} ${rule.parameters.threshold ?? '--'}`;
}

function isCoolingDown(rule: AlertRuleItem): boolean {
  return rule.cooldownActive === true;
}

function formatTarget(rule: AlertRuleItem): string {
  if (rule.targetScope === 'market') return marketRegionLabel[rule.target] ?? rule.target;
  if (rule.targetScope === 'watchlist') return 'default';
  if (rule.targetScope === 'portfolio_account' || rule.targetScope === 'portfolio_holdings') {
    return rule.target === 'all' ? 'Todas as Contas' : `Conta ${rule.target}`;
  }
  return rule.target;
}

function hasChildTargetCooldown(rule: AlertRuleItem): boolean {
  return rule.targetScope === 'watchlist' || rule.targetScope === 'portfolio_holdings';
}

interface AlertRuleListProps {
  rules: AlertRuleItem[];
  total: number;
  page: number;
  pageSize: number;
  className?: string;
  isLoading?: boolean;
  enabledFilter: AlertRuleEnabledFilter;
  alertTypeFilter: AlertTypeFilter;
  onEnabledFilterChange: (value: AlertRuleEnabledFilter) => void;
  onAlertTypeFilterChange: (value: AlertTypeFilter) => void;
  onPageChange: (page: number) => void;
  onToggleEnabled: (rule: AlertRuleItem) => void;
  onDelete: (rule: AlertRuleItem) => void;
  onTest: (rule: AlertRuleItem) => void;
  busyRule?: AlertRuleBusyState | null;
}

export const AlertRuleList: React.FC<AlertRuleListProps> = ({
  rules,
  total,
  page,
  pageSize,
  className,
  isLoading = false,
  enabledFilter,
  alertTypeFilter,
  onEnabledFilterChange,
  onAlertTypeFilterChange,
  onPageChange,
  onToggleEnabled,
  onDelete,
  onTest,
  busyRule = null,
}) => {
  const [pendingDelete, setPendingDelete] = useState<AlertRuleItem | null>(null);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const isRuleBusy = (rule: AlertRuleItem) => busyRule?.id === rule.id;
  const isRuleActionBusy = (rule: AlertRuleItem, action: AlertRuleBusyAction) => (
    busyRule?.id === rule.id && busyRule.action === action
  );

  return (
    <Card title="Regras de Alerta" subtitle={`${total} regras`} variant="bordered" padding="md" className={className}>
      <div className="mb-4 grid gap-3 md:grid-cols-2">
        <Select
          label="Status de Ativação"
          value={enabledFilter}
          options={ENABLED_FILTER_OPTIONS}
          onChange={(value) => {
            onEnabledFilterChange(value as AlertRuleEnabledFilter);
          }}
        />
        <Select
          label="Tipo da Regra"
          value={alertTypeFilter}
          options={ALERT_TYPE_FILTER_OPTIONS}
          onChange={(value) => {
            onAlertTypeFilterChange(value as AlertTypeFilter);
          }}
        />
      </div>

      {rules.length === 0 ? (
        <div className="flex min-h-[220px] flex-1 items-center justify-center">
          <EmptyState
            icon={<Bell className="h-6 w-6" />}
            title={isLoading ? 'Carregando regras...' : 'Nenhuma regra de alerta encontrada'}
            description="Depois de criar a Regra, a avaliação no background irá analisar e checar as métricas continuamente."
          />
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-x-auto">
          <table className="w-full min-w-[960px] text-left text-sm">
            <thead className="border-b border-border/60 text-xs uppercase text-muted-text">
              <tr>
                <th className="px-3 py-2 font-medium">Regra</th>
                <th className="px-3 py-2 font-medium">Alvo</th>
                <th className="px-3 py-2 font-medium">Tipo</th>
                <th className="px-3 py-2 font-medium">Parâmetros</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Resfriamento</th>
                <th className="px-3 py-2 font-medium">Atualizado Em</th>
                <th className="px-3 py-2 text-right font-medium">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {rules.map((rule) => (
                <tr key={rule.id} className="align-top">
                  <td className="px-3 py-3">
                    <div className="font-medium text-foreground">{rule.name}</div>
                    <div className="mt-1 text-xs text-muted-text">Origem：{rule.source}</div>
                  </td>
                  <td className="px-3 py-3 text-secondary-text">
                    <div className="font-mono">{formatTarget(rule)}</div>
                    <div className="mt-1 text-xs">{scopeLabel[rule.targetScope] ?? rule.targetScope}</div>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-col items-start gap-1">
                      <Badge variant="info">{typeLabel[rule.alertType]}</Badge>
                      <Badge variant={rule.severity === 'critical' ? 'danger' : rule.severity === 'warning' ? 'warning' : 'default'}>
                        {severityLabel[rule.severity] ?? rule.severity}
                      </Badge>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-secondary-text">{formatParameters(rule)}</td>
                  <td className="px-3 py-3">
                    <Badge variant={rule.enabled ? 'success' : 'default'}>
                      {rule.enabled ? 'Ativado' : 'Desativado'}
                    </Badge>
                  </td>
                  <td className="px-3 py-3 text-xs text-secondary-text">
                    <div>{isCoolingDown(rule) ? 'Resfriando' : 'Sem Resfriamento'}</div>
                    <div className="mt-1">{formatDateTime(rule.cooldownUntil)}</div>
                    {hasChildTargetCooldown(rule) ? (
                      <div className="mt-1 text-muted-text">Sub-Alvo no Histórico</div>
                    ) : null}
                  </td>
                  <td className="px-3 py-3 text-xs text-secondary-text">{formatDateTime(rule.updatedAt ?? rule.createdAt)}</td>
                  <td className="px-3 py-3">
                    <div className="flex justify-end gap-2">
                      <Button
                        size="xsm"
                        variant="outline"
                        onClick={() => onTest(rule)}
                        isLoading={isRuleActionBusy(rule, 'test')}
                        loadingText="Testando"
                        disabled={isRuleBusy(rule) && !isRuleActionBusy(rule, 'test')}
                      >
                        Teste
                      </Button>
                      <Button
                        size="xsm"
                        variant={rule.enabled ? 'secondary' : 'primary'}
                        onClick={() => onToggleEnabled(rule)}
                        isLoading={isRuleActionBusy(rule, 'toggle')}
                        loadingText={rule.enabled ? 'Desativando' : 'Ativando'}
                        disabled={isRuleBusy(rule) && !isRuleActionBusy(rule, 'toggle')}
                      >
                        {rule.enabled ? 'Desativar' : 'Ativar'}
                      </Button>
                      <Button
                        size="xsm"
                        variant="danger-subtle"
                        aria-label={`Excluir ${rule.name}`}
                        onClick={() => setPendingDelete(rule)}
                        disabled={isRuleBusy(rule)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Excluir
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Pagination
        currentPage={page}
        totalPages={totalPages}
        onPageChange={onPageChange}
        className="mt-5"
      />

      <ConfirmDialog
        isOpen={pendingDelete != null}
        title="Excluir Regra de Alerta"
        message={pendingDelete ? `Deseja excluir a regra «${pendingDelete.name}»? A ação não afetará o histórico.` : ''}
        confirmText="Excluir"
        cancelText="Cancelar"
        isDanger
        onConfirm={() => {
          if (pendingDelete) {
            onDelete(pendingDelete);
          }
          setPendingDelete(null);
        }}
        onCancel={() => setPendingDelete(null)}
      />
    </Card>
  );
};
