package com.vinclarice.capture.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * Ported by hand from the web application's own tokens
 * (frontend/src/app/tailwind.css's `@theme` block), which is the
 * authoritative definition of what Clarice looks like. Keep these two in
 * sync if that file's values change -- there is no shared build step
 * between a Gradle project and a Vite one to enforce it automatically.
 *
 * Compose blends alpha the same way CSS does, so translucent web values
 * (surface, outline) are carried over as translucent Color values rather
 * than pre-flattened against a specific background.
 */

// Dark -- the app's primary identity; the launcher icon is drawn against it.
val ClariceDarkBackground = Color(0xFF08111F)
val ClariceDarkSurface = Color(0xD1121F31) // rgba(18, 31, 49, 0.82)
val ClariceDarkSurfaceStrong = Color(0xFF132237)
val ClariceDarkText = Color(0xFFF5F7FB)
val ClariceDarkMutedForeground = Color(0xFFA6B2C3)
val ClariceDarkAccent = Color(0xFF7BE0B8)
val ClariceDarkAccentForeground = Color(0xFF08111F)
val ClariceDarkOutline = Color(0x1AFFFFFF) // rgba(255, 255, 255, 0.1)
val ClariceDarkError = Color(0xFFFFB8B8)
val ClariceDarkOnError = Color(0xFF08111F)

// Light
val ClariceLightBackground = Color(0xFFF1F6F4)
val ClariceLightSurface = Color(0xFFFFFFFF)
val ClariceLightText = Color(0xFF101C26)
val ClariceLightMutedForeground = Color(0xFF55697A)
val ClariceLightAccent = Color(0xFF1C8F66)
val ClariceLightAccentForeground = Color(0xFFFFFFFF)
val ClariceLightOutline = Color(0x1A0F1720) // rgba(15, 23, 32, 0.1)
val ClariceLightError = Color(0xFFB23434)
val ClariceLightOnError = Color(0xFFFFFFFF)
