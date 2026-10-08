package com.lemmiq.app

import android.content.Context
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.time.OffsetDateTime

/**
 * Local V2.10.4 Q Predict analysis history.
 * Server persistence can mirror this later, but this prevents users from having to rerun an analysis
 * simply to reopen the latest answer on the same Android device.
 */
data class SavedPredictAnalysisV2104(
    val marketId:Int=0,
    val question:String="",
    val answer:String="",
    val references:List<AgentReference> = emptyList(),
    val analysedAt:String="",
    val followUp:String="",
    val version:Int=1
)

object PredictAnalysisHistoryV2104 {
    private const val PREF = "lemmiq_q_predict_analysis_v2104"
    private fun key(userId:Int) = "items_$userId"
    private const val MAX_ITEMS = 60
    private val gson = Gson()

    fun list(context:Context,userId:Int):List<SavedPredictAnalysisV2104> {
        val raw=context.getSharedPreferences(PREF,Context.MODE_PRIVATE).getString(key(userId),"[]") ?: "[]"
        return runCatching {
            val t=object:TypeToken<List<SavedPredictAnalysisV2104>>(){}.type
            gson.fromJson<List<SavedPredictAnalysisV2104>>(raw,t) ?: emptyList()
        }.getOrElse { emptyList() }
            .sortedByDescending { it.analysedAt }
    }

    fun latestForMarket(context:Context,userId:Int,marketId:Int):SavedPredictAnalysisV2104? =
        list(context,userId).firstOrNull { it.marketId==marketId }

    fun save(
        context:Context,
        userId:Int,
        marketId:Int,
        question:String,
        result:AgentAnswer,
        followUp:String=""
    ):SavedPredictAnalysisV2104 {
        val existing=list(context,userId)
        val item=SavedPredictAnalysisV2104(
            marketId=marketId,
            question=question,
            answer=result.answer,
            references=result.references,
            analysedAt=OffsetDateTime.now().toString(),
            followUp=followUp,
            version=(existing.count{it.marketId==marketId}+1)
        )
        val merged=(listOf(item)+existing).take(MAX_ITEMS)
        context.getSharedPreferences(PREF,Context.MODE_PRIVATE).edit()
            .putString(key(userId),gson.toJson(merged)).apply()
        return item
    }

    fun clear(context:Context,userId:Int){
        context.getSharedPreferences(PREF,Context.MODE_PRIVATE).edit().remove(key(userId)).apply()
    }
}
