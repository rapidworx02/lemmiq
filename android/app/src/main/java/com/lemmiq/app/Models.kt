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


// LEMMIQ V2.7 Q Vision + simplified Q home
data class QTodayDto(
    val summary:String="",val unread_total:Int=0,val needs_reply_count:Int=0,
    val needs_reply:List<NeedReplyItem> = emptyList(),val follow_ups:Int=0,val promises:Int=0
)
data class QMemoryCountDto(val count:Int=0,val vision_count:Int=0)
data class QToQCountDto(val pending_count:Int=0,val incoming_count:Int=0,val outgoing_count:Int=0)
data class QHomeDto(
    val today:QTodayDto=QTodayDto(),val memory:QMemoryCountDto=QMemoryCountDto(),
    val q_to_q:QToQCountDto=QToQCountDto()
)
data class VisionAnalysisDto(
    val title:String="",val category:String="OTHER",val summary:String="",val extracted_text:String="",
    val details:List<String> = emptyList(),val suggested_actions:List<String> = emptyList()
)
data class VisionHistoryItemDto(val role:String="",val text:String="")
data class VisionMemoryDto(
    val id:Int=0,val title:String="",val category:String="OTHER",val summary:String="",
    val extracted_text:String="",val analysis:VisionAnalysisDto=VisionAnalysisDto(),
    val history:List<VisionHistoryItemDto> = emptyList(),val saved:Boolean=true,
    val mime_type:String="",val original_name:String="",val media_url:String="",
    val created_at:String="",val updated_at:String=""
)


// LEMMIQ V2.8 Q Economy
data class QPlanDto(
    val code:String="",val name:String="",val price_usd:Double=0.0,val daily_rate_percent:Double=0.0,
    val daily_usd_reference:Double=0.0,val daily_q_at_current_reference:Double=0.0,
    val valid_days:Int=365,val cap_percent:Int=200,val cap_usd:Double=0.0,val cap_q_at_current_reference:Double=0.0
)
data class QSubscriptionDto(
    val id:Int=0,val package_code:String="",val package_name:String="",val purchase_usd:Double=0.0,
    val daily_rate_percent:Double=0.0,val accrued_usd_reference:Double=0.0,val accrued_q:Double=0.0,
    val cap_usd:Double=0.0,val remaining_cap_usd:Double=0.0,val status:String="ACTIVE",
    val started_at:String="",val expires_at:String="",val last_accrual_date:String="",val current_q_reference_usd:Double=0.05
)
data class QWalletDto(
    val balance_q:Double=0.0,val balance_usd_reference:Double=0.0,val q_reference_usd:Double=0.05,
    val cashout_enabled:Boolean=false,val cashout_note:String="",val basic_daily_q:Double=0.0,
    val basic_claimed_today:Boolean=false,val signup_bonus_q:Double=0.0,val referral_code:String="",
    val referral_reward_q:Double=0.0,val admin_role:String?=null,
    val packages:List<QSubscriptionDto> = emptyList(),val plans:List<QPlanDto> = emptyList()
)
data class QLedgerDto(
    val id:Int=0,val tx_id:String="",val kind:String="",val amount_q:Double=0.0,val direction:String="IN",
    val other_user_id:Int?=null,val system_wallet:String?=null,val usd_cents:Int?=null,
    val reference:String="",val note:String="",val created_at:String="",
    val feature_key:String?=null,val tier_key:String?=null,val status:String?=null
)

data class QFeatureTierRuleDto(
    val feature_key:String="",val feature_name:String="",val tier_key:String="FREE",
    val q_cost:Double=0.0,val enabled:Boolean=true,val charging_enabled:Boolean=false,
    val included_uses_daily:Int?=null,val included_uses_monthly:Int?=null,val updated_at:String=""
)
data class QReferralEventDto(
    val type:String="",val label:String="",val package_code:String?=null,val reward_q:Double=0.0,
    val status:String="",val created_at:String="",val paid_at:String?=null
)
data class QReferralItemDto(
    val user_id:Int=0,val username:String="",val display_name:String="",val current_tier:String="Free",
    val reward_q:Double=0.0,val pending_q:Double=0.0,val created_at:String="",
    val events:List<QReferralEventDto> = emptyList()
)
data class QReferralSummaryDto(
    val code:String="",val count:Int=0,val paid_users:Int=0,val earned_q:Double=0.0,val pending_q:Double=0.0,
    val items:List<QReferralItemDto> = emptyList()
)
data class QPaymentWalletDto(
    val id:Int=0,val network:String="",val package_code:String?=null,val label:String="",val address:String="",
    val active:Boolean=true,val qr_url:String="",val custom_qr:Boolean=false
)
data class QPaymentOrderDto(
    val id:Int=0,val order_code:String="",val user_id:Int=0,val package_code:String="",val package_name:String="",
    val network:String="",val expected_usdt:Double=0.0,val wallet:QPaymentWalletDto?=null,val tx_hash:String?=null,
    val explorer_url:String?=null,val status:String="",val user_note:String="",val admin_note:String="",
    val created_at:String="",val submitted_at:String?=null,val reviewed_at:String?=null
)
data class QMarketSellerDto(val id:Int=0,val username:String="",val display_name:String="")
data class QMarketMediaDto(
    val id:Int=0,val kind:String="",val name:String="",val mime_type:String="",val size_bytes:Long=0,
    val is_cover:Boolean=false,val sort_order:Int=0,val media_url:String="",val download_url:String="",val created_at:String=""
)
data class QMarketListingDto(
    val id:Int=0,val seller:QMarketSellerDto?=null,val title:String="",val description:String="",val category:String="OTHER",
    val condition:String="SERVICE",val price_q:Double=0.0,val price_usd_reference:Double=0.0,
    val inventory:Int=0,val active:Boolean=true,val media:List<QMarketMediaDto> = emptyList(),val created_at:String="",val updated_at:String=""
)
data class QMarketOrderDto(
    val id:Int=0,val order_code:String="",val listing:QMarketListingDto?=null,val buyer_id:Int=0,val seller_id:Int=0,
    val quantity:Int=1,val total_q:Double=0.0,val fee_percent:Double=0.0,val status:String="",
    val dispute_note:String="",val created_at:String="",val updated_at:String=""
)


