import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import java.util.Properties

val lemmiqLocalProperties = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}
val lemmiqReleaseProperties = Properties().apply {
    val file = rootProject.file("keystore.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}

fun releaseValue(propertyName:String, envName:String):String? =
    lemmiqReleaseProperties.getProperty(propertyName)?.trim()?.takeIf { it.isNotEmpty() }
        ?: System.getenv(envName)?.trim()?.takeIf { it.isNotEmpty() }

val releaseStorePath = releaseValue("storeFile", "LEMMIQ_UPLOAD_STORE_FILE")
val releaseStorePassword = releaseValue("storePassword", "LEMMIQ_UPLOAD_STORE_PASSWORD")
val releaseKeyAlias = releaseValue("keyAlias", "LEMMIQ_UPLOAD_KEY_ALIAS")
val releaseKeyPassword = releaseValue("keyPassword", "LEMMIQ_UPLOAD_KEY_PASSWORD")
val releaseSigningConfigured =
    releaseStorePath != null &&
    releaseStorePassword != null &&
    releaseKeyAlias != null &&
    releaseKeyPassword != null &&
    rootProject.file(releaseStorePath).exists()

val lemmiqFirebaseConfigured = file("google-services.json").exists()
val lemmiqApiBaseUrl = (
    System.getenv("LEMMIQ_API_BASE_URL")
        ?: lemmiqLocalProperties.getProperty("lemmiq.apiBaseUrl", "https://lemmiq-api.onrender.com")
    ).trim().trimEnd('/')

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

// google-services.json is deliberately not committed.
// Add android/app/google-services.json locally, or let the release workflow restore it from a GitHub secret.
if (lemmiqFirebaseConfigured) {
    apply(plugin = "com.google.gms.google-services")
}

android {
    namespace="com.lemmiq.app"
    compileSdk=37

    defaultConfig {
        applicationId="com.lemmiq.app"
        minSdk=26
        targetSdk=37
        versionCode=55
        versionName="2.10.5"
        buildConfigField("String", "API_BASE_URL", "\"${lemmiqApiBaseUrl}\"")
        buildConfigField("boolean", "FCM_CONFIGURED", lemmiqFirebaseConfigured.toString())
    }

    signingConfigs {
        create("release") {
            if (releaseSigningConfigured) {
                storeFile = rootProject.file(releaseStorePath!!)
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        getByName("debug") {
            versionNameSuffix = "-debug"
        }
        getByName("release") {
            isMinifyEnabled = false
            isShrinkResources = false
            if (releaseSigningConfigured) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    buildFeatures { compose=true; buildConfig=true }
    compileOptions {
        sourceCompatibility=JavaVersion.VERSION_17
        targetCompatibility=JavaVersion.VERSION_17
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

dependencies {
    val composeBom=platform("androidx.compose:compose-bom:2026.08.00")
    implementation(composeBom)
    implementation("androidx.core:core-ktx:1.18.0")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.fragment:fragment-ktx:1.9.1")
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
    implementation("io.livekit:livekit-android:2.+")
    implementation("io.coil-kt:coil-compose:2.7.0")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
