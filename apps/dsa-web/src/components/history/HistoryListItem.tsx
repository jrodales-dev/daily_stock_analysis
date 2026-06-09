import type React from 'react';
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
    <div className={`flex items-center gap-2 group/wrapper relative transition-all duration-300 ${isEditing ? 'pl-1' : ''}`}>
      <div className={`transition-all duration-300 overflow-hidden flex items-center ${isEditing || isChecked ? 'w-6 opacity-100' : 'w-0 opacity-0 group-hover/wrapper:w-6 group-hover/wrapper:opacity-100'}`}>
        <input
          type="checkbox"
          checked={isChecked}
          onChange={() => onToggleChecked(item.id)}
          disabled={isDeleting}
          className="h-4 w-4 cursor-pointer rounded border-subtle bg-transparent accent-primary focus:ring-primary/40 disabled:opacity-50 transition-colors"
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
        className={`flex-1 text-left p-3 rounded-2xl border transition-all duration-300 group/item relative overflow-hidden ${
          isViewing 
            ? 'bg-primary/10 border-primary/40 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.1)]' 
            : 'bg-surface/30 border-subtle hover:bg-surface/60 hover:border-primary/20 hover:shadow-lg hover:-translate-y-0.5'
        }`}
      >
        {isViewing && (
          <div className="absolute inset-0 bg-gradient-to-r from-primary/5 to-transparent pointer-events-none" />
        )}
        <div className={`flex items-center gap-3 relative z-10${isTruncated ? ' group-hover/item:z-20' : ''}`}>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5">
              {sentimentColor && (
                <div
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{
                    backgroundColor: sentimentColor,
                    boxShadow: `0 0 8px ${sentimentColor}80`,
                  }}
                />
              )}
              <span className="truncate text-[13px] font-semibold text-foreground tracking-tight">
                <span className="group-hover/item:hidden">
                  {truncateStockName(stockName)}
                </span>
                <span className="hidden group-hover/item:inline">
                  {stockName}
                </span>
              </span>
            </div>
            
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-muted-text">
                <span className="px-1.5 py-0.5 rounded-md bg-background/50 border border-subtle text-[10px] font-mono tracking-wider shadow-sm">
                  {item.stockCode}
                </span>
                <span className="text-[10px] font-medium flex items-center gap-1 opacity-80">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {formatDateTime(item.createdAt)}
                </span>
              </div>
              
              {sentimentColor && (
                <div
                  className={`shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-full transition-all duration-300 ${isViewing ? 'opacity-100' : 'opacity-80 group-hover/item:opacity-100'}`}
                  style={{
                    color: sentimentColor,
                    backgroundColor: `${sentimentColor}15`,
                  }}
                >
                  {getOperationBadgeLabel(item.operationAdvice)}
                </div>
              )}
            </div>
          </div>
        </div>
      </button>
    </div>
  );
};
