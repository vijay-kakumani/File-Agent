import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import MainWorkspace from './components/MainWorkspace';
import SettingsModal from './components/SettingsModal';
import { sendQuery, sendQueryStream, selectDocument, checkHealth, getCurrentDocument } from './services/api';

export default function App() {
  const [messages, setMessages] = useState([]);
  const [isThinking, setIsThinking] = useState(false);
  const [thinkingStatus, setThinkingStatus] = useState('');
  const [orbState, setOrbState] = useState('breathing');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isBackendReady, setIsBackendReady] = useState(false);
  const [currentDocument, setCurrentDocument] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [composerFocusTrigger, setComposerFocusTrigger] = useState(0);

  // Synchronize active document state from backend
  const refreshActiveDocument = useCallback(async () => {
    try {
      const data = await getCurrentDocument();
      if (data && data.current_document) {
        setCurrentDocument(data.current_document);
      } else {
        setCurrentDocument(null);
      }
    } catch {
      // Backend may still be initializing
    }
  }, []);

  // Poll health until backend is online
  useEffect(() => {
    let intervalId;

    const verifyHealth = async () => {
      const health = await checkHealth();
      if (health && (health.status === 'healthy' || health.agent_ready)) {
        setIsBackendReady(true);
        setOrbState('breathing');
        refreshActiveDocument();
        if (intervalId) clearInterval(intervalId);
      } else {
        setIsBackendReady(false);
        setOrbState('working');
      }
    };

    verifyHealth();
    intervalId = setInterval(verifyHealth, 1500);

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [refreshActiveDocument]);

  // "+ New Search" clears visible conversation and focuses composer
  const handleNewSearch = () => {
    setMessages([]);
    setIsThinking(false);
    setOrbState('breathing');
    setComposerFocusTrigger((prev) => prev + 1);
  };

  const handleSendMessage = async (queryText) => {
    if (!queryText || isProcessing) return;

    const trimmed = queryText.trim();
    if (!trimmed) return;

    // 1. Immediately add user message
    const userMsg = {
      id: `user-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
      role: 'user',
      content: trimmed
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsProcessing(true);

    // 2. Set thinking orb state and status
    const lower = trimmed.toLowerCase();
    let status = 'Thinking...';
    let orb = 'working';

    if (lower.startsWith('find') || lower.startsWith('search')) {
      status = 'Searching documents...';
      orb = 'searching';
    } else if (lower.includes('summariz') || lower.includes('overview')) {
      status = 'Summarizing document...';
      orb = 'weaving';
    } else if (lower.startsWith('open') || lower.includes('open it')) {
      status = 'Opening document...';
      orb = 'connecting';
    } else if (lower.includes('where') || lower.includes('location')) {
      status = 'Locating document...';
      orb = 'solving';
    } else {
      status = 'Formulating answer...';
      orb = 'solving';
    }

    setThinkingStatus(status);
    setOrbState(orb);
    setIsThinking(true);

    const asstMsgId = `asst-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
    let hasCreatedAssistantMessage = false;
    let accumulatedContent = '';
    let metaData = {};

    try {
      await sendQueryStream(trimmed, {
        onMeta: (meta) => {
          metaData = meta;
          if (meta.action === 'ask') {
            setThinkingStatus('Formulating answer...');
            setOrbState('solving');
          } else if (meta.action === 'summarize') {
            setThinkingStatus('Generating summary...');
            setOrbState('weaving');
          }
        },
        onToken: (token) => {
          accumulatedContent += token;
          if (!hasCreatedAssistantMessage) {
            hasCreatedAssistantMessage = true;
            setIsThinking(false); // Stop thinking orb placeholder on first token
            setOrbState(lower.includes('summariz') ? 'weaving' : 'working'); // Subtle activity during generation
            setMessages((prev) => [
              ...prev,
              {
                id: asstMsgId,
                role: 'assistant',
                content: accumulatedContent,
                action: metaData.action,
                targetDocument: metaData.current_document || null,
                ambiguous: Boolean(metaData.ambiguous),
                results: metaData.results || [],
                success: Boolean(metaData.success ?? true),
                isStreaming: true,
              }
            ]);
          } else {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === asstMsgId
                  ? { ...msg, content: accumulatedContent }
                  : msg
              )
            );
          }
        },
        onDone: (doneData) => {
          const finalContent = doneData.message || accumulatedContent;
          if (!hasCreatedAssistantMessage) {
            hasCreatedAssistantMessage = true;
            setIsThinking(false);
            setMessages((prev) => [
              ...prev,
              {
                id: asstMsgId,
                role: 'assistant',
                content: finalContent || (doneData.success ? 'Completed.' : "I couldn't find a matching document."),
                action: doneData.action || metaData.action,
                targetDocument: doneData.current_document || metaData.current_document || null,
                ambiguous: Boolean(doneData.ambiguous ?? metaData.ambiguous),
                results: doneData.results || metaData.results || [],
                success: Boolean(doneData.success ?? true),
                isStreaming: false,
              }
            ]);
          } else {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === asstMsgId
                  ? {
                      ...msg,
                      content: finalContent,
                      action: doneData.action || msg.action,
                      targetDocument: doneData.current_document || msg.targetDocument,
                      ambiguous: Boolean(doneData.ambiguous ?? msg.ambiguous),
                      results: doneData.results || msg.results,
                      success: Boolean(doneData.success ?? msg.success),
                      isStreaming: false,
                    }
                  : msg
              )
            );
          }

          if (doneData.current_document) {
            setCurrentDocument(doneData.current_document);
          } else {
            refreshActiveDocument();
          }
        },
        onError: (err) => {
          throw err;
        }
      });
    } catch (err) {
      console.error('Agent Stream API Error:', err);
      setIsThinking(false);
      const errorMsg = {
        id: `asst-err-${Date.now()}`,
        role: 'assistant',
        content:
          err.message && !err.message.includes('Failed to fetch')
            ? err.message
            : 'The document agent is currently unavailable. Please ensure the local service is running.',
        success: false
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsThinking(false);
      setIsProcessing(false);
      setOrbState('breathing');
      setThinkingStatus('');
    }
  };

  // Ambiguity selection option clicked
  const handleSelectOption = async (doc) => {
    if (!doc || !doc.path) return;

    // Add user selection message
    const userMsg = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: `Select ${doc.name}`
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsProcessing(true);
    setIsThinking(true);
    setThinkingStatus('Selecting document...');
    setOrbState('connecting');

    try {
      await selectDocument(doc.path, false);
      const assistantMsg = {
        id: `asst-${Date.now()}`,
        role: 'assistant',
        content: `Selected: **${doc.name}**\n\nYou can now ask questions, request a summary, or open this document.`,
        action: 'search',
        targetDocument: doc,
        success: true
      };
      setMessages((prev) => [...prev, assistantMsg]);
      refreshActiveDocument();
    } catch (err) {
      const errorMsg = {
        id: `asst-err-${Date.now()}`,
        role: 'assistant',
        content: `Failed to select document: ${doc.name}`,
        success: false
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsThinking(false);
      setIsProcessing(false);
      setOrbState('breathing');
    }
  };

  // Open action clicked on message
  const handleOpenDocument = async (doc) => {
    if (!doc || !doc.path) return;
    try {
      await selectDocument(doc.path, true);
      const openMsg = {
        id: `asst-open-${Date.now()}`,
        role: 'assistant',
        content: `Opened: **${doc.name}** in your default application.`,
        action: 'open',
        targetDocument: doc,
        success: true
      };
      setMessages((prev) => [...prev, openMsg]);
      refreshActiveDocument();
    } catch (err) {
      console.error('Failed to open document:', err);
    }
  };

  // Location action clicked on message
  const handleShowLocation = (doc) => {
    if (!doc || !doc.name) return;
    handleSendMessage(`Where did I save ${doc.name}?`);
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#F5F5F5] text-[#111111] font-sans antialiased selection:bg-neutral-900 selection:text-white">
      {/* Fixed Sidebar */}
      <Sidebar
        currentDocument={currentDocument}
        onNewSearch={handleNewSearch}
        onOpenSettings={() => setSettingsOpen(true)}
        isOpen={sidebarOpen}
        onToggleOpen={() => setSidebarOpen((prev) => !prev)}
      />

      {/* Main Workspace with Scrollable Conversation and Fixed Composer */}
      <MainWorkspace
        messages={messages}
        isThinking={isThinking}
        thinkingStatus={thinkingStatus}
        orbState={orbState}
        onSendMessage={handleSendMessage}
        onSelectOption={handleSelectOption}
        onOpenDocument={handleOpenDocument}
        onShowLocation={handleShowLocation}
        isBackendReady={isBackendReady}
        isProcessing={isProcessing}
        onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
        sidebarOpen={sidebarOpen}
        composerFocusTrigger={composerFocusTrigger}
      />

      {/* Settings Modal */}
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
    </div>
  );
}
