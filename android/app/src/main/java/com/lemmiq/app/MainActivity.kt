package com.lemmiq.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color

class MainActivity:ComponentActivity(){
    override fun onCreate(savedInstanceState:Bundle?){
        super.onCreate(savedInstanceState)
        setContent{
            MaterialTheme(colorScheme=lightColorScheme(
                primary=Color(0xFF6C4DFF),secondary=Color(0xFFFF4F9A),
                background=Color(0xFFF7F7FB),surface=Color.White
            )){LemmiqApp()}
        }
    }
}
