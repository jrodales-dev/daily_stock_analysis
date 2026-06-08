import type React from 'react';
import { Badge } from '../common';
import type { HistoryItem } from '../../types/analysis';
import { getSentimentColor } from '../../types/analysis';
import { formatDateTime } from '../../utils/format';
import { truncateStockName, isStockNameTruncated } from '../../utils/stockName';
import { localizeOperationAdvice } from '../../utils/reportLanguage';

interface HistoryListItemProps {
  item: HistoryItem;
  isViewing: boolean;
  isChecked: boolean;
  isEditing: boolean; // Indicates if the list is in edit mode
  isDeleting: boolean;
  onToggleChecked: (recordId: number) => void;
  onClick: (recordId: number) => void;
}

const getOperationBadgeLabel = (advice?: string) => {
  if (!advice?.trim()) return 'Sentimento';
  // Translate Chinese/English to Portuguese first
  const localized = localizeOperationAdvice(advice);
  // Match known Portuguese labels
  if (localized.includes('Forte Venda')) return 'Forte Venda';
  if (localized.includes('Vender') || localized.toLowerCase().includes('vend')) return 'Vender';
  if (localized.includes('Reduzir') || localized.toLowerCase().includes('reduz')) return 'Reduzir';
  if (localized.includes('Observar') || localized.toLowerCase().includes('observ') || localized.toLowerCase().includes('aguard')) return 'Observar';
  if (localized.includes('Manter') || localized.toLowerCase().includes('mant')) return 'Manter';
  if (localized.includes('Forte Compra')) return 'Forte Compra';
  if (localized.includes('Comprar') || localized.toLowerCase().includes('compr')) return 'Comprar';
  return localized.split(/[，。；、\s]/)[0] || 'Sugestão';
};

export const HistoryListItem: React.FC<HistoryListItemProps> = ({
  item,
  isViewing,
  isChecked,
  isEditing,
  isDeleting,
  onToggleChecked,
  onClick,
}) => {
  const sentimentColor = item.sentimentScore !== undefined ? getSentimentColor(item.sentimentScore) : null;
  const stockName = item.stockName || item.stockCode;
  const isTruncated = isStockNameTruncated(stockName);

  return (
    <div className={`flex items-stretch gap-2 group/wrapper relative transition-all duration-200 ${isEditing ? 'pl-1' : ''}`}>
      <div className={`pt-3 transition-all duration-200 overflow-hidden flex items-center ${isEditing || isChecked ? 'w-6 opacity-100' : 'w-0 opacity-0 group-hover/wrapper:w-6 group-hover/wrapper:opacity-100'}`}>
        <input
          type="checkbox"
          checked={isChecked}
          onChange={() => onToggleChecked(item.id)}
          disabled={isDeleting}
          className="h-4 w-4 cursor-pointer rounded border-subtle bg-transparent accent-primary focus:ring-primary/30 disabled:opacity-50 transition-colors"
        />
      </div>
      <button
        type="button"
        onClick={(e) => {
          if (isEditing) {
            e.preventDefault();
            onToggleChecked(item.id);
          } else {
            onClick(item.id);
          }
        }}
        className={`home-history-item flex-1 text-left p-3 rounded-xl border border-transparent transition-all duration-200 group/item ${
          isViewing ? 'home-history-item-selected bg-surface/80 border-border/50 shadow-sm' : 'hover:bg-surface/50 hover:border-border/30'
        }`}
      >
        <div className={`flex items-center gap-3 relative z-10${isTruncated ? ' group-hover/item:z-20' : ''}`}>
          {sentimentColor && (
            <div
              className="w-1 h-10 rounded-full flex-shrink-0 transition-all duration-300 group-hover/item:h-12"
              style={{
                backgroundColor: sentimentColor,
                boxShadow: `0 0 12px ${sentimentColor}50`,
              }}
            />
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2 mb-1">
              <div className="min-w-0 flex-1">
                <span className="truncate text-sm font-semibold text-foreground tracking-tight">
                  <span className="group-hover/item:hidden">
                    {truncateStockName(stockName)}
                  </span>
                  <span className="hidden group-hover/item:inline">
                    {stockName}
                  </span>
                </span>
              </div>
              {sentimentColor && (
                <Badge
                  variant="default"
                  size="sm"
                  className={`home-history-sentiment-badge shrink-0 shadow-none text-[11px] font-semibold leading-none transition-opacity duration-200${isTruncated ? ' group-hover/item:opacity-80' : ''}`}
                  style={{
                    color: sentimentColor,
                    borderColor: `${sentimentColor}30`,
                    backgroundColor: `${sentimentColor}10`,
                  }}
                >
                  {getOperationBadgeLabel(item.operationAdvice)} {item.sentimentScore}
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1.5 opacity-80 group-hover/item:opacity-100 transition-opacity">
              <span className="home-accent-chip px-1.5 py-0.5 text-[10px] font-mono tracking-wider">
                {item.stockCode}
              </span>
              <span className="text-[11px] text-muted-text font-medium flex items-center gap-1">
                <svg className="w-3 h-3 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {formatDateTime(item.createdAt)}
              </span>
            </div>
          </div>
        </div>
      </button>
    </div>
  );
};
