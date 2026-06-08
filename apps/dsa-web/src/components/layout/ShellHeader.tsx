import type React from 'react';
import { Menu, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { ThemeToggle } from '../theme/ThemeToggle';

type ShellHeaderProps = {
  collapsed: boolean;
  onToggleSidebar: () => void;
  onOpenMobileNav: () => void;
};

const TITLES: Record<string, { title: string; description: string }> = {
  '/': { title: 'Início', description: 'Área de Trabalho de Análises e Relatórios' },
  '/chat': { title: 'Chatbot', description: 'Múltiplas conversas com IA' },
  '/backtest': { title: 'Backtesting', description: 'Tarefas de Backtesting e Histórico' },
  '/settings': { title: 'Configurações', description: 'Configuração do sistema, modelos e autenticação' },
};

export const ShellHeader: React.FC<ShellHeaderProps> = ({
  collapsed,
  onToggleSidebar,
  onOpenMobileNav,
}) => {
  const location = useLocation();
  const current = TITLES[location.pathname] ?? { title: 'Daily Stock Analysis', description: 'Web workspace' };

  return (
    <header className="sticky top-0 z-30 border-b border-border/60 bg-background/84 backdrop-blur-xl">
      <div className="mx-auto flex h-16 w-full max-w-[1680px] items-center gap-3 px-4 sm:px-6 lg:px-8">
        <button
          type="button"
          onClick={onOpenMobileNav}
          className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-border/70 bg-card/70 text-secondary-text transition-colors hover:bg-hover hover:text-foreground lg:hidden"
          aria-label="Abrir Menu de Navegação"
        >
          <Menu className="h-5 w-5" />
        </button>

        <button
          type="button"
          onClick={onToggleSidebar}
          className="hidden h-10 w-10 items-center justify-center rounded-xl border border-border/70 bg-card/70 text-secondary-text transition-colors hover:bg-hover hover:text-foreground lg:inline-flex"
          aria-label={collapsed ? 'Expandir barra lateral' : 'Recolher barra lateral'}
        >
          {collapsed ? <PanelLeftOpen className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
        </button>

        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-foreground">{current.title}</p>
          <p className="truncate text-xs text-secondary-text">{current.description}</p>
        </div>

        <ThemeToggle />
      </div>
    </header>
  );
};
