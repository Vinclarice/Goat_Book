package com.vinclarice.capture

import android.content.Intent
import android.os.Build
import android.os.Bundle
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.fragment.app.FragmentActivity
import com.vinclarice.capture.ui.theme.ClariceTheme

/**
 * The whole app is one activity. Bittern scoped this client to capture and
 * nothing else; android-full-client-plan.md's slices have been cracking that
 * boundary open one surface at a time -- Today (read-only), then Agenda
 * (read and act: complete, reschedule, quick-add). Three destinations is
 * still not enough to justify a real navigation graph -- [RootTabBar] is a
 * hand-rolled tab switcher rather than Jetpack Navigation Compose or a
 * Material `NavigationBar` (which would need an icon library this app has
 * never depended on), trivially replaceable with either once there are
 * enough tabs to need one.
 *
 * FragmentActivity rather than ComponentActivity (its own superclass) since
 * design/android-unlock-plan.md's BiometricPrompt requires one -- everything
 * that worked before, setContent included, is still ComponentActivity API
 * and stays available.
 */
class MainActivity : FragmentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Built here rather than injected: one activity, two collaborators,
        // and a dependency-injection framework would be more machinery than
        // the whole app currently contains.
        val api = OkHttpClariceApi(baseUrl = BuildConfig.CLARICE_BASE_URL)
        val dailyApi = OkHttpDailyApi(baseUrl = BuildConfig.CLARICE_BASE_URL)
        val agendaApi = OkHttpAgendaApi(baseUrl = BuildConfig.CLARICE_BASE_URL)
        val store = KeystoreTokenStore(applicationContext)
        val connector = Connector(api = api, store = store)
        val queue = CaptureQueue(EncryptedQueueStorage(applicationContext))
        val scheduler = CaptureWorker.prepare(applicationContext)
        val preferences = AndroidCapturePreferences(applicationContext)
        val unlockGate = BiometricUnlockGate(this)

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
            ClariceTheme {
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
                            dailyApi = dailyApi,
                            agendaApi = agendaApi,
                            store = store,
                            queue = queue,
                            scheduler = scheduler,
                            preferences = preferences,
                            unlockGate = unlockGate,
                            draft = draft,
                        )
                    }
                }
            }
        }
    }
}

/** The places someone can be once connected. Settings sits outside this
 *  set on purpose -- see the class doc on why it stays a per-tab link
 *  rather than an entry here. */
private enum class RootTab(val label: String) {
    Capture("Capture"),
    Today("Today"),
    Agenda("Agenda"),
}

@Composable
private fun Root(
    connector: Connector,
    api: ClariceApi,
    dailyApi: DailyApi,
    agendaApi: AgendaApi,
    store: TokenStore,
    queue: CaptureQueue,
    scheduler: DeliveryScheduler,
    preferences: CapturePreferences,
    unlockGate: UnlockGate,
    draft: String? = null,
) {
    // Checked once per process, not remembered across recompositions past
    // that: cold-start only, the same way a half-typed draft survives a
    // rotation but not a force-stop. Re-locking mid-session on some elapsed
    // timer is a different, heavier feature -- design/android-unlock-plan.md.
    var unlocked by remember { mutableStateOf(!preferences.requireUnlock()) }

    // Ahead of every other branch, including the share-intent bypass below:
    // a lock that only covered the capture box and left a shared draft or
    // the Connect screen's own state reachable without it would be
    // guarding the wrong thing.
    if (!unlocked) {
        LockScreen(gate = unlockGate, onUnlocked = { unlocked = true })
        return
    }

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
    // Same reasoning as captureModel: held above the tab switch so opening
    // Settings and coming back doesn't drop today's already-loaded state.
    val dailyModel = remember { DailyViewModel(dailyApi, store) }
    // Same again, and doubly so here: the Agenda's own filter selections
    // (area, tag, scope, search) live in this model too, and losing them
    // on every trip to Settings would be worse than losing loaded data.
    val agendaModel = remember { AgendaViewModel(agendaApi, store) }

    var connected by remember { mutableStateOf(connectModel.isConnected) }
    var showSettings by remember { mutableStateOf(false) }
    var selectedTab by remember { mutableStateOf(RootTab.Capture) }

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
            onDisconnected = {
                // Settings' own disconnect() already cleared the stored
                // token through this same Connector; this clears the
                // *other* view model's leftover state, so returning to
                // Connect doesn't show "Connected as ..." for whoever was
                // just disconnected.
                connectModel.disconnect()
                connected = false
                showSettings = false
            },
        )
        return
    }

    // Connect exists only to get here once; from here it's a choice between
    // the two tabs, weighted so whichever screen is active fills the space
    // above the bar rather than the bar floating mid-screen.
    Column(modifier = Modifier.fillMaxSize()) {
        Box(modifier = Modifier.weight(1f)) {
            when (selectedTab) {
                RootTab.Capture -> CaptureScreen(
                    model = captureModel,
                    onOpenSettings = { showSettings = true },
                )
                RootTab.Today -> DailyScreen(
                    model = dailyModel,
                    onOpenSettings = { showSettings = true },
                )
                RootTab.Agenda -> AgendaScreen(
                    model = agendaModel,
                    onOpenSettings = { showSettings = true },
                )
            }
        }
        RootTabBar(selected = selectedTab, onSelect = { selectedTab = it })
    }
}

@Composable
private fun RootTabBar(selected: RootTab, onSelect: (RootTab) -> Unit) {
    HorizontalDivider()
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceEvenly,
    ) {
        RootTab.entries.forEach { tab ->
            TextButton(onClick = { onSelect(tab) }) {
                Text(
                    tab.label,
                    color = if (tab == selected) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                    fontWeight = if (tab == selected) FontWeight.SemiBold else FontWeight.Normal,
                )
            }
        }
    }
}
