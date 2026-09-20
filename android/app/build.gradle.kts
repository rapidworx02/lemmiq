import java.util.Properties

val lemmiqLocalProperties = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) {
        file.inputStream().use { load(it) }
    }
}
val lemmiqApiBaseUrl = lemmiqLocalProperties
    .getProperty("lemmiq.apiBaseUrl", "https://YOUR-RENDER-SERVICE.onrender.com")
    .trim()
    .trimEnd('/')

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}
android {
    namespace="com.lemmiq.app"
    compileSdk=37
    defaultConfig {
        applicationId="com.lemmiq.app"
        minSdk=26
        targetSdk=37
        versionCode=6
        versionName="1.6.2"
        buildConfigField("String", "API_BASE_URL", "\"${lemmiqApiBaseUrl}\"")
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
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
