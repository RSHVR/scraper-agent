-- Supabase Authentication Tables Migration
-- Run this in Supabase SQL Editor: Dashboard -> SQL Editor -> New Query

-- API Keys table (for programmatic access)
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    scopes TEXT[] DEFAULT ARRAY['scrape:read', 'scrape:write'],
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active) WHERE is_active = true;

-- Session ownership (links scrape sessions to users)
CREATE TABLE IF NOT EXISTS session_ownership (
    session_id TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for user session lookups
CREATE INDEX IF NOT EXISTS idx_session_ownership_user ON session_ownership(user_id);

-- Enable Row Level Security
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_ownership ENABLE ROW LEVEL SECURITY;

-- Users can only see and manage their own API keys
CREATE POLICY "Users can view own API keys" ON api_keys
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own API keys" ON api_keys
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own API keys" ON api_keys
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own API keys" ON api_keys
    FOR DELETE USING (auth.uid() = user_id);

-- Users can only see and manage their own sessions
CREATE POLICY "Users can view own sessions" ON session_ownership
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own sessions" ON session_ownership
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own sessions" ON session_ownership
    FOR DELETE USING (auth.uid() = user_id);

-- Service role bypass for backend operations
-- The service role key bypasses RLS, so the backend can:
-- 1. Validate API keys without user context
-- 2. Link sessions to users
-- 3. Update last_used_at on API keys
