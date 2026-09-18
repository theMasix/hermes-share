import React, { useState } from 'react';
import { Terminal, Wrench, ChevronDown, ChevronRight } from 'lucide-react';
import { ToolCall } from '../types';

interface Props {
  toolCalls?: ToolCall[] | string | null;
  toolResult?: {
    tool_name?: string | null;
    content?: string | null;
  };
}

export const ToolCallBlock: React.FC<Props> = ({ toolCalls, toolResult }) => {
  const [isOpen, setIsOpen] = useState(false);

  // If this is a tool result message (role === 'tool')
  if (toolResult) {
    const toolName = toolResult.tool_name || 'Tool Output';
    return (
      <div className="border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-900/40 rounded-xl overflow-hidden text-xs my-2">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full px-3.5 py-2 flex items-center justify-between text-left text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/40 transition select-none"
        >
          <div className="flex items-center space-x-2 font-mono text-[11px]">
            <Wrench className="w-3.5 h-3.5 text-amber-500" />
            <span className="font-semibold text-amber-600 dark:text-amber-400">
              [{toolName}]
            </span>
            <span className="text-slate-400 dark:text-slate-500 truncate max-w-xs sm:max-w-md">
              {toolResult.content?.slice(0, 60)}...
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
          <pre className="p-3 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-[11px] font-mono text-slate-700 dark:text-slate-300 overflow-x-auto max-h-96 leading-relaxed">
            {toolResult.content}
          </pre>
        )}
      </div>
    );
  }

  // If this is assistant calling tools
  if (!toolCalls) return null;

  let parsedCalls: ToolCall[] = [];
  if (typeof toolCalls === 'string') {
    try {
      parsedCalls = JSON.parse(toolCalls);
    } catch {
      return null;
    }
  } else if (Array.isArray(toolCalls)) {
    parsedCalls = toolCalls;
  }

  if (parsedCalls.length === 0) return null;

  return (
    <div className="space-y-2 my-2">
      {parsedCalls.map((call, idx) => {
        const name = call.function?.name || call.name || 'tool';
        const rawArgs = call.function?.arguments || '';
        let formattedArgs = rawArgs;
        try {
          formattedArgs = JSON.stringify(JSON.parse(rawArgs), null, 2);
        } catch {
          // keep raw
        }

        return (
          <div
            key={idx}
            className="border border-indigo-200/60 dark:border-indigo-900/40 bg-indigo-50/40 dark:bg-indigo-950/20 rounded-xl overflow-hidden text-xs"
          >
            <div className="px-3.5 py-2 flex items-center justify-between text-indigo-700 dark:text-indigo-300 font-mono text-[11px]">
              <div className="flex items-center space-x-2">
                <Terminal className="w-3.5 h-3.5 text-indigo-500" />
                <span className="font-bold">Invoke: {name}</span>
              </div>
            </div>
            {formattedArgs && (
              <pre className="px-3.5 py-2 border-t border-indigo-100 dark:border-indigo-900/30 bg-white/70 dark:bg-slate-950/70 text-[11px] font-mono text-slate-700 dark:text-slate-300 overflow-x-auto">
                {formattedArgs}
              </pre>
            )}
          </div>
        );
      })}
    </div>
  );
};
