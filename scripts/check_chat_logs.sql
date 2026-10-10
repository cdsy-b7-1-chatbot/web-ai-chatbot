-- PostgreSQL psql에서 내 사용자 ID를 지정한 뒤 실행:
-- \set user_id 12
-- \i scripts/check_chat_logs.sql
-- 실제 사용자 ID는 GET /api/auth/me의 id 또는 검증 스크립트 출력으로 확인한다.
SELECT id, user_id, conversation_id, created_at, question, answer,
       status, error_code, model, input_tokens, output_tokens, latency_ms
FROM chats
WHERE user_id = :user_id
ORDER BY created_at DESC, id DESC
LIMIT 50;

SELECT id, user_id, title, created_at, updated_at
FROM conversations
WHERE user_id = :user_id
ORDER BY updated_at DESC, id DESC;
