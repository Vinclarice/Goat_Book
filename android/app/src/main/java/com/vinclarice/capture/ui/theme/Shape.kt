package com.vinclarice.capture.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

/**
 * Same proportions as the web app's --radius scale (frontend/src/app/tailwind.css,
 * base --radius: 0.625rem with 0.6x/0.8x/1x/1.4x steps) -- the two products
 * should round their corners by the same amount, not just share a palette.
 */
val ClariceShapes = Shapes(
    small = RoundedCornerShape(6.dp),
    medium = RoundedCornerShape(8.dp),
    large = RoundedCornerShape(10.dp),
    extraLarge = RoundedCornerShape(14.dp),
)
