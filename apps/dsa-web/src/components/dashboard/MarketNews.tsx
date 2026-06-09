import React from 'react';
import { useNews } from '../../hooks/useNews';
import { Card } from '../common';
import { Newspaper } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';

interface MarketNewsProps {
  ticker?: string;
  limit?: number;
  className?: string;
}

export const MarketNews: React.FC<MarketNewsProps> = ({ ticker, limit = 10, className = '' }) => {
  const { data: news, isLoading, error } = useNews(ticker, limit);

  if (isLoading) {
    return (
      <Card className={`p-6 flex flex-col gap-4 animate-pulse ${className}`}>
        <div className="h-6 w-48 bg-[var(--border-subtle)] rounded-md mb-4"></div>
        {[1, 2, 3].map(i => (
          <div key={i} className="flex gap-4 p-4 border border-[var(--border-subtle)] rounded-lg">
            <div className="flex-1 space-y-2">
              <div className="h-4 w-full bg-[var(--border-subtle)] rounded"></div>
              <div className="h-4 w-3/4 bg-[var(--border-subtle)] rounded"></div>
              <div className="h-3 w-32 bg-[var(--border-subtle)] rounded mt-4"></div>
            </div>
          </div>
        ))}
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={`p-6 text-red-500 bg-red-500/5 ${className}`}>
        Falha ao carregar as notícias. Tente novamente mais tarde.
      </Card>
    );
  }

  const getSentimentColor = (sentiment?: string) => {
    switch (sentiment) {
      case 'positive': return 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20';
      case 'negative': return 'text-red-500 bg-red-500/10 border-red-500/20';
      case 'neutral': return 'text-amber-500 bg-amber-500/10 border-amber-500/20';
      default: return 'text-[var(--secondary-text)] bg-[var(--surface)] border-[var(--border-subtle)]';
    }
  };

  const getSentimentLabel = (sentiment?: string) => {
    switch (sentiment) {
      case 'positive': return 'Positivo';
      case 'negative': return 'Negativo';
      case 'neutral': return 'Neutro';
      default: return 'Desconhecido';
    }
  };

  return (
    <Card className={`p-0 overflow-hidden flex flex-col h-full ${className}`}>
      <div className="p-5 border-b border-[var(--border-subtle)] flex items-center justify-between sticky top-0 bg-[var(--surface)] z-10">
        <div className="flex items-center gap-2 text-[var(--foreground)] font-semibold text-lg">
          <Newspaper className="w-5 h-5 text-blue-500" />
          {ticker ? `Notícias de ${ticker}` : 'Feed de Notícias Globais'}
        </div>
      </div>
      
      <div className="overflow-y-auto flex-1 p-5 space-y-4">
        {news && news.length > 0 ? (
          news.map((item) => (
            <a 
              key={item.id} 
              href={item.url} 
              target="_blank" 
              rel="noreferrer"
              className="block p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface)] hover:border-[var(--primary)] hover:shadow-sm transition-all group"
            >
              <div className="flex justify-between items-start gap-4 mb-2">
                <h3 className="font-semibold text-[var(--foreground)] group-hover:text-[var(--primary)] transition-colors line-clamp-2">
                  {item.title}
                </h3>
                {item.sentiment_label && (
                  <span className={`px-2 py-1 rounded text-xs font-semibold whitespace-nowrap border ${getSentimentColor(item.sentiment_label)}`}>
                    {getSentimentLabel(item.sentiment_label)}
                  </span>
                )}
              </div>
              
              <p className="text-sm text-[var(--secondary-text)] line-clamp-3 mb-4 leading-relaxed">
                {item.summary}
              </p>
              
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-3 text-[var(--secondary-text)]">
                  <span className="font-medium text-[var(--foreground)]">{item.source}</span>
                  <span>&bull;</span>
                  <span>{formatDistanceToNow(new Date(item.published_at), { addSuffix: true, locale: ptBR })}</span>
                </div>
                
                {item.related_tickers && item.related_tickers.length > 0 && (
                  <div className="flex items-center gap-1">
                    {item.related_tickers.map(t => (
                      <span key={t} className="px-1.5 py-0.5 bg-[var(--hover)] text-[var(--foreground)] rounded font-mono text-[10px]">
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </a>
          ))
        ) : (
          <div className="text-center py-10 text-[var(--secondary-text)]">
            Nenhuma notícia encontrada no momento.
          </div>
        )}
      </div>
    </Card>
  );
};
