import React, { useEffect, useRef } from 'react';
import { createChart, CandlestickSeries, LineSeries } from 'lightweight-charts';
import type { IChartApi, ISeriesApi, Time } from 'lightweight-charts';
import type { OhlcvData } from '../../api/market';
import { useUiStore } from '../../store/uiStore';

interface LightweightChartProps {
  data: OhlcvData[];
  type?: 'candlestick' | 'line';
  height?: number;
}

export const LightweightChart: React.FC<LightweightChartProps> = ({ 
  data, 
  type = 'candlestick',
  height = 400
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<any> | null>(null);
  const { theme } = useUiStore();

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Detect actual theme if system
    const isDark = theme === 'dark' || 
      (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

    const chartOptions = {
      layout: {
        background: { color: 'transparent' },
        textColor: isDark ? '#d1d5db' : '#374151',
      },
      grid: {
        vertLines: { color: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)' },
        horzLines: { color: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)' },
      },
      width: chartContainerRef.current.clientWidth,
      height: height,
    };

    const chart = createChart(chartContainerRef.current, chartOptions);
    chartRef.current = chart;

    if (type === 'candlestick') {
      const candlestickSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#10b981',
        downColor: '#ef4444',
        borderVisible: false,
        wickUpColor: '#10b981',
        wickDownColor: '#ef4444',
      });
      seriesRef.current = candlestickSeries;
    } else {
      const lineSeries = chart.addSeries(LineSeries, {
        color: '#3b82f6',
        lineWidth: 2,
      });
      seriesRef.current = lineSeries;
    }

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [theme, type, height]);

  // Update data
  useEffect(() => {
    if (seriesRef.current && data.length > 0) {
      const formattedData = data.map(item => ({
        time: item.time as Time,
        open: item.open,
        high: item.high,
        low: item.low,
        close: item.close,
        value: item.close // For line series
      }));
      seriesRef.current.setData(formattedData);
    }
  }, [data]);

  return <div ref={chartContainerRef} className="w-full" style={{ height }} />;
};
