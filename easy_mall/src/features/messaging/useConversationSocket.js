import { useEffect, useRef, useState } from "react";
import { API_BASE_URL, getAccessToken } from "../../lib/apiClient";

const WS_BASE_URL = API_BASE_URL.replace(/^http/, "ws").replace(/\/api\/v1\/?$/, "");

/**
 * Connexion WebSocket temps réel à une conversation — remplace le polling
 * HTTP. Se reconnecte automatiquement (délai croissant, plafonné à 15s) si
 * la connexion tombe, ce qui arrive facilement sur un réseau mobile.
 *
 * `onMessage` est appelé pour chaque message reçu (y compris ceux qu'on a
 * soi-même envoyés : le serveur les redistribue à tout le groupe).
 */
export function useConversationSocket(conversationId, onMessage) {
  const [connected, setConnected] = useState(false);
  const socketRef = useRef(null);
  const retryDelayRef = useRef(1000);
  const reconnectAttemptsRef = useRef(0);
  const closedByUserRef = useRef(false);
  const reconnectTimerRef = useRef(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!conversationId) return undefined;
    closedByUserRef.current = false;
    reconnectAttemptsRef.current = 0;

    function scheduleReconnect() {
      if (closedByUserRef.current) return;
      reconnectAttemptsRef.current += 1;
      reconnectTimerRef.current = setTimeout(connect, retryDelayRef.current);
      retryDelayRef.current = Math.min(retryDelayRef.current * 2, 15000);
    }

    function connect() {
      if (closedByUserRef.current) return;
      const token = getAccessToken();
      if (!token) {
        scheduleReconnect();
        return;
      }

      const socket = new WebSocket(`${WS_BASE_URL}/ws/messaging/${conversationId}/?token=${token}`);
      socketRef.current = socket;

      socket.onopen = () => {
        setConnected(true);
        retryDelayRef.current = 1000;
        reconnectAttemptsRef.current = 0;
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "message_deleted") {
            onMessageRef.current(payload);
            return;
          }
          onMessageRef.current(payload);
        } catch {
          // message non-JSON ignoré
        }
      };

      socket.onclose = () => {
        if (socketRef.current === socket) {
          setConnected(false);
          scheduleReconnect();
        }
      };

      socket.onerror = () => socket.close();
    }

    connect();

    return () => {
      closedByUserRef.current = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      socketRef.current?.close();
    };
  }, [conversationId]);

  function send(payload) {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }

  return { connected, send };
}
