package com.lemmiq.app

import android.content.Intent
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.FileProvider
import coil.compose.AsyncImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.util.Locale

private val CreatorPurple = Color(0xFF6C4DFF)
private val CreatorBg = Color(0xFFF7F7FB)
private val CreatorMuted = Color(0xFF777A8D)
private val CreatorGreen = Color(0xFF16865F)
private fun qText(q: Double) = String.format(Locale.US, "%,.2f", q).trimEnd('0').trimEnd('.')
private fun qInput(s: String): Double? = s.trim().toDoubleOrNull()?.takeIf { it.isFinite() && it >= 0.0 && it <= 100000.0 }

@Composable
private fun CreatorTag(text: String) {
    Surface(color = Color(0xFFF0ECFF), shape = RoundedCornerShape(14.dp)) {
        Text(text, Modifier.padding(horizontal = 9.dp, vertical = 5.dp), fontSize = 10.sp, color = CreatorPurple)
    }
}

@Composable
private fun CreatorAvatar(profile: CreatorProfileNative, size: Int = 52) {
    val uri = profile.avatar_url?.let { if (it.startsWith("https://")) it else BuildConfig.API_BASE_URL.trimEnd('/') + it }
    Box(Modifier.size(size.dp).clip(CircleShape).background(Color(0xFFEAE6FF)), contentAlignment = Alignment.Center) {
        if (uri != null) AsyncImage(model = uri, contentDescription = profile.display_name,
            modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        else Text(profile.display_name.take(1).uppercase(), fontWeight = FontWeight.Bold, color = CreatorPurple)
    }
}

@Composable
private fun CreatorConfirm(title: String, detail: String, confirmText: String = "Confirm", onCancel: () -> Unit, onConfirm: () -> Unit) {
    AlertDialog(onDismissRequest = onCancel, title = { Text(title) },
        text = { Text(detail) }, confirmButton = { Button(onClick = onConfirm) { Text(confirmText) } },
        dismissButton = { TextButton(onClick = onCancel) { Text("Cancel") } })
}

/** Entry point installed under More and the Me/Profile shortcut. Native Compose, not a WebView. */
@Composable
fun V2131CreatorsAndroidScreen(vm: LemmiqViewModel) {
    val context = LocalContext.current
    val client = remember(vm.store) { CreatorApiV2131(context.applicationContext, vm.store) }
    val scope = rememberCoroutineScope()
    var tab by remember { mutableIntStateOf(0) }
    var query by remember { mutableStateOf("") }
    var category by remember { mutableStateOf("") }
    var profiles by remember { mutableStateOf<List<CreatorProfileNative>>(emptyList()) }
    var mine by remember { mutableStateOf(CreatorMineNative()) }
    var config by remember { mutableStateOf(CreatorConfigNative()) }
    var selectedId by remember { mutableStateOf<Int?>(null) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var banner by remember { mutableStateOf<String?>(null) }
    var reload by remember { mutableIntStateOf(0) }

    fun refresh() { reload++ }
    LaunchedEffect(tab, query, category, reload) {
        busy = true
        error = null
        try {
            config = client.config()
            if (tab == 0 || tab == 1) profiles = client.discover(query, category, tab == 1)
            if (tab == 2 || tab == 3) mine = client.mine()
        } catch (e: Exception) { error = e.message ?: "Unable to load Q Creators" }
        finally { busy = false }
    }

    Column(Modifier.fillMaxSize().background(CreatorBg)) {
        if (selectedId != null) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                TextButton({ selectedId = null; refresh() }) { Text("‹ Q Creators") }
                Spacer(Modifier.weight(1f))
                Text("Profile", fontWeight = FontWeight.SemiBold)
            }
            CreatorProfileDetails(client, selectedId!!, config, onError = { error = it }, onUpdated = ::refresh)
        } else {
            Column(Modifier.fillMaxWidth().background(Color.White).padding(horizontal = 16.dp, vertical = 12.dp)) {
                Text("Q Creators", fontSize = 26.sp, fontWeight = FontWeight.Black)
                Text("Discover · Follow · Subscribe · Create", color = CreatorMuted, fontSize = 11.sp)
                Spacer(Modifier.height(10.dp))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                    items(listOf("Discover", "Following", "Creator Studio", "Requests")) { title ->
                        val index = listOf("Discover", "Following", "Creator Studio", "Requests").indexOf(title)
                        FilterChip(selected = tab == index, onClick = { tab = index },
                            label = { Text(title, fontSize = 11.sp) })
                    }
                }
            }
            if (tab == 0 || tab == 1) {
                OutlinedTextField(query, { query = it }, Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 5.dp),
                    singleLine = true, label = { Text("Search creator or @username") })
                LazyRow(Modifier.padding(horizontal = 14.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(listOf("", "FASHION", "LIFESTYLE", "FITNESS", "GLAMOUR", "EDUCATION", "MUSIC", "OTHER")) { c ->
                        FilterChip(selected = c == category, onClick = { category = c }, label = { Text(if (c.isBlank()) "All" else c.lowercase().replaceFirstChar { it.uppercase() }, fontSize = 10.sp) })
                    }
                }
            }
            if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (tab == 0 || tab == 1) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 28.dp)) {
                    if (profiles.isEmpty() && !busy) item { CreatorEmpty("No creators found", "Approved professional profiles will appear here.") }
                    items(profiles, key = { it.id }) { profile ->
                        Card(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 5.dp).clickable { selectedId = profile.id }, shape = RoundedCornerShape(18.dp)) {
                            Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                                CreatorAvatar(profile)
                                Spacer(Modifier.width(12.dp))
                                Column(Modifier.weight(1f)) {
                                    Text(profile.display_name, fontWeight = FontWeight.Bold, maxLines = 1)
                                    Text("@${profile.username} · ${profile.category.lowercase()}", color = CreatorMuted, fontSize = 11.sp)
                                    Text("${profile.followers} followers · ${if (profile.monthly_q == 0.0) "Free" else "${qText(profile.monthly_q)} Q / 30 days"}", fontSize = 11.sp)
                                }
                                Text("›", fontSize = 24.sp, color = CreatorPurple)
                            }
                        }
                    }
                }
            } else if (tab == 2) {
                CreatorStudio(client, mine, config, onError = { error = it }, onSuccess = { banner = it; refresh() })
            } else {
                CreatorRequests(client, onError = { error = it }, onSuccess = { banner = it })
            }
        }
    }
    error?.let { message ->
        AlertDialog(onDismissRequest = { error = null }, title = { Text("Q Creators") },
            text = { Text(message) }, confirmButton = { TextButton({ error = null }) { Text("OK") } })
    }
    banner?.let { message ->
        AlertDialog(onDismissRequest = { banner = null }, title = { Text("LEMMIQ") },
            text = { Text(message) }, confirmButton = { TextButton({ banner = null }) { Text("OK") } })
    }
}

