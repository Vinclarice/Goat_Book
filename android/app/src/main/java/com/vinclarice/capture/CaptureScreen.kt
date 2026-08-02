package com.vinclarice.capture

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.isCtrlPressed
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

/**
 * The whole point of the app: open it, type, send, leave.
 *
 * The field takes focus on open so the keyboard is already up -- the plan
 * measures this app against opening a browser, and every tap saved is the
 * difference. All the decisions live in [CaptureViewModel]; this draws them.
 */
@Composable
fun CaptureScreen(
    model: CaptureViewModel,
    onOpenSettings: () -> Unit = {},
) {
    val state by model.state.collectAsState()
    val scope = rememberCoroutineScope()
    val focus = remember { FocusRequester() }

    // The half-typed thought, kept somewhere that survives the activity being
    // destroyed and rebuilt.
    //
    // The queue only protects a capture once it has been submitted, and the
    // view model lives in composition, so before this an unfinished thought
    // was lost to anything that recreates the activity: a rotation, a font
    // size change, and -- on the foldable this was written for -- opening the
    // phone. Losing text because the screen got bigger is exactly the kind of
    // failure somebody blames on themselves.
    var savedDraft by rememberSaveable { mutableStateOf("") }
    // Read once, before the write-back below can touch it. Reading it inside
    // the effect instead would race with the SideEffect that keeps it current
    // and restore an empty string over the real one.
    val restored = remember { savedDraft }

    LaunchedEffect(Unit) {
        if (restored.isNotEmpty()) model.onTextChange(restored)
        focus.requestFocus()
        // What is already queued from a previous session, so a restart does
        // not look like an empty queue.
        model.refresh()
        // Then keep it honest. This suspends for as long as the screen is
        // open; a count that only updates on open sat at "3 waiting to send"
        // over an empty queue on a real phone.
        model.watchDeliveries()
    }

    SideEffect { savedDraft = state.text }

    val canSend = !state.sending && state.text.isNotBlank()
    val send: () -> Unit = { if (canSend) { scope.launch { model.submit() } } }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // A plain text button rather than an app bar: an app bar would take
        // a band of height off the field on every screen for one action.
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // Visible rather than silent. A queue nobody can see is
            // indistinguishable from a capture that went missing.
            Text(
                if (state.pending > 0) "${state.pending} waiting to send" else "",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            TextButton(onClick = onOpenSettings) { Text("Settings") }
        }

        OutlinedTextField(
            value = state.text,
            onValueChange = model::onTextChange,
            placeholder = { Text("What's on your mind?") },
            enabled = !state.sending,
            // Whose choice this is belongs to whoever is typing. Sending
            // costs the soft keyboard's newline key outright, since a
            // multiline field's Enter is one thing or the other; a newline
            // costs a tap on every capture. Short captures make sending the
            // better default, which is not the same as it being right for
            // everybody, so Settings decides.
            //
            // Either way multi-line text displays and submits perfectly well
            // -- a shared link arrives as a title and a URL on two lines.
            // What the send setting gives up is typing a newline, not
            // having one.
            keyboardOptions = KeyboardOptions(
                capitalization = KeyboardCapitalization.Sentences,
                imeAction = if (state.enterSends) ImeAction.Send else ImeAction.Default,
            ),
            keyboardActions = KeyboardActions(onSend = { send() }),
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .focusRequester(focus)
                // Ctrl+Enter, for a hardware keyboard. The IME action above
                // covers the soft keyboard, but a physical Enter inserts a
                // newline regardless of it -- so this is the same convention
                // every mail and chat client already taught people, for the
                // case the soft keyboard cannot reach.
                .onPreviewKeyEvent { event ->
                    val sendPressed = event.type == KeyEventType.KeyDown &&
                        event.key == Key.Enter &&
                        event.isCtrlPressed
                    if (sendPressed) send()
                    sendPressed
                }
                .semantics { contentDescription = "Capture text" },
        )

        state.message?.let { message ->
            Text(
                message,
                style = MaterialTheme.typography.bodyMedium,
                color = if (state.isError) {
                    MaterialTheme.colorScheme.error
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
            )
        }

        Button(
            onClick = send,
            enabled = canSend,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (state.sending) "Sending…" else "Capture")
        }
    }
}
