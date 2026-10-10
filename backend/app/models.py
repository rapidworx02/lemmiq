from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

def utcnow():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    avatar: Mapped[str | None] = mapped_column(String(500), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    salt: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Chat(Base):
    __tablename__ = "chats"
    __table_args__ = (UniqueConstraint("user1_id", "user2_id", name="uq_direct_chat"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user1_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user2_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

class ChatSetting(Base):
    __tablename__ = "chat_settings"
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    category: Mapped[str] = mapped_column(String(30), default="FRIEND")
    ai_mode: Mapped[str] = mapped_column(String(20), default="ASSIST")
    tone: Mapped[str] = mapped_column(String(40), default="Natural")

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)

class Moment(Base):
    __tablename__ = "moments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class InsightEvent(Base):
    __tablename__ = "insight_events"
    __table_args__ = (UniqueConstraint("user_id", "client_event_id", name="uq_insight_user_event"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    client_event_id: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(String(220), default="")
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    direction: Mapped[str] = mapped_column(String(12), default="UNKNOWN")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MessageAttachment(Base):
    __tablename__ = "message_attachments"
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # PHOTO, VIDEO, FILE, CONTACT
    object_key: Mapped[str | None] = mapped_column(String(190), nullable=True)
    original_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(35), nullable=True)


class PushDevice(Base):
    __tablename__ = "push_devices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token: Mapped[str] = mapped_column(String(300), unique=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BusinessProfile(Base):
    __tablename__ = "business_profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    business_name: Mapped[str] = mapped_column(String(120), default="")
    business_type: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    website: Mapped[str] = mapped_column(String(300), default="")
    phone: Mapped[str] = mapped_column(String(60), default="")
    email: Mapped[str] = mapped_column(String(160), default="")
    hours: Mapped[str] = mapped_column(Text, default="")
    service_area: Mapped[str] = mapped_column(Text, default="")
    tone: Mapped[str] = mapped_column(String(40), default="Professional")
    currency: Mapped[str] = mapped_column(String(12), default="AUD")
    auto_threshold: Mapped[int] = mapped_column(Integer, default=90)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BusinessKnowledge(Base):
    __tablename__ = "business_knowledge"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(24), default="OTHER", index=True)
    title: Mapped[str] = mapped_column(String(120))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(180), default="Manual")
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BusinessChatSetting(Base):
    __tablename__ = "business_chat_settings"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mode: Mapped[str] = mapped_column(String(12), default="ASSIST")
    customer_label: Mapped[str] = mapped_column(String(80), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BusinessCustomerMemory(Base):
    __tablename__ = "business_customer_memory"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), primary_key=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(String(300), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------- LEMMIQ V2.4 messenger expansion ----------------
class LemmiqGroup(Base):
    __tablename__ = "lemmiq_groups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    photo_key: Mapped[str | None] = mapped_column(String(190), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

class GroupMember(Base):
    __tablename__ = "group_members"
    group_id: Mapped[int] = mapped_column(ForeignKey("lemmiq_groups.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(12), default="MEMBER")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class GroupSetting(Base):
    __tablename__ = "group_settings"
    group_id: Mapped[int] = mapped_column(ForeignKey("lemmiq_groups.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    ai_mode: Mapped[str] = mapped_column(String(20), default="ASSIST")
    tone: Mapped[str] = mapped_column(String(40), default="Natural")

class GroupRead(Base):
    __tablename__ = "group_reads"
    group_id: Mapped[int] = mapped_column(ForeignKey("lemmiq_groups.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    last_read_message_id: Mapped[int] = mapped_column(Integer, default=0)

class GroupMessage(Base):
    __tablename__ = "group_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("lemmiq_groups.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)

class GroupMessageAttachment(Base):
    __tablename__ = "group_message_attachments"
    message_id: Mapped[int] = mapped_column(ForeignKey("group_messages.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    object_key: Mapped[str | None] = mapped_column(String(190), nullable=True)
    original_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

class VoiceNote(Base):
    __tablename__ = "voice_notes"
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), primary_key=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    transcript: Mapped[str] = mapped_column(Text, default="")
    transcribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class GroupVoiceNote(Base):
    __tablename__ = "group_voice_notes"
    message_id: Mapped[int] = mapped_column(ForeignKey("group_messages.id"), primary_key=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    transcript: Mapped[str] = mapped_column(Text, default="")
    transcribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class CallRecord(Base):
    __tablename__ = "call_records"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), index=True)
    caller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    callee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    room_name: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="RINGING")
    call_type: Mapped[str] = mapped_column(String(12), default="VOICE")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class StatusPost(Base):
    __tablename__ = "status_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(12), default="TEXT")
    text: Mapped[str] = mapped_column(Text, default="")
    media_key: Mapped[str | None] = mapped_column(String(190), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="ALL")
    allow_user_ids: Mapped[str] = mapped_column(Text, default="")
    exclude_user_ids: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

class StatusView(Base):
    __tablename__ = "status_views"
    status_id: Mapped[int] = mapped_column(ForeignKey("status_posts.id"), primary_key=True)
    viewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class TrustHistory(Base):
    __tablename__ = "trust_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    checked_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="UNVERIFIED")
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    sources_json: Mapped[str] = mapped_column(Text, default="[]")
    advice: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

class SocialMemory(Base):
    __tablename__ = "social_memories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    chat_id: Mapped[int | None] = mapped_column(ForeignKey("chats.id"), nullable=True, index=True)
    memory_type: Mapped[str] = mapped_column(String(24), default="IMPORTANT")
    title: Mapped[str] = mapped_column(String(160))
    detail: Mapped[str] = mapped_column(Text, default="")
    source_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

class QThreadState(Base):
    """Per-user read cursor for the synthetic Q assistant thread.

    Q thread content is derived from Q actions (starting with Q-to-Q) so we do
    not duplicate private message text into another server table.
    """
    __tablename__ = "q_thread_states"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class QCoordinationRequest(Base):
    """Privacy-preserving Q-to-Q coordination request.

    Only the explicit prompt/options chosen by the initiator are shared with the target.
    LEMMIQ never exposes either user's private chat memory through this table.
    """
    __tablename__ = "q_coordination_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_key: Mapped[str] = mapped_column(String(40), index=True)
    initiator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24), default="PLAN")
    prompt: Mapped[str] = mapped_column(Text)
    options_json: Mapped[str] = mapped_column(Text, default="[]")
    response_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


# ---------------- LEMMIQ V2.7 Q Vision + Smart Memory ----------------

class VisionMemory(Base):
    __tablename__ = "vision_memories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    object_key: Mapped[str] = mapped_column(String(190))
    original_name: Mapped[str] = mapped_column(String(200), default="image")
    mime_type: Mapped[str] = mapped_column(String(100), default="image/jpeg")
    category: Mapped[str] = mapped_column(String(32), default="OTHER", index=True)
    title: Mapped[str] = mapped_column(String(160), default="Vision scan")
    summary: Mapped[str] = mapped_column(Text, default="")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    analysis_json: Mapped[str] = mapped_column(Text, default="{}")
    history_json: Mapped[str] = mapped_column(Text, default="[]")
    saved: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class ChatMemorySummary(Base):
    __tablename__ = "chat_memory_summaries"
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    through_message_id: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class AutoReplyReceipt(Base):
    __tablename__ = "auto_reply_receipts"
    trigger_message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), primary_key=True)
    responder_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reply_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

# ---------------- LEMMIQ V2.4 messenger polish ----------------

class MessageMeta(Base):
    __tablename__ = "message_meta"
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), primary_key=True)
    reply_to_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), nullable=True)
    edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_for_everyone: Mapped[bool] = mapped_column(Boolean, default=False)

class MessageReaction(Base):
    __tablename__ = "message_reactions"
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    emoji: Mapped[str] = mapped_column(String(16))

class MessageHidden(Base):
    __tablename__ = "message_hidden"
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)

class ChatPreference(Base):
    __tablename__ = "chat_preferences"
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    favourite: Mapped[bool] = mapped_column(Boolean, default=False)
    muted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    draft_text: Mapped[str] = mapped_column(Text, default="")

class UserPrivacy(Base):
    __tablename__ = "user_privacy"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    profile_photo: Mapped[str] = mapped_column(String(20), default="EVERYONE")
    last_seen: Mapped[str] = mapped_column(String(20), default="EVERYONE")
    status_visibility: Mapped[str] = mapped_column(String(20), default="EVERYONE")

class UserBlock(Base):
    __tablename__ = "user_blocks"
    blocker_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    blocked_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class UserReport(Base):
    __tablename__ = "user_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reported_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reason: Mapped[str] = mapped_column(String(60), default="OTHER")
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
