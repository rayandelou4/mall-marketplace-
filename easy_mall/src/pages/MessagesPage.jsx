import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { ArrowDown, ArrowLeft, Check, CheckCheck, CheckSquare, Flag, MoreVertical, RefreshCw, Search, Send, MapPin, Trash2, X, Pencil, CornerUpLeft, Mic, Square, MessageCircle } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { LoadingBlock, ErrorBlock, SectionHeading } from "../components/ui/StatusBlocks";
import { useTheme } from "../features/theme/ThemeContext";
import { useAuth } from "../features/auth/AuthContext";
import { clearMessages, deleteMessage, fetchConversations, fetchMessages, hideConversation, sendMessage, startConversation, updateMessage } from "../features/messaging/api";
import { useConversationSocket } from "../features/messaging/useConversationSocket";
import { createMessageReport } from "../features/moderation/api";
import { createWhatsAppUrl } from "../lib/whatsapp";
import { cx } from "../styles/theme";

function getInitials(username) {
  return username?.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase() || "?";
}

function formatTime(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function formatDay(value) {
  if (!value) return "";
  const date = new Date(value);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return "Aujourd’hui";
  if (date.toDateString() === yesterday.toDateString()) return "Hier";
  return new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric" }).format(date);
}

function isSameDay(first, second) {
  return first && second && new Date(first).toDateString() === new Date(second).toDateString();
}

function isWithinEditWindow(message, now) {
  return Boolean(message?.created_at) && now < new Date(message.created_at).getTime() + 5 * 60 * 1000;
}

function getMessagePreview(message) {
  if (message.is_deleted_for_all) return "Ce message a été supprimé";
  return message.content
    || (message.voice_url ? "Message vocal" : "")
    || (message.image_url ? "Image" : "")
    || (message.location_lat != null ? "Position partagée" : "")
    || "Nouveau message";
}

function getRecordingErrorMessage(error) {
  switch (error?.name) {
    case "NotFoundError":
    case "DevicesNotFoundError":
      return "Aucun microphone détecté. Branchez ou réparez un micro pour enregistrer un vocal.";
    case "NotAllowedError":
    case "PermissionDeniedError":
      return "L'accès au microphone est refusé. Autorisez-le dans les réglages du navigateur.";
    case "NotReadableError":
    case "TrackStartError":
      return "Le microphone est détecté, mais il est inaccessible. Vérifiez qu'aucune autre application ne l'utilise.";
    case "SecurityError":
      return "L'accès au microphone nécessite une page sécurisée (HTTPS ou localhost).";
    case "OverconstrainedError":
    case "ConstraintNotSatisfiedError":
      return "Aucun microphone ne correspond aux capacités requises par le navigateur.";
    default:
      return "Impossible d'accéder au microphone. Vérifiez qu'un micro est branché et autorisé.";
  }
}

export default function MessagesPage() {
  const { t } = useTheme();
  const { isAuthenticated, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { id: routeConversationId } = useParams();

  const [conversations, setConversations] = useState({ loading: true, error: null, items: [] });
  const [messages, setMessages] = useState({ loading: false, error: null, items: [] });
  const [draft, setDraft] = useState("");
  const [conversationSearch, setConversationSearch] = useState("");
  const [sending, setSending] = useState(false);
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [selectedMessageIds, setSelectedMessageIds] = useState(new Set());
  const [selectionMode, setSelectionMode] = useState(false);
  const [editingMessage, setEditingMessage] = useState(null);
  const [editClock, setEditClock] = useState(Date.now());
  const [replyTarget, setReplyTarget] = useState(null);
  const [reportingMessageId, setReportingMessageId] = useState(null);
  const [reportReason, setReportReason] = useState("inappropriate");
  const [reportDescription, setReportDescription] = useState("");
  const [reportNotice, setReportNotice] = useState(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const scrollRef = useRef(null);
  const latestMessageRef = useRef(null);
  const scrollAnchorRef = useRef(null);
  const headerMenuRef = useRef(null);
  const stickToBottomRef = useRef(true);
  const readMessageIdsRef = useRef(new Set());
  const recorderRef = useRef(null);
  const recordingStartedAtRef = useRef(0);

  useEffect(() => {
    if (!selectedMessage && !editingMessage) return undefined;
    const timer = window.setInterval(() => setEditClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [selectedMessage, editingMessage]);

  useEffect(() => {
    if (!isRecording) return undefined;
    const timer = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - recordingStartedAtRef.current) / 1000);
      setRecordingSeconds(elapsed);
      if (elapsed >= 120 && recorderRef.current?.recorder.state === "recording") {
        recorderRef.current.recorder.stop();
      }
    }, 250);
    return () => window.clearInterval(timer);
  }, [isRecording]);

  useEffect(() => () => {
    const session = recorderRef.current;
    if (!session) return;
    session.cancelled = true;
    session.stream.getTracks().forEach((track) => track.stop());
    if (session.recorder.state !== "inactive") session.recorder.stop();
  }, []);

  const activeId = routeConversationId || null;
  const startWith = !activeId ? location.state?.startWith : null;

  function handleConversationScroll() {
    const container = scrollRef.current;
    if (!container) return;
    const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight <= 80;
    stickToBottomRef.current = isAtBottom;
    setShowScrollToBottom(!isAtBottom);
  }

  function scrollToLatest() {
    const container = scrollRef.current;
    if (!container) return;
    stickToBottomRef.current = true;
    setShowScrollToBottom(false);
    latestMessageRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }

  useEffect(() => {
    if (!isAuthenticated) navigate("/auth");
  }, [isAuthenticated, navigate]);

  const loadConversations = useCallback(({ silent = false } = {}) => {
    if (!silent) setConversations((state) => ({ ...state, loading: true }));
    fetchConversations()
      .then((items) => setConversations((state) => ({ ...state, loading: false, error: null, items })))
      .catch((err) => setConversations((state) => ({
        ...state,
        loading: false,
        error: silent ? state.error : err.message,
        items: silent ? state.items : [],
      })));
  }, []);

  useEffect(() => {
    if (isAuthenticated) loadConversations();
  }, [isAuthenticated, loadConversations]);

  useEffect(() => {
    if (!isAuthenticated) return undefined;
    const timer = window.setInterval(() => loadConversations({ silent: true }), 12000);
    return () => window.clearInterval(timer);
  }, [isAuthenticated]);

  useEffect(() => {
    if (!activeId) {
      stickToBottomRef.current = true;
      setShowScrollToBottom(false);
      setMessages({ loading: false, error: null, items: [] });
      return;
    }
    stickToBottomRef.current = true;
    setShowScrollToBottom(false);
    let cancelled = false;
    setMessages({ loading: true, error: null, items: [], page: 1, hasMore: false });
    fetchMessages(activeId, 1)
      .then((data) => {
        if (!cancelled) {
          setMessages((state) => {
            const messagesById = new Map(state.items.map((message) => [message.id, message]));
            (data.results || []).forEach((message) => messagesById.set(message.id, message));
            return {
              ...state,
              loading: false,
              error: null,
              items: [...messagesById.values()].sort((first, second) => new Date(first.created_at) - new Date(second.created_at)),
              page: data.page || 1,
              hasMore: Boolean(data.has_more),
            };
          });
          setConversations((state) => ({
            ...state,
            items: state.items.map((conversation) => conversation.id === activeId
              ? { ...conversation, unread_count: 0 }
              : conversation),
          }));
        }
      })
      .catch((err) => {
        if (!cancelled) setMessages((s) => ({ ...s, loading: false, error: err.message }));
      });
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  // Nouveaux messages en temps réel — l'historique ci-dessus reste chargé via
  // REST (le WebSocket ne porte que ce qui arrive après la connexion).
  const handleIncomingMessage = useCallback((message) => {
    if (message.type === "rate_limited") {
      setMessages((state) => ({ ...state, error: message.detail }));
      return;
    }
    if (message.type === "message_error") {
      setMessages((state) => ({ ...state, error: message.detail }));
      return;
    }
    if (message.type === "messages_read") {
      message.message_ids.forEach((messageId) => readMessageIdsRef.current.add(messageId));
      setMessages((state) => ({
        ...state,
        items: state.items.map((item) => message.message_ids.includes(item.id)
          ? { ...item, is_read: true }
          : item),
      }));
      if (message.reader_username === user?.username) {
        setConversations((state) => ({
          ...state,
          items: state.items.map((conversation) => conversation.id === activeId
            ? { ...conversation, unread_count: 0 }
            : conversation),
        }));
      }
      return;
    }
    if (message.type === "messages_hidden") {
      if (String(message.user_id) !== String(user?.id)) return;
      const hiddenIds = new Set(message.message_ids);
      setMessages((state) => ({ ...state, items: state.items.filter((item) => !hiddenIds.has(item.id)) }));
      setSelectedMessage((selected) => selected && hiddenIds.has(selected.id) ? null : selected);
      setSelectedMessageIds((ids) => new Set([...ids].filter((id) => !hiddenIds.has(String(id)))));
      loadConversations({ silent: true });
      return;
    }
    if (message.type === "message_updated") {
      setMessages((state) => ({ ...state, items: state.items.map((item) => item.id === message.message.id ? message.message : item) }));
      loadConversations({ silent: true });
      return;
    }
    if (message.type === "message_deleted") {
      if (message.scope === "all") {
        setMessages((state) => ({ ...state, items: state.items.map((item) => item.id === message.message_id ? { ...item, content: "Ce message a été supprimé", image_url: null, voice_url: null, location_lat: null, location_lng: null, is_deleted_for_all: true } : item) }));
      }
      loadConversations({ silent: true });
      return;
    }
    const wasAlreadyRead = readMessageIdsRef.current.delete(message.id);
    const incomingMessage = wasAlreadyRead ? { ...message, is_read: true } : message;
    setMessages((state) => {
      if (state.items.some((item) => item.id === incomingMessage.id)) return state;
      return { ...state, items: [...state.items, incomingMessage] };
    });
    setConversations((state) => ({
      ...state,
      items: state.items
        .map((conversation) => conversation.id === activeId
          ? { ...conversation, last_message: { content: getMessagePreview(message), created_at: message.created_at, sender_username: message.sender_username }, updated_at: message.created_at }
          : conversation)
        .sort((first, second) => new Date(second.updated_at) - new Date(first.updated_at)),
    }));
  }, [activeId, loadConversations, user?.id, user?.username]);
  const { connected } = useConversationSocket(activeId, handleIncomingMessage);

  useEffect(() => {
    if (!activeId || connected) return undefined;
    let cancelled = false;
    let timer;

    async function pollMessages() {
      try {
        const data = await fetchMessages(activeId, 1);
        if (cancelled) return;
        const latestMessages = data.results || [];
        setMessages((state) => {
          const messagesById = new Map(state.items.map((message) => [message.id, message]));
          latestMessages.forEach((message) => messagesById.set(message.id, message));
          return {
            ...state,
            items: [...messagesById.values()].sort((first, second) => new Date(first.created_at) - new Date(second.created_at)),
            page: state.page || data.page || 1,
            hasMore: state.page > 1 ? state.hasMore : Boolean(data.has_more),
            error: null,
          };
        });
        setConversations((state) => ({
          ...state,
          items: state.items.map((conversation) => conversation.id === activeId
            ? {
              ...conversation,
              unread_count: 0,
              ...(latestMessages.length ? {
                last_message: {
                  content: getMessagePreview(latestMessages.at(-1)),
                  created_at: latestMessages.at(-1).created_at,
                  sender_username: latestMessages.at(-1).sender_username,
                },
              } : {}),
            }
            : conversation),
        }));
      } catch (error) {
        if (!cancelled) setMessages((state) => ({ ...state, error: error.message }));
      } finally {
        if (!cancelled) timer = window.setTimeout(pollMessages, 4000);
      }
    }

    timer = window.setTimeout(pollMessages, 4000);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [activeId, connected]);

  useEffect(() => {
    if (scrollAnchorRef.current && scrollRef.current) {
      const { height, top } = scrollAnchorRef.current;
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight - height + top;
      scrollAnchorRef.current = null;
      return;
    }
    if (stickToBottomRef.current && scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages.items]);

  async function startVoiceRecording() {
    if (!activeId || sending || isRecording) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setMessages((state) => ({ ...state, error: "L'enregistrement vocal n'est pas pris en charge par ce navigateur." }));
      return;
    }

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"]
        .find((type) => MediaRecorder.isTypeSupported(type));
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const session = { recorder, stream, chunks: [], cancelled: false };
      recorderRef.current = session;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) session.chunks.push(event.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        if (recorderRef.current === session) recorderRef.current = null;
        if (session.cancelled || session.chunks.length === 0) return;

        setIsRecording(false);
        setRecordingSeconds(0);
        const voiceBlob = new Blob(session.chunks, { type: recorder.mimeType || "audio/webm" });
        if (voiceBlob.size > 12 * 1024 * 1024) {
          setMessages((state) => ({ ...state, error: "Ce vocal dépasse la limite de 12 Mo." }));
          return;
        }

        setSending(true);
        try {
          const formData = new FormData();
          const extension = voiceBlob.type.includes("mp4") ? "m4a" : voiceBlob.type.includes("ogg") ? "ogg" : "webm";
          formData.append("voice", voiceBlob, `vocal-${Date.now()}.${extension}`);
          const message = await sendMessage(activeId, formData);
          setMessages((state) => state.items.some((item) => item.id === message.id)
            ? state
            : { ...state, items: [...state.items, message] });
          loadConversations({ silent: true });
          setMessages((state) => ({ ...state, error: null }));
        } catch (error) {
          setMessages((state) => ({ ...state, error: error.message }));
        } finally {
          setSending(false);
        }
      };
      recorder.start();
      recordingStartedAtRef.current = Date.now();
      setRecordingSeconds(0);
      setIsRecording(true);
      setMessages((state) => ({ ...state, error: null }));
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop());
      recorderRef.current?.stream.getTracks().forEach((track) => track.stop());
      recorderRef.current = null;
      setMessages((state) => ({
        ...state,
        error: getRecordingErrorMessage(error),
      }));
    }
  }

  function stopVoiceRecording(cancelled = false) {
    const session = recorderRef.current;
    if (!session) return;
    session.cancelled = cancelled;
    if (session.recorder.state !== "inactive") session.recorder.stop();
    setIsRecording(false);
    if (cancelled) setRecordingSeconds(0);
  }

  async function handleSend(e) {
    e?.preventDefault();
    if (!draft.trim()) return;
    setSending(true);
    try {
      if (editingMessage && activeId) {
        const updatedMessage = await updateMessage(activeId, editingMessage.id, draft);
        setMessages((state) => ({ ...state, items: state.items.map((item) => item.id === updatedMessage.id ? updatedMessage : item) }));
        loadConversations({ silent: true });
        setEditingMessage(null);
      } else if (activeId) {
        stickToBottomRef.current = true;
        setShowScrollToBottom(false);
        const payload = { content: draft, ...(replyTarget ? { reply_to_id: replyTarget.id } : {}) };
        const message = await sendMessage(activeId, payload);
        setMessages((state) => state.items.some((item) => item.id === message.id)
          ? state
          : { ...state, items: [...state.items, message] });
        loadConversations({ silent: true });
        setReplyTarget(null);
      } else if (startWith) {
        const conversation = await startConversation({
          recipientUsername: startWith.username,
          productId: startWith.productId,
          content: draft,
        });
        loadConversations({ silent: true });
        navigate(`/messages/${conversation.id}`, { replace: true });
      }
      setDraft("");
      setMessages((state) => ({ ...state, error: null }));
    } catch (err) {
      window.alert(err.message);
    } finally {
      setSending(false);
    }
  }

  async function loadOlderMessages() {
    if (!activeId || loadingOlder || !messages.hasMore) return;
    const container = scrollRef.current;
    const oldHeight = container?.scrollHeight || 0;
    const oldTop = container?.scrollTop || 0;
    scrollAnchorRef.current = { height: oldHeight, top: oldTop };
    setLoadingOlder(true);
    try {
      const data = await fetchMessages(activeId, (messages.page || 1) + 1);
      setMessages((state) => ({
        ...state,
        items: [...new Map([...(data.results || []), ...state.items].map((message) => [message.id, message])).values()]
          .sort((first, second) => new Date(first.created_at) - new Date(second.created_at)),
        page: data.page || (state.page || 1) + 1,
        hasMore: Boolean(data.has_more),
      }));
    } catch (err) {
      scrollAnchorRef.current = null;
      setMessages((state) => ({ ...state, error: err.message }));
    } finally {
      setLoadingOlder(false);
    }
  }

  async function handleDeleteMessage(message, scope) {
    if (!message || !activeId) return;
    const label = scope === "all" ? "supprimer ce message pour tous" : "supprimer ce message pour vous";
    if (!window.confirm(`Voulez-vous vraiment ${label} ?`)) return;
    try {
      await deleteMessage(activeId, message.id, scope);
      setMessages((state) => ({
        ...state,
        items: scope === "all"
          ? state.items.map((item) => item.id === message.id ? { ...item, content: "Ce message a été supprimé", image_url: null, voice_url: null, location_lat: null, location_lng: null, is_deleted_for_all: true } : item)
          : state.items.filter((item) => item.id !== message.id),
      }));
      loadConversations({ silent: true });
      setSelectedMessage(null);
      setSelectedMessageIds((ids) => new Set([...ids].filter((id) => String(id) !== String(message.id))));
    } catch (err) {
      window.alert(err.message);
    }
  }

  async function handleBulkDeleteMessages(scope) {
    if (!activeId || selectedMessageIds.size === 0) return;
    const selected = messages.items.filter((message) => selectedMessageIds.has(message.id));
    const label = scope === "all" ? "pour tous" : "pour vous";
    if (!window.confirm(`Supprimer ${selected.length} message${selected.length > 1 ? "s" : ""} ${label} ?`)) return;
    const results = await Promise.allSettled(selected.map((message) => deleteMessage(activeId, message.id, scope)));
    const successfulIds = new Set(selected.filter((_, index) => results[index].status === "fulfilled").map((message) => String(message.id)));
    setMessages((state) => ({
      ...state,
      items: scope === "all"
        ? state.items.map((item) => successfulIds.has(String(item.id)) ? { ...item, content: "Ce message a été supprimé", image_url: null, voice_url: null, location_lat: null, location_lng: null, is_deleted_for_all: true } : item)
        : state.items.filter((item) => !successfulIds.has(String(item.id))),
    }));
    setSelectedMessageIds(new Set());
    setSelectionMode(false);
    loadConversations({ silent: true });
    const failedCount = results.length - successfulIds.size;
    if (failedCount) window.alert(`${failedCount} message${failedCount > 1 ? "s n’ont" : " n’a"} pas pu être supprimé${failedCount > 1 ? "s" : ""}.`);
  }

  async function handleClearMessages() {
    if (!activeId || !window.confirm("Effacer tous les messages de cette conversation pour vous ?")) return;
    try {
      await clearMessages(activeId);
      setMessages((state) => ({ ...state, items: [] }));
      loadConversations({ silent: true });
    } catch (err) {
      window.alert(err.message);
    }
  }

  async function handleMessageReport(event) {
    event.preventDefault();
    if (!selectedMessage || reportingMessageId !== selectedMessage.id) return;
    setReportBusy(true);
    try {
      await createMessageReport({
        message_id: selectedMessage.id,
        reason: reportReason,
        description: reportDescription,
      });
      setReportNotice("Votre signalement a été transmis à l’équipe de modération.");
      setReportingMessageId(null);
      setReportDescription("");
      setSelectedMessage(null);
    } catch (error) {
      setMessages((state) => ({ ...state, error: error.message }));
    } finally {
      setReportBusy(false);
    }
  }

  async function handleHideConversation(conversation) {
    if (!window.confirm(`Supprimer la conversation avec ${conversation.other_username} de votre liste ? Elle restera visible par l'autre utilisateur.`)) return;
    try {
      await hideConversation(conversation.id);
      setConversations((state) => ({
        ...state,
        items: state.items.filter((item) => item.id !== conversation.id),
      }));
      if (conversation.id === activeId) navigate("/messages", { replace: true });
    } catch (err) {
      window.alert(err.message);
    }
  }

  const activeConversation = conversations.items.find((c) => c.id === activeId);
  const selectedMessages = messages.items.filter((message) => selectedMessageIds.has(message.id));
  const canDeleteSelectedForAll = selectedMessages.length > 0
    && selectedMessages.every((message) => message.sender_username === user?.username && !message.is_deleted_for_all);
  const showThread = Boolean(activeId || startWith);
  const filteredConversations = conversations.items.filter((conversation) => {
    const query = conversationSearch.trim().toLowerCase();
    const productNames = conversation.products?.map((product) => product.title).join(" ") || conversation.product_title || "";
    return !query || `${conversation.other_username} ${productNames} ${conversation.last_message?.content || ""}`.toLowerCase().includes(query);
  });
  const contactName = activeConversation?.other_username || startWith?.username;
  const whatsappUrl = createWhatsAppUrl(
    activeConversation?.other_phone_number || startWith?.phoneNumber,
    `Bonjour ${contactName || ""}, je vous contacte depuis Easy Mall.`,
  );

  return (
    <div className={cx("flex min-h-screen flex-col transition-colors duration-300", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <div className="mx-auto flex w-full max-w-6xl flex-1 gap-4 px-4 py-5 sm:px-6 lg:py-8">
        <aside className={cx("w-full flex-col overflow-hidden sm:flex sm:w-80 sm:shrink-0", showThread ? "hidden sm:flex" : "flex")}>
          <div className="mb-4 flex items-center justify-between">
            <SectionHeading title="Messages" t={t} />
            <button type="button" onClick={loadConversations} className={cx("rounded-full border p-2 transition hover:border-indigo-400", t.border, t.textMuted)} aria-label="Actualiser les conversations">
              <RefreshCw className={cx("h-4 w-4", conversations.loading && "animate-spin")} />
            </button>
          </div>
          <label className={cx("mb-3 flex items-center gap-2 rounded-xl border px-3 py-2", t.inputBg, t.border)}>
            <Search className={cx("h-4 w-4 shrink-0", t.textMuted)} />
            <input value={conversationSearch} onChange={(event) => setConversationSearch(event.target.value)} placeholder="Rechercher une conversation" className={cx("w-full bg-transparent text-sm outline-none", t.textPrimary)} />
          </label>
          {conversations.loading ? (
            <LoadingBlock t={t} />
          ) : conversations.error ? (
            <ErrorBlock message={conversations.error} t={t} />
          ) : filteredConversations.length === 0 && !startWith ? (
            <p className={cx("text-sm", t.textMuted)}>Aucune conversation pour l'instant.</p>
          ) : (
            <div className="flex flex-col gap-1 overflow-y-auto pr-1">
              {filteredConversations.map((c) => (
                <div
                  key={c.id}
                  className={cx("flex items-center gap-2 rounded-xl border p-2 transition hover:border-indigo-300", c.id === activeId ? "border-indigo-500" : t.cardBorder, t.cardBg)}
                >
                  <button type="button" onClick={() => navigate(`/messages/${c.id}`)} className="flex min-w-0 flex-1 items-center gap-3 p-1 text-left text-sm">
                    {c.other_avatar_url ? (
                      <img src={c.other_avatar_url} alt={`Photo de profil de ${c.other_username}`} className="h-11 w-11 shrink-0 rounded-full object-cover" />
                    ) : (
                      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">{getInitials(c.other_username)}</span>
                    )}
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center justify-between gap-2">
                        <span className={cx("truncate font-medium", t.textPrimary)}>{c.other_username}</span>
                        <span className={cx("shrink-0 text-[11px]", t.textMuted)}>{formatTime(c.last_message?.created_at || c.updated_at)}</span>
                      </span>
                      <span className="flex items-center justify-between gap-2">
                        <span className={cx("truncate text-xs", t.textMuted)}>
                          {c.products?.length ? c.products.map((product) => product.title).join(" · ") : c.product_title || c.last_message?.content || "Nouvelle conversation"}
                        </span>
                        {c.unread_count > 0 && <span className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-indigo-600 px-1 text-[10px] font-semibold text-white">{c.unread_count}</span>}
                      </span>
                    </span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </aside>

        <section className={cx("min-h-[32rem] flex-1 flex-col overflow-hidden rounded-2xl border", t.cardBorder, t.cardBg, showThread ? "flex" : "hidden sm:flex")}>
          {!showThread ? (
            <div className={cx("flex flex-1 items-center justify-center text-sm", t.textMuted)}>Choisissez une conversation.</div>
          ) : (
            <>
              <div className={cx("flex items-center gap-3 border-b px-4 py-3", t.border)}>
                <button onClick={() => navigate("/messages")} className="sm:hidden" aria-label="Retour">
                  <ArrowLeft className="h-4 w-4" />
                </button>
                {activeConversation?.other_avatar_url ? (
                  <img src={activeConversation.other_avatar_url} alt={`Photo de profil de ${contactName}`} className="h-10 w-10 rounded-full object-cover" />
                ) : (
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">{getInitials(contactName)}</span>
                )}
                <span className="min-w-0 flex-1">
                  <span className={cx("block truncate text-sm font-semibold", t.textPrimary)}>{contactName}</span>
                  <span className={cx("block truncate text-xs", t.textMuted)}>{connected ? "Chat en direct" : "Synchronisation"}</span>
                  {(activeConversation?.products?.length || activeConversation?.product_title || startWith?.productTitle) && (
                    <span className="mt-1 flex flex-wrap gap-1.5">
                      {activeConversation?.products?.length ? activeConversation.products.map((product) => (
                        <Link key={product.id} to={`/produit/${product.id}`} onClick={(event) => event.stopPropagation()} className="max-w-48 truncate rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700 hover:border-indigo-400 dark:border-indigo-900 dark:bg-indigo-950 dark:text-indigo-300">
                          {product.title}
                        </Link>
                      )) : (
                        <Link to={`/produit/${activeConversation?.product || startWith?.productId}`} className="max-w-48 truncate rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700 hover:border-indigo-400 dark:border-indigo-900 dark:bg-indigo-950 dark:text-indigo-300">
                          {activeConversation?.product_title || startWith?.productTitle}
                        </Link>
                      )}
                    </span>
                  )}
                </span>
                {activeId && <span className={cx("h-2.5 w-2.5 rounded-full", connected ? "bg-emerald-500" : "animate-pulse bg-amber-400")} title={connected ? "Messagerie en temps réel" : "Synchronisation de secours active"} />}
                <details ref={headerMenuRef} className="relative shrink-0">
                  <summary className={cx("flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-full border", t.border, t.textMuted)} aria-label="Fonctionnalités de la conversation">
                    <MoreVertical className="h-5 w-5" />
                  </summary>
                  <div className={cx("absolute right-0 top-full z-20 mt-2 grid min-w-60 gap-1 rounded-xl border p-2 shadow-xl", t.cardBg, t.cardBorder)}>
                    <button type="button" onClick={() => { setSelectionMode((enabled) => !enabled); if (selectionMode) setSelectedMessageIds(new Set()); headerMenuRef.current?.removeAttribute("open"); }} className={cx("rounded-lg px-3 py-2 text-left text-sm hover:bg-black/5 dark:hover:bg-white/5", t.textPrimary)}>
                      {selectionMode ? "Terminer la sélection" : "Sélectionner des messages"}
                    </button>
                    {selectionMode && <>
                      <p className={cx("px-3 py-1 text-xs", t.textMuted)}>{selectedMessageIds.size} message{selectedMessageIds.size > 1 ? "s" : ""} sélectionné{selectedMessageIds.size > 1 ? "s" : ""}</p>
                      <button type="button" disabled={!selectedMessageIds.size} onClick={() => { headerMenuRef.current?.removeAttribute("open"); handleBulkDeleteMessages("me"); }} className="rounded-lg px-3 py-2 text-left text-sm text-rose-600 hover:bg-rose-50 disabled:opacity-50 dark:hover:bg-rose-950">
                        Supprimer la sélection pour moi
                      </button>
                      {canDeleteSelectedForAll && <button type="button" onClick={() => { headerMenuRef.current?.removeAttribute("open"); handleBulkDeleteMessages("all"); }} className="rounded-lg px-3 py-2 text-left text-sm text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950">
                        Supprimer la sélection pour tous
                      </button>}
                    </>}
                    {whatsappUrl && <a href={whatsappUrl} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-emerald-700 hover:bg-emerald-50 dark:text-emerald-400 dark:hover:bg-emerald-950"><MessageCircle className="h-4 w-4" /> Contacter sur WhatsApp</a>}
                    {activeId && <button type="button" onClick={() => { headerMenuRef.current?.removeAttribute("open"); handleClearMessages(); }} className={cx("flex items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-black/5 dark:hover:bg-white/5", t.textPrimary)}><Trash2 className="h-4 w-4" /> Effacer tous les messages</button>}
                    {activeConversation && <button type="button" onClick={() => { headerMenuRef.current?.removeAttribute("open"); handleHideConversation(activeConversation); }} className="flex items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950"><Trash2 className="h-4 w-4" /> Supprimer la conversation</button>}
                  </div>
                </details>
              </div>

              {reportNotice && <p role="status" className="border-b border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">{reportNotice}</p>}

              <div className="relative flex min-h-0 flex-1">
                <div ref={scrollRef} onScroll={handleConversationScroll} className={cx("flex-1 overflow-y-auto p-4", t.surfaceAlt)}>
                  {messages.loading && <LoadingBlock t={t} />}
                  {messages.error && <ErrorBlock message={messages.error} t={t} showApi={false} />}
                  {messages.hasMore && <div className="mb-4 text-center"><button type="button" onClick={loadOlderMessages} disabled={loadingOlder} className={cx("rounded-full border px-3 py-1.5 text-xs disabled:opacity-60", t.border, t.textMuted)}>{loadingOlder ? "Chargement…" : "Charger les anciens messages"}</button></div>}
                  {!activeId && startWith && (
                    <p className={cx("text-center text-xs", t.textMuted)}>Écrivez votre premier message ci-dessous.</p>
                  )}
                  {messages.items.map((m, index) => {
                    const ownMessage = m.sender_username === user?.username;
                    const previousMessage = messages.items[index - 1];
                    return <div key={m.id}>
                      {(!previousMessage || !isSameDay(previousMessage.created_at, m.created_at)) && <div className="my-4 text-center"><span className={cx("rounded-full px-3 py-1 text-[11px] shadow-sm", t.cardBg, t.textMuted)}>{formatDay(m.created_at)}</span></div>}
                      <div className={cx("group mb-1 flex items-end gap-1", ownMessage ? "justify-end" : "justify-start")}>
                        {selectionMode && <button type="button" onClick={() => setSelectedMessageIds((ids) => {
                          const next = new Set(ids);
                          if (next.has(m.id)) next.delete(m.id);
                          else if (!m.is_deleted_for_all) next.add(m.id);
                          return next;
                        })} disabled={m.is_deleted_for_all} className={cx("rounded p-1 disabled:opacity-40", t.textMuted)} aria-label={`${selectedMessageIds.has(m.id) ? "Désélectionner" : "Sélectionner"} le message`}>
                          {selectedMessageIds.has(m.id) ? <CheckSquare className="h-4 w-4 text-indigo-600" /> : <span className="block h-4 w-4 rounded border" />}
                        </button>}
                        {ownMessage && !selectionMode && <button type="button" onClick={() => setSelectedMessage(selectedMessage?.id === m.id ? null : m)} className={cx("rounded-full p-1 opacity-70 transition-opacity hover:opacity-100", t.textMuted)} aria-label="Options du message"><MoreVertical className="h-3.5 w-3.5" /></button>}
                        <div
                          className={cx(
                            "max-w-[82%] rounded-2xl px-3.5 py-2 text-sm shadow-sm sm:max-w-[70%]",
                            ownMessage ? "rounded-br-md bg-indigo-600 text-white" : cx("border", t.cardBorder, t.cardBg, t.textPrimary),
                            m.is_deleted_for_all && "italic opacity-75"
                          )}
                        >
                          {m.reply_to && <div className={cx("mb-1 border-l-2 pl-2 text-xs opacity-80", ownMessage ? "border-indigo-200" : "border-indigo-500")}><span className="block font-semibold">{m.reply_to_sender_username || "Réponse"}</span><span className="line-clamp-2">{m.reply_to_content}</span></div>}
                          {m.content && <p className="whitespace-pre-wrap break-words">{m.content}</p>}
                          {m.image_url && <img src={m.image_url} alt="" className="mt-2 max-h-48 rounded-lg" />}
                          {m.voice_url && <audio controls preload="metadata" src={m.voice_url} className="mt-2 max-w-full" aria-label={`Message vocal de ${m.sender_username}`} />}
                          {m.location_lat != null && <span className="mt-1 flex items-center gap-1 text-xs opacity-80"><MapPin className="h-3 w-3" /> Position partagée</span>}
                          <span className={cx("mt-1 flex items-center justify-end gap-1 text-[10px]", ownMessage ? "text-indigo-100" : t.textMuted)}>
                            {formatTime(m.created_at)}
                            {m.edited_at && <span> · modifié</span>}
                            {ownMessage && (m.is_read ? <CheckCheck className="h-3.5 w-3.5" /> : <Check className="h-3.5 w-3.5" />)}
                          </span>
                        </div>
                        {!ownMessage && !selectionMode && <button type="button" onClick={() => setSelectedMessage(selectedMessage?.id === m.id ? null : m)} className={cx("rounded-full p-1 opacity-70 transition-opacity hover:opacity-100", t.textMuted)} aria-label="Options du message"><MoreVertical className="h-3.5 w-3.5" /></button>}
                      </div>
                      {selectedMessage?.id === m.id && !selectionMode && <div className={cx("mb-3 flex", ownMessage ? "justify-end pr-7" : "justify-start pl-7")}>
                        <div className={cx("max-w-[90%] rounded-lg border p-3", t.border, t.cardBg)}>
                          <div className="flex flex-wrap gap-2">
                            <button type="button" onClick={() => { setReplyTarget(m); setEditingMessage(null); setSelectedMessage(null); }} className={cx("flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs", t.border, t.textPrimary)}><CornerUpLeft className="h-3.5 w-3.5" /> Répondre</button>
                            {ownMessage && m.content && !m.is_deleted_for_all && isWithinEditWindow(m, editClock) && <button type="button" onClick={() => { setEditingMessage(m); setReplyTarget(null); setDraft(m.content); setSelectedMessage(null); }} className={cx("flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs", t.border, t.textPrimary)}><Pencil className="h-3.5 w-3.5" /> Modifier</button>}
                            {!m.is_deleted_for_all && <button type="button" onClick={() => handleDeleteMessage(m, "me")} className="rounded-lg border border-rose-200 px-3 py-1.5 text-xs text-rose-600">Supprimer pour moi</button>}
                            {ownMessage && !m.is_deleted_for_all && <button type="button" onClick={() => handleDeleteMessage(m, "all")} className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs text-white">Supprimer pour tous</button>}
                            {!ownMessage && !m.is_deleted_for_all && <button type="button" onClick={() => { setReportingMessageId(m.id); setReportReason("inappropriate"); setReportDescription(""); }} className={cx("flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs", t.border, t.textPrimary)}><Flag className="h-3.5 w-3.5" /> Signaler ce message</button>}
                          </div>
                          {reportingMessageId === m.id && <form onSubmit={handleMessageReport} className={cx("mt-3 grid gap-3 border-t pt-3 sm:grid-cols-2", t.border)}>
                            <label className={cx("grid gap-1 text-xs font-medium", t.textPrimary)}>
                              Motif du signalement
                              <select value={reportReason} onChange={(event) => setReportReason(event.target.value)} className={cx("rounded-lg border px-3 py-2 text-sm", t.inputBg, t.border, t.textPrimary)}>
                                <option value="threat">Menace</option><option value="inappropriate">Message inapproprié</option><option value="harassment">Harcèlement</option><option value="fraud">Fraude ou tentative d’arnaque</option><option value="other">Autre motif</option>
                              </select>
                            </label>
                            <label className={cx("grid gap-1 text-xs font-medium", t.textPrimary)}>Précisions (facultatif)<textarea value={reportDescription} onChange={(event) => setReportDescription(event.target.value)} rows={2} maxLength={2000} className={cx("rounded-lg border px-3 py-2 text-sm", t.inputBg, t.border, t.textPrimary)} /></label>
                            <div className="flex gap-2 sm:col-span-2"><button type="submit" disabled={reportBusy} className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-60">{reportBusy ? "Envoi…" : "Envoyer le signalement"}</button><button type="button" onClick={() => setReportingMessageId(null)} className={cx("rounded-lg border px-3 py-1.5 text-xs", t.border, t.textMuted)}>Annuler</button></div>
                          </form>}
                        </div>
                      </div>}
                    </div>;
                  })}
                  <div ref={latestMessageRef} />
                </div>
                {showScrollToBottom && (
                  <button
                    type="button"
                    onClick={scrollToLatest}
                    className="absolute bottom-3 right-4 z-10 flex h-10 w-10 items-center justify-center rounded-full border border-indigo-200 bg-white text-indigo-700 shadow-lg transition hover:bg-indigo-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
                    aria-label="Aller aux derniers messages"
                    title="Aller aux derniers messages"
                  >
                    <ArrowDown className="h-5 w-5" />
                  </button>
                )}
              </div>

              <form onSubmit={handleSend} className={cx("flex items-end gap-2 border-t p-3", t.border)}>
                {(replyTarget || editingMessage) && <div className={cx("flex items-center justify-between gap-3 border-t px-3 py-2 text-xs", t.cardBg, t.border)}><span className={cx("truncate", t.textMuted)}>{editingMessage ? `Modification : ${editingMessage.content}` : `Réponse à ${replyTarget.sender_username} : ${replyTarget.content}`}</span><button type="button" onClick={() => { setReplyTarget(null); setEditingMessage(null); setDraft(""); }} aria-label="Annuler"><X className="h-4 w-4" /></button></div>}
                {isRecording ? (
                  <div className={cx("flex min-h-10 flex-1 items-center gap-3 rounded-2xl border px-3", t.inputBg, t.border)}>
                    <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-rose-500" />
                    <span className={cx("flex-1 text-sm tabular-nums", t.textPrimary)}>
                      {String(Math.floor(recordingSeconds / 60)).padStart(2, "0")}:{String(recordingSeconds % 60).padStart(2, "0")}
                    </span>
                    <button type="button" onClick={() => stopVoiceRecording(true)} className={cx("rounded-full p-2", t.textMuted)} aria-label="Annuler l'enregistrement vocal" title="Annuler"><X className="h-4 w-4" /></button>
                    <button type="button" onClick={() => stopVoiceRecording()} disabled={sending} className="rounded-full bg-rose-600 p-2.5 text-white disabled:opacity-60" aria-label="Arrêter et envoyer le vocal" title="Arrêter et envoyer"><Square className="h-4 w-4" /></button>
                  </div>
                ) : (
                  <>
                    <textarea
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" && !event.shiftKey) {
                          event.preventDefault();
                          handleSend(event);
                        }
                      }}
                      rows={1}
                      placeholder="Écrire un message"
                      className={cx("max-h-28 min-h-10 flex-1 resize-none rounded-2xl border px-4 py-2.5 text-sm outline-none focus:border-indigo-500", t.inputBg, t.border, t.textPrimary)}
                    />
                    {activeId && <button type="button" onClick={startVoiceRecording} disabled={sending} className={cx("rounded-full border p-2.5 transition hover:border-indigo-400 disabled:opacity-50", t.border, t.textMuted)} aria-label="Enregistrer un message vocal" title="Enregistrer un vocal"><Mic className="h-4 w-4" /></button>}
                    <button
                      type="submit"
                      disabled={sending || !draft.trim()}
                      className="rounded-full bg-indigo-600 p-2.5 text-white disabled:opacity-60"
                      aria-label="Envoyer"
                    >
                      <Send className="h-4 w-4" />
                    </button>
                  </>
                )}
              </form>
            </>
          )}
        </section>
      </div>

      <SiteFooter t={t} />
    </div>
  );
}
