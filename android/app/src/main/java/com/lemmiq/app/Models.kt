package com.lemmiq.app

data class UserDto(val id:Int,val username:String,val display_name:String,val avatar:String?=null,val avatar_url:String?=null)
data class AuthResponse(val token:String,val user:UserDto)
data class ChatDto(
    val id:Int,val other_user:UserDto,val category:String="FRIEND",val ai_mode:String="ASSIST",
    val tone:String="Natural",val last_message:String?=null,val updated_at:String?=null,val unread:Int=0,
    val pinned:Boolean=false,val archived:Boolean=false,val favourite:Boolean=false,val muted_until:String?=null,val draft_text:String=""
)
data class MessageDto(
    val id:Int,val chat_id:Int,val sender_id:Int,val text:String,val created_at:String,
    val read_at:String?=null,val ai_generated:Boolean=false,val attachment:AttachmentDto?=null,
    val edited_at:String?=null,val deleted_for_everyone:Boolean=false,val reply_to_message_id:Int?=null,
    val reply_to:ReplyPreviewDto?=null,val reactions:List<ReactionDto> = emptyList()
)

data class ReplyPreviewDto(val id:Int=0,val sender_id:Int=0,val text:String="")
data class ReactionDto(val emoji:String="",val user_ids:List<Int> = emptyList(),val count:Int=0)

data class MomentDto(val id:Int,val user:UserDto,val text:String,val created_at:String,val expires_at:String)
data class SuggestResponse(val reply:String)


data class TrustSource(val title:String="",val url:String="")
data class TrustResult(
    val status:String="UNVERIFIED", val confidence:Int=0, val summary:String="",
    val reasons:List<String> = emptyList(), val sources:List<TrustSource> = emptyList(), val advice:String=""
)
data class AgentContact(
    val id:Int=0,val username:String="",val display_name:String="",val avatar:String?=null
)
data class NeedReplyItem(
    val chat_id:Int=0,val contact:AgentContact=AgentContact(),val message:String="",
    val created_at:String="",val category:String="FRIEND"
)
data class RecentConversation(
    val chat_id:Int=0,val contact:String="",val last_message:String="",val from_me:Boolean=false,val unread:Int=0
)
data class AgentBrief(
    val summary:String="",val unread_total:Int=0,val needs_reply_count:Int=0,
    val recent_conversations:List<RecentConversation> = emptyList(),
    val needs_reply:List<NeedReplyItem> = emptyList()
)
data class StyleProfile(
    val summary:String="",val signals:List<String> = emptyList(),val sample_size:Int=0
)
data class AgentReference(
    val chat_id:Int=0,val contact:String="",val text:String="",val created_at:String?=null
)
data class AgentAnswer(
    val answer:String="",val references:List<AgentReference> = emptyList()
)
data class ChatSummary(
    val summary:String="",val key_points:List<String> = emptyList(),val follow_ups:List<String> = emptyList()
)
data class MemorySearchItem(
    val message_id:Int=0,val chat_id:Int=0,val contact:String="",val sender:String="",
    val text:String="",val created_at:String=""
)


data class InsightBrief(
    val spending_cents:Long=0,val incoming_cents:Long=0,val transactions:Int=0,
    val detected_count:Int=0,val events:List<PhoneEvent> = emptyList(),
    val note:String=""
)


data class AttachmentDto(
    val kind:String="",val name:String?=null,val mime_type:String?=null,val size_bytes:Long?=null,
    val media_id:Int?=null,val contact_name:String?=null,val contact_phone:String?=null,
    val duration_ms:Int?=null,val transcript:String?=null
)

// LEMMIQ V1.8 Business Beta
data class BusinessProfileDto(
    val enabled:Boolean=false,
    val business_name:String="",
    val business_type:String="",
    val description:String="",
    val website:String="",
    val phone:String="",
    val email:String="",
    val hours:String="",
    val service_area:String="",
    val tone:String="Professional",
    val currency:String="AUD",
    val auto_threshold:Int=90,
    val updated_at:String?=null
)
data class BusinessKnowledgeDto(
    val id:Int=0,val category:String="OTHER",val title:String="",val content:String="",
    val source:String="Manual",val approved:Boolean=true,val active:Boolean=true,
    val created_at:String?=null,val updated_at:String?=null
)
data class BusinessChatSettingDto(
    val enabled:Boolean=false,val mode:String="ASSIST",val customer_label:String="",val updated_at:String?=null
)
data class BusinessMemoryDto(val notes:String="",val tags:String="",val updated_at:String?=null)
data class BusinessChatBundle(
    val setting:BusinessChatSettingDto=BusinessChatSettingDto(),
    val memory:BusinessMemoryDto=BusinessMemoryDto()
)
data class BusinessSourceDto(val id:Int=0,val title:String="",val category:String="")
data class BusinessSuggestionDto(
    val reply:String="",val confidence:Int=0,val requires_review:Boolean=true,
    val reason:String="",val sources:List<BusinessSourceDto> = emptyList()
)
data class BusinessLearnCandidate(val category:String="OTHER",val title:String="",val content:String="")
data class BusinessLearnResponse(
    val candidates:List<BusinessLearnCandidate> = emptyList(),val note:String=""
)