// LEMMIQ V2.10.5 Q Predict — main Q wallet staking. Legacy PC fields remain read-only for old test records.
data class PredictPositionDto(
    val outcome:String="",
    val stake_q:Double=0.0,val payout_q:Double=0.0,val fee_q:Double=0.0,
    val stake_pc:Double=0.0,val payout_pc:Double=0.0,val fee_pc:Double=0.0,
    val status:String="OPEN"
)
data class PredictResolutionDto(val outcome:String="",val source_value:String="",val note:String="",val resolved_at:String="")
data class PredictCommentDto(val id:Int=0,val text:String="",val created_at:String="",val user:UserDto?=null)
data class PredictMarketDto(
    val id:Int=0,val market_key:String="",val question:String="",val category:String="TRENDING",val template_code:String="",
    val status:String="REVIEW",val wallet_unit:String="Q",val legacy_pc:Boolean=false,val yes_percent:Double=50.0,val no_percent:Double=50.0,
    val yes_pool_q:Double=0.0,val no_pool_q:Double=0.0,val pool_q:Double=0.0,
    val yes_pool_pc:Double=0.0,val no_pool_pc:Double=0.0,val pool_pc:Double=0.0,
    val participants:Int=0,val comments:Int=0,val trend_score:Int=0,val resolution_confidence:Int=0,
    val resolution_source_name:String="",val resolution_source_url:String="",val resolution_rule:String="",val source_type:String="",
    val close_at:String="",val resolve_after:String="",val result:String?=null,val auto_resolve:Boolean=false,val generated_by:String="",
    val agent_reason:String="",val watched:Boolean=false,val my_positions:List<PredictPositionDto> = emptyList(),
    val resolution:PredictResolutionDto?=null,val discussion:List<PredictCommentDto> = emptyList(),val created_at:String="",val updated_at:String=""
)
// Legacy wallet is retained only so older V2.9 server payloads deserialize safely. New UI uses QWalletDto.balance_q.
data class PredictWalletDto(
    val balance_q:Double=0.0,val lifetime_won_q:Double=0.0,val lifetime_staked_q:Double=0.0,
    val balance_pc:Double=0.0,val starting_pc:Double=0.0,val lifetime_won_pc:Double=0.0,val lifetime_staked_pc:Double=0.0,
    val markets_won:Int=0,val markets_resolved:Int=0
)
data class PredictHomeDto(
    val mode:String="Q_WALLET",val real_q_enabled:Boolean=false,val wallet:PredictWalletDto=PredictWalletDto(),
    val fee_percent:Double=0.0,val notice:String="",val live:List<PredictMarketDto> = emptyList(),
    val resolved:List<PredictMarketDto> = emptyList(),val categories:List<String> = emptyList(),
    val minimum_stake_q:Double=0.0,val maximum_stake_q:Double=0.0
)
data class PredictStakeResponseDto(
    val market:PredictMarketDto=PredictMarketDto(),val wallet_balance_q:Double=0.0,val wallet_balance_pc:Double=0.0
)
data class PredictMyDto(
    val market:PredictMarketDto=PredictMarketDto(),val outcome:String="",
    val stake_q:Double=0.0,val payout_q:Double=0.0,val stake_pc:Double=0.0,val payout_pc:Double=0.0,val status:String=""
)
data class PredictLeaderDto(
    val rank:Int=0,val user:UserDto?=null,val accuracy_percent:Double=0.0,
    val net_won_q:Double=0.0,val net_won_pc:Double=0.0,val resolved:Int=0
)
