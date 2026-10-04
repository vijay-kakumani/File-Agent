const API_ROOT = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const API_BASE_URL = `${API_ROOT}/api`;

export async function checkHealth() {
  try {
    const response = await fetch(`${API_ROOT}/health`);
    if (!response.ok) {
      // Fallback check to /api/health
      const fb = await fetch(`${API_BASE_URL}/health`);
      if (!fb.ok) return { status: 'error' };
      return await fb.json();
    }
    return await response.json();
  } catch (err) {
    return { status: 'error', error: String(err) };
  }
}

export async function sendQuery(query) {
  const response = await fetch(`${API_ROOT}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Server error (${response.status})`);
  }
  return response.json();
}

export async function sendQueryStream(query, { onMeta, onToken, onDone, onError, signal } = {}) {
  try {
    const response = await fetch(`${API_ROOT}/query/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
      signal,
    });

    if (!response.ok) {
      // Fallback check: if /query/stream not found, fallback to sendQuery
      if (response.status === 404) {
        const syncRes = await sendQuery(query);
        if (onMeta) onMeta(syncRes);
        if (onToken) onToken(syncRes.message || '');
        if (onDone) onDone(syncRes);
        return;
      }
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Server error (${response.status})`);
    }

    if (!response.body) {
      const syncRes = await sendQuery(query);
      if (onMeta) onMeta(syncRes);
      if (onToken) onToken(syncRes.message || '');
      if (onDone) onDone(syncRes);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() || '';

      for (const block of blocks) {
        const trimmedBlock = block.trim();
        if (!trimmedBlock) continue;

        for (const line of trimmedBlock.split('\n')) {
          if (line.startsWith('data: ')) {
            const rawData = line.slice(6).trim();
            if (!rawData) continue;
            try {
              const parsed = JSON.parse(rawData);
              if (parsed.type === 'meta' && onMeta) {
                onMeta(parsed);
              } else if (parsed.type === 'token' && onToken) {
                onToken(parsed.content || '');
              } else if (parsed.type === 'done' && onDone) {
                onDone(parsed);
              } else if (parsed.type === 'error') {
                if (onError) onError(new Error(parsed.error || 'Streaming error'));
              }
            } catch (err) {
              console.warn('Failed to parse SSE line:', rawData, err);
            }
          }
        }
      }
    }

    if (buffer.trim()) {
      for (const line of buffer.trim().split('\n')) {
        if (line.startsWith('data: ')) {
          const rawData = line.slice(6).trim();
          try {
            const parsed = JSON.parse(rawData);
            if (parsed.type === 'meta' && onMeta) onMeta(parsed);
            else if (parsed.type === 'token' && onToken) onToken(parsed.content || '');
            else if (parsed.type === 'done' && onDone) onDone(parsed);
            else if (parsed.type === 'error' && onError) onError(new Error(parsed.error || 'Streaming error'));
          } catch {
            // ignore
          }
        }
      }
    }
  } catch (err) {
    if (onError) {
      onError(err);
    } else {
      throw err;
    }
  }
}

export async function sendMessage(message) {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Server error (${response.status})`);
  }
  return response.json();
}

export async function refreshDocuments() {
  const response = await fetch(`${API_BASE_URL}/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    throw new Error('Failed to refresh document index');
  }
  return response.json();
}

export async function getCurrentDocument() {
  const response = await fetch(`${API_BASE_URL}/current-document`);
  if (!response.ok) {
    throw new Error('Failed to fetch current document');
  }
  return response.json();
}

export async function getDocuments(query = '') {
  const url = query
    ? `${API_BASE_URL}/documents?query=${encodeURIComponent(query)}`
    : `${API_BASE_URL}/documents`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error('Failed to fetch documents');
  }
  return response.json();
}

export async function selectDocument(path, openFileFlag = false) {
  const response = await fetch(`${API_BASE_URL}/select-document`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, open_file_flag: openFileFlag }),
  });
  if (!response.ok) {
    throw new Error('Failed to select document');
  }
  return response.json();
}
