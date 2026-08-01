// Plugins are declared here and applied in :app, so every module resolves
// the same versions from gradle/libs.versions.toml.
// No kotlin-android plugin: AGP 9 has built-in Kotlin support and rejects
// it outright ("no longer required for Kotlin support since AGP 9.0").
// Every guide written before AGP 9 still declares it.
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.compose) apply false
}
