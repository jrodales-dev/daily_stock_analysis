import React from 'react';
import type { AnalysisResult, AnalysisReport } from '../../types/analysis';
import { ReportOverview } from './ReportOverview';
import { ReportStrategy } from './ReportStrategy';
import { ReportNews } from './ReportNews';
import { ReportDetails } from './ReportDetails';
import { ReportDiagnostics } from './ReportDiagnostics';
import { AnalysisContextSummary } from './AnalysisContextSummary';
import { normalizeReportLanguage } from '../../utils/reportLanguage';

interface ReportSummaryProps {
  data: AnalysisResult | AnalysisReport;
  isHistory?: boolean;
}

/**
 * Componente Completo de Apresentação de Relatório
 * Mostra os resultados pela prioridade, da mais alta a transparência.
 */
export const ReportSummary: React.FC<ReportSummaryProps> = ({
  data,
  isHistory = false,
}) => {
  // Suporta formatos AnalysisResult e AnalysisReport
  const report: AnalysisReport = 'report' in data ? data.report : data;
  // O id do Relatório tem de ser utilizado para evitar duplicidade de IDs
  const recordId = report.meta.id;
  const diagnosticSummary = 'diagnosticSummary' in data ? data.diagnosticSummary : undefined;

  const { meta, summary, strategy, details } = report;
  const reportLanguage = normalizeReportLanguage(meta.reportLanguage);

  return (
    <div className="flex flex-col flex-1 space-y-5 pb-0 animate-fade-in">
      {/* Visão Geral (Tela Inicial) */}
      <ReportOverview
        meta={meta}
        summary={summary}
        details={details}
        isHistory={isHistory}
      />

      {/* Área de Estratégias */}
      <ReportStrategy strategy={strategy} language={reportLanguage} />

      {/* Área de Informações/Notícias */}
      <ReportNews recordId={recordId} limit={8} language={reportLanguage} />

      {/* Resumo não sensível */}
      <AnalysisContextSummary
        overview={details?.analysisContextPackOverview}
        language={reportLanguage}
      />

      {/* Resumo do diagnóstico */}
      <ReportDiagnostics
        recordId={recordId}
        summary={diagnosticSummary}
        language={reportLanguage}
      />

      {/* Rastreabilidade e Transparência */}
      <div className="mt-auto">
        <ReportDetails details={details} recordId={recordId} language={reportLanguage} />
      </div>

    </div>
  );
};
