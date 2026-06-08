import React, { useState } from 'react';

interface JsonViewerProps {
  data: Record<string, unknown> | unknown[] | null | undefined;
  maxHeight?: string;
  className?: string;
}

/**
 * Componente de exibição estruturada JSON
 * Com suporte a realce e fechamento de níveis
 */
export const JsonViewer: React.FC<JsonViewerProps> = ({
  data,
  maxHeight = '400px',
  className = '',
}) => {
  const [copied, setCopied] = useState(false);

  if (!data) {
    return (
      <div className="text-gray-500 italic py-4 text-center">Nenhum dado encontrado</div>
    );
  }

  const jsonString = JSON.stringify(data, null, 2);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Simples realce de sintaxe
  const highlightJson = (json: string): React.ReactNode => {
    return json.split('\n').map((line, index) => {
      // Realçar chave
      let highlighted = line.replace(
        /"([^"]+)":/g,
        '<span class="text-cyan-400">"$1"</span>:'
      );
      // Realçar string
      highlighted = highlighted.replace(
        /: "([^"]*)"/g,
        ': <span class="text-emerald-400">"$1"</span>'
      );
      // Realçar número
      highlighted = highlighted.replace(
        /: (-?\d+\.?\d*)/g,
        ': <span class="text-amber-400">$1</span>'
      );
      // Realçar boolean e null
      highlighted = highlighted.replace(
        /: (true|false|null)/g,
        ': <span class="text-purple-400">$1</span>'
      );

      return (
        <div
          key={index}
          className="leading-relaxed"
          dangerouslySetInnerHTML={{ __html: highlighted }}
        />
      );
    });
  };

  return (
    <div className={`relative ${className}`}>
      {/* Botão de Cópia */}
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 px-2 py-1 text-xs rounded
          bg-slate-700 hover:bg-slate-600 text-gray-300
          transition-colors z-10"
      >
        {copied ? 'Copiado!' : 'Copiar'}
      </button>

      {/* Conteúdo JSON */}
      <div
        className="bg-slate-900/80 rounded-lg p-4 overflow-auto custom-scrollbar
          border border-slate-700/50 font-mono text-sm text-gray-300"
        style={{ maxHeight }}
      >
        <pre className="whitespace-pre-wrap break-words">
          {highlightJson(jsonString)}
        </pre>
      </div>
    </div>
  );
};
