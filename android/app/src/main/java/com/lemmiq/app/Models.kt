package com.lemmiq.app

data class UserDto(val id:Int,val username:String,val display_name:String,val avatar:String?=null)
data class AuthResponse(val token:String,val user:UserDto)
data class ChatDto(
    val id:Int,val other_user:UserDto,val category:String="FRIEND",val ai_mode:String="ASSIST",
    val tone:String="Natural",val last_message:String?=null,val updated_at:String?=null,val unread:Int=0
)
data class MessageDto(
    val id:Int,val chat_id:Int,val sender_id:Int,val text:String,val created_at:String,
    val read_at:String?=null,val ai_generated:Boolean=false,val attachment:AttachmentDto?=null
)
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
    val media_id:Int?=null,val contact_name:String?=null,val contact_phone:String?=null
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
