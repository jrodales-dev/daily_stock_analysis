import React, { useEffect, useState } from 'react';
import { BarChart3, Bell, BriefcaseBusiness, Home, LogOut, MessageSquareQuote, Search, Settings2, ChevronLeft, ChevronRight } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { ALPHASIFT_CONFIG_CHANGED_EVENT, SYSTEM_CONFIG_CHANGED_EVENT, alphasiftApi } from '../../api/alphasift';
import { useAuth } from '../../contexts/AuthContext';
import { useAgentChatStore } from '../../stores/agentChatStore';
import { cn } from '../../utils/cn';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { StatusDot } from '../common/StatusDot';
import { ThemeToggle } from '../theme/ThemeToggle';

type SidebarNavProps = {
  collapsed?: boolean;
  onNavigate?: () => void;
  onToggleCollapse?: () => void;
};

type NavItem = {
  key: string;
  label: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
  badge?: 'completion';
};

const NAV_ITEMS: NavItem[] = [
  { key: 'home', label: 'Início', to: '/', icon: Home, exact: true },
  { key: 'market', label: 'Mercado', to: '/market', icon: BarChart3 },
  { key: 'chat', label: 'Chat', to: '/chat', icon: MessageSquareQuote, badge: 'completion' },
  { key: 'screening', label: 'Triagem', to: '/screening', icon: Search },
  { key: 'portfolio', label: 'Portfólio (Alpaca)', to: '/portfolio', icon: BriefcaseBusiness },
  { key: 'portfolio_legacy', label: 'Portfólio (Manual)', to: '/portfolio-legacy', icon: BriefcaseBusiness },
  { key: 'backtest', label: 'Backtest', to: '/backtest', icon: BarChart3 },
  { key: 'alerts', label: 'Alertas', to: '/alerts', icon: Bell },
  { key: 'settings', label: 'Configurações', to: '/settings', icon: Settings2 },
];

export const SidebarNav: React.FC<SidebarNavProps> = ({ collapsed = false, onNavigate, onToggleCollapse }) => {
  const { authEnabled, logout } = useAuth();
  const completionBadge = useAgentChatStore((state) => state.completionBadge);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [showAlphaSiftNav, setShowAlphaSiftNav] = useState(false);

  useEffect(() => {
    let active = true;

    const refreshAlphaSiftStatus = async () => {
      try {
        const status = await alphasiftApi.getStatus();
        if (active) {
          setShowAlphaSiftNav(status.enabled);
        }
      } catch {
        if (active) {
          setShowAlphaSiftNav(false);
        }
      }
    };

    void refreshAlphaSiftStatus();
    window.addEventListener(ALPHASIFT_CONFIG_CHANGED_EVENT, refreshAlphaSiftStatus);
    window.addEventListener(SYSTEM_CONFIG_CHANGED_EVENT, refreshAlphaSiftStatus);

    return () => {
      active = false;
      window.removeEventListener(ALPHASIFT_CONFIG_CHANGED_EVENT, refreshAlphaSiftStatus);
      window.removeEventListener(SYSTEM_CONFIG_CHANGED_EVENT, refreshAlphaSiftStatus);
    };
  }, []);

  const navItems = showAlphaSiftNav ? NAV_ITEMS : NAV_ITEMS.filter((item) => item.key !== 'screening');

  return (
    <div className="flex h-full flex-col w-full min-w-0">
      <div className={cn('mb-4 flex items-center gap-2 px-1', collapsed ? 'justify-center' : '')}>
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary-gradient text-[hsl(var(--primary-foreground))] shadow-[0_12px_28px_var(--nav-brand-shadow)]">
          <BarChart3 className="h-5 w-5" />
        </div>
        {!collapsed ? (
          <p className="min-w-0 truncate text-sm font-semibold text-foreground">DSA</p>
        ) : null}
      </div>

      <nav className="flex flex-1 flex-col gap-1.5 overflow-y-auto overflow-x-hidden min-h-0 pr-1" aria-label="Main Navigation">
        {navItems.map(({ key, label, to, icon: Icon, exact, badge }) => (
          <NavLink
            key={key}
            to={to}
            end={exact}
            onClick={onNavigate}
            title={collapsed ? label : undefined}
            aria-label={label}
            className={({ isActive }) =>
              cn(
                'group relative flex items-center min-w-0 gap-3 text-sm transition-all duration-200 rounded-xl',
                collapsed ? 'h-10 w-10 justify-center mx-auto px-0' : 'h-[var(--nav-item-height)] w-full px-4',
                isActive
                  ? 'bg-primary/10 text-[hsl(var(--primary))] scale-[0.98]'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon className={cn('h-5 w-5 shrink-0 transition-colors', isActive ? 'text-[hsl(var(--primary))]' : 'text-current')} />
                {!collapsed ? <span className="truncate font-medium">{label}</span> : null}
                {badge === 'completion' && completionBadge ? (
                  <StatusDot
                    tone="info"
                    data-testid="chat-completion-badge"
                    className={cn(
                      'absolute right-3 border-2 border-background shadow-[0_0_10px_var(--nav-indicator-shadow)]',
                      collapsed ? 'right-2 top-2' : ''
                    )}
                    aria-label="New chat message"
                  />
                ) : null}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mt-4 mb-2 flex flex-col gap-2">
        <ThemeToggle variant="nav" collapsed={collapsed} />
      {authEnabled ? (
        <button
          type="button"
          onClick={() => setShowLogoutConfirm(true)}
          className={cn(
            'mt-5 flex h-11 w-full cursor-pointer select-none items-center gap-3 rounded-2xl border border-transparent px-3 text-sm text-secondary-text transition-all hover:border-border/70 hover:bg-hover hover:text-foreground',
            collapsed ? 'justify-center px-2' : ''
          )}
        >
          <LogOut className="h-5 w-5 shrink-0" />
          {!collapsed ? <span>Sair</span> : null}
        </button>
      ) : null}

      {onToggleCollapse && (
        <button
          type="button"
          onClick={onToggleCollapse}
          className="mt-2 flex h-11 w-full cursor-pointer select-none items-center justify-center rounded-2xl border border-transparent px-2 text-sm text-secondary-text transition-all hover:border-border/70 hover:bg-hover hover:text-foreground"
          title={collapsed ? 'Expandir Menu' : 'Minimizar Menu'}
          aria-label={collapsed ? 'Expandir Menu' : 'Minimizar Menu'}
        >
          {collapsed ? <ChevronRight className="h-5 w-5 shrink-0" /> : <ChevronLeft className="h-5 w-5 shrink-0" />}
        </button>
      )}

      <ConfirmDialog
        isOpen={showLogoutConfirm}
        title="Sair"
        message="Tem certeza que deseja sair? Você precisará inserir sua senha novamente para entrar."
        confirmText="Confirmar"
        cancelText="Cancelar"
        isDanger
        onConfirm={() => {
          setShowLogoutConfirm(false);
          onNavigate?.();
          void logout();
        }}
        onCancel={() => setShowLogoutConfirm(false)}
      />
      </div>
    </div>
  );
};