@Composable private fun CreatorEmpty(title: String, sub: String) {
    Column(Modifier.fillMaxWidth().padding(30.dp), horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(title, fontWeight = FontWeight.SemiBold)
        Text(sub, fontSize = 12.sp, color = CreatorMuted)
    }
}

@Composable
private fun CreatorProfileDetails(client: CreatorApiV2131, creatorId: Int, config: CreatorConfigNative,
                                  onError: (String) -> Unit, onUpdated: () -> Unit) {
    val scope = rememberCoroutineScope()
    var page by remember(creatorId) { mutableStateOf<CreatorPageNative?>(null) }
    var gallery by remember(creatorId) { mutableStateOf<List<CreatorGalleryNative>>(emptyList()) }
    var tab by remember(creatorId) { mutableIntStateOf(0) }
    var refresh by remember { mutableIntStateOf(0) }
    var confirm by remember { mutableStateOf<Pair<String, suspend () -> Unit>?>(null) }
    var viewer by remember { mutableStateOf<Int?>(null) }
    var postViewer by remember { mutableStateOf<CreatorPostNative?>(null) }
    var requestKind by remember { mutableStateOf<String?>(null) }
    var requestMessage by remember { mutableStateOf("") }
    var scheduleAt by remember { mutableStateOf("") }
    var tipValue by remember { mutableStateOf("10") }
    var busy by remember { mutableStateOf(false) }

    LaunchedEffect(creatorId, refresh) {
        try { page = client.profile(creatorId); gallery = client.gallery(creatorId) }
        catch (e: Exception) { onError(e.message ?: "Unable to open creator") }
    }
    val p = page?.profile
    if (p == null) { CircularProgressIndicator(Modifier.padding(22.dp)); return }

    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(horizontal = 14.dp, vertical = 6.dp),
        verticalArrangement = Arrangement.spacedBy(9.dp)) {
        item {
            Card(shape = RoundedCornerShape(20.dp)) {
                Column(Modifier.fillMaxWidth().padding(17.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CreatorAvatar(p, 64); Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(p.display_name, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                            Text("@${p.username}", color = CreatorMuted, fontSize = 12.sp)
                            CreatorTag(p.category + " · " + p.level)
                        }
                    }
                    if (p.bio.isNotBlank()) Text(p.bio)
                    Text("${p.followers} followers  •  ${p.subscribers} subscribers", color = CreatorMuted, fontSize = 12.sp)
                    if (!p.mine) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(onClick = {
                                scope.launch { busy = true; try {
                                    if (p.following) client.unfollow(p.id) else client.follow(p.id)
                                    refresh++; onUpdated()
                                } catch (e: Exception) { onError(e.message ?: "Follow failed") } finally { busy = false } }
                            }, enabled = !busy, modifier = Modifier.weight(1f)) { Text(if (p.following) "Following ✓" else "Follow") }
                            Button(onClick = { confirm = "Subscribe for ${qText(p.monthly_q)} Q" to suspend { client.subscribe(p.id); refresh++; onUpdated(); Unit } },
                                enabled = !busy && !p.subscribed && (p.monthly_q == 0.0 || config.payments_enabled),
                                modifier = Modifier.weight(1f)) {
                                Text(if (p.subscribed) "Subscribed ✓" else if (p.monthly_q == 0.0) "Subscribe free" else "${qText(p.monthly_q)} Q / 30d", fontSize = 11.sp)
                            }
                        }
                        if (p.tips_enabled) Row(verticalAlignment = Alignment.CenterVertically) {
                            OutlinedTextField(tipValue, { tipValue = it }, Modifier.width(95.dp), label = { Text("Tip Q") }, singleLine = true)
                            Spacer(Modifier.width(6.dp))
                            OutlinedButton(onClick = {
                                val amt = qInput(tipValue)
                                if (amt == null || amt <= 0) onError("Enter a valid Q tip")
                                else confirm = "Send ${qText(amt)} Q tip" to suspend { client.tip(p.id, amt); refresh++; Unit }
                            }, enabled = config.payments_enabled) { Text("Send tip") }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                            // V2134_LEGACY_CHAT_DISABLED: paid chat uses separate professional screen
                            if (p.chat_q > 0) Text("Paid Chat: open Creator Inbox → Discover", fontSize = 11.sp, color = CreatorMuted)
                            if (p.voice_q > 0) TextButton({ requestKind = "VOICE" }) { Text("Voice ${qText(p.voice_q)} Q", fontSize = 11.sp) }
                            if (p.video_q > 0) TextButton({ requestKind = "VIDEO" }) { Text("Video ${qText(p.video_q)} Q", fontSize = 11.sp) }
                        }
                    }
                }
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(tab == 0, { tab = 0 }, label = { Text("Posts") })
                FilterChip(tab == 1, { tab = 1 }, label = { Text("Exclusive photos & videos") })
            }
        }
        if (tab == 0) {
            if (page?.posts.isNullOrEmpty()) item { CreatorEmpty("No posts yet", "Creator posts will appear after approval") }
            items(page?.posts.orEmpty(), key = { it.id }) { post ->
                Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp)) {
                    Column(Modifier.padding(15.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(post.title, Modifier.weight(1f), fontWeight = FontWeight.Bold)
                            CreatorTag(post.visibility)
                        }
                        if (post.teaser.isNotBlank()) Text(post.teaser, fontSize = 12.sp)
                        if (post.unlocked) {
                            post.body?.let { if (it.isNotBlank()) Text(it) }
                            if (post.media_url != null) OutlinedButton({ postViewer = post }) { Text("View ${post.kind.lowercase()} securely") }
                        } else {
                            Text("🔒 Locked content", color = CreatorMuted)
                            Button(onClick = {
                                confirm = "Unlock post for ${qText(post.price_q)} Q" to suspend { client.unlockPost(post.id); refresh++; Unit }
                            }, enabled = config.payments_enabled && post.visibility == "PPV") { Text("Unlock ${qText(post.price_q)} Q") }
                        }
                        if (p.mine) Text("Moderation: ${post.review}", fontSize = 10.sp, color = CreatorMuted)
                    }
                }
            }
        } else {
            if (gallery.isEmpty()) item { CreatorEmpty("No exclusive content yet", "Photos, videos and albums appear here") }
            items(gallery, key = { it.id }) { item ->
                Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp)) {
                    Column(Modifier.padding(15.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(if (item.kind == "VIDEO") "▶" else if (item.kind == "ALBUM") "▦" else "▧", fontSize = 29.sp)
                            Spacer(Modifier.width(10.dp))
                            Column(Modifier.weight(1f)) {
                                Text(item.title, fontWeight = FontWeight.Bold)
                                Text("${item.media_count} file(s) · ${item.visibility}", fontSize = 11.sp, color = CreatorMuted)
                            }
                            CreatorTag(if (item.visibility == "PPV") "${qText(item.price_q)} Q" else "Subscribers")
                        }
                        if (item.teaser.isNotBlank()) Text(item.teaser, fontSize = 12.sp)
                        if (p.mine) Text("Moderation: ${item.review}", color = CreatorMuted, fontSize = 10.sp)
                        if (item.unlocked) Button(onClick = { viewer = item.id }) { Text("View media") }
                        else Button(onClick = {
                            confirm = "Unlock exclusive for ${qText(item.price_q)} Q" to suspend { client.unlockGallery(item.id); refresh++; Unit }
                        }, enabled = config.payments_enabled && item.visibility == "PPV") { Text("Unlock for ${qText(item.price_q)} Q") }
                    }
                }
            }
        }
    }

    viewer?.let { CreatorGalleryMediaDialog(client, it) { viewer = null } }
    postViewer?.let { post -> CreatorSingleMediaDialog(client, post.media_url ?: "", post.kind, post.title) { postViewer = null } }
    confirm?.let { pair ->
        CreatorConfirm(pair.first, "LEMMIQ will charge Q only if this is a paid purchase. Confirm the price and creator before proceeding.",
            onCancel = { confirm = null }, onConfirm = {
                val op = pair.second; confirm = null; busy = true
                scope.launch { try { op(); refresh++; onUpdated() } catch (e: Exception) { onError(e.message ?: "Creator payment failed") }
                    finally { busy = false } }
            })
    }
    requestKind?.let { kind ->
        AlertDialog(onDismissRequest = { requestKind = null }, title = { Text("Paid $kind request") },
            text = { Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
                Text("Q is reserved until the request is confirmed or cancelled, under LEMMIQ's settlement rules.", fontSize = 12.sp)
                OutlinedTextField(requestMessage, { requestMessage = it }, label = { Text("Message / request details") })
                if (kind != "CHAT") OutlinedTextField(scheduleAt, { scheduleAt = it },
                    label = { Text("Date/time with timezone (ISO 8601)") },
                    placeholder = { Text("2026-12-01T18:00:00+11:00") })
            } }, confirmButton = { Button(onClick = {
                val k = kind; val m = requestMessage; val whenAt = if (kind == "CHAT") null else scheduleAt.trim()
                requestKind = null
                scope.launch { try { client.request(p.id, k, m, whenAt) } catch (e: Exception) { onError(e.message ?: "Request failed") } }
            }, enabled = config.payments_enabled && requestMessage.trim().length >= 3 && (kind == "CHAT" || scheduleAt.contains('T'))) { Text("Reserve Q & request") } },
            dismissButton = { TextButton({ requestKind = null }) { Text("Cancel") } })
    }
}

