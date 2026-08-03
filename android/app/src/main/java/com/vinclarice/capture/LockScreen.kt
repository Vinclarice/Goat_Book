package com.vinclarice.capture

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/**
 * Stands in front of everything else -- Connect, Capture and Settings
 * alike -- when design/android-unlock-plan.md's setting is on. A gate that
 * only covered the capture box and left a shared-text draft or the Connect
 * screen's own state reachable without it would be guarding the wrong
 * thing.
 */
@Composable
fun LockScreen(gate: UnlockGate, onUnlocked: () -> Unit) {
    var message by remember { mutableStateOf<String?>(null) }

    val requestUnlock: () -> Unit = {
        message = null
        gate.requestUnlock { result ->
            when (result) {
                Unlocked -> onUnlocked()
                // Backing out of the prompt is not an error, so it is not
                // shown as one -- the button underneath is enough of an
                // invitation to try again.
                UnlockCancelled -> Unit
                is UnlockFailed -> message = result.message
            }
        }
    }

    // Asked immediately on open, the same instinct as the capture field
    // taking focus on open: someone who turned this setting on wants the
    // prompt, not an extra tap to reach it.
    LaunchedEffect(Unit) { requestUnlock() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
    ) {
        Text("Clarice Capture is locked", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Unlock your phone to continue.",
            style = MaterialTheme.typography.bodyMedium,
        )
        message?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
        Button(onClick = requestUnlock, modifier = Modifier.fillMaxWidth()) {
            Text("Unlock")
        }
    }
}
