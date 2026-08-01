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
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/**
 * The whole app is one activity. Bittern scopes this client to capture and
 * nothing else -- no triage, no idea management, no task editing -- so there
 * is no navigation graph to justify yet, and adding one now would be
 * scaffolding for screens the plan says not to build.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    Placeholder()
                }
            }
        }
    }
}

@Composable
private fun Placeholder() {
    Column(modifier = Modifier.padding(24.dp)) {
        Text("Clarice Capture", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Connect, Capture and Settings land next -- see " +
                "design/bittern-plan.md, M2.",
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
