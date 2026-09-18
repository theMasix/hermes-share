import React, { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { MessageList } from './components/MessageList';
import { Message, Session, ShareMetadata } from './types';
import { Loader2, AlertCircle } from 'lucide-react';

export const App: React.FC = () => {
  const [token, setToken] = useState<string>('');
  const [session, setSession] = useState<Session | null>(null);
  const [share, setShare] = useState<ShareMetadata | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isLive, setIsLive] = useState<boolean>(true);
  const [isDark, setIsDark] = useState<boolean>(() => {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  // Extract token from URL /s/{token}
  useEffect(() => {
    const pathParts = window.location.pathname.split('/');
    const tokenIdx = pathParts.indexOf('s');
    if (tokenIdx !== -1 && pathParts[tokenIdx + 1]) {
      setToken(pathParts[tokenIdx + 1]);
    } else {
      // Fallback for dev or direct query
      const params = new URLSearchParams(window.location.search);
      const qToken = params.get('token');
      if (qToken) {
        setToken(qToken);
      } else {
        setError('No share token found in URL path.');
        setLoading(false);
      }
    }
  }, []);

  // Sync theme with document element
  useEffect(() => {
    const root = document.documentElement;
    if (isDark) {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [isDark]);

  // Connect to SSE stream
  useEffect(() => {
    if (!token) return;

    const streamUrl = `/api/v1/shares/${token}/stream`;
    const evtSource = new EventSource(streamUrl);

    evtSource.addEventListener('initial', (e) => {
      try {
        const data = JSON.parse(e.data);
        setSession(data.session);
        setShare(data.share);
        setMessages(data.messages || []);
        setLoading(false);
      } catch (err) {
        console.error('Failed to parse initial payload', err);
      }
    });

    evtSource.addEventListener('append', (e) => {
      try {
        const newMsg: Message = JSON.parse(e.data);
        setMessages((prev) => {
          if (prev.some((m) => m.id === newMsg.id)) return prev;
          return [...prev, newMsg];
        });
      } catch (err) {
        console.error('Failed to parse append event', err);
      }
    });

    evtSource.addEventListener('update', (e) => {
      try {
        const updatedMsg: Message = JSON.parse(e.data);
        setMessages((prev) =>
          prev.map((m) => (m.id === updatedMsg.id ? updatedMsg : m))
        );
      } catch (err) {
        console.error('Failed to parse update event', err);
      }
    });

    evtSource.addEventListener('complete', () => {
      setIsLive(false);
      evtSource.close();
    });

    evtSource.addEventListener('revoked', () => {
      setError('This share link was revoked by the owner.');
      evtSource.close();
    });

    evtSource.onerror = () => {
      // Fallback: try snapshot fetch if SSE fails
      fetch(`/api/v1/shares/${token}`)
        .then((res) => {
          if (!res.ok) {
            if (res.status === 410) {
              throw new Error('This share link has expired or was revoked.');
            }
            throw new Error(`Failed to load share (HTTP ${res.status})`);
          }
          return res.json();
        })
        .then((data) => {
          setSession(data.session);
          setShare(data.share);
          setMessages(data.messages || []);
          setLoading(false);
          setIsLive(false);
        })
        .catch((err) => {
          setError(err.message);
          setLoading(false);
        });
    };

    return () => {
      evtSource.close();
    };
  }, [token]);

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      <Header
        session={session}
        share={share}
        isLive={isLive}
        isDark={isDark}
        onToggleTheme={() => setIsDark(!isDark)}
      />

      <main className="flex-1 max-w-4xl w-full mx-auto p-4 sm:p-6 flex flex-col">
        {loading && (
          <div className="flex-1 flex flex-col items-center justify-center space-y-3 py-20 text-slate-400">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
            <p className="text-sm">Connecting to Hermes live stream...</p>
          </div>
        )}

        {error && (
          <div className="flex-1 flex flex-col items-center justify-center space-y-3 py-20">
            <div className="p-3 rounded-full bg-red-100 dark:bg-red-950/50 text-red-600 dark:text-red-400">
              <AlertCircle className="w-8 h-8" />
            </div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              Unable to Load Conversation
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md text-center">
              {error}
            </p>
          </div>
        )}

        {!loading && !error && (
          <div className="flex-1">
            <MessageList messages={messages} />
          </div>
        )}
      </main>

      <footer className="py-4 border-t border-slate-200 dark:border-slate-900 text-center text-xs text-slate-400 dark:text-slate-600">
        Shared with <span className="font-medium text-indigo-500">hermes-share</span> • Read-only snapshot
      </footer>
    </div>
  );
};
