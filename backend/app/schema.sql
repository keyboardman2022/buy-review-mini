CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, phone TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
  code TEXT UNIQUE NOT NULL, color TEXT NOT NULL, created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS challenges (
  id TEXT PRIMARY KEY, phone TEXT NOT NULL, hash TEXT NOT NULL, ip TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0, used BOOLEAN NOT NULL DEFAULT FALSE,
  created_at BIGINT NOT NULL, expires_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_challenges_phone_created ON challenges(phone, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_challenges_ip_created ON challenges(ip, created_at DESC);
CREATE TABLE IF NOT EXISTS friend_requests (
  id TEXT PRIMARY KEY, sender TEXT NOT NULL REFERENCES users(id), recipient TEXT NOT NULL REFERENCES users(id),
  status TEXT NOT NULL CHECK (status IN ('pending','accepted','rejected')), created_at BIGINT NOT NULL,
  CHECK (sender <> recipient)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_friend_requests_pending
  ON friend_requests(LEAST(sender, recipient), GREATEST(sender, recipient)) WHERE status='pending';
CREATE INDEX IF NOT EXISTS idx_friend_requests_recipient ON friend_requests(recipient, status);
CREATE TABLE IF NOT EXISTS friends (
  a TEXT NOT NULL REFERENCES users(id), b TEXT NOT NULL REFERENCES users(id), created_at BIGINT NOT NULL,
  PRIMARY KEY(a,b), CHECK(a < b)
);
CREATE TABLE IF NOT EXISTS media (
  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), mime TEXT NOT NULL,
  size INTEGER NOT NULL CHECK(size > 0), created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), title TEXT NOT NULL,
  price INTEGER NOT NULL CHECK(price > 0), reason TEXT NOT NULL, category TEXT NOT NULL,
  link TEXT NOT NULL, visibility TEXT NOT NULL CHECK(visibility IN ('friends','private')),
  images JSONB NOT NULL DEFAULT '[]'::jsonb, created_at BIGINT NOT NULL, updated_at BIGINT NOT NULL,
  deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_items_owner_created ON items(owner_id, created_at DESC) WHERE NOT deleted;
CREATE TABLE IF NOT EXISTS comments (
  id TEXT PRIMARY KEY, item_id TEXT NOT NULL REFERENCES items(id), user_id TEXT NOT NULL REFERENCES users(id),
  text TEXT NOT NULL, created_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comments_item_created ON comments(item_id, created_at DESC);
CREATE TABLE IF NOT EXISTS reactions (
  item_id TEXT NOT NULL REFERENCES items(id), user_id TEXT NOT NULL REFERENCES users(id),
  value SMALLINT NOT NULL CHECK(value IN (-1,1)), PRIMARY KEY(item_id,user_id)
);
CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), item_id TEXT NOT NULL REFERENCES items(id),
  snapshot JSONB NOT NULL, rule TEXT NOT NULL CHECK(rule IN ('veto','majority','unanimous')),
  status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','expired','cancelled')),
  created_at BIGINT NOT NULL, expires_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_approvals_owner_created ON approvals(owner_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_approvals_pending_item ON approvals(owner_id,item_id) WHERE status='pending';
CREATE TABLE IF NOT EXISTS votes (
  approval_id TEXT NOT NULL REFERENCES approvals(id), user_id TEXT NOT NULL REFERENCES users(id),
  decision TEXT CHECK(decision IN ('accept','reject')), comment TEXT, voted_at BIGINT,
  PRIMARY KEY(approval_id,user_id)
);
CREATE INDEX IF NOT EXISTS idx_votes_user ON votes(user_id,approval_id);
CREATE TABLE IF NOT EXISTS outbox (
  id TEXT PRIMARY KEY, event_key TEXT UNIQUE NOT NULL, approval_id TEXT NOT NULL REFERENCES approvals(id),
  sender TEXT NOT NULL REFERENCES users(id), recipient TEXT NOT NULL REFERENCES users(id),
  kind TEXT NOT NULL CHECK(kind IN ('review','result')), body TEXT NOT NULL, params JSONB NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','sending','mock','sent','failed','unknown')),
  provider_id TEXT, error TEXT, created_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outbox_status_created ON outbox(status,created_at);

-- A prior process may have dispatched a message before it stopped. Do not blindly resend it.
UPDATE outbox SET status='unknown', error='发送中断，需核对供应商记录，未自动重发'
WHERE status='sending';