@Composable
private fun CreatorStudio(client: CreatorApiV2131, mine: CreatorMineNative, config: CreatorConfigNative,
                          onError: (String) -> Unit, onSuccess: (String) -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val profile = mine.profile
    var bio by remember(profile?.id) { mutableStateOf(profile?.bio.orEmpty()) }
    var category by remember(profile?.id) { mutableStateOf(profile?.category ?: "LIFESTYLE") }
    var level by remember(profile?.id) { mutableStateOf(profile?.level ?: "MAINSTREAM") }
    var adultInterest by remember(profile?.id) { mutableStateOf(profile?.adult_requested ?: false) }
    var monthly by remember(profile?.id) { mutableStateOf(profile?.monthly_q?.toString() ?: "0") }
    var chat by remember(profile?.id) { mutableStateOf(profile?.chat_q?.toString() ?: "0") }
    var voice by remember(profile?.id) { mutableStateOf(profile?.voice_q?.toString() ?: "0") }
    var video by remember(profile?.id) { mutableStateOf(profile?.video_q?.toString() ?: "0") }
    var tips by remember(profile?.id) { mutableStateOf(profile?.tips_enabled ?: true) }
    var status by remember { mutableStateOf("Profile") }
    var busy by remember { mutableStateOf(false) }
    var assetTitle by remember { mutableStateOf("") }
    var assets by remember { mutableStateOf<List<CreatorAssetNative>>(emptyList()) }
    var gallery by remember { mutableStateOf<List<CreatorGalleryNative>>(emptyList()) }
    var earnings by remember { mutableStateOf<CreatorEarningsNative?>(null) }
    var postTitle by remember { mutableStateOf("") }
    var postTeaser by remember { mutableStateOf("") }
    var postBody by remember { mutableStateOf("") }
    var postVisibility by remember { mutableStateOf("PUBLIC") }
    var postPrice by remember { mutableStateOf("25") }
    var postMedia by remember { mutableStateOf<Uri?>(null) }
    var itemTitle by remember { mutableStateOf("") }
    var itemTeaser by remember { mutableStateOf("") }
    var itemVisibility by remember { mutableStateOf("PPV") }
    var itemPrice by remember { mutableStateOf("50") }
    val selectedAssets = remember { mutableStateListOf<Int>() }
    var transferAmount by remember { mutableStateOf("") }
    var refresh by remember { mutableIntStateOf(0) }
    var viewGallery by remember { mutableStateOf<Int?>(null) }

    LaunchedEffect(profile?.status, refresh) {
        if (profile?.status == "APPROVED") {
            try { assets = client.library(); gallery = client.galleryMine(); earnings = client.earnings() }
            catch (e: Exception) { onError(e.message ?: "Studio refresh failed") }
        }
    }
    val libraryPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) scope.launch {
            busy = true
            try { client.uploadAsset(uri, assetTitle.trim(), level); assetTitle = ""; refresh++; onSuccess("Upload submitted for moderation. It cannot be sold until approved.") }
            catch (e: Exception) { onError(e.message ?: "Upload failed") }
            finally { busy = false }
        }
    }
    val postPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri -> postMedia = uri }

    Column(Modifier.fillMaxSize()) {
        LazyRow(Modifier.padding(12.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            items(listOf("Profile", "Posts", "Media Library", "Exclusive Gallery", "Earnings")) { t ->
                FilterChip(status == t, { status = t }, label = { Text(t, fontSize = 10.sp) })
            }
        }
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 15.dp, vertical = 7.dp),
            verticalArrangement = Arrangement.spacedBy(9.dp)) {
            if (profile == null || status == "Profile") {
                Card { Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                    Text("Professional Creator", fontSize = 20.sp, fontWeight = FontWeight.Bold)
                    Text(if (profile == null) "Apply to convert your existing account" else "Status: ${profile.status}", color = CreatorMuted)
                    Text("Creator uploads may be inspected by authorised LEMMIQ moderators for policy and safety review. Individual inspections do not generate a notification.", fontSize = 11.sp, color = CreatorMuted)
                    OutlinedTextField(bio, { bio = it.take(900) }, Modifier.fillMaxWidth(), label = { Text("Creator bio") }, minLines = 2)
                    Text("Category", fontWeight = FontWeight.SemiBold)
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        items(listOf("FASHION", "LIFESTYLE", "FITNESS", "GLAMOUR", "MUSIC", "ART", "EDUCATION", "GAMING", "OTHER")) { c ->
                            FilterChip(category == c, { category = c }, label = { Text(c.lowercase(), fontSize = 10.sp) })
                        }
                    }
                    Text("Publishing level", fontWeight = FontWeight.SemiBold)
                    Row(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                        FilterChip(level == "MAINSTREAM", { level = "MAINSTREAM" }, label = { Text("Mainstream") })
                        FilterChip(level == "GLAMOUR", { level = "GLAMOUR" }, label = { Text("Non-explicit glamour") })
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(adultInterest, { adultInterest = it })
                        Text("Register interest in separately verified 18+ web service", fontSize = 12.sp)
                    }
                    Text("Set your service prices (Q)")
                    OutlinedTextField(monthly, { monthly = it }, Modifier.fillMaxWidth(), label = { Text("Subscription Q / 30 days (0 = free)") })
                    Row(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                        OutlinedTextField(chat, { chat = it }, Modifier.weight(1f), label = { Text("Chat Q") })
                        OutlinedTextField(voice, { voice = it }, Modifier.weight(1f), label = { Text("Voice Q") })
                    }
                    OutlinedTextField(video, { video = it }, Modifier.fillMaxWidth(), label = { Text("Video session Q") })
                    Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(tips, { tips = it }); Text("Allow Q tips") }
                    Text("Commission: ${qText(config.fee_percent)}%. Displayed net proceeds are estimates until settled.", fontSize = 11.sp, color = CreatorMuted)
                    Button(onClick = {
                        val values = listOf(monthly, chat, voice, video).map { qInput(it) }
                        if (values.any { it == null }) { onError("Enter valid Q prices between 0 and 100,000"); return@Button }
                        busy = true
                        scope.launch { try {
                            client.saveProfile(mapOf("bio" to bio, "category" to category, "level" to level,
                                "adult_requested" to adultInterest, "monthly_q" to values[0]!!, "chat_q" to values[1]!!,
                                "voice_q" to values[2]!!, "video_q" to values[3]!!, "tips_enabled" to tips))
                            onSuccess("Professional profile saved. Master Admin approval is required before publishing.")
                        } catch (e: Exception) { onError(e.message ?: "Cannot save creator settings") }
                        finally { busy = false } }
                    }, enabled = !busy, modifier = Modifier.fillMaxWidth()) { Text("Save professional settings") }
                } }
            } else if (profile.status != "APPROVED") {
                CreatorEmpty("Creator approval pending", "Publishing and paid media are available only after Master Admin approval.")
            } else when (status) {
                "Posts" -> {
                    Text("Create a post", fontSize = 20.sp, fontWeight = FontWeight.Bold)
                    OutlinedTextField(postTitle, { postTitle = it.take(140) }, Modifier.fillMaxWidth(), label = { Text("Title") })
                    OutlinedTextField(postTeaser, { postTeaser = it.take(240) }, Modifier.fillMaxWidth(), label = { Text("Public teaser") })
                    OutlinedTextField(postBody, { postBody = it.take(12000) }, Modifier.fillMaxWidth(), label = { Text("Post text") }, minLines = 3)
                    Text("Visibility")
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                        items(listOf("PUBLIC", "FOLLOWERS", "SUBSCRIBERS", "PPV")) { v ->
                            FilterChip(postVisibility == v, { postVisibility = v }, label = { Text(v, fontSize = 10.sp) })
                        }
                    }
                    if (postVisibility == "PPV") OutlinedTextField(postPrice, { postPrice = it }, Modifier.fillMaxWidth(), label = { Text("Post unlock price Q") })
                    OutlinedButton(onClick = { postPicker.launch("*/*") }) { Text(if (postMedia == null) "Attach photo/video (optional)" else "Selected media: ${postMedia!!.lastPathSegment.orEmpty().take(35)}") }
                    Text("Only JPG, PNG, WebP, MP4 or WebM. One file per post; use Exclusive Gallery for albums.", fontSize = 11.sp, color = CreatorMuted)
                    Button(onClick = {
                        val price = if (postVisibility == "PPV") qInput(postPrice) else 0.0
                        if (price == null || (postVisibility == "PPV" && price <= 0)) { onError("Enter a valid, positive PPV price"); return@Button }
                        busy = true
                        scope.launch { try {
                            val post = client.createPost(postTitle, postTeaser, postBody, postVisibility, price, level)
                            postMedia?.let { client.uploadPostMedia(post.id, it) }
                            postTitle = ""; postTeaser = ""; postBody = ""; postMedia = null
                            onSuccess("Post submitted to Master Admin moderation.")
                        } catch (e: Exception) { onError(e.message ?: "Cannot publish post") }
                        finally { busy = false } }
                    }, enabled = !busy && postTitle.trim().length >= 3 && postBody.trim().isNotEmpty()) { Text("Submit post for approval") }
                }
                "Media Library" -> {
                    Text("Creator Media Library", fontSize = 20.sp, fontWeight = FontWeight.Bold)
                    Text("Upload approved photos and videos once, then reuse them for posts, albums and chat offers.", fontSize = 12.sp, color = CreatorMuted)
                    OutlinedTextField(assetTitle, { assetTitle = it.take(140) }, Modifier.fillMaxWidth(), label = { Text("Media title") })
                    Button(onClick = { libraryPicker.launch("*/*") }, enabled = assetTitle.trim().length >= 3 && !busy) { Text("Upload photo or video") }
                    OutlinedButton({ refresh++ }) { Text("Refresh moderation status") }
                    assets.forEach { a ->
                        Card { Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(if (a.kind == "VIDEO") "▶" else "▧", fontSize = 24.sp)
                            Spacer(Modifier.width(10.dp))
                            Column(Modifier.weight(1f)) { Text(a.title, fontWeight = FontWeight.SemiBold); Text("#${a.id} · ${a.review}", color = CreatorMuted, fontSize = 11.sp) }
                            if (a.review == "APPROVED") CreatorTag("Ready")
                        } }
                    }
                }
                "Exclusive Gallery" -> {
                    Text("Exclusive photos & videos", fontSize = 20.sp, fontWeight = FontWeight.Bold)
                    Text("Select one approved photo/video or multiple files for an album.", fontSize = 11.sp, color = CreatorMuted)
                    OutlinedTextField(itemTitle, { itemTitle = it.take(140) }, Modifier.fillMaxWidth(), label = { Text("Gallery item title") })
                    OutlinedTextField(itemTeaser, { itemTeaser = it.take(240) }, Modifier.fillMaxWidth(), label = { Text("Teaser") })
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(listOf("PPV", "SUBSCRIBERS")) { v ->
                            FilterChip(itemVisibility == v, { itemVisibility = v }, label = { Text(if (v == "PPV") "Pay per unlock" else "Included in subscription") })
                        }
                    }
                    if (itemVisibility == "PPV") OutlinedTextField(itemPrice, { itemPrice = it }, Modifier.fillMaxWidth(), label = { Text("Unlock price Q") })
                    Text("Choose approved media (${selectedAssets.size}/20)", fontWeight = FontWeight.SemiBold)
                    assets.filter { it.review == "APPROVED" }.forEach { a ->
                        Row(Modifier.fillMaxWidth().clickable {
                            if (selectedAssets.contains(a.id)) selectedAssets.remove(a.id)
                            else if (selectedAssets.size < 20) selectedAssets.add(a.id)
                        }.padding(3.dp), verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(selectedAssets.contains(a.id), onCheckedChange = {
                                if (it && selectedAssets.size < 20) selectedAssets.add(a.id)
                                else if (!it) selectedAssets.remove(a.id)
                            })
                            Text("${a.kind} · ${a.title} #${a.id}", fontSize = 12.sp)
                        }
                    }
                    Button(onClick = {
                        val price = if (itemVisibility == "PPV") qInput(itemPrice) else 0.0
                        if (price == null || (itemVisibility == "PPV" && price <= 0)) { onError("Enter a valid positive Q price"); return@Button }
                        val selected = assets.filter { it.id in selectedAssets }
                        val kind = when { selected.size > 1 -> "ALBUM"; selected.firstOrNull()?.kind == "VIDEO" -> "VIDEO"; else -> "PHOTO" }
                        busy = true
                        scope.launch { try {
                            client.createGallery(itemTitle, itemTeaser, kind, itemVisibility, price, selectedAssets.toList())
                            itemTitle = ""; itemTeaser = ""; selectedAssets.clear(); refresh++
                            onSuccess("Exclusive item submitted for Master Admin review.")
                        } catch (e: Exception) { onError(e.message ?: "Gallery creation failed") }
                        finally { busy = false } }
                    }, enabled = !busy && selectedAssets.isNotEmpty() && itemTitle.trim().length >= 3) { Text("Create exclusive item") }
                    Divider()
                    Text("My exclusive gallery", fontWeight = FontWeight.Bold)
                    OutlinedButton({ refresh++ }) { Text("Refresh") }
                    gallery.forEach { item ->
                        Card { Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) { Text(item.title, fontWeight = FontWeight.SemiBold); Text("${item.review} · ${item.visibility} · ${qText(item.price_q)} Q", fontSize = 11.sp, color = CreatorMuted) }
                            if (item.unlocked) TextButton({ viewGallery = item.id }) { Text("View") }
                        } }
                    }
                }
                "Earnings" -> {
                    Text("Creator Earnings Wallet", fontSize = 20.sp, fontWeight = FontWeight.Bold)
                    Text("Available: ${qText(earnings?.available_q ?: mine.earnings.available_q)} Q", fontWeight = FontWeight.Bold, fontSize = 22.sp, color = CreatorGreen)
                    Text("Lifetime earned: ${qText(earnings?.lifetime_q ?: 0.0)} Q · Transferred: ${qText(earnings?.transferred_q ?: 0.0)} Q", color = CreatorMuted, fontSize = 12.sp)
                    Text("LEMMIQ creator fee: ${qText(config.fee_percent)}%", color = CreatorMuted, fontSize = 12.sp)
                    OutlinedTextField(transferAmount, { transferAmount = it }, Modifier.fillMaxWidth(), label = { Text("Move available Q to normal wallet") })
                    Button(onClick = {
                        val amount = qInput(transferAmount)
                        if (amount == null || amount <= 0) { onError("Enter a positive Q amount"); return@Button }
                        busy = true
                        scope.launch { try { client.transfer(amount); transferAmount = ""; refresh++; onSuccess("Q transferred to your LEMMIQ Wallet") }
                        catch (e: Exception) { onError(e.message ?: "Transfer failed") } finally { busy = false } }
                    }, enabled = !busy) { Text("Transfer available Q") }
                    Divider()
                    Text("Recent transactions", fontWeight = FontWeight.Bold)
                    earnings?.transactions.orEmpty().forEach { t ->
                        Card { Column(Modifier.padding(10.dp)) {
                            Text("${t.kind} · ${t.status}", fontWeight = FontWeight.SemiBold, fontSize = 12.sp)
                            Text("Gross ${qText(t.gross_q)} Q  •  Fee ${qText(t.fee_q)} Q  •  Net ${qText(t.net_q)} Q", color = CreatorMuted, fontSize = 11.sp)
                        } }
                    }
                }
            }
            Spacer(Modifier.height(25.dp))
        }
    }
    viewGallery?.let { id -> CreatorGalleryMediaDialog(client, id) { viewGallery = null } }
}

