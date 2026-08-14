import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

// Absent by default, deliberately: local.properties is per-machine and
// gitignored already (it holds sdk.dir), and the release signing key is not
// something this build should ever generate or hold itself -- see
// design/android-release-signing-plan.md for why, and the exact keytool
// command that creates it. A debug build never reads this; assembleRelease
// with nothing configured here still builds, just unsigned, exactly as it
// always has.
val releaseSigningProperties = Properties().also { properties ->
    val file = rootProject.file("local.properties")
    if (file.exists()) file.inputStream().use(properties::load)
}

fun releaseSigningProperty(key: String): String? =
    releaseSigningProperties.getProperty(key)?.takeIf { it.isNotBlank() }

android {
    namespace = "com.vinclarice.capture"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.vinclarice.capture"
        minSdk = 26
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // Configuration, not source. The plan is explicit that no endpoint
        // is hard-coded into this app; overriding it is
        // -PclariceBaseUrl=https://staging.example/ at build time, which is
        // also how anyone pointing a debug build at their own machine does
        // it without editing a file they might commit.
        buildConfigField(
            "String",
            "CLARICE_BASE_URL",
            "\"${project.findProperty("clariceBaseUrl") ?: "https://vinclarice.com/"}\"",
        )

        // Where captures go, when it is somewhere other than Clarice. Empty by
        // default and empty means unsplit -- see [Backends] -- so a build
        // without -PsecondMindBaseUrl behaves exactly as every build before
        // this field existed. There is deliberately no default host: guessing
        // one would point somebody's thoughts at a server they never chose.
        buildConfigField(
            "String",
            "SECOND_MIND_BASE_URL",
            "\"${project.findProperty("secondMindBaseUrl") ?: ""}\"",
        )
    }

    signingConfigs {
        // Only created when local.properties actually has all four keys.
        // RELEASE_STORE_FILE is an absolute path -- the keystore is free to
        // live anywhere on this machine, including entirely outside the
        // repo, and does not have to sit under android/ just because that's
        // where *.jks is gitignored.
        val storeFile = releaseSigningProperty("RELEASE_STORE_FILE")
        val storePassword = releaseSigningProperty("RELEASE_STORE_PASSWORD")
        val keyAlias = releaseSigningProperty("RELEASE_KEY_ALIAS")
        val keyPassword = releaseSigningProperty("RELEASE_KEY_PASSWORD")
        if (storeFile != null && storePassword != null && keyAlias != null && keyPassword != null) {
            create("release") {
                this.storeFile = file(storeFile)
                this.storePassword = storePassword
                this.keyAlias = keyAlias
                this.keyPassword = keyPassword
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // Unsigned when local.properties has nothing configured, the
            // same as before this existed -- assembleRelease still
            // succeeds, it just isn't installable anywhere but a machine
            // willing to trust an unsigned APK.
            signingConfigs.findByName("release")?.let { signingConfig = it }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlin {
        compilerOptions {
            jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.okhttp)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.androidx.work)
    implementation(libs.androidx.biometric)

    testImplementation(libs.junit)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.json)

    androidTestImplementation(libs.androidx.test.junit)
    androidTestImplementation(libs.androidx.test.runner)
}
