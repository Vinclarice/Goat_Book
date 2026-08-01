package com.vinclarice.capture

import android.os.Bundle
import androidx.activity.ComponentActivity
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
    var connected by remember { mutableStateOf(connectModel.isConnected) }

    if (!connected) {
        ConnectScreen(model = connectModel, onConnected = { connected = true })
        return
    }

    // Capture is the destination; Connect exists only to get here once.
    val captureModel = remember { CaptureViewModel(api, store) }
    CaptureScreen(model = captureModel)
}
