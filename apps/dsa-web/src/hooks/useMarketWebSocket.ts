import { useEffect, useRef } from 'react';
import { useMarketStore } from '../store/marketStore';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/market/stream';

export const useMarketWebSocket = () => {
  const ws = useRef<WebSocket | null>(null);
  const { setConnectionStatus, setQuote, activeSubscriptions } = useMarketStore();
  
  // Track previous subscriptions to know what to subscribe/unsubscribe
  const prevSubsRef = useRef<string[]>([]);

  useEffect(() => {
    // Initialize WebSocket
    ws.current = new WebSocket(WS_URL);

    ws.current.onopen = () => {
      setConnectionStatus(true);
      // Re-subscribe to all active subscriptions
      const currentSubs = useMarketStore.getState().activeSubscriptions;
      if (currentSubs.length > 0) {
        ws.current?.send(JSON.stringify({
          action: 'subscribe',
          symbols: currentSubs
        }));
      }
    };

    ws.current.onclose = () => {
      setConnectionStatus(false);
      // Implement basic reconnection logic here if needed
      setTimeout(() => {
        // Reconnect trigger
      }, 5000);
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'quote' && data.data) {
          setQuote(data.data.symbol, data.data);
        }
      } catch (err) {
        console.error('Error parsing WS message', err);
      }
    };

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [setConnectionStatus, setQuote]);

  // Handle subscriptions dynamically
  useEffect(() => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) return;

    const currentSubs = activeSubscriptions;
    const prevSubs = prevSubsRef.current;

    const added = currentSubs.filter(s => !prevSubs.includes(s));
    const removed = prevSubs.filter(s => !currentSubs.includes(s));

    if (added.length > 0) {
      ws.current.send(JSON.stringify({
        action: 'subscribe',
        symbols: added
      }));
    }

    if (removed.length > 0) {
      ws.current.send(JSON.stringify({
        action: 'unsubscribe',
        symbols: removed
      }));
    }

    prevSubsRef.current = currentSubs;
  }, [activeSubscriptions]);

  return { ws: ws.current };
};
