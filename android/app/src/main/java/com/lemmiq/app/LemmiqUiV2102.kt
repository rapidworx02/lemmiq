package com.lemmiq.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/**
 * LEMMIQ V2.10.2 native Android UI patch.
 *
 * Goals:
 *  - six persistent bottom tabs
 *  - More owns the secondary destinations
 *  - Q assistant sheet contains Q actions only
 *  - floating Q button is more transparent
 */
enum class LemmiqMainTabV2102(
    val key: String,
    val label: String,
    val glyph: String
) {
    CHATS("chats", "Chats", "💬"),
    UPDATES("updates", "Updates", "⭕"),
    Q_ECONOMY("q-economy", "Q Economy", "Q+"),
    Q_PREDICT("q-predict", "Q Predict", "◇"),
    CALLS("calls", "Calls", "☎"),
    MORE("more", "More", "☰")
}

@Composable
fun LemmiqBottomNavV2102(
    selectedKey: String,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    NavigationBar(
        modifier = modifier.fillMaxWidth(),
        tonalElevation = 3.dp,
        containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.96f)
    ) {
        LemmiqMainTabV2102.entries.forEach { tab ->
            NavigationBarItem(
                selected = selectedKey == tab.key,
                onClick = { onSelect(tab.key) },
                icon = {
                    Text(
                        text = tab.glyph,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                },
                label = {
                    Text(
                        text = tab.label,
                        style = MaterialTheme.typography.labelSmall,
                        maxLines = 1
                    )
                },
                alwaysShowLabel = true
            )
        }
    }
}

data class LemmiqMoreItemV2102(
    val key: String,
    val glyph: String,
    val title: String,
    val subtitle: String
)

val LemmiqMoreItemsV2102 = listOf(
    LemmiqMoreItemV2102("profile", "🙂", "Me / Profile", "Account, photo and sign out"),
    LemmiqMoreItemV2102("trust", "🛡", "Trust / Fact Check", "Check claims and saved Trust history"),
    LemmiqMoreItemV2102("business", "💼", "Business Agent", "Business profile, knowledge and replies"),
    LemmiqMoreItemV2102("activity", "◈", "Activity", "Detected notification intelligence"),
    LemmiqMoreItemV2102("money", "💳", "Money", "Review detected payments"),
    LemmiqMoreItemV2102("settings", "⚙", "Settings", "LEMMIQ preferences and controls"),
    LemmiqMoreItemV2102("privacy", "🔒", "Privacy & Security", "Permissions, privacy and security"),
)

@Composable
fun LemmiqMoreScreenV2102(
    onOpen: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 18.dp, vertical = 14.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text(
            text = "More",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )
        Text(
            text = "Profile, Trust, Business, privacy and other LEMMIQ tools.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        LemmiqMoreItemsV2102.forEach { item ->
            ElevatedCard(
                onClick = { onOpen(item.key) },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(20.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(18.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(item.glyph, style = MaterialTheme.typography.headlineSmall)
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            item.title,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                        Spacer(Modifier.height(2.dp))
                        Text(
                            item.subtitle,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    Text("›", style = MaterialTheme.typography.headlineSmall)
                }
            }
        }
        Spacer(Modifier.height(90.dp))
    }
}

@Composable
fun LemmiqQAssistantSheetV2102(
    onCatchUp: () -> Unit,
    onPromises: () -> Unit,
    onNeedsReply: () -> Unit,
    onOpenFullQ: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Box(
            modifier = Modifier
                .width(44.dp)
                .height(4.dp)
                .align(Alignment.CenterHorizontally)
        ) {
            Surface(
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.65f),
                shape = RoundedCornerShape(99.dp),
                modifier = Modifier.fillMaxSize()
            ) {}
        }

        Row(verticalAlignment = Alignment.CenterVertically) {
            Surface(
                color = MaterialTheme.colorScheme.primary,
                shape = RoundedCornerShape(22.dp),
                modifier = Modifier.size(48.dp)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Text("Q", color = MaterialTheme.colorScheme.onPrimary)
                }
            }
            Spacer(Modifier.width(12.dp))
            Column {
                Text(
                    "Your LEMMIQ assistant",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    "Available wherever you are in LEMMIQ.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        OutlinedButton(
            onClick = onCatchUp,
            modifier = Modifier.fillMaxWidth()
        ) { Text("Catch me up") }

        OutlinedButton(
            onClick = onPromises,
            modifier = Modifier.fillMaxWidth()
        ) { Text("What did I promise?") }

        OutlinedButton(
            onClick = onNeedsReply,
            modifier = Modifier.fillMaxWidth()
        ) { Text("Which chats need a reply?") }

        Button(
            onClick = onOpenFullQ,
            modifier = Modifier.fillMaxWidth()
        ) { Text("Open full Q workspace") }

        // Intentionally NO "Profile, Trust, Business & Settings" link here.
        // Those destinations now live in the persistent More tab.
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
fun LemmiqFloatingQButtonV2102(
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    FilledTonalButton(
        onClick = onClick,
        modifier = modifier.size(64.dp),
        shape = RoundedCornerShape(32.dp),
        colors = ButtonDefaults.filledTonalButtonColors(
            containerColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.62f),
            contentColor = Color.White
        ),
        contentPadding = PaddingValues(0.dp)
    ) {
        Text(
            "Q",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.SemiBold
        )
    }
}