@Composable
private fun CreatorRequests(client: CreatorApiV2131, onError: (String) -> Unit, onSuccess: (String) -> Unit) {
    val scope = rememberCoroutineScope()
    var requests by remember { mutableStateOf<List<CreatorRequestNative>>(emptyList()) }
    var replyTo by remember { mutableStateOf<CreatorRequestNative?>(null) }
    var reply by remember { mutableStateOf("") }
    var reload by remember { mutableIntStateOf(0) }
    var running by remember { mutableStateOf(false) }
    LaunchedEffect(reload) {
        try { requests = client.requests() } catch (e: Exception) { onError(e.message ?: "Unable to load requests") }
    }
    fun action(id: Int, name: String, response: String = "") {
        running = true
        scope.launch { try { client.requestAction(id, name, response); reload++; onSuccess("Request $name recorded") }
        catch (e: Exception) { onError(e.message ?: "Action failed") }
        finally { running = false } }
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(15.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item { Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Creator service requests", Modifier.weight(1f), fontWeight = FontWeight.Bold, fontSize = 18.sp)
            TextButton({ reload++ }) { Text("Refresh") }
        } }
        if (requests.isEmpty()) item { CreatorEmpty("No requests yet", "Paid messages and session bookings appear here") }
        items(requests, key = { it.id }) { item ->
            Card { Column(Modifier.padding(13.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("${item.kind} · ${item.status}", Modifier.weight(1f), fontWeight = FontWeight.Bold)
                    CreatorTag(item.role)
                }
                if (item.message.isNotBlank()) Text(item.message, fontSize = 12.sp)
                if (item.reply.isNotBlank()) Text("Creator: ${item.reply}", fontSize = 12.sp)
                if (!item.scheduled_at.isNullOrBlank()) Text("Scheduled: ${item.scheduled_at}", fontSize = 11.sp, color = CreatorMuted)
                Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                    when {
                        item.role == "CREATOR" && item.status == "REQUESTED" -> {
                            OutlinedButton(onClick = { action(item.id, "ACCEPT") }, enabled = !running) { Text("Accept") }
                            OutlinedButton(onClick = { action(item.id, "CANCEL") }, enabled = !running) { Text("Cancel") }
                            if (item.kind == "CHAT") Button(onClick = { replyTo = item }, enabled = !running) { Text("Reply") }
                        }
                        item.role == "CREATOR" && item.kind == "CHAT" && item.status == "ACCEPTED" -> Button(onClick = { replyTo = item }, enabled = !running) { Text("Reply") }
                        item.role == "CREATOR" && item.kind != "CHAT" && item.status == "ACCEPTED" -> Button(onClick = { action(item.id, "DELIVERED") }, enabled = !running) { Text("Mark delivered") }
                        item.role == "FAN" && item.status == "DELIVERED" -> Button(onClick = { action(item.id, "CONFIRM") }, enabled = !running) { Text("Confirm delivery") }
                        item.role == "FAN" && item.status == "REQUESTED" -> OutlinedButton(onClick = { action(item.id, "CANCEL") }, enabled = !running) { Text("Cancel") }
                    }
                }
            } }
        }
    }
    replyTo?.let { req ->
        AlertDialog(onDismissRequest = { replyTo = null }, title = { Text("Reply to paid chat #${req.id}") },
            text = { OutlinedTextField(reply, { reply = it }, Modifier.fillMaxWidth(), label = { Text("Your reply") }, minLines = 3) },
            confirmButton = { Button(onClick = { action(req.id, "REPLY", reply); replyTo = null; reply = "" }, enabled = reply.trim().length >= 3) { Text("Deliver reply") } },
            dismissButton = { TextButton({ replyTo = null }) { Text("Cancel") } })
    }
}

