package com.vinclarice.capture

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

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
        val connector = Connector(
            api = OkHttpClariceApi(baseUrl = BuildConfig.CLARICE_BASE_URL),
            store = KeystoreTokenStore(applicationContext),
        )

        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    Root(connector)
                }
            }
        }
    }
}

@Composable
private fun Root(connector: Connector) {
    val model = remember { ConnectViewModel(connector) }
    var connected by remember { mutableStateOf(model.isConnected) }

    if (!connected) {
        ConnectScreen(model = model, onConnected = { connected = true })
        return
    }

    // Capture lands here next; until it does, say so rather than showing an
    // empty screen that looks like a failure.
    Column(modifier = Modifier.padding(24.dp)) {
        Text("Connected", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Capture and Settings land next -- see design/bittern-plan.md, M2.",
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
