import camelcaseKeys from 'camelcase-keys';

/**
 * Converter chaves do objeto snake_case para camelCase
 * @param data Dados da resposta da API (snake_case)
 * @returns Objeto camelCase convertido
 */
export function toCamelCase<T>(data: unknown): T {
    if (data === null || data === undefined) {
        return data as T;
    }
    return camelcaseKeys(data as Record<string, unknown>, { deep: true }) as T;
}