data class PushStatusDto(val firebase_configured:Boolean=false,val registered_devices:Int=0)


// LEMMIQ V2.4
data class GroupMemberDto(val id:Int=0,val username:String="",val display_name:String="",val avatar:String?=null,val avatar_url:String?=null,val role:String="MEMBER")
data class GroupDto(
    val id:Int=0,val name:String="",val created_by:Int=0,val has_photo:Boolean=false,val photo_url:String?=null,
    val member_count:Int=0,val role:String="MEMBER",val ai_mode:String="ASSIST",val tone:String="Natural",
    val last_message:String?=null,val updated_at:String?=null,val unread:Int=0,val members:List<GroupMemberDto> = emptyList()
)
data class GroupMessageDto(
    val id:Int=0,val group_id:Int=0,val sender_id:Int=0,val sender:UserDto?=null,val text:String="",
    val created_at:String="",val ai_generated:Boolean=false,val attachment:AttachmentDto?=null
)
data class GroupSummaryDto(val summary:String="",val decisions:List<String> = emptyList(),val actions:List<String> = emptyList())
data class GroupAskDto(val answer:String="",val references:List<String> = emptyList())

data class VoiceAiDto(val transcript:String="",val summary:String="",val suggested_reply:String="")
data class CallDto(
    val id:String="",val chat_id:Int=0,val caller_id:Int=0,val callee_id:Int=0,val other_user:UserDto?=null,
    val status:String="",val duration_seconds:Int=0,val started_at:String="",val answered_at:String?=null,val ended_at:String?=null
)
data class CallJoinDto(val call:CallDto=CallDto(),val ws_url:String="",val token:String="",val incoming:Boolean=false)
data class CallStatusDto(val configured:Boolean=false,val provider:String="LiveKit",val voice:Boolean=true,val video:Boolean=false)

data class StatusDto(
    val id:Int=0,val user:UserDto=UserDto(0,"",""),val kind:String="TEXT",val text:String="",
    val media_url:String?=null,val mime_type:String?=null,val visibility:String="ALL",
    val created_at:String="",val expires_at:String="",val view_count:Int?=null,val viewed:Boolean=false
)

data class TrustHistoryDto(
    val id:Int=0,val checked_text:String="",val status:String="UNVERIFIED",val confidence:Int=0,val summary:String="",
    val reasons:List<String> = emptyList(),val sources:List<TrustSource> = emptyList(),val advice:String="",
    val checked_at:String="",val cached:Boolean=false
)

data class SocialMemoryDto(
    val id:Int=0,val chat_id:Int?=null,val contact:String?=null,val memory_type:String="IMPORTANT",val title:String="",
    val detail:String="",val source_message_id:Int?=null,val due_at:String?=null,val resolved:Boolean=false,val created_at:String=""
)
data class SocialBriefDto(
    val count:Int=0,val items:List<SocialMemoryDto> = emptyList(),val promises:Int=0,val follow_ups:Int=0
)
data class SocialScanDto(val added:Int=0,val items:List<SocialMemoryDto> = emptyList(),val note:String?=null)

data class ChatPrefDto(
    val pinned:Boolean=false,val archived:Boolean=false,val favourite:Boolean=false,val muted_until:String?=null,val draft_text:String=""
)
data class PrivacyDto(val profile_photo:String="EVERYONE",val last_seen:String="EVERYONE",val status_visibility:String="EVERYONE")
data class MediaItemDto(val message_id:Int=0,val kind:String="",val name:String?=null,val mime_type:String?=null,val size_bytes:Long?=null)


// LEMMIQ V2.6 Q Agent
data class QAgentActionDto(
    val type:String="",val label:String="",val approval_required:Boolean=false,
    val permission:String="SAFE",val available:Boolean=true,val note:String?=null
)
data class QDoResponseDto(
    val mode:String="DO",val answer:String="",val references:List<AgentReference> = emptyList(),
    val actions:List<QAgentActionDto> = emptyList()
)
data class QCoordinationDto(
    val id:Int=0,val request_key:String="",val kind:String="PLAN",val prompt:String="",
    val options:List<String> = emptyList(),val response:Map<String,String> = emptyMap(),
    val status:String="PENDING",val created_at:String="",val updated_at:String="",val expires_at:String="",
    val initiator:UserDto?=null,val target:UserDto?=null,val mine:Boolean=false
)
data class QCoordinationListDto(
    val inbox:List<QCoordinationDto> = emptyList(),val outbox:List<QCoordinationDto> = emptyList()
)
data class QCoordinationCreateDto(
    val request_key:String="",val count:Int=0,val requests:List<QCoordinationDto> = emptyList(),val note:String=""
)
data class QDailyBriefDto(
    val summary:String="",val unread_total:Int=0,val needs_reply_count:Int=0,
    val needs_reply:List<NeedReplyItem> = emptyList(),val commitments:List<SocialMemoryDto> = emptyList(),
    val promises:List<SocialMemoryDto> = emptyList(),val follow_ups:List<SocialMemoryDto> = emptyList(),
    val generated_at:String=""
)
