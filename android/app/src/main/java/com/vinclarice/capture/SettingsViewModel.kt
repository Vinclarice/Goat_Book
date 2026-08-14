package com.vinclarice.capture

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext

/**
 * The workspace connection, on a split install.
 *
 * Its own type rather than more fields on [SettingsUiState] because it is
 * genuinely absent when capture and the workspace face the same server -- and
 * `null` says that in a way a set of defaulted booleans cannot. Rendering one
 * account twice under two headings would invite someone to disconnect what
 * they took for a spare.
 */
data class WorkspaceConnection(
    val loading: Boolean = true,
    val identity: Identity? = null,
    val message: String? = null,
    val isError: Boolean = false,
    val connected: Boolean = true,
)

data class SettingsUiState(
    val loading: Boolean = true,
    val identity: Identity? = null,
    val message: String? = null,
    val isError: Boolean = false,
    // Whether a token is held, which is not the same as whether it works.
    // A revoked token leaves this true until someone disconnects.
    val connected: Boolean = true,
    /**
     * Clarice, when captures are going somewhere else. Null on an unsplit
     * install, where the fields above describe the only connection there is.
     */
    val workspace: WorkspaceConnection? = null,
    /** Captures the app will keep trying to send on its own. */
    val waiting: Int = 0,
    /** Captures that have stopped trying and need a person. */
    val needsAttention: List<PendingCapture> = emptyList(),
    /** Whether the keyboard's Enter key sends a capture or breaks a line. */
    val enterSends: Boolean = true,
    /** Whether opening the app costs a device unlock first. */
    val requireUnlock: Boolean = false,
)

/**
 * The account behind the stored token, the queue behind the app, and the way
 * to stop using either.
 *
 * The screen's real job is answering "is this thing still working?", so it
 * asks the server every time it opens rather than showing something it
 * remembered. Two of the three answers -- revoked, and unreachable -- have to
 * stay distinct all the way to the text on screen, because one calls for a
 * new token and the other calls for patience.
 *
 * The queue is read regardless of any of that. Being offline is exactly when
 * somebody wants to know what is still unsent, so hiding it behind a
 * successful identity lookup would withhold it at the only moment it
 * matters.
 */
class SettingsViewModel(
    private val connector: Connector,
    private val queue: CaptureQueue,
    private val scheduler: DeliveryScheduler = DeliveryScheduler.None,
    private val preferences: CapturePreferences,
    /**
     * Clarice, when captures go elsewhere. Null on an unsplit install, which
     * is what keeps this one screen honest about how many connections exist
     * rather than always drawing two.
     */
    private val workspaceConnector: Connector? = null,
    /** Which server captures go to, named in the stalled-capture text. */
    val serverName: String = "Clarice",
    private val io: CoroutineDispatcher = Dispatchers.IO,
) {

    // Seeded with a loading workspace when there is one, rather than left null
    // until loadWorkspace() answers. Null means "there is no second
    // connection", so leaving it null while one is being asked about makes the
    // whole section *absent* -- not spinning, absent -- until the capture
    // server replies, which on an unreachable one is a ten-second timeout
    // followed by a section appearing from nowhere.
    private val _state = MutableStateFlow(
        SettingsUiState(
            workspace = if (workspaceConnector != null) WorkspaceConnection() else null,
        )
    )
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    suspend fun load() {
        readQueue()
        // Before the network call, and outside it. These are device
        // preferences, not account facts; withholding either because a
        // request failed would be absurd.
        _state.value = _state.value.copy(
            enterSends = preferences.enterSends(),
            requireUnlock = preferences.requireUnlock(),
        )

        when (val outcome = connector.whoAmI()) {
            is Connected -> _state.value = _state.value.copy(
                loading = false,
                identity = outcome.identity,
                message = null,
            )
            // The token is kept. Settings is where someone comes to find out
            // their token stopped working; ejecting them to Connect before
            // they have read why is not an answer.
            is Refused -> report(outcome.message, isError = true)
            // Not an error in the sense that anything needs fixing, so it is
            // said plainly rather than in red.
            is Failed -> report(outcome.message, isError = false)
            Blank -> _state.value = _state.value.copy(loading = false, connected = false)
        }

        loadWorkspace()
    }

    /**
     * The same three answers for the other server, kept apart from the first.
     *
     * Asked after capture rather than alongside it: two servers fail
     * independently, and the screen has to be able to say Clarice is refusing
     * a token while Second Mind is fine. Collapsing them into one status would
     * send somebody to reconnect the half that was working.
     */
    private suspend fun loadWorkspace() {
        val workspace = workspaceConnector ?: return

        val next = when (val outcome = workspace.whoAmI()) {
            is Connected -> WorkspaceConnection(loading = false, identity = outcome.identity)
            is Refused -> WorkspaceConnection(loading = false, message = outcome.message, isError = true)
            is Failed -> WorkspaceConnection(loading = false, message = outcome.message, isError = false)
            Blank -> WorkspaceConnection(loading = false, connected = false)
        }
        _state.value = _state.value.copy(workspace = next)
    }

    /**
     * One more go at a capture that stopped trying.
     *
     * The queue keeps the original key through this, which is the entire
     * reason a stalled item is kept rather than dropped: a fresh key would
     * turn one thought into a second note the moment it finally landed.
     */
    suspend fun retry(key: String) {
        withContext(io) { queue.retry(key) }
        scheduler.schedule()
        readQueue()
    }

    /**
     * Whether Enter sends or breaks a line.
     *
     * Written through immediately rather than on leaving the screen: a
     * preference that only takes effect if you exit the right way is a
     * preference people stop trusting.
     */
    fun setEnterSends(sends: Boolean) {
        preferences.setEnterSends(sends)
        _state.value = _state.value.copy(enterSends = sends)
    }

    /** Same immediacy as [setEnterSends], and for the same reason: a
     *  security setting that only takes effect if you leave the screen the
     *  right way is one people learn not to trust. */
    fun setRequireUnlock(require: Boolean) {
        preferences.setRequireUnlock(require)
        _state.value = _state.value.copy(requireUnlock = require)
    }

    fun disconnect() {
        connector.disconnect()
        // The queue is deliberately untouched. It has its own Keystore alias
        // precisely so that disconnecting cannot destroy unsent thoughts.
        //
        // So is the workspace. Two servers, two credentials: replacing the
        // token for one of them must not cost the other, and on a split
        // install this is the *capture* connection -- the act the app exists
        // for -- so the reverse would be worse still.
        _state.value = _state.value.copy(
            loading = false,
            connected = false,
            identity = null,
            message = null,
        )
    }

    /**
     * Forget Clarice's token and keep capturing.
     *
     * A no-op when there is no second connection. The screen never offers the
     * button in that case, but the model should not be relying on the screen
     * to enforce it.
     */
    fun disconnectWorkspace() {
        val workspace = workspaceConnector ?: return

        workspace.disconnect()
        _state.value = _state.value.copy(
            workspace = WorkspaceConnection(loading = false, connected = false),
        )
    }

    private suspend fun readQueue() = withContext(io) {
        val all = queue.all()
        _state.value = _state.value.copy(
            waiting = all.count { it.state == QueueState.WAITING },
            needsAttention = all.filter { it.state != QueueState.WAITING },
        )
    }

    private fun report(message: String, isError: Boolean) {
        _state.value = _state.value.copy(
            loading = false,
            identity = null,
            message = message,
            isError = isError,
        )
    }
}
