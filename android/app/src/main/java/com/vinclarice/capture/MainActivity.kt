package com.vinclarice.capture

import android.content.Intent
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
        val queue = CaptureQueue(EncryptedQueueStorage(applicationContext))
        val scheduler = CaptureWorker.prepare(applicationContext)
        val preferences = AndroidCapturePreferences(applicationContext)

        // getCharSequenceExtra rather than getStringExtra: apps sharing
        // formatted text send a Spanned, and getStringExtra returns null for
        // it -- a share that silently arrives empty is worse than one that
        // arrives plain.
        val draft = SharedText.from(
            action = intent?.action,
            type = intent?.type,
            text = intent?.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString(),
            subject = intent?.getCharSequenceExtra(Intent.EXTRA_SUBJECT)?.toString(),
        )

        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    // The Surface fills the screen so its background paints
                    // behind the system bars; the content is inset so it
                    // does not sit *under* them. Applications targeting
                    // SDK 35 and above draw edge to edge whether they ask to
                    // or not, and without this the Capture button sat under
                    // the gesture bar -- reachable, but half-hidden and
                    // easy to mistake for a mis-tap.
                    Box(modifier = Modifier.windowInsetsPadding(WindowInsets.safeDrawing)) {
                        Root(
                            connector = connector,
                            api = api,
                            store = store,
                            queue = queue,
                            scheduler = scheduler,
                            preferences = preferences,
                            draft = draft,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun Root(
    connector: Connector,
    api: ClariceApi,
    store: TokenStore,
    queue: CaptureQueue,
    scheduler: DeliveryScheduler,
    preferences: CapturePreferences,
    draft: String? = null,
) {
    val connectModel = remember {
        // A login-minted token is labelled by the device it came from, so
        // the Access tokens page on the web can tell two phones apart --
        // "Android" alone would leave every login indistinguishable there.
        ConnectViewModel(connector, deviceLabel = "Android (${Build.MODEL})")
    }
    // Held here rather than inside the Capture branch, so that a trip to
    // Settings and back does not drop it out of composition along with
    // whatever half-finished thought was in the field. The queue now covers
    // everything already submitted; this covers what is still being typed.
    val captureModel = remember { CaptureViewModel(api, store, queue, scheduler, preferences) }

    var connected by remember { mutableStateOf(connectModel.isConnected) }
    var showSettings by remember { mutableStateOf(false) }

    // Seeded, never sent. Another app's content is put in front of a person
    // to edit or abandon; posting it on their behalf would make every share
    // menu a way to write to somebody's Inbox without them reading it.
    LaunchedEffect(draft) { draft?.let(captureModel::onTextChange) }

    // A share outranks the connection gate. Sending somebody to Connect
    // would discard what they just shared, and the queue can hold a capture
    // with no token perfectly well -- it says so, and delivers it once a
    // token exists.
    if (!connected && draft == null) {
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
        val settingsModel = remember { SettingsViewModel(connector, queue, scheduler, preferences) }
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
