package com.vinclarice.capture

/**
 * The Agenda's own shape, trimmed to what slice 2 renders and acts on --
 * mirrors lists.api_v1.AgendaOut, minus the chrome fields
 * android-full-client-plan.md §7 names as deliberately out of scope
 * (archive_url, daily_digest, settings_url, the server's own `buckets`
 * labels -- Android buckets client-side via [bucketFor], the same way the
 * web page derives its own scope counts).
 */
data class AgendaEntry(
    val today: String,
    val items: List<AgendaTaskEntry>,
    val completedToday: List<AgendaTaskEntry>,
    val areas: List<AgendaAreaEntry>,
    val projects: List<AgendaProjectEntry>,
)

/**
 * Mirrors lists.api_v1.TaskOut / lists.serializers.serialize_item, trimmed
 * to what a row renders or a mutation needs. [url] is the address every
 * write in this slice PATCHes -- carried on the task rather than built
 * client-side, the same reason DayEntry's areas/projects carry their own
 * urls.
 */
data class AgendaTaskEntry(
    val id: Int,
    val text: String,
    val dueDate: String?,
    val tags: List<String>,
    val areaId: Int,
    val projectId: Int?,
    val url: String,
)

data class AgendaAreaEntry(
    val id: Int,
    val title: String,
    val colorKey: String,
    val openCount: Int,
    val overdueCount: Int,
    /** Where quick-add posts a new task into this area. */
    val createItemUrl: String,
)

data class AgendaProjectEntry(
    val id: Int,
    val title: String,
)
