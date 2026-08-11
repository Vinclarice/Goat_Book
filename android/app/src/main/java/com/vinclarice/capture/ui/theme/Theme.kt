package com.vinclarice.capture.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val ClariceDarkColors = darkColorScheme(
    primary = ClariceDarkAccent,
    onPrimary = ClariceDarkAccentForeground,
    background = ClariceDarkBackground,
    onBackground = ClariceDarkText,
    surface = ClariceDarkSurface,
    onSurface = ClariceDarkText,
    surfaceVariant = ClariceDarkSurfaceStrong,
    onSurfaceVariant = ClariceDarkMutedForeground,
    outline = ClariceDarkOutline,
    error = ClariceDarkError,
    onError = ClariceDarkOnError,
)

private val ClariceLightColors = lightColorScheme(
    primary = ClariceLightAccent,
    onPrimary = ClariceLightAccentForeground,
    background = ClariceLightBackground,
    onBackground = ClariceLightText,
    surface = ClariceLightSurface,
    onSurface = ClariceLightText,
    surfaceVariant = ClariceLightSurface,
    onSurfaceVariant = ClariceLightMutedForeground,
    outline = ClariceLightOutline,
    error = ClariceLightError,
    onError = ClariceLightOnError,
)

/**
 * Clarice's own palette, type and shape rather than Compose's Material
 * baseline -- the launcher icon already promises a dark navy, mint-accented
 * app, and MaterialTheme {} on its own broke that promise with stock
 * purple. No dynamic (wallpaper-derived) color: the brand is fixed, not
 * per-device.
 *
 * Follows the system light/dark setting, same as the web app's unset
 * (prefers-color-scheme) default -- there is no in-app override here the
 * way the web app's ThemeToggle has one, because Settings' own principle
 * ("deliberately not a place to change anything except [account and exit]")
 * argues against adding one until somebody actually wants it.
 */
@Composable
fun ClariceTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) ClariceDarkColors else ClariceLightColors,
        typography = ClariceTypography,
        shapes = ClariceShapes,
        content = content,
    )
}
