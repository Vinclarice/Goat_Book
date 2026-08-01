package com.vinclarice.capture

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier

/**
 * The whole app is one activity. Bittern scopes this client to capture and
 * nothing else -- no triage, no idea management, no task editing -- so
 * there is no navigation graph to justify yet, and adding one now would be
 * scaffolding for screens the plan says not to build.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Built here rather than injected: one activity, two collaborators,
        // and a dependency-injection framework would be more machinery than
        // the whole app currently contains.
        val api = OkHttpClariceApi(baseUrl = BuildConfig.CLARICE_BASE_URL)
        val store = KeystoreTokenStore(applicationContext)
        val connector = Connector(api = api, store = store)

        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    Root(connector = connector, api = api, store = store)
                }
            }
        }
    }
}

@Composable
private fun Root(connector: Connector, api: ClariceApi, store: TokenStore) {
    val connectModel = remember { ConnectViewModel(connector) }
    // Held here rather than inside the Capture branch, so that a trip to
    // Settings and back does not drop it out of composition -- along with
    // whatever half-finished thought was in the field. Until M3 exists that
    // field is the only place an undelivered capture lives.
    val captureModel = remember { CaptureViewModel(api, store) }

    var connected by remember { mutableStateOf(connectModel.isConnected) }
    var showSettings by remember { mutableStateOf(false) }

    if (!connected) {
        ConnectScreen(
            model = connectModel,
            onConnected = { connected = true; showSettings = false },
        )
        return
    }

    if (showSettings) {
        // Not remembered across visits, deliberately: a fresh model per open
        // is what makes it ask the server again instead of showing the
        // account it saw last time.
        val settingsModel = remember { SettingsViewModel(connector) }
        BackHandler { showSettings = false }
        SettingsScreen(
            model = settingsModel,
            onBack = { showSettings = false },
            onDisconnected = { connected = false; showSettings = false },
        )
        return
    }

    // Capture is the destination; Connect exists only to get here once.
    CaptureScreen(model = captureModel, onOpenSettings = { showSettings = true })
}
