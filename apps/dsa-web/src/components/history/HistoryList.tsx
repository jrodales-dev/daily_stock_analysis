import type React from 'react';
import { useRef, useCallback, useEffect, useId, useState } from 'react';
import type { HistoryItem } from '../../types/analysis';
import { Badge, Button, ScrollArea } from '../common';
import { DashboardPanelHeader, DashboardStateBlock } from '../dashboard';
import { HistoryListItem } from './HistoryListItem';

interface HistoryListProps {
  items: HistoryItem[];
  isLoading: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  selectedId?: number;  // ID selecionado no momento
  selectedIds: Set<number>;
  isDeleting?: boolean;
  onItemClick: (recordId: number) => void;  // Callback ao clicar
  onLoadMore: () => void;
  onToggleItemSelection: (recordId: number) => void;
  onToggleSelectAll: () => void;
  onDeleteSelected: () => void;
  className?: string;
}

/**
 * Componente de Lista de Histórico (Atualizado)
 * Implementação usando o novo sistema visual de Componentes, com suporte a Infinite Scrolling
 */
export const HistoryList: React.FC<HistoryListProps> = ({
  items,
  isLoading,
  isLoadingMore,
  hasMore,
  selectedId,
  selectedIds,
  isDeleting = false,
  onItemClick,
  onLoadMore,
  onToggleItemSelection,
  onToggleSelectAll,
  onDeleteSelected,
  className = '',
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const loadMoreTriggerRef = useRef<HTMLDivElement>(null);
  const selectAllRef = useRef<HTMLInputElement>(null);
  const selectAllId = useId();
  const [isEditing, setIsEditing] = useState(false);

  const selectedCount = items.filter((item) => selectedIds.has(item.id)).length;
  const allVisibleSelected = items.length > 0 && selectedCount === items.length;
  const someVisibleSelected = selectedCount > 0 && !allVisibleSelected;

  // IntersectionObserver que checa rolagem até o fim da página
  const handleObserver = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      const target = entries[0];
      if (target.isIntersecting && hasMore && !isLoading && !isLoadingMore) {
        const container = scrollContainerRef.current;
        if (container && container.scrollHeight > container.clientHeight) {
          onLoadMore();
        }
      }
    },
    [hasMore, isLoading, isLoadingMore, onLoadMore]
  );

  useEffect(() => {
    const trigger = loadMoreTriggerRef.current;
    const container = scrollContainerRef.current;
    if (!trigger || !container) return;

    const observer = new IntersectionObserver(handleObserver, {
      root: container,
      rootMargin: '20px',
      threshold: 0.1,
    });

    observer.observe(trigger);
    return () => observer.disconnect();
  }, [handleObserver]);

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someVisibleSelected;
    }
  }, [someVisibleSelected]);

  useEffect(() => {
    if (items.length === 0) {
      setIsEditing(false);
    }
  }, [items.length]);

  const toggleEditMode = () => {
    if (isEditing && selectedCount > 0) {
      // Clear selections when exiting edit mode
      items.forEach(item => {
        if (selectedIds.has(item.id)) {
          onToggleItemSelection(item.id);
        }
      });
    }
    setIsEditing(!isEditing);
  };

  const groupedItems = items.reduce((acc, item) => {
    const dateStr = new Date(item.createdAt).toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
    if (!acc[dateStr]) acc[dateStr] = [];
    acc[dateStr].push(item);
    return acc;
  }, {} as Record<string, HistoryItem[]>);

  const getDateGroupLabel = (dateStr: string) => {
    const todayStr = new Date().toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
    const yesterdayDate = new Date();
    yesterdayDate.setDate(yesterdayDate.getDate() - 1);
    const yesterdayStr = yesterdayDate.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });

    if (dateStr === todayStr) return 'Hoje';
    if (dateStr === yesterdayStr) return 'Ontem';
    return dateStr;
  };

  return (
    <aside className={`glass-card overflow-hidden flex flex-col ${className}`}>
      <ScrollArea
        viewportRef={scrollContainerRef}
        viewportClassName="p-4"
        testId="home-history-list-scroll"
      >
        <div className="mb-4 space-y-3">
          {!isEditing ? (
            <DashboardPanelHeader
              className="mb-1"
              title="Histórico de Análises"
              titleClassName="text-sm font-medium"
              leading={(
                <svg className="h-4 w-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              )}
              headingClassName="items-center"
              actions={
                items.length > 0 && (
                  <Button
                    variant="ghost"
                    size="xsm"
                    onClick={toggleEditMode}
                    className="text-muted-text hover:text-foreground text-xs"
                  >
                    Editar
                  </Button>
                )
              }
            />
          ) : (
            <div className="flex items-center justify-between gap-2 p-2 bg-surface rounded-xl border border-border shadow-sm animate-in fade-in slide-in-from-top-2">
              <label
                className="flex items-center gap-2 cursor-pointer px-1"
                htmlFor={selectAllId}
              >
                <input
                  id={selectAllId}
                  ref={selectAllRef}
                  type="checkbox"
                  checked={allVisibleSelected}
                  onChange={onToggleSelectAll}
                  disabled={isDeleting}
                  aria-label="Selecionar todos os históricos"
                  className="h-4 w-4 cursor-pointer rounded border-subtle bg-transparent accent-primary focus:ring-primary/30 transition-colors"
                />
                <span className="text-xs font-medium select-none">Tudo</span>
              </label>
              
              <div className="flex items-center gap-2">
                {selectedCount > 0 && (
                  <Badge variant="info" size="sm" className="shadow-none mr-1">
                    {selectedCount} selecionado(s)
                  </Badge>
                )}
                <Button
                  variant="danger"
                  size="xsm"
                  onClick={() => {
                    onDeleteSelected();
                    setIsEditing(false);
                  }}
                  disabled={selectedCount === 0 || isDeleting}
                  isLoading={isDeleting}
                  className="px-3"
                >
                  Excluir
                </Button>
                <Button
                  variant="ghost"
                  size="xsm"
                  onClick={toggleEditMode}
                  className="px-3"
                >
                  Concluído
                </Button>
              </div>
            </div>
          )}
        </div>

        {isLoading ? (
          <DashboardStateBlock
            loading
            compact
            title="Carregando histórico..."
          />
        ) : items.length === 0 ? (
          <DashboardStateBlock
            title="Nenhum histórico de análise"
            description="Após a primeira análise, os resultados recentes aparecerão aqui."
            icon={(
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            )}
          />
        ) : (
          <div className="space-y-4">
            {Object.entries(groupedItems).map(([dateStr, groupItems]) => (
              <div key={dateStr} className="space-y-2">
                <div className="sticky top-0 z-20 bg-background/95 backdrop-blur py-1.5 px-2">
                  <span className="text-xs font-semibold text-secondary-text uppercase tracking-widest">{getDateGroupLabel(dateStr)}</span>
                </div>
                <div className="space-y-1.5">
                  {groupItems.map((item) => (
                    <HistoryListItem
                      key={item.id}
                      item={item}
                      isViewing={selectedId === item.id}
                      isChecked={selectedIds.has(item.id)}
                      isEditing={isEditing}
                      isDeleting={isDeleting}
                      onToggleChecked={onToggleItemSelection}
                      onClick={onItemClick}
                    />
                  ))}
                </div>
              </div>
            ))}

            <div ref={loadMoreTriggerRef} className="h-4" />
            
            {isLoadingMore && (
              <div className="flex justify-center py-4">
                <div className="home-spinner h-5 w-5 animate-spin border-2" />
              </div>
            )}

            {!hasMore && items.length > 0 && (
              <div className="text-center py-5">
                <div className="h-px bg-subtle w-full mb-3" />
                <span className="text-[10px] text-secondary-text uppercase tracking-[0.2em]">FIM DA LISTA</span>
              </div>
            )}
          </div>
        )}
      </ScrollArea>
    </aside>
  );
};
