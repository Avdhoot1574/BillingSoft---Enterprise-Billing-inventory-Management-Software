-- 0003 - Authentication sessions, invitations and brute-force protection.

-- Opaque refresh tokens are stored hashed (sha256). One row per login/device.
CREATE TABLE user_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash text NOT NULL UNIQUE,
    user_agent text,
    ip_address inet,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_used_at timestamptz,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz
);
CREATE INDEX idx_user_sessions_active ON user_sessions (user_id) WHERE revoked_at IS NULL;

CREATE TABLE invitations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL,
    email text NOT NULL,
    role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    token_hash text NOT NULL UNIQUE,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','revoked','expired')),
    invited_by uuid REFERENCES users(id) ON DELETE SET NULL,
    accepted_by uuid REFERENCES users(id) ON DELETE SET NULL,
    accepted_at timestamptz,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, company_id) REFERENCES companies(tenant_id, id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX uq_invitations_pending ON invitations (company_id, lower(email)) WHERE status = 'pending';

ALTER TABLE users
    ADD COLUMN failed_login_count integer NOT NULL DEFAULT 0,
    ADD COLUMN locked_until timestamptz;
