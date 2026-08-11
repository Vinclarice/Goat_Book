package com.vinclarice.capture.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/**
 * The web identity sets its display type in Inter; matching that exactly
 * here would mean bundling a font (or a network-fetched one) for four
 * screens of text, which is the wrong trade for an app whose whole premise
 * is working when the network can't be trusted. System sans (Roboto) stays
 * the base face -- restraint spent on color and shape, not typography.
 *
 * The one deliberate exception: headlineSmall is the only "display" text in
 * the app (the three screen titles -- "Connect to Clarice", "Settings",
 * "Clarice Capture is locked"), so it earns a slightly heavier, tighter
 * treatment instead of Material's default.
 */
val ClariceTypography = Typography().let { base ->
    base.copy(
        headlineSmall = base.headlineSmall.copy(
            fontWeight = FontWeight.SemiBold,
            letterSpacing = (-0.2).sp,
        ),
    )
}