/** Media is requested only after the API grants gallery access. No unauthenticated thumbnails. */
@Composable
private fun CreatorGalleryMediaDialog(client: CreatorApiV2131, itemId: Int, onClose: () -> Unit) {
    var assets by remember(itemId) { mutableStateOf<List<CreatorGalleryAssetNative>>(emptyList()) }
    var error by remember(itemId) { mutableStateOf<String?>(null) }
    LaunchedEffect(itemId) {
        try { assets = client.galleryAssets(itemId) }
        catch (e: Exception) { error = e.message ?: "Content unavailable" }
    }
    AlertDialog(onDismissRequest = onClose, title = { Text("Exclusive media · #$itemId") },
        text = { Column(Modifier.heightIn(max = 480.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            error?.let { Text(it, color = Color.Red) }
            if (assets.isEmpty() && error == null) CircularProgressIndicator()
            assets.forEach { item ->
                CreatorMediaPreview(client, "/v2131/exclusives/gallery/$itemId/assets/${item.id}/media", item.kind, "File #${item.id}")
            }
        } }, confirmButton = { TextButton(onClick = onClose) { Text("Close") } })
}

@Composable
private fun CreatorSingleMediaDialog(client: CreatorApiV2131, path: String, kind: String, title: String, onClose: () -> Unit) {
    AlertDialog(onDismissRequest = onClose, title = { Text(title) },
        text = { CreatorMediaPreview(client, path, kind, title) },
        confirmButton = { TextButton(onClick = onClose) { Text("Close") } })
}

@Composable
private fun CreatorMediaPreview(client: CreatorApiV2131, path: String, kind: String, title: String) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var bitmap by remember(path) { mutableStateOf<android.graphics.Bitmap?>(null) }
    var error by remember(path) { mutableStateOf<String?>(null) }
    var loading by remember(path) { mutableStateOf(true) }
    var videoLoading by remember(path) { mutableStateOf(false) }
    if (kind == "PHOTO") LaunchedEffect(path) {
        try {
            val data = client.media(path, 21L * 1024 * 1024)
            bitmap = withContext(Dispatchers.Default) {
                val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                BitmapFactory.decodeByteArray(data, 0, data.size, bounds)
                var scale = 1
                while (bounds.outWidth / scale > 1800 || bounds.outHeight / scale > 1800) scale *= 2
                BitmapFactory.decodeByteArray(data, 0, data.size,
                    BitmapFactory.Options().apply { inSampleSize = scale })
            } ?: throw IllegalStateException("Unable to decode image")
        } catch (e: Exception) { error = e.message ?: "Unable to load media" }
        finally { loading = false }
    }
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        if (kind == "PHOTO") {
            if (loading) CircularProgressIndicator()
            bitmap?.let { image -> Image(image.asImageBitmap(), title,
                modifier = Modifier.fillMaxWidth().heightIn(max = 390.dp), contentScale = ContentScale.Fit) }
        } else {
            OutlinedButton(onClick = { scope.launch {
                videoLoading = true
                try {
                    val (output, mime) = client.downloadVideo(path, ctx.cacheDir)
                    val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.files", output)
                    val intent = Intent(Intent.ACTION_VIEW).apply {
                        setDataAndType(uri, mime)
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }
                    ctx.startActivity(Intent.createChooser(intent, "View creator video"))
                } catch (e: Exception) { error = e.message ?: "Unable to play video" }
                finally { videoLoading = false }
            } }, enabled = !videoLoading) { Text(if (videoLoading) "Loading private video…" else "▶ Open approved video") }
            Text("Video is opened using an installed player. Do not share creator media without permission.", fontSize = 10.sp, color = CreatorMuted)
        }
        error?.let { Text(it, color = Color.Red, fontSize = 12.sp) }
    }
}

