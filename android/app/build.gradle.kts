import java.util.Properties

val lemmiqLocalProperties = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) {
        file.inputStream().use { load(it) }
    }
}
val lemmiqFirebaseConfigured = file("google-services.json").exists()

val lemmiqApiBaseUrl = lemmiqLocalProperties
    .getProperty("lemmiq.apiBaseUrl", "https://YOUR-RENDER-SERVICE.onrender.com")
    .trim()
    .trimEnd('/')

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}
// Add your Firebase google-services.json to android/app/ to enable push registration.
// Without that file, normal messaging still compiles and works without FCM.
if (file("google-services.json").exists()) {
    apply(plugin = "com.google.gms.google-services")
}

android {
    namespace="com.lemmiq.app"
    compileSdk=37
    defaultConfig {
        applicationId="com.lemmiq.app"
        minSdk=26
        targetSdk=37
        versionCode=23
        versionName="2.2.0"
        buildConfigField("String", "API_BASE_URL", "\"${lemmiqApiBaseUrl}\"")
        buildConfigField("boolean", "FCM_CONFIGURED", lemmiqFirebaseConfigured.toString())
    }
    buildFeatures { compose=true; buildConfig=true }
    compileOptions {
        sourceCompatibility=JavaVersion.VERSION_17
        targetCompatibility=JavaVersion.VERSION_17
    }
}
dependencies {
    val composeBom=platform("androidx.compose:compose-bom:2026.08.00")
    implementation(composeBom)
    implementation("androidx.core:core-ktx:1.18.0")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.10.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.10.0")
    implementation("androidx.navigation:navigation-compose:2.10.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("com.squareup.okhttp3:okhttp:5.1.0")
    implementation("com.google.code.gson:gson:2.13.1")
    implementation(platform("com.google.firebase:firebase-bom:34.18.0"))
    implementation("com.google.firebase:firebase-messaging")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
