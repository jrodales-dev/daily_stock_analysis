import type React from 'react';
import { ChevronDown, RefreshCw } from 'lucide-react';
import { Badge, Card, StatusDot } from '../common';
import { DashboardPanelHeader } from '../dashboard';
import type { TaskInfo } from '../../types/analysis';

/**
 * Propriedades de Tarefa
 */
interface TaskItemProps {
  task: TaskInfo;
}

/**
 * Tarefa Única
 */
const TaskItem: React.FC<TaskItemProps> = ({ task }) => {
  const isPending = task.status === 'pending';
  const isProcessing = task.status === 'processing';
  const statusLabel = isProcessing ? 'Analisando' : 'Aguardando';
  const statusVariant = isProcessing ? 'info' : 'default';
  const statusTone = isProcessing ? 'info' : 'neutral';
  const progress = Math.max(0, Math.min(100, task.progress || 0));
  const traceId = (task.traceId || '').trim();

  return (
    <div className="home-subpanel flex items-center gap-3 px-3 py-2.5">
      {/* Ícones de Estado */}
      <div className="shrink-0">
        {isProcessing ? (
          <StatusDot tone="info" pulse className="h-2.5 w-2.5" aria-label="Tarefa em andamento" />
        ) : isPending ? (
          <StatusDot tone="neutral" className="h-2.5 w-2.5" aria-label="Tarefa aguardando" />
        ) : null}
      </div>

      {/* Info sobre Processos */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground truncate">
            {task.stockName || task.stockCode}
          </span>
          <span className="text-xs text-muted-text">
            {task.stockCode}
          </span>
        </div>
        {task.message && (
          <p className="text-xs text-secondary-text truncate mt-0.5">
            {task.message}
          </p>
        )}
        <div className="mt-2 flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/8">
            <div
              className="h-full rounded-full bg-cyan transition-[width] duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="shrink-0 text-[11px] text-muted-text tabular-nums">
            {progress}%
          </span>
        </div>
        {traceId ? (
          <details className="group/task mt-2 text-xs">
            <summary className="flex cursor-pointer list-none items-center gap-2 text-muted-text">
              <span>Diagnóstico de execução</span>
              <span className="font-mono text-[11px] text-secondary-text">
                {traceId.length > 18 ? `${traceId.slice(0, 10)}...` : traceId}
              </span>
              <ChevronDown className="h-3.5 w-3.5 transition-transform group-open/task:rotate-180" aria-hidden="true" />
            </summary>
            <div className="mt-1 rounded-lg border border-subtle bg-base/50 px-2 py-1.5 text-muted-text">
              <span className="mr-1">Trace:</span>
              <code className="break-all font-mono text-[11px] text-secondary-text">
                {traceId}
              </code>
            </div>
          </details>
        ) : null}
      </div>

      {/* Etiquetas Lógicas */}
      <div className="flex-shrink-0">
        <Badge
          variant={statusVariant}
          className="min-w-[4.75rem] justify-center gap-1.5 shadow-none"
          aria-label={`Status da tarefa: ${statusLabel}`}
        >
          <StatusDot tone={statusTone} pulse={isProcessing} className="h-1.5 w-1.5" />
          {statusLabel}
        </Badge>
      </div>
    </div>
  );
};

/**
 * Propriedades do Painel
 */
interface TaskPanelProps {
  /** Lista de Tarefas */
  tasks: TaskInfo[];
  /** Deve Exibir */
  visible?: boolean;
  /** Título */
  title?: string;
  /** Classe CSS Customizada */
  className?: string;
}

/**
 * Componente Painel de Tarefas
 * Mostrar Lista de Tarefas Analíticas em Andamento
 */
export const TaskPanel: React.FC<TaskPanelProps> = ({
  tasks,
  visible = true,
  title = 'Tarefas de análise',
  className = '',
}) => {
  // Otimização que exibe Ativos (Processando ou Em Standby)
  const activeTasks = tasks.filter(
    (t) => t.status === 'pending' || t.status === 'processing'
  );

  // Oculta o DOM para salvar Rendering
  if (!visible || activeTasks.length === 0) {
    return null;
  }

  const pendingCount = activeTasks.filter((t) => t.status === 'pending').length;
  const processingCount = activeTasks.filter((t) => t.status === 'processing').length;

  return (
    <Card
      variant="bordered"
      padding="none"
      className={`home-panel-card overflow-hidden ${className}`}
    >
      <div className="border-b border-subtle px-3 py-3">
        <DashboardPanelHeader
          className="mb-0"
          title={title}
          titleClassName="text-sm font-medium"
          leading={(
            <RefreshCw className="h-4 w-4 text-cyan" aria-hidden="true" />
          )}
          headingClassName="items-center"
          actions={(
            <div className="flex items-center gap-2 text-xs text-muted-text">
              {processingCount > 0 && (
                <span className="flex items-center gap-1">
                  <StatusDot tone="info" pulse className="h-1.5 w-1.5" aria-label="Tarefas em andamento" />
                  {processingCount} em andamento
                </span>
              )}
              {pendingCount > 0 ? (
                <span className="flex items-center gap-1">
                  <StatusDot tone="neutral" className="h-1.5 w-1.5" aria-label="Tarefas aguardando" />
                  {pendingCount} aguardando
                </span>
              ) : null}
            </div>
          )}
        />
      </div>

      <div className="max-h-64 overflow-y-auto p-2">
        <div className="space-y-2">
          {activeTasks.map((task) => (
            <TaskItem key={task.taskId} task={task} />
          ))}
        </div>
      </div>
    </Card>
  );
};

export default TaskPanel;
