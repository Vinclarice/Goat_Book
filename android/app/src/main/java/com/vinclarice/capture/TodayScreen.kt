package com.vinclarice.capture

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/**
 * One page for everything — android-overhaul-plan.md increment 5.
 *
 * Vince, September 6, 2026, on seeing the tabbed build run: *"right off the
 * bat, I want like one page for everything."* So `RootTab` and `RootTabBar`
 * are gone, and what was three screens is one scrolling surface — the shape
 * `app-overhaul-plan.md` gives the web, arriving on the phone first because
 * the phone had the least to unpick.
 *
 * **This owns the scroll, and it is the only one.** Each section below renders
 * into this column without a scroll or a `fillMaxSize` of its own; two
 * scrolling containers in one page is one of them that never reaches its end.
 *
 * **Capture is first, and that is a deliberate divergence from the web.** Rule
 * 4 there keeps `/mind/` server-rendered because the binding constraint is *a
 * page comfortable to type into with a thumb, loading instantly* — but that
 * argument is about a page **load**, and there is no load here. A native
 * surface is already resident, so a box at the top of it costs no round trip
 * and no scroll. The offline queue and the share target are untouched either
 * way: both are about the act rather than the surface.
 *
 * **Three view models behind one screen**, which is what `DayRoute.tsx`
 * already does on the web with several queries. They stay separate because
 * they fail separately — a pool that will not load must not blank a day that
 * did.
 */
@Composable
fun TodayScreen(
    captureModel: CaptureViewModel,
    dayModel: DailyViewModel,
    poolModel: PoolViewModel,
    onOpenSettings: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState()),
    ) {
        // One Settings link for the page, where there were three for three
        // tabs. A plain text button rather than an app bar, for the reason
        // CaptureSection already gave: an app bar takes a band of height off
        // the field for one action.
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp),
            horizontalArrangement = Arrangement.End,
        ) {
            TextButton(onClick = onOpenSettings) { Text("Settings") }
        }

        CaptureSection(captureModel)

        HorizontalDivider()

        DaySection(dayModel)

        HorizontalDivider()

        PoolSection(poolModel)
    }
}
