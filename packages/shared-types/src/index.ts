export type UserRole = "owner" | "admin" | "member";

export type ConsentChannel = "voice" | "email";
export type ConsentStatus = "granted" | "revoked";
export type SuppressionReason = "dnd" | "unsubscribe" | "bounce" | "complaint" | "manual";

export type CampaignType = "voice" | "email";
export type CampaignStatus =
  | "draft"
  | "scheduled"
  | "running"
  | "paused"
  | "completed"
  | "failed";

export type CampaignContactStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "skipped"
  | "failed";

export type EventModule = "system" | "voice" | "email" | "seo";

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "dead_letter";

export interface User {
  id: string;
  workspace_id: string;
  email: string;
  name: string;
  role: UserRole;
}

export interface Workspace {
  id: string;
  name: string;
  timezone: string;
  default_language: string;
  settings: Record<string, unknown>;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  workspace: Workspace;
}

export interface SessionResponse {
  user: User;
  workspace: Workspace;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Contact {
  id: string;
  name: string | null;
  phone: string | null;
  email: string | null;
  language: string | null;
  tags: string[];
  source: string | null;
  custom_fields: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Consent {
  id: string;
  contact_id: string;
  channel: ConsentChannel;
  status: ConsentStatus;
  proof: string | null;
  recorded_at: string;
}

export interface ChannelEligibility {
  allowed: boolean;
  reason: string | null;
  message: string;
}

export interface Eligibility {
  contact_id: string;
  voice: ChannelEligibility;
  email: ChannelEligibility;
}

export interface Suppression {
  id: string;
  channel: ConsentChannel;
  value: string;
  reason: SuppressionReason;
  created_at: string;
}

export interface ImportErrorItem {
  row: number;
  field: string | null;
  code: string;
  message: string;
}

export interface ImportPreviewRow {
  row: number;
  name: string | null;
  phone: string | null;
  email: string | null;
  status: "valid" | "duplicate" | "invalid";
  message: string | null;
}

export interface ImportResult {
  dry_run: boolean;
  total_rows: number;
  valid_rows: number;
  duplicate_rows: number;
  invalid_rows: number;
  created: number;
  errors: ImportErrorItem[];
  preview: ImportPreviewRow[];
  truncated: boolean;
}

export interface Campaign {
  id: string;
  type: CampaignType;
  name: string;
  status: CampaignStatus;
  scheduled_at: string | null;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CampaignContact {
  id: string;
  campaign_id: string;
  contact_id: string;
  status: CampaignContactStatus;
  attempts: number;
  last_attempt_at: string | null;
  contact: Contact;
}

export interface CampaignAddContactsResult {
  added: number;
  skipped: number;
  missing: number;
}

export interface EventItem {
  id: string;
  contact_id: string | null;
  source_module: EventModule;
  type: string;
  payload: Record<string, unknown>;
  occurred_at: string;
  created_at: string;
}

export interface Job {
  id: string;
  type: string;
  status: JobStatus;
  progress: number;
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  attempts: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface DashboardSummary {
  contacts: number;
  calls: number;
  emails_sent: number;
  latest_seo_score: number | null;
  running_campaigns: number;
  active_campaigns: Campaign[];
  recent_events: EventItem[];
}

export interface Member {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string;
    details?: Array<{ field: string; message: string }>;
  };
}
