import React from 'react';
import { Message } from '../types';
import { MarkdownContent } from './MarkdownContent';
import { ReasoningBlock } from './ReasoningBlock';
import { ToolCallBlock } from './ToolCallBlock';
import { Bot } from 'lucide-react';

interface Props {
  messages: Message[];
}

export const MessageList: React.FC<Props> = ({ messages }) => {
  return (
    <div className="space-y-6">
      {messages.map((msg) => {
        const isUser = msg.role === 'user';
        const isAssistant = msg.role === 'assistant';
        const isTool = msg.role === 'tool';

        if (isUser) {
          return (
            <div key={msg.id} className="flex justify-end">
              <div className="max-w-[85%] bg-indigo-600 text-white px-4 py-3 rounded-2xl rounded-tr-sm shadow-sm text-sm sm:text-base leading-relaxed whitespace-pre-wrap">
                {msg.content}
              </div>
            </div>
          );
        }

        if (isTool) {
          return (
            <div key={msg.id} className="max-w-3xl">
              <ToolCallBlock
                toolResult={{
                  tool_name: msg.tool_name,
                  content: msg.content,
                }}
              />
            </div>
          );
        }

        if (isAssistant) {
          return (
            <div key={msg.id} className="flex flex-col space-y-2 max-w-full">
              <div className="flex items-center space-x-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
                <div className="w-5 h-5 rounded-md bg-indigo-100 dark:bg-indigo-900/60 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
                  <Bot className="w-3.5 h-3.5" />
                </div>
                <span>Hermes</span>
              </div>

              {msg.reasoning_content && (
                <ReasoningBlock reasoning={msg.reasoning_content} />
              )}

              {msg.tool_calls && <ToolCallBlock toolCalls={msg.tool_calls} />}

              {msg.content && <MarkdownContent content={msg.content} />}
            </div>
          );
        }

        return null;
      })}
    </div>
  );
};
