import React, { useState } from 'react';
import { Share2, Check, Sun, Moon, Radio } from 'lucide-react';
import { Session, ShareMetadata } from '../types';

interface Props {
  session: Session | null;
  share: ShareMetadata | null;
  isLive: boolean;
  isDark: boolean;
  onToggleTheme: () => void;
}

export const Header: React.FC<Props> = ({
  session,
  share,
  isLive,
  isDark,
  onToggleTheme,
}) => {
  const [copied, setCopied] = useState(false);

  const copyUrl = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const title = session?.title || 'Hermes Session';
  const model = session?.model || 'Hermes Agent';

  return (
    <header className="sticky top-0 z-30 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 px-4 sm:px-6 py-3 transition-colors">
      <div className="max-w-5xl mx-auto flex items-center justify-between">
        <div className="flex items-center space-x-3 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-sm flex-shrink-0">
            H
          </div>
          <div className="min-w-0">
            <h1 className="font-semibold text-sm sm:text-base text-slate-900 dark:text-slate-100 truncate">
              {title}
            </h1>
            <div className="flex items-center space-x-2 text-xs text-slate-500 dark:text-slate-400">
              <span className="bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded text-slate-600 dark:text-slate-300 font-mono text-[11px]">
                {model}
              </span>
              <span>•</span>
              {share?.allow_live && isLive ? (
                <span className="flex items-center text-emerald-600 dark:text-emerald-400 font-medium text-[11px]">
                  <Radio className="w-3 h-3 mr-1 animate-pulse" /> Live Sync
                </span>
              ) : (
                <span className="text-slate-400 dark:text-slate-500 text-[11px]">
                  Snapshot
                </span>
              )}
              {share?.view_count !== undefined && share.view_count > 0 && (
                <>
                  <span>•</span>
                  <span className="text-[11px] text-slate-400">{share.view_count} views</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 flex-shrink-0">
          <button
            onClick={onToggleTheme}
            className="p-2 rounded-lg text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
            title="Toggle theme"
          >
            {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
          <button
            onClick={copyUrl}
            className="flex items-center space-x-1.5 text-xs bg-slate-900 dark:bg-slate-800 hover:bg-slate-800 dark:hover:bg-slate-700 text-white dark:text-slate-200 border border-slate-700 px-3 py-1.5 rounded-lg transition shadow-sm font-medium"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Share2 className="w-3.5 h-3.5" />
                <span>Share Link</span>
              </>
            )}
          </button>
        </div>
      </div>
    </header>
  );
};
