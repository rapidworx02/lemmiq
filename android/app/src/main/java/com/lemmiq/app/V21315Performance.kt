/* LEMMIQ 2.13.15 — bounded Android message history pagination. */
package com.lemmiq.app

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

@Composable
fun V21315LoadOlderMessages(vm:LemmiqViewModel){
    if(vm.canLoadOlderDirectMessages){
        OutlinedButton(
            onClick={vm.loadOlderDirectMessages()},
            enabled=!vm.loadingOlderDirectMessages,
            modifier=Modifier.fillMaxWidth()
        ){
            Text(if(vm.loadingOlderDirectMessages)"Loading older messages..." else "↑ Load older messages")
        }
    }
}