/** Native PPV message content: replaces the raw [[QCREATORS_PPV:n]] marker in direct chats. */
@Composable
fun V2131PpvOfferBubble(vm: LemmiqViewModel, offerId: Int, mine: Boolean) {
    val ctx = LocalContext.current
    val client = remember(vm.store) { CreatorApiV2131(ctx.applicationContext, vm.store) }
    val scope = rememberCoroutineScope()
    var offer by remember(offerId) { mutableStateOf<CreatorOfferNative?>(null) }
    var reload by remember(offerId) { mutableIntStateOf(0) }
    var confirm by remember { mutableStateOf(false) }
    var viewer by remember { mutableStateOf<Int?>(null) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(offerId, reload) {
        try { offer = client.offer(offerId) }
        catch (e: Exception) { error = e.message ?: "Offer unavailable" }
    }
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("🔒 Q Creators · Private PPV", fontWeight = FontWeight.Bold, fontSize = 12.sp,
            color = if (mine) Color.White else CreatorPurple)
        offer?.let { o ->
            Text(o.title, fontWeight = FontWeight.SemiBold, color = if (mine) Color.White else Color.Black)
            Text("${o.kind} · ${qText(o.price_q)} Q", fontSize = 11.sp, color = if (mine) Color.White else CreatorMuted)
            when {
                o.unlocked -> Button(onClick = { viewer = o.item_id }) { Text("View unlocked content") }
                mine -> Text("Waiting for recipient to unlock", fontSize = 11.sp, color = Color.White)
                else -> Button(onClick = { confirm = true }, enabled = !busy) { Text("Unlock for ${qText(o.price_q)} Q") }
            }
        } ?: Text("Loading locked offer…", fontSize = 11.sp)
        error?.let { Text(it, fontSize = 11.sp, color = if (mine) Color.White else Color.Red) }
    }
    if (confirm) CreatorConfirm("Unlock private content", "Pay ${qText(offer?.price_q ?: 0.0)} Q to unlock ${offer?.title.orEmpty()}?",
        confirmText = "Pay Q", onCancel = { confirm = false }, onConfirm = {
            confirm = false; busy = true
            scope.launch {
                try { client.unlockOffer(offerId); reload++ }
                catch (e: Exception) { error = e.message ?: "Unlock failed" }
                finally { busy = false }
            }
        })
    viewer?.let { CreatorGalleryMediaDialog(client, it) { viewer = null } }
}

