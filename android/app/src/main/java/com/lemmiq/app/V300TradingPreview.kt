package com.lemmiq.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.text.NumberFormat

private data class PreviewPool300(val name:String,val minimum:Int,val capacity:Int,val fee:Int)
private val pools300=listOf(PreviewPool300("Q Shield AI",100,1000,30),PreviewPool300("Q Pulse AI",500,5000,20),PreviewPool300("Q Surge AI",1000,10000,10))

/** Read-only product concept. No trading requests, allocation control or balance mutation. */
@Composable
fun V300TradingPreview(reference:Double){
    val valid=reference.isFinite()&&reference>0.0
    val fmt=NumberFormat.getNumberInstance().apply{maximumFractionDigits=6}
    Column(Modifier.fillMaxWidth(),verticalArrangement=Arrangement.spacedBy(10.dp)){
        Text("AI Trading Pools",fontSize=24.sp,fontWeight=FontWeight.Bold)
        Text("Powered by RapidTradeX · Coming Soon",color=MaterialTheme.colorScheme.primary,fontSize=13.sp)
        Text("Planned shared Q Predict wallet. No separate Q purchase. Q Economy and Demo balances remain separate.",fontSize=13.sp)
        Text(if(valid)"Reference: ${fmt.format(reference)} USDT/Q" else "Reference price unavailable · Q equivalents not shown",fontSize=12.sp)
        for(pool in pools300){
            Card(Modifier.fillMaxWidth(),shape=RoundedCornerShape(15.dp)){
                Column(Modifier.padding(14.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
                    Text(pool.name,fontSize=18.sp,fontWeight=FontWeight.Bold)
                    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)){
                        Column(Modifier.weight(1f)){Text("Minimum allocation",fontSize=11.sp);Text("${fmt.format(pool.minimum)} USDT",fontWeight=FontWeight.Bold);if(valid)Text("≈ ${fmt.format(pool.minimum/reference)} Q",fontSize=11.sp)}
                        Column(Modifier.weight(1f)){Text("Pool capacity",fontSize=11.sp);Text("${fmt.format(pool.capacity)} USDT",fontWeight=FontWeight.Bold);if(valid)Text("≈ ${fmt.format(pool.capacity/reference)} Q",fontSize=11.sp)}
                    }
                    Text("Admin performance fee ${pool.fee}% · Member profit share ${100-pool.fee}%",fontSize=12.sp)
                    Text("Proposed: 12 monthly unit unlocks · Monthly profit settlement · Sequential pools",fontSize=11.sp)
                    Text("Coming Soon · No allocations",color=MaterialTheme.colorScheme.primary,fontWeight=FontWeight.Medium)
                }
            }
        }
        Text("Concept only. No trading, deposits, allocations or profit credits are available. Capital losses are possible. Returns and redemptions are not guaranteed. Subject to appropriate financial authorisation.",fontSize=12.sp)
    }
}
