# Chat Reliability Flow

GLIKCH NEXUZ uses a guarded send flow to reduce accidental or duplicate requests. Pressing Enter once arms the message and updates the live status strip. Pressing Enter again sends the request. Shift+Enter keeps the normal newline behavior, and the Send button remains a direct send action.

The chat UI mirrors request lifecycle events into the Developer log pane: request prepared, response received, and UI/API errors. The visible live strip shows ready, sending, receiving, and error states.

The assistant response area renders a temporary Thinking indicator while waiting for LM Studio, then replaces it with the final response or removes it on error.
