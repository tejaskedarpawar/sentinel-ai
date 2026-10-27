import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api.js";

const SUGGESTED_QUESTIONS = [
  "Who uploaded the most to personal cloud last week?",
  "Summarize EMP003",
  "Any open Critical cases?",
  "Show Critical alerts",
  "Show USB activity",
  "Risk trend for EMP014",
];

// Helper to format simple markdown (tables, bold, lists, code) without heavy dependencies
function renderFormattedMarkdown(text) {
  if (!text) return null;

  const lines = text.split("\n");
  const elements = [];
  let inTable = false;
  let tableHeaders = [];
  let tableRows = [];

  const flushTable = (key) => {
    if (tableHeaders.length > 0) {
      elements.push(
        <div key={`table-${key}`} className="my-2.5 overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-2xs">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="border-b border-slate-200 bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500">
              <tr>
                {tableHeaders.map((h, i) => (
                  <th key={i} className="px-3 py-2 font-semibold">
                    {h.trim()}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
              {tableRows.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-slate-50/70 transition-colors">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="px-3 py-1.5 whitespace-nowrap">
                      {cell.trim().replace(/^\*\*(.*?)\*\*$/, "$1")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    inTable = false;
    tableHeaders = [];
    tableRows = [];
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();

    // Check markdown table row
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      const parts = trimmed.slice(1, -1).split("|");
      // Check if separator line
      if (parts.every((p) => /^[\s\-:]+$/.test(p))) {
        return;
      }
      if (!inTable) {
        inTable = true;
        tableHeaders = parts;
      } else {
        tableRows.push(parts);
      }
      return;
    }

    if (inTable) {
      flushTable(idx);
    }

    // Headers
    if (trimmed.startsWith("### ")) {
      elements.push(
        <h4 key={idx} className="font-semibold text-slate-900 mt-3 mb-1 text-xs">
          {trimmed.slice(4)}
        </h4>
      );
      return;
    }
    if (trimmed.startsWith("## ")) {
      elements.push(
        <h3 key={idx} className="font-semibold text-slate-900 mt-3.5 mb-1.5 text-sm">
          {trimmed.slice(3)}
        </h3>
      );
      return;
    }

    // Bullet points
    if (trimmed.startsWith("* ") || trimmed.startsWith("- ")) {
      const itemText = trimmed.slice(2);
      elements.push(
        <li key={idx} className="ml-4 list-disc text-slate-700 my-0.5">
          {formatInlineMarkdown(itemText)}
        </li>
      );
      return;
    }

    // Empty lines
    if (!trimmed) {
      elements.push(<div key={idx} className="h-1.5" />);
      return;
    }

    // Regular paragraphs
    elements.push(
      <p key={idx} className="text-slate-700 my-1">
        {formatInlineMarkdown(trimmed)}
      </p>
    );
  });

  if (inTable) {
    flushTable("final");
  }

  return elements;
}

function formatInlineMarkdown(str) {
  // Simple bold and code format replacement
  const parts = [];
  let remaining = str;
  let key = 0;

  while (remaining) {
    // Check bold **...**
    const boldMatch = remaining.match(/^(.*?)\*\*(.*?)\*\*(.*)$/);
    // Check code `...`
    const codeMatch = remaining.match(/^(.*?)`(.*?)`(.*)$/);

    if (boldMatch && (!codeMatch || boldMatch[1].length <= codeMatch[1].length)) {
      if (boldMatch[1]) parts.push(<span key={key++}>{boldMatch[1]}</span>);
      parts.push(
        <strong key={key++} className="font-semibold text-slate-900">
          {boldMatch[2]}
        </strong>
      );
      remaining = boldMatch[3];
    } else if (codeMatch) {
      if (codeMatch[1]) parts.push(<span key={key++}>{codeMatch[1]}</span>);
      parts.push(
        <code
          key={key++}
          className="px-1 py-0.5 rounded bg-slate-100 text-slate-800 font-mono text-[10px] ring-1 ring-slate-200"
        >
          {codeMatch[2]}
        </code>
      );
      remaining = codeMatch[3];
    } else {
      parts.push(<span key={key++}>{remaining}</span>);
      break;
    }
  }

  return parts;
}

export default function SOCAssistantDrawer({ isOpen, onClose }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hello Analyst! I am your Sentinel AI Security Assistant. Ask me about top uploaders, specific employee investigations, open incidents, or USB activity. All responses are verified strictly through read-only database queries.",
      tools_used: [],
      mode: "system",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [modeFilter, setModeFilter] = useState("auto"); // "auto" | "ollama" | "fallback"
  const [expandedToolsIdx, setExpandedToolsIdx] = useState({});
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  const handleSend = async (overrideText) => {
    const text = overrideText || input;
    if (!text || !text.trim() || loading) return;

    const userMessage = { role: "user", content: text };
    const newHistory = [...messages.filter((m) => m.mode !== "system"), userMessage];

    setMessages((prev) => [...prev, userMessage]);
    if (!overrideText) setInput("");
    setLoading(true);

    try {
      const modeParam = modeFilter === "auto" ? null : modeFilter;
      const res = await api.assistantChat(text, newHistory.slice(-6), modeParam);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.answer,
          tools_used: res.tools_used || [],
          mode: res.mode,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `⚠️ Error executing assistant query: ${err.message}`,
          tools_used: [],
          mode: "fallback",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const toggleToolsExpand = (idx) => {
    setExpandedToolsIdx((prev) => ({
      ...prev,
      [idx]: !prev[idx],
    }));
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs cursor-pointer"
          />

          {/* Slide-over Panel */}
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 26, stiffness: 240 }}
            className="relative z-10 w-full max-w-xl h-full bg-white border-l border-slate-200 shadow-2xl flex flex-col overflow-hidden text-slate-800"
          >
            {/* Header */}
            <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/80">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-slate-200/80 ring-1 ring-slate-300 flex items-center justify-center text-slate-700">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                    SOC Security Assistant
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Safe, read-only threat queries &bull; Zero SQL execution
                  </p>
                </div>
              </div>

              {/* Mode Selector & Close */}
              <div className="flex items-center gap-2">
                <select
                  value={modeFilter}
                  onChange={(e) => setModeFilter(e.target.value)}
                  className="text-[11px] bg-white text-slate-700 rounded px-2.5 py-1 border border-slate-300 cursor-pointer shadow-2xs font-medium"
                  title="Execution Mode"
                >
                  <option value="auto">Auto (Cloud LLM)</option>
                  <option value="ollama">Cloud LLM (gemma4:31b-cloud)</option>
                  <option value="fallback">Deterministic Intent Router (No LLM)</option>
                </select>

                <button
                  onClick={onClose}
                  className="w-7 h-7 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-800 flex items-center justify-center transition-colors cursor-pointer text-lg leading-none"
                >
                  &times;
                </button>
              </div>
            </div>

            {/* Suggested Question Chips */}
            <div className="px-5 py-2.5 bg-slate-50 border-b border-slate-200 flex items-center gap-1.5 overflow-x-auto scrollbar-none">
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap mr-1">
                Suggestions:
              </span>
              {SUGGESTED_QUESTIONS.map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSend(q)}
                  disabled={loading}
                  className="text-[11px] px-2.5 py-1 rounded-full bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 whitespace-nowrap transition-colors cursor-pointer shadow-2xs font-medium disabled:opacity-50"
                >
                  {q}
                </button>
              ))}
            </div>

            {/* Chat Messages Stream */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 bg-slate-50/30">
              {messages.map((m, idx) => {
                const isUser = m.role === "user";
                const isExpanded = !!expandedToolsIdx[idx];
                const hasTools = m.tools_used && m.tools_used.length > 0;

                return (
                  <div
                    key={idx}
                    className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
                  >
                    {/* Message Bubble */}
                    <div
                      className={`max-w-[92%] rounded-xl px-4 py-3 shadow-xs ${
                        isUser
                          ? "bg-slate-900 text-white rounded-br-none"
                          : "bg-white border border-slate-200 text-slate-800 rounded-bl-none"
                      }`}
                    >
                      {/* Header badge for Assistant messages */}
                      {!isUser && m.mode && m.mode !== "system" && (
                        <div className="flex items-center justify-between gap-2 mb-2 pb-1.5 border-b border-slate-100">
                          <span
                            className={`inline-flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full ${
                              m.mode === "ollama"
                                ? "bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200"
                                : "bg-amber-50 text-amber-800 ring-1 ring-amber-200"
                            }`}
                          >
                            <span
                              className={`w-1.5 h-1.5 rounded-full ${
                                m.mode === "ollama" ? "bg-emerald-600" : "bg-amber-600"
                              }`}
                            />
                            {m.mode === "ollama" ? "Cloud LLM (gemma4:31b-cloud)" : "Deterministic Intent Router (No LLM)"}
                          </span>
                        </div>
                      )}

                      {/* Content */}
                      {isUser ? (
                        <p className="text-xs leading-relaxed">{m.content}</p>
                      ) : (
                        <div className="text-xs leading-relaxed">
                          {renderFormattedMarkdown(m.content)}
                        </div>
                      )}

                      {/* Expandable "Data used" Section */}
                      {!isUser && hasTools && (
                        <div className="mt-3 pt-2 border-t border-slate-100">
                          <button
                            onClick={() => toggleToolsExpand(idx)}
                            className="flex items-center gap-1.5 text-[11px] font-medium text-slate-700 hover:text-slate-900 cursor-pointer select-none"
                          >
                            <span>📊 Data used ({m.tools_used.length} query {m.tools_used.length === 1 ? "function" : "functions"})</span>
                            <span className="text-[10px] text-slate-400">
                              {isExpanded ? "▲ Hide" : "▼ Show"}
                            </span>
                          </button>

                          {isExpanded && (
                            <motion.div
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: "auto" }}
                              className="mt-2 space-y-1.5 overflow-hidden"
                            >
                              {m.tools_used.map((t, tIdx) => (
                                <div
                                  key={tIdx}
                                  className="p-2 rounded bg-slate-50 border border-slate-200 text-[11px] font-mono text-slate-700"
                                >
                                  <div className="flex items-center justify-between font-semibold text-slate-800 mb-1">
                                    <span>{t.name}()</span>
                                    <span className="text-[10px] text-slate-500 font-normal">{t.rows} rows returned</span>
                                  </div>
                                  <div className="text-[10px] text-slate-500">
                                    Arguments: <span className="text-slate-700">{JSON.stringify(t.args)}</span>
                                  </div>
                                </div>
                              ))}
                            </motion.div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {loading && (
                <div className="flex items-center gap-2 text-xs text-slate-500 pl-2">
                  <div className="w-2 h-2 rounded-full bg-slate-600 animate-ping" />
                  <span>Executing whitelisted query tools...</span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input Bar */}
            <div className="p-4 bg-white border-t border-slate-200">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSend();
                }}
                className="flex items-center gap-2"
              >
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask SOC Assistant (e.g. Who uploaded the most to personal cloud?)..."
                  disabled={loading}
                  className="flex-1 bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-slate-500 focus:bg-white transition-colors disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="px-4 py-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer flex items-center gap-1.5 shadow-xs"
                >
                  <span>Send</span>
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </button>
              </form>
              <p className="mt-2 text-[10px] text-slate-400 text-center">
                Guardrailed SOC Assistant &bull; Whitelisted ORM queries only &bull; Audited request log
              </p>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