/** The same approved Gallery asset can be offered privately at a creator-selected Q price. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun V2131SendPpvSheet(vm: LemmiqViewModel, chatId: Int, onClose: () -> Unit, onSent: () -> Unit) {
    val ctx = LocalContext.current
    val client = remember(vm.store) { CreatorApiV2131(ctx.applicationContext, vm.store) }
    val scope = rememberCoroutineScope()
    var gallery by remember { mutableStateOf<List<CreatorGalleryNative>>(emptyList()) }
    var selected by remember { mutableStateOf<CreatorGalleryNative?>(null) }
    var price by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var confirm by remember { mutableStateOf(false) }
    LaunchedEffect(chatId) {
        try { gallery = client.galleryMine().filter { it.review == "APPROVED" } }
        catch (e: Exception) { error = e.message ?: "You need an approved professional creator account" }
    }
    ModalBottomSheet(onDismissRequest = onClose) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 9.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Send PPV photo / video", fontSize = 22.sp, fontWeight = FontWeight.Bold)
            Text("Choose approved media from Creator Studio. Recipients must follow or subscribe to you. The price can differ from the public Exclusive Gallery price.", fontSize = 12.sp, color = CreatorMuted)
            Column(Modifier.heightIn(max = 260.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                gallery.forEach { item ->
                    Card(Modifier.fillMaxWidth().clickable { selected = item; price = qText(item.price_q) },
                        colors = CardDefaults.cardColors(containerColor = if (selected?.id == item.id) Color(0xFFF1EBFF) else Color.White)) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            RadioButton(selected?.id == item.id, onClick = { selected = item; price = qText(item.price_q) })
                            Column { Text(item.title, fontWeight = FontWeight.Bold); Text("${item.kind} · ${item.media_count} media · Gallery ${qText(item.price_q)} Q", fontSize = 11.sp, color = CreatorMuted) }
                        }
                    }
                }
                if (gallery.isEmpty()) CreatorEmpty("No approved exclusive items", "Upload media, create a gallery item and wait for Master Admin approval.")
            }
            OutlinedTextField(price, { price = it }, Modifier.fillMaxWidth(), label = { Text("Private unlock price (Q)") })
            error?.let { Text(it, color = Color.Red, fontSize = 12.sp) }
            Button(onClick = { confirm = true }, enabled = selected != null && qInput(price)?.let { it > 0 } == true && !busy,
                modifier = Modifier.fillMaxWidth()) { Text("Send locked PPV offer") }
            Spacer(Modifier.height(16.dp))
        }
    }
    if (confirm) CreatorConfirm("Send locked PPV media", "Send ${selected?.title.orEmpty()} for $price Q? Only the targeted chat recipient can unlock the private offer.",
        confirmText = "Send PPV", onCancel = { confirm = false }, onConfirm = {
            confirm = false
            val item = selected ?: return@CreatorConfirm
            val q = qInput(price) ?: return@CreatorConfirm
            busy = true
            scope.launch {
                try { client.chatOffer(chatId, item.id, q); onSent(); onClose() }
                catch (e: Exception) { error = e.message ?: "Unable to send private PPV offer" }
                finally { busy = false }
            }
        })
}
