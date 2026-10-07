# 04 — Android media + 6-tab navigation merge

## A. Add media viewer Activity

Upload:

```text
android/app/src/main/java/com/lemmiq/app/LemmiqMediaViewerActivity.kt
```

Add inside `<application>` in `android/app/src/main/AndroidManifest.xml`:

```xml
<activity
    android:name=".LemmiqMediaViewerActivity"
    android:exported="false"
    android:theme="@style/Theme.Lemmiq" />
```

Use the same app theme name as your current activities if it is not `Theme.Lemmiq`.

## B. Open a chat photo full screen

In the chat-image composable/onClick in `LemmiqApp.kt` (or the file that renders media messages), add:

```kotlin
val context = LocalContext.current
```

Then on image tap:

```kotlin
val intent = Intent(context, LemmiqMediaViewerActivity::class.java).apply {
    putExtra(LemmiqMediaViewerActivity.EXTRA_URI, imageUri)
}
context.startActivity(intent)
```

`imageUri` should be your existing safe HTTPS URL or FileProvider `content://` URI. Do not pass a raw `/data/data/...` private file path.

## C. Reduce the coloured border/padding around image bubbles

Find the container that wraps the photo message. Change large padding to approximately:

```kotlin
Modifier.padding(horizontal = 3.dp, vertical = 3.dp)
```

Keep the image rounded:

```kotlin
.clip(RoundedCornerShape(14.dp))
```

Keep timestamp/check marks and `Ask Q Vision` below/over the image, but do not use a large empty purple block around the image.

## D. Bottom navigation is now SIX items

Order is fixed:

```text
Chats · Updates · Q Economy · Q Predict · Calls · More
```

In the existing nav list in `LemmiqApp.kt`, add a sixth item:

```kotlin
BottomItem(
    label = "More",
    icon = Icons.Default.MoreHoriz,
    route = "more"
)
```

If your project uses a different nav item data class/icon set, keep that existing structure and only add the new item.

## E. More screen/sheet content

More must expose:

```text
Profile
Trust / Fact Check
Business Agent
Activity
Money
Settings
Privacy & Security
Get LEMMIQ for Android / app info where appropriate
```

Remove `Profile, Trust, Business & Settings` from the Q assistant sheet so Q remains focused on Q actions.

## F. Floating Q button

Use a less opaque surface. For Compose, target roughly:

```kotlin
containerColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.68f)
```

Keep the Q glyph fully opaque. Position the FAB above the six-tab nav and `navigationBarsPadding()` so content behind remains visible.
