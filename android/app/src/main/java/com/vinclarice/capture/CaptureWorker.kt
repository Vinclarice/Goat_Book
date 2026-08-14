package com.vinclarice.capture

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.map

/**
 * Asking for the queue to be delivered, and hearing when it was.
 *
 * An interface so the view model can be tested on the JVM without
 * WorkManager. The app says "there is something to send"; when and how are
 * the system's business.
 *
 * [completions] exists because a screen cannot see a background drain. A
 * count read once when the screen opened will happily keep displaying "3
 * waiting to send" over a queue the worker emptied minutes ago -- observed
 * on a real phone, and indistinguishable to its owner from three captures
 * having gone missing.
 */
interface DeliveryScheduler {
    fun schedule()

    /** Emits when a background delivery run reaches a conclusion. */
    fun completions(): Flow<Unit> = emptyFlow()

    /** For tests and for the Connect screen, where nothing is queued yet. */
    object None : DeliveryScheduler {
        override fun schedule() = Unit
    }
}

/**
 * Drains the queue in the background, under the system's constraints rather
 * than the app's optimism.
 *
 * Thin on purpose: every decision it could get wrong lives in [QueueDrainer],
 * which has tests. What is left here is translating a [DrainReport] into the
 * two words WorkManager understands.
 */
class CaptureWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        // The capture half of [Backends], matching what MainActivity built.
        // The worker runs in its own process-less context and cannot be handed
        // objects, so it reconstructs them from the same build config -- which
        // is exactly why the pairing of URL and token slot lives in one place
        // rather than being spelled out at each call site.
        val capture = Backends(
            clariceBaseUrl = BuildConfig.CLARICE_BASE_URL,
            secondMindBaseUrl = BuildConfig.SECOND_MIND_BASE_URL,
        ).capture

        val report = QueueDrainer(
            api = OkHttpClariceApi(baseUrl = capture.baseUrl),
            store = KeystoreTokenStore(
                applicationContext,
                alias = capture.tokenAlias,
                prefsName = capture.tokenPrefs,
            ),
            queue = CaptureQueue(EncryptedQueueStorage(applicationContext)),
        ).drain()

        // retry() rather than failure(): failure is terminal, and nothing
        // here is ever terminal while a capture is still waiting. A stalled
        // or rejected item does not count as waiting, which is what stops
        // this rescheduling forever over something no retry can fix.
        return if (report.finished) Result.success() else Result.retry()
    }

    companion object : DeliveryScheduler {

        /**
         * Not usable as a scheduler until [prepare] has been given a
         * context. `Companion` is a singleton with no application of its
         * own, and passing one in beats holding a static Context.
         */
        private var appContext: Context? = null

        fun prepare(context: Context): DeliveryScheduler {
            appContext = context.applicationContext
            return this
        }

        override fun schedule() {
            val context = appContext ?: return
            val request = OneTimeWorkRequestBuilder<CaptureWorker>()
                .setConstraints(
                    Constraints.Builder()
                        // The one thing worth waiting for. Without it the
                        // worker wakes in airplane mode, fails, and spends
                        // an attempt to learn what the system already knew.
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build()
                )
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()

            // KEEP, emphatically not REPLACE. Replacing would restart the
            // backoff every time somebody captured another thought, so a
            // person typing steadily through an outage would push their own
            // queue's next attempt further away with every capture.
            WorkManager.getInstance(context)
                .enqueueUniqueWork(WORK_NAME, ExistingWorkPolicy.KEEP, request)
        }

        /**
         * Every change in the delivery work's state, collapsed to a nudge.
         *
         * Deliberately not filtered to finished runs only. The listener's
         * response is to re-read the queue, which is cheap and always
         * correct, whereas guessing which WorkInfo transitions matter is how
         * a screen ends up stale again in some case nobody thought of.
         */
        override fun completions(): Flow<Unit> {
            val context = appContext ?: return emptyFlow()
            return WorkManager.getInstance(context)
                .getWorkInfosForUniqueWorkFlow(WORK_NAME)
                .map { }
        }

        private const val WORK_NAME = "clarice-capture-delivery"
    }
}
