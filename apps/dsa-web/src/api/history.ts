import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  HistoryListResponse,
  HistoryItem,
  HistoryFilters,
  AnalysisReport,
  NewsIntelResponse,
  NewsIntelItem,
  RunDiagnosticSummary,
} from '../types/analysis';

// ============ Interface da API ============

export interface GetHistoryListParams extends HistoryFilters {
  page?: number;
  limit?: number;
}

export const historyApi = {
  /**
   * Obter a lista de histórico de análise
   * @param params Parâmetros de filtro e paginação
   */
  getList: async (params: GetHistoryListParams = {}): Promise<HistoryListResponse> => {
    const { page = 1, limit = 20 } = params;
    
    // Mocking response because history API was removed in the backend rewrite
    return {
      total: 0,
      page,
      limit,
      items: [],
    };
  },

  /**
   * Obter os detalhes do relatório histórico
   * @param recordId Chave primária do histórico de análise (usar ID em vez de query_id)
   */
  getDetail: async (recordId: number): Promise<AnalysisReport> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}`);
    return toCamelCase<AnalysisReport>(response.data);
  },

  /**
   * Obter as notícias associadas ao relatório histórico
   * @param recordId Chave primária do histórico de análise
   * @param limit Limite do número de retornos
   */
  getNews: async (recordId: number, limit = 20): Promise<NewsIntelResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}/news`, {
      params: { limit },
    });

    const data = toCamelCase<NewsIntelResponse>(response.data);
    return {
      total: data.total,
      items: (data.items || []).map(item => toCamelCase<NewsIntelItem>(item)),
    };
  },

  /**
   * Obter o conteúdo em formato Markdown do relatório
   * @param recordId Chave primária do histórico de análise
   * @returns O conteúdo completo do relatório em formato Markdown
   */
  getMarkdown: async (recordId: number): Promise<string> => {
    const response = await apiClient.get<{ content: string }>(`/api/v1/history/${recordId}/markdown`);
    return response.data.content;
  },

  /**
   * Obter o resumo do diagnóstico de execução do relatório histórico
   * @param recordId Chave primária do histórico de análise
   */
  getDiagnostics: async (recordId: number): Promise<RunDiagnosticSummary> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}/diagnostics`);
    return toCamelCase<RunDiagnosticSummary>(response.data);
  },

  /**
   * Excluir registros do histórico em lote
   * @param recordIds Lista de chaves primárias dos registros
   */
  deleteRecords: async (recordIds: number[]): Promise<{ deleted: number }> => {
    const response = await apiClient.delete<Record<string, unknown>>('/api/v1/history', {
      data: { record_ids: recordIds },
    });

    return toCamelCase<{ deleted: number }>(response.data);
  },
};
