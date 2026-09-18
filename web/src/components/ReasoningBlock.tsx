import React, { useState } from 'react';
import { Brain, ChevronDown, ChevronRight } from 'lucide-react';

interface Props {
  reasoning: string;
}

export const ReasoningBlock: React.FC<Props> = ({ reasoning }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!reasoning || !reasoning.trim()) {
    return null;
  }

  // Estimate approximate token count or words
  const words = reasoning.trim().split(/\s+/).length;

  return (
    <div className="border border-slate-200 dark:border-slate-800/80 bg-slate-50 dark:bg-slate-900/60 rounded-xl overflow-hidden text-xs my-2 transition-all">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3.5 py-2.5 flex items-center justify-between text-left text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/50 transition select-none"
      >
        <div className="flex items-center space-x-2 font-medium">
          <Brain className="w-3.5 h-3.5 text-indigo-500" />
          <span>Thought Process</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
            ~{words} words
          </span>
        </div>
        <div>
          {isOpen ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </div>
      </button>

      {isOpen && (
        <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-950/50 text-[11px] font-mono text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
          {reasoning}
        </div>
      )}
    </div>
  );
};
